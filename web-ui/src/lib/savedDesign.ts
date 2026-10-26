import {
  isModelChoice,
  modelLabel as libraryModelLabel,
  type ModelChoice,
} from '@/assets/modelLibrary'
import { cloneFills, parseFillOp, type FillOp } from '@/lib/fills'
import {
  BRUSH_SIZES,
  resolveBrushSizePx,
  snapBrushSizePx,
  type BrushSizeId,
  type Stroke,
} from '@/lib/strokes'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import {
  documentHasBackInk,
  isStudioDraftV2,
  normalizeActiveSide,
  normalizeBackSentinel,
  normalizeStudioBrush,
  upgradeDraftToV2,
  type StudioBrushState,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { cloneSideBag, emptySideBag, sideHasInk, type StudioSideBag } from '@/lib/studioSideArtwork'

/**
 * Named, immutable design snapshots ("Save as design").
 *
 * Stored as ordinary private `/api/v1/designs` rows, but the top-level
 * `design_data.schema` is `fashionrise.saved_design.v1` and metadata never carries
 * `draftKind`. The backend only treats a row as the singleton Studio working draft when
 * `metadata.draftKind === "studio_working_draft"` or the TOP-LEVEL
 * `design_data.schema === "fashionrise.studio.draft.v1"`, so these rows never enter
 * working-draft reconciliation, revision checks or `pickLatestStudioDraft`.
 *
 * The nested snapshot deliberately has no `schema` key and no `clientRevision`.
 */
export const SAVED_DESIGN_SCHEMA = 'fashionrise.saved_design.v1' as const
export const SAVED_DESIGN_SCHEMA_V2 = 'fashionrise.saved_design.v2' as const
export const SAVED_DESIGN_KIND = 'saved_design' as const
export const SAVED_DESIGN_CATEGORY = 'studio' as const

export const TITLE_MAX_LENGTH = 80
export const MAX_SNAPSHOT_STROKES = 5000
export const MAX_SNAPSHOT_POINTS = 1_500_000
export const MAX_SNAPSHOT_FILLS = 500

export type SavedDesignSnapshot = {
  strokes: Stroke[]
  /** Optional; omitted on pre-WEB-V4B snapshots. */
  fills?: FillOp[]
  activeSide?: 'front' | 'back'
  back?: StudioSideBag
  model: ModelChoice
  brush: StudioBrushState
  dimmed: boolean
}

export type SavedDesignEnvelope = {
  schema: typeof SAVED_DESIGN_SCHEMA | typeof SAVED_DESIGN_SCHEMA_V2
  saveRequestId: string
  savedAt: string
  /** Working-draft revision the snapshot was taken from (informational only). */
  sourceRevision: number | null
  snapshot: SavedDesignSnapshot
}

export type SavedDesignRecord = {
  id: string
  title: string
  savedAt: string
  createdAt: string
  saveRequestId: string
  snapshot: SavedDesignSnapshot
}

/** A row that claims the saved-design schema but fails validation. Shown, never opened. */
export type DamagedSavedDesign = {
  id: string
  title: string
  createdAt: string
}

type DesignRowLike = {
  id: string
  user_id: string
  title: string
  design_data: Record<string, unknown> | null
  metadata: Record<string, unknown> | null
  visibility: string
  created_at: string
}

const SIZE_IDS = Object.keys(BRUSH_SIZES) as BrushSizeId[]
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001F\u007F-\u009F\u2028\u2029]/

export type TitleValidation = { ok: true; title: string } | { ok: false; message: string }

export function validateDesignTitle(raw: string): TitleValidation {
  if (CONTROL_CHARS.test(raw.replace(/[\t\n\r]/g, ' '))) {
    return { ok: false, message: 'Title contains characters that are not allowed.' }
  }
  const title = raw.replace(/\s+/g, ' ').trim()
  if (!title) return { ok: false, message: 'Enter a title for your design.' }
  if ([...title].length > TITLE_MAX_LENGTH) {
    return { ok: false, message: `Keep the title to ${TITLE_MAX_LENGTH} characters or fewer.` }
  }
  return { ok: true, title }
}

