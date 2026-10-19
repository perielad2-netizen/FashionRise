import { describe, expect, it } from 'vitest'
import { createEmptyDraftDocument, STUDIO_DRAFT_KIND } from '@/lib/draftDocument'
import { extractStudioDraft, pickLatestStudioDraft, type DesignRead } from '@/services/designsApi'

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
})
