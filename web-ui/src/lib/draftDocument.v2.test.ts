import { describe, expect, it } from 'vitest'
import {
  STUDIO_DRAFT_SCHEMA,
  STUDIO_DRAFT_SCHEMA_V2,
  createEmptyDraftDocument,
  draftContentFingerprint,
  parseStudioDraftDocument,
  serializeStudioDraftDocument,
  upgradeDraftToV2,
} from '@/lib/draftDocument'

describe('draftDocument v2', () => {
  it('fingerprints absent back differently from empty back bag on v2', () => {
    const v2Base = upgradeDraftToV2({
      ...createEmptyDraftDocument(),
      strokes: [
        {
          id: 'f1',
          tool: 'draw',
          points: [1, 2, 0.5],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
    })
    const withEmptyBack = { ...v2Base, back: { strokes: [], fills: [] } }
    const absentBack = { ...v2Base }
    delete (absentBack as { back?: unknown }).back
    expect(draftContentFingerprint(withEmptyBack)).not.toBe(draftContentFingerprint(absentBack))
  })

  it('parses v1 and v2 drafts', () => {
    const v1 = parseStudioDraftDocument({
      schema: STUDIO_DRAFT_SCHEMA,
      strokes: [],
      model: 'female-straight',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 1,
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    expect(v1?.schema).toBe(STUDIO_DRAFT_SCHEMA)
    expect(v1?.back).toBeUndefined()

    const v2 = parseStudioDraftDocument({
      schema: STUDIO_DRAFT_SCHEMA_V2,
      strokes: [],
      fills: [],
      activeSide: 'back',
      back: { strokes: [], fills: [] },
      model: 'male-straight',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 2,
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    expect(v2?.schema).toBe(STUDIO_DRAFT_SCHEMA_V2)
    expect(v2?.activeSide).toBe('back')
    expect(v2?.back).toEqual({ strokes: [], fills: [] })
  })

  it('serializes complete two-sided doc when v2 and flag on', () => {
    const doc = upgradeDraftToV2(createEmptyDraftDocument())
    const wire = serializeStudioDraftDocument(doc, { frontBackEnabled: true })
    expect(wire.schema).toBe(STUDIO_DRAFT_SCHEMA_V2)
    expect(wire.activeSide).toBe('front')
    expect(wire.back).toEqual({ strokes: [], fills: [] })
    const legacy = serializeStudioDraftDocument(doc, { frontBackEnabled: false })
    expect(legacy.schema).toBe(STUDIO_DRAFT_SCHEMA)
    expect(legacy.back).toBeUndefined()
  })
})
