import { ApiError, apiRequest } from '@/services/api/client'
import {
  STUDIO_DRAFT_KIND,
  STUDIO_DRAFT_SCHEMA,
  STUDIO_DRAFT_SCHEMA_V2,
  parseStudioDraftDocument,
  serializeStudioDraftDocument,
  studioDraftMetadata,
  type StudioDraftDocument,
} from '@/lib/draftDocument'

export type DesignRead = {
  id: string
  user_id: string
  title: string
  description: string | null
  garment_category: string
  design_data: Record<string, unknown>
  metadata: Record<string, unknown>
  visibility: string
  status: string
  created_at: string
  updated_at: string
}

export type DraftConflictPayload = {
  expectedRevision: number
  currentRevision: number
  design: DesignRead
}

/** Strip session-only fields and apply schema serialization before cloud write. */
export function documentForCloud(document: StudioDraftDocument): StudioDraftDocument {
  const { clearBackIntent: _intent, ...rest } = document
  const serialized = serializeStudioDraftDocument(rest)
  if (!serialized.customReferenceUrl && !serialized.customReferenceKey) return serialized
  return {
    ...serialized,
    customReferenceUrl: null,
    customReferenceKey: null,
  }
}

export function cloudDraftMetadata(document: StudioDraftDocument): Record<string, unknown> {
  const clearBackIntent = Boolean(document.clearBackIntent)
  const cloud = documentForCloud(document)
  return studioDraftMetadata(cloud, clearBackIntent ? { clearBackIntent: true } : undefined)
}

export async function listMyDesigns(signal?: AbortSignal): Promise<DesignRead[]> {
  return apiRequest<DesignRead[]>('/designs/my', { signal })
}

export async function getDesign(designId: string, signal?: AbortSignal): Promise<DesignRead> {
  return apiRequest<DesignRead>(`/designs/${designId}`, { signal })
}

export async function createStudioDraft(
  document: StudioDraftDocument,
  signal?: AbortSignal,
): Promise<DesignRead> {
  const cloudDoc = documentForCloud(document)
  return apiRequest<DesignRead>('/designs', {
    method: 'POST',
    signal,
    body: {
      title: 'Studio working draft',
      description: 'Private FashionRise Creator Studio draft',
      garment_category: 'studio',
      template_id: null,
      material_id: null,
      color_palette_id: null,
      design_data: cloudDoc,
      metadata: cloudDraftMetadata(document),
      visibility: 'private',
      status: 'draft',
    },
  })
}

export async function updateStudioDraft(
  designId: string,
  document: StudioDraftDocument,
  options?: { expectedRevision?: number | null; signal?: AbortSignal },
): Promise<DesignRead> {
  const cloudDoc = documentForCloud(document)
  const body: Record<string, unknown> = {
    design_data: cloudDoc,
    metadata: cloudDraftMetadata(document),
    visibility: 'private',
    status: 'draft',
  }
  if (options?.expectedRevision != null) {
    body.expected_revision = options.expectedRevision
  }
  return apiRequest<DesignRead>(`/designs/${designId}`, {
    method: 'PUT',
    signal: options?.signal,
    body,
  })
}

/**
 * True when a private designs row claims to be the Studio working draft, even if
 * `design_data` fails strict parse (e.g. damaged V2 Back). Used to distinguish
 * "missing cloud draft" from "present but unreadable".
 */
export function isStudioWorkingDraftClaim(
  design: Pick<DesignRead, 'design_data' | 'metadata' | 'visibility'>,
): boolean {
  if (design.visibility !== 'private') return false
  const schema = design.design_data?.['schema']
  if (schema === STUDIO_DRAFT_SCHEMA || schema === STUDIO_DRAFT_SCHEMA_V2) return true
  const meta = design.metadata ?? {}
  return (
    meta.draftKind === STUDIO_DRAFT_KIND ||
    meta.schema === STUDIO_DRAFT_SCHEMA ||
    meta.schema === STUDIO_DRAFT_SCHEMA_V2
  )
}

/** Best-effort revision token from an unreadable Studio row (OCC / recovery). */
export function studioDraftRevisionHint(design: DesignRead): number | null {
  const dataRev = design.design_data?.['clientRevision']
  if (typeof dataRev === 'number' && Number.isFinite(dataRev) && dataRev > 0) {
    return Math.floor(dataRev)
  }
  const metaRev = design.metadata?.['clientRevision']
  if (typeof metaRev === 'number' && Number.isFinite(metaRev) && metaRev > 0) {
    return Math.floor(metaRev)
  }
  return null
}

export function extractStudioDraft(design: DesignRead): StudioDraftDocument | null {
  const fromData = parseStudioDraftDocument(design.design_data)
  if (fromData) return fromData
  const meta = design.metadata ?? {}
  if (
    meta.draftKind === STUDIO_DRAFT_KIND ||
    meta.schema === STUDIO_DRAFT_SCHEMA ||
    meta.schema === STUDIO_DRAFT_SCHEMA_V2
  ) {
    return parseStudioDraftDocument(design.design_data)
  }
  return null
}

/** Prefer the newest owner-scoped studio working draft. */
export function pickLatestStudioDraft(designs: DesignRead[]): DesignRead | null {
  const matches = designs.filter((d) => {
    if (d.visibility !== 'private') return false
    if (extractStudioDraft(d)) return true
    return isStudioWorkingDraftClaim(d)
  })
  if (matches.length === 0) return null
  return matches.sort((a, b) => {
    const aDoc = extractStudioDraft(a)
    const bDoc = extractStudioDraft(b)
    const aRev = aDoc?.clientRevision ?? studioDraftRevisionHint(a) ?? 0
    const bRev = bDoc?.clientRevision ?? studioDraftRevisionHint(b) ?? 0
    if (aRev !== bRev) return bRev - aRev
    return String(b.updated_at).localeCompare(String(a.updated_at))
  })[0]!
}

export function parseDraftConflict(error: unknown): DraftConflictPayload | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null
  const body = error.body
  if (!body || typeof body !== 'object') return null
  const detail = (body as { detail?: unknown }).detail
  if (!detail || typeof detail !== 'object') return null
  const payload = (detail as { payload?: unknown }).payload
  if (!payload || typeof payload !== 'object') return null
  const p = payload as {
    expected_revision?: unknown
    current_revision?: unknown
    design?: unknown
  }
  if (!p.design || typeof p.design !== 'object') return null
  return {
    expectedRevision: typeof p.expected_revision === 'number' ? p.expected_revision : -1,
    currentRevision: typeof p.current_revision === 'number' ? p.current_revision : -1,
    design: p.design as DesignRead,
  }
}
