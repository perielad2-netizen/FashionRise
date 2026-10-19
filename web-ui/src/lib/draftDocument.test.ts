import { describe, expect, it } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  parseStudioDraftDocument,
  resolveDraftConflict,
  STUDIO_DRAFT_SCHEMA,
} from '@/lib/draftDocument'

describe('draftDocument', () => {
  it('creates and bumps revisions without mutating schema', () => {
    const empty = createEmptyDraftDocument()
    expect(empty.schema).toBe(STUDIO_DRAFT_SCHEMA)
    expect(empty.clientRevision).toBe(1)
    const next = bumpDraftDocument(empty, { model: 'male', dimmed: true })
    expect(next.clientRevision).toBe(2)
    expect(next.model).toBe('male')
    expect(next.dimmed).toBe(true)
  })

  it('parses only valid stroke payloads', () => {
    const parsed = parseStudioDraftDocument({
      schema: STUDIO_DRAFT_SCHEMA,
      strokes: [
        {
          id: 'a',
          tool: 'draw',
          points: [1, 2, 0.5],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
        { id: 'bad', tool: 'laser', points: [] },
      ],
      model: 'female',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 3,
      updatedAt: '2026-10-19T00:00:00.000Z',
    })
    expect(parsed?.strokes).toHaveLength(1)
    expect(parsed?.clientRevision).toBe(3)
  })

  it('never silently prefers an older local revision over a newer server draft', () => {
    const local = createEmptyDraftDocument()
    const server = bumpDraftDocument(local, { model: 'blank' })
    expect(resolveDraftConflict(local, server)).toEqual({
      winner: 'server',
      needsUserChoice: false,
    })
    expect(resolveDraftConflict(server, local)).toEqual({
      winner: 'local',
      needsUserChoice: false,
    })
  })

  it('requires a user choice when revisions match but content differs', () => {
    const a = createEmptyDraftDocument()
    const b = { ...a, model: 'male' as const }
    expect(resolveDraftConflict(a, b).needsUserChoice).toBe(true)
  })
})
