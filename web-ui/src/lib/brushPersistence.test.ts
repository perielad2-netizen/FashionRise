import { describe, expect, it } from 'vitest'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  documentFromEditorState,
  parseStudioDraftDocument,
  STUDIO_DRAFT_SCHEMA,
} from '@/lib/draftDocument'
import {
  parseSavedDesignSnapshot,
  snapshotFingerprint,
  snapshotFromDocument,
} from '@/lib/savedDesign'
import { BRUSH_SIZES } from '@/lib/strokes'

const legacyDraft = {
  schema: STUDIO_DRAFT_SCHEMA,
  strokes: [
    {
      id: 's1',
      tool: 'draw',
      points: [10, 10, 0.5, 40, 50, 0.5],
      color: '#1C1C1E',
      size: 1.75,
      opacity: 1,
    },
  ],
  fills: [],
  model: 'female-straight',
  customReferenceUrl: null,
  customReferenceKey: null,
  brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
  dimmed: false,
  clientRevision: 4,
  updatedAt: '2026-10-22T00:00:00.000Z',
}

describe('WEB-V4G brush persistence', () => {
  it('resolves legacy sizeId-only drafts to exact preset sizePx', () => {
    const parsed = parseStudioDraftDocument(legacyDraft)
    expect(parsed?.brush.sizeId).toBe('thin')
    expect(parsed?.brush.sizePx).toBe(1.75)
    expect(parsed?.strokes[0]?.size).toBe(1.75)
  })

  it('keeps exact numeric sizePx through draft round-trip', () => {
    const empty = createEmptyDraftDocument()
    const next = documentFromEditorState({
      prev: empty,
      strokes: empty.strokes,
      fills: [],
      model: empty.model,
      customReferenceUrl: null,
      customReferenceKey: null,
      sizeId: 'thick',
      sizePx: 6.5,
      opacity: 1,
      color: '#1C1C1E',
      dimmed: false,
    })
    expect(next.brush.sizePx).toBe(6.5)
    expect(next.brush.sizeId).toBe('thick')

    const reparsed = parseStudioDraftDocument(JSON.parse(JSON.stringify(next)))
    expect(reparsed?.brush.sizePx).toBe(6.5)
  })

  it('does not invent cloud conflicts when only sizePx is newly present at equivalent size', () => {
    const legacy = parseStudioDraftDocument(legacyDraft)!
    const withPx = {
      ...legacy,
      brush: { ...legacy.brush, sizePx: BRUSH_SIZES.thin },
    }
    expect(draftContentFingerprint(legacy)).toBe(draftContentFingerprint(withPx))
  })

  it('preserves numeric brush on saved-design snapshots and accepts legacy snapshots', () => {
    const empty = createEmptyDraftDocument()
    const doc = documentFromEditorState({
      prev: empty,
      strokes: [
        {
          id: 'ink',
          tool: 'draw',
          points: [1, 2, 0.5, 3, 4, 0.5],
          color: '#1C1C1E',
          size: 12.75,
          opacity: 1,
        },
      ],
      fills: [],
      model: empty.model,
      customReferenceUrl: null,
      customReferenceKey: null,
      sizeId: 'bold',
      sizePx: 12.75,
      opacity: 0.8,
      color: '#1C1C1E',
      dimmed: false,
    })
    const snap = snapshotFromDocument(doc)
    expect(snap.brush.sizePx).toBe(12.75)
    expect(snap.strokes[0]?.size).toBe(12.75)

    const legacySnap = parseSavedDesignSnapshot({
      strokes: snap.strokes,
      model: snap.model,
      brush: { sizeId: 'bold', opacity: 0.8, color: '#1C1C1E' },
      dimmed: false,
    })
    expect(legacySnap?.brush.sizePx).toBe(BRUSH_SIZES.bold)
    expect(snapshotFingerprint(legacySnap!)).toBe(
      snapshotFingerprint({
        ...legacySnap!,
        brush: { ...legacySnap!.brush, sizePx: BRUSH_SIZES.bold },
      }),
    )
  })
})
