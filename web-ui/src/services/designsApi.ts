import { apiRequest } from '@/services/api/client'
import {
  STUDIO_DRAFT_KIND,
  STUDIO_DRAFT_SCHEMA,
  parseStudioDraftDocument,
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
      design_data: document,
      metadata: studioDraftMetadata(document),
      visibility: 'private',
      status: 'draft',
    },
  })
}

export async function updateStudioDraft(
  designId: string,
  document: StudioDraftDocument,
  signal?: AbortSignal,
): Promise<DesignRead> {
  return apiRequest<DesignRead>(`/designs/${designId}`, {
    method: 'PUT',
    signal,
    body: {
      design_data: document,
      metadata: studioDraftMetadata(document),
      visibility: 'private',
      status: 'draft',
    },
  })
}

export function extractStudioDraft(design: DesignRead): StudioDraftDocument | null {
  const fromData = parseStudioDraftDocument(design.design_data)
  if (fromData) return fromData
  const meta = design.metadata ?? {}
  if (meta.draftKind === STUDIO_DRAFT_KIND || meta.schema === STUDIO_DRAFT_SCHEMA) {
    return parseStudioDraftDocument(design.design_data)
  }
  return null
}

/** Prefer the newest owner-scoped studio working draft. */
export function pickLatestStudioDraft(designs: DesignRead[]): DesignRead | null {
  const matches = designs.filter((d) => {
    if (d.visibility !== 'private') return false
    if (extractStudioDraft(d)) return true
    const meta = d.metadata ?? {}
    return meta.draftKind === STUDIO_DRAFT_KIND
  })
  if (matches.length === 0) return null
  return matches.sort((a, b) => {
    const aDoc = extractStudioDraft(a)
    const bDoc = extractStudioDraft(b)
    const aRev = aDoc?.clientRevision ?? 0
    const bRev = bDoc?.clientRevision ?? 0
    if (aRev !== bRev) return bRev - aRev
    return String(b.updated_at).localeCompare(String(a.updated_at))
  })[0]!
}