export function defaultDesignTitle(now = new Date()): string {
  const date = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(now)
  return `Sketch ${date}`
}

export function createSaveRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `save_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`
}

function canonicalStroke(s: Stroke): Stroke {
  return {
    id: s.id,
    tool: s.tool,
    points: [...s.points],
    color: s.color,
    size: s.size,
    opacity: s.opacity,
  }
}

/** Deep copy of the authoritative document; session-only custom reference fields are dropped. */
export function snapshotFromDocument(doc: StudioDraftDocument): SavedDesignSnapshot {
  const base: SavedDesignSnapshot = {
    strokes: doc.strokes.map(canonicalStroke),
    fills: cloneFills(doc.fills ?? []),
    model: doc.model,
    brush: normalizeStudioBrush(doc.brush),
    dimmed: doc.dimmed,
  }
  if (!isStudioFrontBackEnabled() || !isStudioDraftV2(doc)) return base
  const back = normalizeBackSentinel(doc) ?? emptySideBag()
  return {
    ...base,
    activeSide: normalizeActiveSide(doc),
    back: {
      strokes: back.strokes.map(canonicalStroke),
      fills: cloneFills(back.fills),
    },
  }
}

export function savedSnapshotHasBackInk(snapshot: SavedDesignSnapshot): boolean {
  const bag = snapshot.back
  return bag ? sideHasInk(bag) : false
}

/** Key-order independent: PostgreSQL JSONB does not preserve object key order. */
export function snapshotFingerprint(snapshot: SavedDesignSnapshot): string {
  const payload: Record<string, unknown> = {
    strokes: snapshot.strokes.map(canonicalStroke),
    fills: snapshot.fills ?? [],
    model: snapshot.model,
    brush: normalizeStudioBrush(snapshot.brush),
    dimmed: snapshot.dimmed,
  }
  if ('activeSide' in snapshot) {
    payload.activeSide = snapshot.activeSide === 'back' ? 'back' : 'front'
  }
  if ('back' in snapshot) {
    const bag = snapshot.back
    payload.back = bag
      ? { strokes: bag.strokes.map(canonicalStroke), fills: bag.fills ?? [] }
      : { strokes: [], fills: [] }
  }
  const keys = Object.keys(payload).sort()
  const sorted: Record<string, unknown> = {}
  for (const k of keys) sorted[k] = payload[k]
  return JSON.stringify(sorted)
}

export function buildSavedDesignPayload(args: {
  title: string
  snapshot: SavedDesignSnapshot
  saveRequestId: string
  sourceRevision: number | null
  now?: Date
}) {
  const savedAt = (args.now ?? new Date()).toISOString()
  const useV2 =
    isStudioFrontBackEnabled() &&
    (Boolean(args.snapshot.back) || args.snapshot.activeSide === 'back' || savedSnapshotHasBackInk(args.snapshot))
  const envelope: SavedDesignEnvelope = {
    schema: useV2 ? SAVED_DESIGN_SCHEMA_V2 : SAVED_DESIGN_SCHEMA,
    saveRequestId: args.saveRequestId,
    savedAt,
    sourceRevision: args.sourceRevision,
    snapshot: args.snapshot,
  }
  return {
    title: args.title,
    description: 'Private FashionRise saved design',
    garment_category: SAVED_DESIGN_CATEGORY,
    template_id: null,
    material_id: null,
    color_palette_id: null,
    design_data: envelope,
    metadata: {
      designKind: SAVED_DESIGN_KIND,
      envelope: useV2 ? SAVED_DESIGN_SCHEMA_V2 : SAVED_DESIGN_SCHEMA,
      saveRequestId: args.saveRequestId,
      savedAt,
      model: args.snapshot.model,
      strokeCount: args.snapshot.strokes.length,
      fillCount: (args.snapshot.fills ?? []).length,
    },
    visibility: 'private' as const,
    status: 'draft' as const,
  }
}

function isFiniteNumber(n: unknown): n is number {
  return typeof n === 'number' && Number.isFinite(n)
}

