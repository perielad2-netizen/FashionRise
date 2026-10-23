import {
  DEFAULT_MODEL,
  normalizeModelChoice,
  type ModelChoice,
} from '@/assets/modelLibrary'
import { cloneFills, parseFillOp, type FillOp } from '@/lib/fills'
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
export const STUDIO_DRAFT_KIND = 'studio_working_draft' as const

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
  schema: typeof STUDIO_DRAFT_SCHEMA
  strokes: Stroke[]
  /** Optional garment fills; absent/empty on older V1 drafts. */
  fills: FillOp[]
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

export function isStudioDraftDocument(value: unknown): value is StudioDraftDocument {
  if (!value || typeof value !== 'object') return false
  const doc = value as Partial<StudioDraftDocument>
  return doc.schema === STUDIO_DRAFT_SCHEMA && Array.isArray(doc.strokes)
}

export function parseStudioDraftDocument(raw: unknown): StudioDraftDocument | null {
  if (!isStudioDraftDocument(raw)) return null
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

  const strokes: Stroke[] = []
  for (const s of raw.strokes) {
    if (!s || typeof s !== 'object') continue
    const tool = (s as Stroke).tool
    if (tool !== 'draw' && tool !== 'erase') continue
    if (!Array.isArray((s as Stroke).points)) continue
    strokes.push({
      id: String((s as Stroke).id || `stroke_${strokes.length}`),
      tool: tool as ToolKind,
      points: (s as Stroke).points.filter((n) => typeof n === 'number'),
      color: typeof (s as Stroke).color === 'string' ? (s as Stroke).color : color,
      size: typeof (s as Stroke).size === 'number' ? (s as Stroke).size : sizePx,
      opacity: typeof (s as Stroke).opacity === 'number' ? (s as Stroke).opacity : 1,
    })
  }

  const fills: FillOp[] = []
  const rawFills = (raw as { fills?: unknown }).fills
  if (Array.isArray(rawFills)) {
    for (const item of rawFills) {
      const fill = parseFillOp(item)
      if (fill) fills.push(fill)
    }
  }

  return {
    schema: STUDIO_DRAFT_SCHEMA,
    strokes,
    fills,
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
  patch: Partial<Omit<StudioDraftDocument, 'schema' | 'clientRevision' | 'updatedAt'>>,
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
  return {
    ...prev,
    ...patch,
    brush,
    schema: STUDIO_DRAFT_SCHEMA,
    clientRevision: prev.clientRevision + 1,
    updatedAt: now.toISOString(),
  }
}

export function draftContentFingerprint(doc: StudioDraftDocument): string {
  return JSON.stringify({
    strokes: doc.strokes,
    fills: doc.fills ?? [],
    model: doc.model,
    customReferenceUrl: doc.customReferenceUrl,
    customReferenceKey: doc.customReferenceKey,
    // Normalized sizePx so legacy docs (sizeId only) do not conflict with equivalents.
    brush: normalizeStudioBrush(doc.brush),
    dimmed: doc.dimmed,
  })
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

export function studioDraftMetadata(doc: StudioDraftDocument) {
  return {
    draftKind: STUDIO_DRAFT_KIND,
    schema: STUDIO_DRAFT_SCHEMA,
    clientRevision: doc.clientRevision,
    updatedAt: doc.updatedAt,
  }
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
  return {
    ...local,
    strokes: local.strokes.map((stroke) => ({ ...stroke, points: [...stroke.points] })),
    fills: cloneFills(local.fills ?? []),
    brush: normalizeStudioBrush(local.brush),
    clientRevision: Math.max(local.clientRevision, floor) + 1,
    updatedAt: now.toISOString(),
  }
}

export function documentFromEditorState(input: {
  prev: StudioDraftDocument
  strokes: StudioDraftDocument['strokes']
  fills?: StudioDraftDocument['fills']
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
  return bumpDraftDocument(input.prev, {
    strokes: input.strokes,
    fills: input.fills ?? input.prev.fills ?? [],
    model: input.model,
    customReferenceUrl: input.customReferenceUrl,
    customReferenceKey: input.customReferenceKey,
    brush: {
      // Keep an exact legacy id when the numeric size matches a preset; otherwise nearest.
      sizeId: BRUSH_SIZES[input.sizeId] === sizePx ? input.sizeId : nearestBrushSizeId(sizePx),
      sizePx,
      opacity: input.opacity,
      color: input.color,
    },
    dimmed: input.dimmed,
  })
}
