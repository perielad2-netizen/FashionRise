import {
  DEFAULT_MODEL,
  normalizeModelChoice,
  type ModelChoice,
} from '@/assets/modelLibrary'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import { cloneFills, parseFillOp, type FillOp } from '@/lib/fills'
import {
  cloneSideBag,
  emptySideBag,
  normalizeSideBag,
  sideHasInk,
  type StudioPaperSide,
  type StudioSideBag,
} from '@/lib/studioSideArtwork'
import {
  BRUSH_SIZE_DEFAULT_PX,
  BRUSH_SIZES,
  INK_SWATCHES,
  nearestBrushSizeId,
  resolveBrushSizePx,
  snapBrushSizePx,
  type BrushSizeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'

export const STUDIO_DRAFT_SCHEMA = 'fashionrise.studio.draft.v1' as const
export const STUDIO_DRAFT_SCHEMA_V2 = 'fashionrise.studio.draft.v2' as const
export const STUDIO_DRAFT_KIND = 'studio_working_draft' as const

export type StudioDraftSchema =
  | typeof STUDIO_DRAFT_SCHEMA
  | typeof STUDIO_DRAFT_SCHEMA_V2

export type StudioBrushState = {
  /** Legacy preset id kept for older clients / parsers. */
  sizeId: BrushSizeId
  /**
   * Authoritative continuous brush size in design-space px (WEB-V4G).
   * Optional on disk for backward compatibility; parsers always resolve it.
   */
  sizePx?: number
  opacity: number
  color: string
}

/** Normalize brush for fingerprints / equality so missing sizePx does not fake a conflict. */
export function normalizeStudioBrush(brush: StudioBrushState): StudioBrushState {
  const sizePx = resolveBrushSizePx(brush)
  return {
    sizeId: brush.sizeId,
    sizePx,
    opacity: brush.opacity,
    color: brush.color,
  }
}

export type StudioDraftDocument = {
  schema: StudioDraftSchema
  /** Front-side ink (always authoritative for v1 and v2). */
  strokes: Stroke[]
  /** Optional garment fills; absent/empty on older V1 drafts. */
  fills: FillOp[]
  /** v2 only — which side is active in Studio when reopened. */
  activeSide?: StudioPaperSide
  /** v2 only — rear artwork bag; absent key ≠ empty bag for fingerprints. */
  back?: StudioSideBag
  /**
   * Transient: set when intentionally clearing non-empty Back before cloud write.
   * Stripped from persisted local copies after enqueue.
   */
  clearBackIntent?: boolean
  model: ModelChoice
  customReferenceUrl: string | null
  customReferenceKey: string | null
  brush: StudioBrushState
  dimmed: boolean
  /** Monotonic document revision used as optimistic concurrency token. */
  clientRevision: number
  updatedAt: string
}

export type SaveStatus =
  | 'idle'
  | 'restoring'
  | 'pending'
  | 'saving'
  | 'saved'
  | 'error'
  | 'local-only'

const SIZE_IDS = Object.keys(BRUSH_SIZES) as BrushSizeId[]

export function createEmptyDraftDocument(now = new Date()): StudioDraftDocument {
  return {
    schema: STUDIO_DRAFT_SCHEMA,
    strokes: [],
    fills: [],
    model: DEFAULT_MODEL,
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: {
      sizeId: 'thin',
      sizePx: BRUSH_SIZE_DEFAULT_PX,
      opacity: 1,
      color: INK_SWATCHES[0]!.color,
    },
    dimmed: false,
    clientRevision: 1,
    updatedAt: now.toISOString(),
  }
}

const STUDIO_SCHEMAS = new Set<string>([STUDIO_DRAFT_SCHEMA, STUDIO_DRAFT_SCHEMA_V2])

export function isStudioDraftV2(doc: Pick<StudioDraftDocument, 'schema'>): boolean {
  return doc.schema === STUDIO_DRAFT_SCHEMA_V2
}

export function normalizeActiveSide(doc: Pick<StudioDraftDocument, 'activeSide'>): StudioPaperSide {
  const side = doc.activeSide
  return side === 'back' ? 'back' : 'front'
}

/** Align with Stage B BE: absent `back` key → null; present → normalized bag. */
export function normalizeBackSentinel(
  doc: Pick<StudioDraftDocument, 'back'> & { back?: StudioSideBag },
): StudioSideBag | null {
  if (!('back' in doc)) return null
  const bag = doc.back
  if (!bag || typeof bag !== 'object') return { strokes: [], fills: [] }
  return {
    strokes: Array.isArray(bag.strokes) ? bag.strokes : [],
    fills: _normalizeFillList(bag.fills),
  }
}

function _normalizeFillList(fills: unknown): FillOp[] {
  if (fills == null) return []
  if (!Array.isArray(fills)) return []
  return fills as FillOp[]
}

export function backArtworkFromDoc(doc: StudioDraftDocument): StudioSideBag {
  const bag = normalizeBackSentinel(doc)
  return bag ? cloneSideBag(bag) : emptySideBag()
}

export function frontArtworkFromDoc(doc: StudioDraftDocument): StudioSideBag {
  return { strokes: doc.strokes, fills: doc.fills ?? [] }
}

export function documentHasBackInk(doc: StudioDraftDocument): boolean {
  const bag = normalizeBackSentinel(doc)
  return bag ? sideHasInk(bag) : false
}

export function isStudioDraftDocument(value: unknown): value is StudioDraftDocument {
  if (!value || typeof value !== 'object') return false
  const doc = value as Partial<StudioDraftDocument>
  return typeof doc.schema === 'string' && STUDIO_SCHEMAS.has(doc.schema) && Array.isArray(doc.strokes)
}

/** Lenient Front / V1 stroke recovery — skips bad items rather than failing the document. */
function parseSideStrokes(
  rawList: unknown[],
  fallbackColor: string,
  sizePx: number,
): Stroke[] {
  const strokes: Stroke[] = []
  for (const s of rawList) {
    if (!s || typeof s !== 'object') continue
    const tool = (s as Stroke).tool
    if (tool !== 'draw' && tool !== 'erase') continue
    if (!Array.isArray((s as Stroke).points)) continue
    strokes.push({
      id: String((s as Stroke).id || `stroke_${strokes.length}`),
      tool: tool as ToolKind,
      points: (s as Stroke).points.filter((n) => typeof n === 'number'),
      color: typeof (s as Stroke).color === 'string' ? (s as Stroke).color : fallbackColor,
      size: typeof (s as Stroke).size === 'number' ? (s as Stroke).size : sizePx,
      opacity: typeof (s as Stroke).opacity === 'number' ? (s as Stroke).opacity : 1,
    })
  }
  return strokes
}

/**
 * Atomic Back stroke parse: any malformed item rejects the whole list (and therefore V2).
 * Does not invent ids/colors/sizes for damaged records.
 */
function parseStrictSideStrokes(rawList: unknown[]): Stroke[] | null {
  const strokes: Stroke[] = []
  for (const s of rawList) {
    if (!s || typeof s !== 'object') return null
    const tool = (s as Stroke).tool
    if (tool !== 'draw' && tool !== 'erase') return null
    if (typeof (s as Stroke).id !== 'string' || !(s as Stroke).id) return null
    if (!Array.isArray((s as Stroke).points)) return null
    if (!(s as Stroke).points.every((n) => typeof n === 'number' && Number.isFinite(n))) return null
    if (typeof (s as Stroke).color !== 'string') return null
    if (typeof (s as Stroke).size !== 'number' || !Number.isFinite((s as Stroke).size)) return null
    if (typeof (s as Stroke).opacity !== 'number' || !Number.isFinite((s as Stroke).opacity)) {
      return null
    }
    strokes.push({
      id: (s as Stroke).id,
      tool: tool as ToolKind,
      points: [...(s as Stroke).points],
      color: (s as Stroke).color,
      size: (s as Stroke).size,
      opacity: (s as Stroke).opacity,
    })
  }
  return strokes
}

/** Atomic Back fill parse: any malformed item rejects the whole list. */
function parseStrictSideFills(rawList: unknown[]): FillOp[] | null {
  const fills: FillOp[] = []
  for (const item of rawList) {
    const fill = parseFillOp(item)
    if (!fill) return null
    fills.push(fill)
  }
  return fills
}

/**
 * Parse a present V2 `back` bag. Returns `null` when the bag (or any item) is malformed —
 * callers must fail the entire V2 document, never coerce to an empty bag.
 */
export function parseStrictV2BackBag(rawBack: unknown): StudioSideBag | null {
  const structure = normalizeSideBag(rawBack)
  if (!structure) return null
  const strokes = parseStrictSideStrokes(structure.strokes)
  if (!strokes) return null
  const fills = parseStrictSideFills(structure.fills)
  if (!fills) return null
  return { strokes, fills }
}

export class StudioDraftSerializeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'StudioDraftSerializeError'
  }
}