function parseStroke(raw: unknown): Stroke | null {
  if (!raw || typeof raw !== 'object') return null
  const s = raw as Record<string, unknown>
  if (s.tool !== 'draw' && s.tool !== 'erase') return null
  if (typeof s.id !== 'string' || !s.id || s.id.length > 128) return null
  if (!Array.isArray(s.points) || !s.points.every(isFiniteNumber)) return null
  if (typeof s.color !== 'string' || !HEX_COLOR.test(s.color)) return null
  if (!isFiniteNumber(s.size) || s.size <= 0 || s.size > 200) return null
  if (!isFiniteNumber(s.opacity) || s.opacity < 0 || s.opacity > 1) return null
  return {
    id: s.id,
    tool: s.tool,
    points: [...(s.points as number[])],
    color: s.color,
    size: s.size,
    opacity: s.opacity,
  }
}

/**
 * Strict validation: a snapshot with any invalid stroke is rejected as a whole rather than
 * silently dropping ink, so reopening always reproduces exactly what was saved.
 */
export function parseSavedDesignSnapshot(raw: unknown): SavedDesignSnapshot | null {
  if (!raw || typeof raw !== 'object') return null
  const s = raw as Record<string, unknown>
  if (!isModelChoice(s.model)) return null
  const model = s.model
  if (typeof s.dimmed !== 'boolean') return null
  const brush = s.brush as Record<string, unknown> | null
  if (!brush || typeof brush !== 'object') return null
  if (!SIZE_IDS.includes(brush.sizeId as BrushSizeId)) return null
  if (!isFiniteNumber(brush.opacity) || brush.opacity < 0.05 || brush.opacity > 1) return null
  if (typeof brush.color !== 'string' || !HEX_COLOR.test(brush.color)) return null
  // Optional sizePx: reject only when present but invalid; legacy snapshots omit it.
  let sizePx: number | undefined
  if (brush.sizePx !== undefined) {
    if (!isFiniteNumber(brush.sizePx) || brush.sizePx <= 0 || brush.sizePx > 200) return null
    sizePx = snapBrushSizePx(brush.sizePx)
  } else {
    sizePx = resolveBrushSizePx({ sizeId: brush.sizeId as BrushSizeId })
  }
  if (!Array.isArray(s.strokes) || s.strokes.length > MAX_SNAPSHOT_STROKES) return null
  const strokes: Stroke[] = []
  let points = 0
  for (const rawStroke of s.strokes) {
    const stroke = parseStroke(rawStroke)
    if (!stroke) return null
    points += stroke.points.length
    if (points > MAX_SNAPSHOT_POINTS) return null
    strokes.push(stroke)
  }
  let fills: FillOp[] | undefined
  if (s.fills !== undefined) {
    if (!Array.isArray(s.fills) || s.fills.length > MAX_SNAPSHOT_FILLS) return null
    fills = []
    for (const rawFill of s.fills) {
      const fill = parseFillOp(rawFill)
      if (!fill) return null
      fills.push(fill)
    }
  }
  const snapshot: SavedDesignSnapshot = {
    strokes,
    ...(fills ? { fills } : {}),
    model,
    brush: {
      sizeId: brush.sizeId as BrushSizeId,
      sizePx,
      opacity: brush.opacity,
      color: brush.color,
    },
    dimmed: s.dimmed,
  }
  if ('activeSide' in s) {
    if (s.activeSide !== 'front' && s.activeSide !== 'back') return null
    snapshot.activeSide = s.activeSide
  }
  if ('back' in s) {
    // Present Back must parse atomically — never omit a damaged bag and keep Front-only.
    const rawBack = s.back
    if (!rawBack || typeof rawBack !== 'object') return null
    const bag = rawBack as { strokes?: unknown; fills?: unknown }
    if (!Array.isArray(bag.strokes)) return null
    if (bag.fills !== undefined && !Array.isArray(bag.fills)) return null
    const backStrokes: Stroke[] = []
    for (const rawStroke of bag.strokes) {
      const stroke = parseStroke(rawStroke)
      if (!stroke) return null
      backStrokes.push(stroke)
    }
    const backFills: FillOp[] = []
    if (Array.isArray(bag.fills)) {
      for (const rawFill of bag.fills) {
        const fill = parseFillOp(rawFill)
        if (!fill) return null
        backFills.push(fill)
      }
    }
    snapshot.back = { strokes: backStrokes, fills: backFills }
  }
  return snapshot
}

