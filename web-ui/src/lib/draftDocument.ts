import type { ModelChoice } from '@/shell/modelTypes'
import {
  BRUSH_SIZES,
  INK_SWATCHES,
  type BrushSizeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'

export const STUDIO_DRAFT_SCHEMA = 'fashionrise.studio.draft.v1' as const
export const STUDIO_DRAFT_KIND = 'studio_working_draft' as const

export type StudioBrushState = {
  sizeId: BrushSizeId
  opacity: number
  color: string
}

export type StudioDraftDocument = {
  schema: typeof STUDIO_DRAFT_SCHEMA
  strokes: Stroke[]
  model: ModelChoice
  customReferenceUrl: string | null
  customReferenceKey: string | null
  brush: StudioBrushState
  dimmed: boolean
  /** Monotonic client revision for conflict detection across devices/tabs. */
  clientRevision: number
  updatedAt: string
}

export type StudioDraftEnvelope = {
  designId: string | null
  document: StudioDraftDocument
  source: 'server' | 'local'
}

export type SaveStatus = 'idle' | 'restoring' | 'saving' | 'saved' | 'error' | 'local-only'

const MODEL_CHOICES: ModelChoice[] = ['female', 'male', 'custom', 'blank']
const SIZE_IDS = Object.keys(BRUSH_SIZES) as BrushSizeId[]

export function createEmptyDraftDocument(now = new Date()): StudioDraftDocument {
  return {
    schema: STUDIO_DRAFT_SCHEMA,
    strokes: [],
    model: 'female',
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: {
      sizeId: 'thin',
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
  const model = MODEL_CHOICES.includes(raw.model as ModelChoice)
    ? (raw.model as ModelChoice)
    : 'female'
  const sizeId = SIZE_IDS.includes(raw.brush?.sizeId as BrushSizeId)
    ? (raw.brush.sizeId as BrushSizeId)
    : 'thin'
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
      size: typeof (s as Stroke).size === 'number' ? (s as Stroke).size : BRUSH_SIZES[sizeId],
      opacity: typeof (s as Stroke).opacity === 'number' ? (s as Stroke).opacity : 1,
    })
  }

  return {
    schema: STUDIO_DRAFT_SCHEMA,
    strokes,
    model,
    customReferenceUrl:
      typeof raw.customReferenceUrl === 'string' && raw.customReferenceUrl
        ? raw.customReferenceUrl
        : null,
    customReferenceKey:
      typeof raw.customReferenceKey === 'string' && raw.customReferenceKey
        ? raw.customReferenceKey
        : null,
    brush: { sizeId, opacity, color },
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
  return {
    ...prev,
    ...patch,
    brush: patch.brush ? { ...prev.brush, ...patch.brush } : prev.brush,
    schema: STUDIO_DRAFT_SCHEMA,
    clientRevision: prev.clientRevision + 1,
    updatedAt: now.toISOString(),
  }
}

export function draftContentFingerprint(doc: StudioDraftDocument): string {
  return JSON.stringify({
    strokes: doc.strokes,
    model: doc.model,
    customReferenceUrl: doc.customReferenceUrl,
    customReferenceKey: doc.customReferenceKey,
    brush: doc.brush,
    dimmed: doc.dimmed,
  })
}

export type ConflictChoice = 'keep-local' | 'use-server'

/**
 * Decide which draft wins when both local IndexedDB and server copies exist.
 * Never silently discard a newer local revision.
 */
export function resolveDraftConflict(
  local: StudioDraftDocument,
  server: StudioDraftDocument,
): { winner: 'local' | 'server' | 'equal'; needsUserChoice: boolean } {
  if (local.clientRevision === server.clientRevision) {
    if (draftContentFingerprint(local) === draftContentFingerprint(server)) {
      return { winner: 'equal', needsUserChoice: false }
    }
    // Same revision number but different content — ask the user.
    return { winner: 'local', needsUserChoice: true }
  }
  if (local.clientRevision > server.clientRevision) {
    return { winner: 'local', needsUserChoice: false }
  }
  if (server.clientRevision > local.clientRevision) {
    return { winner: 'server', needsUserChoice: false }
  }
  return { winner: 'local', needsUserChoice: true }
}

export function studioDraftMetadata(doc: StudioDraftDocument) {
  return {
    draftKind: STUDIO_DRAFT_KIND,
    schema: STUDIO_DRAFT_SCHEMA,
    clientRevision: doc.clientRevision,
    updatedAt: doc.updatedAt,
  }
}