export function parseStudioDraftDocument(raw: unknown): StudioDraftDocument | null {
  if (!isStudioDraftDocument(raw)) return null
  const schema =
    raw.schema === STUDIO_DRAFT_SCHEMA_V2 ? STUDIO_DRAFT_SCHEMA_V2 : STUDIO_DRAFT_SCHEMA
  const model = normalizeModelChoice(raw.model)
  const sizeId = SIZE_IDS.includes(raw.brush?.sizeId as BrushSizeId)
    ? (raw.brush.sizeId as BrushSizeId)
    : 'thin'
  const rawSizePx = (raw.brush as { sizePx?: unknown } | undefined)?.sizePx
  const sizePx =
    typeof rawSizePx === 'number' && Number.isFinite(rawSizePx) && rawSizePx > 0
      ? snapBrushSizePx(rawSizePx)
      : BRUSH_SIZES[sizeId]
  const opacity =
    typeof raw.brush?.opacity === 'number'
      ? Math.min(1, Math.max(0.05, raw.brush.opacity))
      : 1
  const color =
    typeof raw.brush?.color === 'string' && /^#[0-9a-fA-F]{6}$/.test(raw.brush.color)
      ? raw.brush.color.toUpperCase()
      : INK_SWATCHES[0]!.color

  const strokes = parseSideStrokes(raw.strokes, color, sizePx)

  const fills: FillOp[] = []
  const rawFills = (raw as { fills?: unknown }).fills
  if (Array.isArray(rawFills)) {
    for (const item of rawFills) {
      const fill = parseFillOp(item)
      if (fill) fills.push(fill)
    }
  }

  let activeSide: StudioPaperSide | undefined
  if (schema === STUDIO_DRAFT_SCHEMA_V2) {
    if ('activeSide' in (raw as object)) {
      const side = (raw as { activeSide?: unknown }).activeSide
      if (side !== 'front' && side !== 'back') return null
      activeSide = side
    } else {
      activeSide = 'front'
    }
  }

  let back: StudioSideBag | undefined
  if (schema === STUDIO_DRAFT_SCHEMA_V2 && 'back' in (raw as object)) {
    // Present-but-malformed Back must reject the entire V2 document (no empty-bag coercion).
    const parsedBack = parseStrictV2BackBag((raw as { back?: unknown }).back)
    if (!parsedBack) return null
    back = parsedBack
  }

  return {
    schema,
    strokes,
    fills,
    ...(activeSide ? { activeSide } : {}),
    ...(back ? { back } : {}),
    model,
    customReferenceUrl:
      typeof raw.customReferenceUrl === 'string' && raw.customReferenceUrl
        ? raw.customReferenceUrl
        : null,
    customReferenceKey:
      typeof raw.customReferenceKey === 'string' && raw.customReferenceKey
        ? raw.customReferenceKey
        : null,
    brush: { sizeId, sizePx, opacity, color },
    dimmed: Boolean(raw.dimmed),
    clientRevision:
      typeof raw.clientRevision === 'number' && raw.clientRevision > 0
        ? Math.floor(raw.clientRevision)
        : 1,
    updatedAt:
      typeof raw.updatedAt === 'string' && raw.updatedAt
        ? raw.updatedAt
        : new Date().toISOString(),
  }
}

