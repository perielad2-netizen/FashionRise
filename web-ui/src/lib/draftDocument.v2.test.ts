import { describe, expect, it } from 'vitest'
import {
  STUDIO_DRAFT_SCHEMA,
  STUDIO_DRAFT_SCHEMA_V2,
  StudioDraftSerializeError,
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
    expect(() => serializeStudioDraftDocument(doc, { frontBackEnabled: false })).toThrow(
      StudioDraftSerializeError,
    )
  })

  it('rejects malformed v2 back bags on parse', () => {
    const bad = parseStudioDraftDocument({
      schema: STUDIO_DRAFT_SCHEMA_V2,
      strokes: [],
      fills: [],
      activeSide: 'front',
      back: { strokes: 'not-an-array', fills: [] },
      model: 'female-straight',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 2,
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    expect(bad).toBeNull()
  })
})

const v2Base = {
  schema: STUDIO_DRAFT_SCHEMA_V2,
  strokes: [
    {
      id: 'f1',
      tool: 'draw' as const,
      points: [1, 2, 0.5],
      color: '#1C1C1E',
      size: 2,
      opacity: 1,
    },
  ],
  fills: [],
  activeSide: 'front' as const,
  model: 'female-straight',
  customReferenceUrl: null,
  customReferenceKey: null,
  brush: { sizeId: 'thin' as const, opacity: 1, color: '#1C1C1E' },
  dimmed: false,
  clientRevision: 2,
  updatedAt: '2026-10-25T00:00:00.000Z',
}

const goodBackStroke = {
  id: 'b1',
  tool: 'draw' as const,
  points: [3, 4, 0.5],
  color: '#1C1C1E',
  size: 2,
  opacity: 1,
}

const goodBackFill = {
  id: 'bf1',
  contour: [10, 10, 20, 10, 20, 20, 10, 20],
  style: { kind: 'solid' as const, color: '#B91C1C' },
  seedX: 15,
  seedY: 15,
}

describe('draftDocument v2 atomic Back parse', () => {
  it('allows absent Back on v2 (Front-only documents)', () => {
    const parsed = parseStudioDraftDocument({ ...v2Base })
    expect(parsed).not.toBeNull()
    expect(parsed?.back).toBeUndefined()
    expect(parsed?.strokes).toHaveLength(1)
  })

  it('accepts a well-formed nonempty Back bag', () => {
    const parsed = parseStudioDraftDocument({
      ...v2Base,
      back: { strokes: [goodBackStroke], fills: [goodBackFill] },
    })
    expect(parsed?.back?.strokes).toHaveLength(1)
    expect(parsed?.back?.fills).toHaveLength(1)
  })

  it.each([
    ['back null', null],
    ['back string', 'oops'],
    ['strokes missing', { fills: [] }],
    ['strokes not array', { strokes: 'nope', fills: [] }],
    ['fills wrong type', { strokes: [goodBackStroke], fills: 'nope' }],
    [
      'malformed stroke tool',
      {
        strokes: [{ ...goodBackStroke, tool: 'spray' }],
        fills: [],
      },
    ],
    [
      'malformed stroke points',
      {
        strokes: [{ ...goodBackStroke, points: [1, Number.NaN] }],
        fills: [],
      },
    ],
    [
      'malformed fill item',
      {
        strokes: [goodBackStroke],
        fills: [{ id: 'bad', contour: [1], style: { kind: 'solid', color: '#111111' }, seedX: 0, seedY: 0 }],
      },
    ],
  ])('rejects entire V2 draft when Back is malformed (%s)', (_label, back) => {
    const parsed = parseStudioDraftDocument({ ...v2Base, back })
    expect(parsed).toBeNull()
  })

  it('rejects invalid activeSide without coercing to front', () => {
    expect(parseStudioDraftDocument({ ...v2Base, activeSide: 'sideways' })).toBeNull()
  })

  it('does not coerce damaged Back fills to empty and keep Front ink', () => {
    const parsed = parseStudioDraftDocument({
      ...v2Base,
      back: { strokes: [goodBackStroke], fills: { length: 0 } },
    })
    expect(parsed).toBeNull()
  })
})
