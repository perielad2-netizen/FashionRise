import { describe, expect, it } from 'vitest'
import { bumpDraftDocument, createEmptyDraftDocument, STUDIO_DRAFT_KIND } from '@/lib/draftDocument'
import { ApiError } from '@/services/api/client'
import {
  documentForCloud,
  extractStudioDraft,
  parseDraftConflict,
  pickLatestStudioDraft,
  type DesignRead,
} from '@/services/designsApi'

function design(partial: Partial<DesignRead> & { id: string }): DesignRead {
  return {
    user_id: 'u1',
    title: 'Studio working draft',
    description: null,
    garment_category: 'studio',
    design_data: {},
    metadata: {},
    visibility: 'private',
    status: 'draft',
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    ...partial,
  }
}

describe('designsApi helpers', () => {
  it('extracts studio drafts and picks the newest revision', () => {
    const older = createEmptyDraftDocument()
    const newer = { ...older, clientRevision: 5, model: 'male' as const }
    const rows = [
      design({
        id: 'd1',
        design_data: older as unknown as Record<string, unknown>,
        metadata: { draftKind: STUDIO_DRAFT_KIND },
        updated_at: '2026-10-10T00:00:00Z',
      }),
      design({
        id: 'd2',
        design_data: newer as unknown as Record<string, unknown>,
        metadata: { draftKind: STUDIO_DRAFT_KIND },
        updated_at: '2026-10-11T00:00:00Z',
      }),
      design({
        id: 'public',
        visibility: 'public',
        design_data: newer as unknown as Record<string, unknown>,
      }),
    ]
    const picked = pickLatestStudioDraft(rows)
    expect(picked?.id).toBe('d2')
    expect(extractStudioDraft(picked!)?.clientRevision).toBe(5)
  })

  it('strips custom reference fields before cloud write', () => {
    const doc = bumpDraftDocument(createEmptyDraftDocument(), {
      model: 'custom',
      customReferenceUrl: '/static/uploads/x.png',
      customReferenceKey: 'uploads/x.png',
    })
    const cloud = documentForCloud(doc)
    expect(cloud.customReferenceUrl).toBeNull()
    expect(cloud.customReferenceKey).toBeNull()
    expect(cloud.model).toBe('custom')
  })

  it('parses 409 conflict payloads for operator resolution', () => {
    const row = design({
      id: 'd9',
      design_data: createEmptyDraftDocument() as unknown as Record<string, unknown>,
      metadata: { draftKind: STUDIO_DRAFT_KIND },
    })
    const err = new ApiError('conflict', 409, {
      detail: {
        code: 'conflict',
        message: 'Draft was updated elsewhere.',
        payload: {
          expected_revision: 2,
          current_revision: 4,
          design: row,
        },
      },
    })
    const parsed = parseDraftConflict(err)
    expect(parsed?.expectedRevision).toBe(2)
    expect(parsed?.currentRevision).toBe(4)
    expect(parsed?.design.id).toBe('d9')
  })
})