export function bumpDraftDocument(
  prev: StudioDraftDocument,
  patch: Partial<Omit<StudioDraftDocument, 'clientRevision' | 'updatedAt'>>,
  now = new Date(),
): StudioDraftDocument {
  let brush = prev.brush
  if (patch.brush) {
    const merged = { ...prev.brush, ...patch.brush }
    // If a caller updates sizeId without sizePx, do not keep a stale sizePx from prev.
    if (patch.brush.sizePx === undefined && patch.brush.sizeId) {
      merged.sizePx = BRUSH_SIZES[patch.brush.sizeId]
    }
    brush = normalizeStudioBrush(merged)
  }
  const next: StudioDraftDocument = {
    ...prev,
    ...patch,
    brush,
    schema: patch.schema ?? prev.schema,
    clientRevision: prev.clientRevision + 1,
    updatedAt: now.toISOString(),
  }
  if (!patch.clearBackIntent) delete next.clearBackIntent
  return next
}

/** Stage B BE-aligned content fingerprint (sort_keys stable via ordered keys). */
export function draftContentFingerprint(doc: StudioDraftDocument): string {
  const payload: Record<string, unknown> = {
    schema: doc.schema ?? STUDIO_DRAFT_SCHEMA,
    strokes: doc.strokes,
    fills: doc.fills ?? [],
    model: doc.model,
    customReferenceUrl: doc.customReferenceUrl,
    customReferenceKey: doc.customReferenceKey,
    brush: normalizeStudioBrush(doc.brush),
    dimmed: doc.dimmed,
    activeSide: normalizeActiveSide(doc),
    back: normalizeBackSentinel(doc),
  }
  const keys = Object.keys(payload).sort()
  const sorted: Record<string, unknown> = {}
  for (const k of keys) sorted[k] = payload[k]
  return JSON.stringify(sorted)
}