export function isSavedDesignRow(row: Pick<DesignRowLike, 'design_data'>): boolean {
  const schema = (row.design_data ?? {})['schema']
  return schema === SAVED_DESIGN_SCHEMA || schema === SAVED_DESIGN_SCHEMA_V2
}

/**
 * Validate a designs-API row as an owner-private saved design.
 * Returns null for rows of another owner, non-private rows or malformed envelopes.
 */
export function parseSavedDesign(row: DesignRowLike, ownerId: string): SavedDesignRecord | null {
  if (row.user_id !== ownerId) return null
  if (row.visibility !== 'private') return null
  const data = row.design_data
  if (
    !data ||
    (data.schema !== SAVED_DESIGN_SCHEMA && data.schema !== SAVED_DESIGN_SCHEMA_V2)
  )
    return null
  const meta = row.metadata ?? {}
  if ('draftKind' in meta) return null
  if (typeof data.saveRequestId !== 'string' || !data.saveRequestId) return null
  const snapshot = parseSavedDesignSnapshot(data.snapshot)
  if (!snapshot) return null
  return {
    id: row.id,
    title: typeof row.title === 'string' ? row.title : '',
    savedAt:
      typeof data.savedAt === 'string' && !Number.isNaN(Date.parse(data.savedAt))
        ? data.savedAt
        : row.created_at,
    createdAt: row.created_at,
    saveRequestId: data.saveRequestId,
    snapshot,
  }
}

export type SavedDesignLibrary = {
  designs: SavedDesignRecord[]
  damaged: DamagedSavedDesign[]
}

/** Split an owner's design list into valid saved designs and damaged saved-design rows. */
export function partitionSavedDesigns(rows: DesignRowLike[], ownerId: string): SavedDesignLibrary {
  const designs: SavedDesignRecord[] = []
  const damaged: DamagedSavedDesign[] = []
  for (const row of rows) {
    if (row.user_id !== ownerId || !isSavedDesignRow(row)) continue
    const parsed = parseSavedDesign(row, ownerId)
    if (parsed) designs.push(parsed)
    else damaged.push({ id: row.id, title: String(row.title ?? ''), createdAt: row.created_at })
  }
  designs.sort((a, b) => Date.parse(b.savedAt) - Date.parse(a.savedAt))
  return { designs, damaged }
}

/**
 * Working-draft content for an opened saved design. The revision advances strictly above
 * both the local and the last server-acknowledged revision so the OCC write is a normal
 * forward transition of the same singleton row.
 */
export function workingDocumentFromSnapshot(args: {
  current: StudioDraftDocument
  serverRevision: number | null
  snapshot: SavedDesignSnapshot
  now?: Date
}): StudioDraftDocument {
  const floor = Math.max(args.current.clientRevision, args.serverRevision ?? 0)
  let next: StudioDraftDocument = {
    ...args.current,
    strokes: args.snapshot.strokes.map(canonicalStroke),
    fills: cloneFills(args.snapshot.fills ?? []),
    model: args.snapshot.model,
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: { ...args.snapshot.brush },
    dimmed: args.snapshot.dimmed,
    clientRevision: floor + 1,
    updatedAt: (args.now ?? new Date()).toISOString(),
  }
  if (isStudioFrontBackEnabled() && (args.snapshot.back || args.snapshot.activeSide)) {
    next = upgradeDraftToV2(next)
    next.activeSide = args.snapshot.activeSide === 'back' ? 'back' : 'front'
    next.back = args.snapshot.back
      ? cloneSideBag({
          strokes: args.snapshot.back.strokes.map(canonicalStroke),
          fills: cloneFills(args.snapshot.back.fills ?? []),
        })
      : emptySideBag()
  } else if (documentHasBackInk(next) || args.snapshot.back) {
    next = upgradeDraftToV2(next)
    if (args.snapshot.back) next.back = cloneSideBag(args.snapshot.back)
  }
  return next
}

export function modelLabel(model: ModelChoice): string {
  return libraryModelLabel(model)
}
