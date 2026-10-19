import { describe, expect, it } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  documentFromEditorState,
  draftContentFingerprint,
} from '@/lib/draftDocument'
import { documentForCloud } from '@/services/designsApi'

/**
 * Regression: applyDocument + immediate flushSave must never rebuild the save
 * payload from uncommitted React state (empty editor) after restoring a nonempty local doc.
 */
describe('authoritative snapshot save (P0 race)', () => {
  it('keeps every stroke and brush setting when flushing from the snapshot ref, not empty React state', () => {
    const restored = bumpDraftDocument(createEmptyDraftDocument(), {
      strokes: [
        {
          id: 'keep-me',
          tool: 'draw',
          points: [5, 5, 1, 15, 25, 1],
          color: '#112233',
          size: 4,
          opacity: 0.9,
        },
      ],
      model: 'male',
      brush: { sizeId: 'bold', opacity: 0.55, color: '#998877' },
      dimmed: true,
    })

    // Authoritative ref after restore (what flushSave must read).
    const authoritativeDocRef = { current: restored }

    // React state still empty / initial — the race the PM observed.
    const reactState = {
      strokes: [] as typeof restored.strokes,
      model: 'female' as const,
      customReferenceUrl: null as string | null,
      customReferenceKey: null as string | null,
      sizeId: 'thin' as const,
      opacity: 1,
      color: '#1C1C1E',
      dimmed: false,
    }

    const fromReact = documentFromEditorState({
      prev: createEmptyDraftDocument(),
      ...reactState,
    })
    const fromRef = authoritativeDocRef.current

    expect(draftContentFingerprint(fromReact)).not.toBe(draftContentFingerprint(fromRef))
    expect(fromRef.strokes).toHaveLength(1)
    expect(fromRef.strokes[0]?.id).toBe('keep-me')
    expect(fromRef.model).toBe('male')
    expect(fromRef.brush.sizeId).toBe('bold')
    expect(fromRef.brush.opacity).toBe(0.55)
    expect(fromRef.dimmed).toBe(true)

    // Cloud payload must preserve strokes (custom refs stripped only).
    const cloud = documentForCloud(fromRef)
    expect(cloud.strokes).toHaveLength(1)
    expect(cloud.model).toBe('male')
  })
})