export function upgradeDraftToV2(doc: StudioDraftDocument): StudioDraftDocument {
  if (isStudioDraftV2(doc)) return doc
  return {
    ...doc,
    schema: STUDIO_DRAFT_SCHEMA_V2,
    activeSide: normalizeActiveSide(doc),
    back: backArtworkFromDoc(doc),
  }
}

/**
 * Serialize for disk / API. When Front/Back flag is off, always v1 without side bags.
 * When on, v2 documents always include `activeSide` + `back`.
 */
export function serializeStudioDraftDocument(
  doc: StudioDraftDocument,
  options?: { frontBackEnabled?: boolean },
): StudioDraftDocument {
  const frontBackEnabled = options?.frontBackEnabled ?? isStudioFrontBackEnabled()
  const { clearBackIntent: _clearBackIntent, ...rest } = doc
  if (!frontBackEnabled && isStudioDraftV2(rest)) {
    throw new StudioDraftSerializeError(
      'Front/Back is disabled; refusing to downgrade or strip a v2 studio draft.',
    )
  }
  if (!frontBackEnabled || !isStudioDraftV2(rest)) {
    const v1: StudioDraftDocument = {
      ...rest,
      schema: STUDIO_DRAFT_SCHEMA,
      strokes: rest.strokes,
      fills: rest.fills ?? [],
    }
    delete (v1 as { activeSide?: unknown }).activeSide
    delete (v1 as { back?: unknown }).back
    return v1
  }
  const back = rest.back ?? emptySideBag()
  return {
    ...rest,
    schema: STUDIO_DRAFT_SCHEMA_V2,
    activeSide: normalizeActiveSide(rest),
    strokes: rest.strokes,
    fills: rest.fills ?? [],
    back: cloneSideBag(back),
  }
}

