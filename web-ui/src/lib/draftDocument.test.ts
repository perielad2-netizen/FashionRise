import { describe, expect, it } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  documentFromEditorState,
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
    // Pre-WEB-V4B drafts omit fills — open as empty fills, strokes preserved.
    expect(parsed?.fills).toEqual([])
  })

  it('preserves V1 strokes when fills are absent and restores optional fills', () => {
    const v1 = parseStudioDraftDocument({
      schema: STUDIO_DRAFT_SCHEMA,
      strokes: [
        {
          id: 'ink',
          tool: 'draw',
          points: [5, 5, 0.5, 15, 20, 0.5],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      model: 'female',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 2,
      updatedAt: '2026-10-19T00:00:00.000Z',
    })
    expect(v1?.strokes).toHaveLength(1)
    expect(v1?.fills).toEqual([])

    const withFills = parseStudioDraftDocument({
      ...v1!,
      fills: [
        {
          id: 'fill-1',
          contour: [10, 10, 40, 10, 40, 40, 10, 40],
          style: { kind: 'solid', color: '#b91c1c' },
          seedX: 20,
          seedY: 20,
        },
      ],
    })
    expect(withFills?.fills).toHaveLength(1)
    expect(withFills?.fills[0]?.style).toEqual({ kind: 'solid', color: '#B91C1C' })
    expect(withFills?.strokes).toHaveLength(1)
  })

  it('never auto-picks a winner when local and server content differ', () => {
    const local = createEmptyDraftDocument()
    const server = bumpDraftDocument(local, { model: 'blank' })
    expect(resolveDraftConflict(local, server)).toEqual({
      equal: false,
      needsUserChoice: true,
    })
    expect(resolveDraftConflict(server, local)).toEqual({
      equal: false,
      needsUserChoice: true,
    })
  })

  it('requires a user choice when revisions match but content differs', () => {
    const a = createEmptyDraftDocument()
    const b = { ...a, model: 'male' as const }
    expect(resolveDraftConflict(a, b).needsUserChoice).toBe(true)
  })

  it('treats identical content as equal regardless of revision labels', () => {
    const a = createEmptyDraftDocument()
    const b = { ...a, clientRevision: 99 }
    expect(resolveDraftConflict(a, b)).toEqual({ equal: true, needsUserChoice: false })
  })

  it('builds the next document from an authoritative previous snapshot', () => {
    const prev = createEmptyDraftDocument()
    const next = documentFromEditorState({
      prev,
      strokes: [
        {
          id: 's1',
          tool: 'draw',
          points: [0, 0, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      model: 'male',
      customReferenceUrl: null,
      customReferenceKey: null,
      sizeId: 'bold',
      opacity: 0.5,
      color: '#FF0000',
      dimmed: true,
    })
    expect(next.clientRevision).toBe(prev.clientRevision + 1)
    expect(next.strokes).toHaveLength(1)
    expect(next.model).toBe('male')
    expect(next.brush.sizeId).toBe('bold')
  })
})