/**
 * When local and server copies differ, always require an explicit operator choice.
 * Never auto-overwrite another device merely because a local revision is higher.
 */
export function resolveDraftConflict(
  local: StudioDraftDocument,
  server: StudioDraftDocument,
): { equal: boolean; needsUserChoice: boolean } {
  if (draftContentFingerprint(local) === draftContentFingerprint(server)) {
    return { equal: true, needsUserChoice: false }
  }
  return { equal: false, needsUserChoice: true }
}

export function studioDraftMetadata(
  doc: StudioDraftDocument,
  extras?: { clearBackIntent?: boolean },
) {
  const serialized = serializeStudioDraftDocument(doc)
  const meta: Record<string, unknown> = {
    draftKind: STUDIO_DRAFT_KIND,
    schema: serialized.schema,
    clientRevision: doc.clientRevision,
    updatedAt: doc.updatedAt,
  }
  if (isStudioDraftV2(serialized) && isStudioFrontBackEnabled()) {
    meta.studioSides = 2
  }
  if (extras?.clearBackIntent) meta.clearBackIntent = true
  return meta
}

/**
 * Build the next authoritative document from a known previous snapshot.
 * Callers must pass the committed snapshot — never reconstruct from stale React state.
 */
/**
 * Explicit "Keep this device" rebase: new revision strictly above the server
 * snapshot the operator just saw. Strokes and settings are copied unchanged.
 */
export function rebaseChosenLocalDraft(
  local: StudioDraftDocument,
  serverRevision: number,
  now = new Date(),
): StudioDraftDocument {
  const floor = Number.isFinite(serverRevision) ? serverRevision : 0
  const rebased: StudioDraftDocument = {
    ...local,
    strokes: local.strokes.map((stroke) => ({ ...stroke, points: [...stroke.points] })),
    fills: cloneFills(local.fills ?? []),
    brush: normalizeStudioBrush(local.brush),
    clientRevision: Math.max(local.clientRevision, floor) + 1,
    updatedAt: now.toISOString(),
  }
  if (local.back) rebased.back = cloneSideBag(local.back)
  return rebased
}

export function documentFromEditorState(input: {
  prev: StudioDraftDocument
  strokes: StudioDraftDocument['strokes']
  fills?: StudioDraftDocument['fills']
  back?: StudioSideBag
  activeSide?: StudioPaperSide
  clearBackIntent?: boolean
  schema?: StudioDraftSchema
  model: StudioDraftDocument['model']
  customReferenceUrl: string | null
  customReferenceKey: string | null
  sizeId: StudioDraftDocument['brush']['sizeId']
  /** Authoritative continuous size; falls back to sizeId preset when omitted. */
  sizePx?: number
  opacity: number
  color: string
  dimmed: boolean
}): StudioDraftDocument {
  const sizePx =
    typeof input.sizePx === 'number' && Number.isFinite(input.sizePx)
      ? snapBrushSizePx(input.sizePx)
      : BRUSH_SIZES[input.sizeId]
  const patch: Partial<StudioDraftDocument> = {
    strokes: input.strokes,
    fills: input.fills ?? input.prev.fills ?? [],
    model: input.model,
    customReferenceUrl: input.customReferenceUrl,
    customReferenceKey: input.customReferenceKey,
    brush: {
      sizeId: BRUSH_SIZES[input.sizeId] === sizePx ? input.sizeId : nearestBrushSizeId(sizePx),
      sizePx,
      opacity: input.opacity,
      color: input.color,
    },
    dimmed: input.dimmed,
  }
  if (input.back !== undefined) patch.back = input.back
  if (input.activeSide !== undefined) patch.activeSide = input.activeSide
  if (input.schema !== undefined) patch.schema = input.schema
  if (input.clearBackIntent) patch.clearBackIntent = true
  return bumpDraftDocument(input.prev, patch)
}
