import { describe, expect, it } from 'vitest'
import {
  MAX_SNAPSHOT_STROKES,
  SAVED_DESIGN_SCHEMA,
  TITLE_MAX_LENGTH,
  buildSavedDesignPayload,
  parseSavedDesign,
  partitionSavedDesigns,
  snapshotFingerprint,
  snapshotFromDocument,
  validateDesignTitle,
  workingDocumentFromSnapshot,
  type SavedDesignSnapshot,
} from '@/lib/savedDesign'
import {
  STUDIO_DRAFT_KIND,
  STUDIO_DRAFT_SCHEMA,
  createEmptyDraftDocument,
  studioDraftMetadata,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { extractStudioDraft, pickLatestStudioDraft, type DesignRead } from '@/services/designsApi'

const OWNER = 'owner-1'

function doc(overrides: Partial<StudioDraftDocument> = {}): StudioDraftDocument {
  return {
    ...createEmptyDraftDocument(new Date('2026-10-20T10:00:00.000Z')),
    strokes: [
      { id: 's1', tool: 'draw', points: [10, 20, 0.5, 30, 40, 0.6], color: '#1C1C1E', size: 1.75, opacity: 0.8 },
      { id: 's2', tool: 'erase', points: [12, 22, 0.5, 14, 24, 0.5], color: '#1C1C1E', size: 7, opacity: 1 },
    ],
    model: 'male',
    brush: { sizeId: 'thick', opacity: 0.6, color: '#1E3A8A' },
    dimmed: true,
    clientRevision: 7,
    ...overrides,
  }
}

function row(overrides: Partial<DesignRead> & { design_data?: Record<string, unknown> }): DesignRead {
  return {
    id: 'row-1',
    user_id: OWNER,
    title: 'Row',
    description: null,
    garment_category: 'studio',
    design_data: {},
    metadata: {},
    visibility: 'private',
    status: 'draft',
    created_at: '2026-10-20T10:00:00.000Z',
    updated_at: '2026-10-20T10:00:00.000Z',
    ...overrides,
  }
}

function savedRow(id: string, snapshot: SavedDesignSnapshot, extra: Partial<DesignRead> = {}): DesignRead {
  const payload = buildSavedDesignPayload({
    title: `Design ${id}`,
    snapshot,
    saveRequestId: `req-${id}`,
    sourceRevision: 7,
    now: new Date('2026-10-20T11:00:00.000Z'),
  })
  return row({
    id,
    title: payload.title,
    design_data: payload.design_data as unknown as Record<string, unknown>,
    metadata: payload.metadata,
    ...extra,
  })
}

function workingDraftRow(id: string, d: StudioDraftDocument): DesignRead {
  return row({
    id,
    title: 'Studio working draft',
    design_data: d as unknown as Record<string, unknown>,
    metadata: studioDraftMetadata(d),
  })
}

describe('saved design envelope format', () => {
  it('is a distinct private record that never looks like the Studio working draft', () => {
    const payload = buildSavedDesignPayload({
      title: 'Evening gown',
      snapshot: snapshotFromDocument(doc({ customReferenceUrl: 'blob:abc', customReferenceKey: 'k' })),
      saveRequestId: 'req-1',
      sourceRevision: 7,
    })
    expect(payload.design_data.schema).toBe(SAVED_DESIGN_SCHEMA)
    expect(payload.design_data.schema).not.toBe(STUDIO_DRAFT_SCHEMA)
    expect(payload.visibility).toBe('private')
    expect(payload.metadata).not.toHaveProperty('draftKind')
    expect(Object.values(payload.metadata)).not.toContain(STUDIO_DRAFT_KIND)
    expect(Object.values(payload.metadata)).not.toContain(STUDIO_DRAFT_SCHEMA)
    expect(payload.design_data.snapshot).not.toHaveProperty('schema')
    expect(payload.design_data.snapshot).not.toHaveProperty('clientRevision')
    expect(JSON.stringify(payload)).not.toContain('blob:')
    expect(payload.design_data.snapshot).not.toHaveProperty('customReferenceUrl')
  })

  it('is ignored by working-draft extraction and selection', () => {
    const working = doc({ clientRevision: 3 })
    const saved = savedRow('saved-1', snapshotFromDocument(doc({ clientRevision: 99 })))
    expect(extractStudioDraft(saved)).toBeNull()
    const picked = pickLatestStudioDraft([saved, workingDraftRow('draft-1', working)])
    expect(picked?.id).toBe('draft-1')
    expect(pickLatestStudioDraft([saved])).toBeNull()
  })

  it('preserves exact strokes, model and brush through save and parse', () => {
    const source = doc()
    const saved = savedRow('saved-1', snapshotFromDocument(source))
    const parsed = parseSavedDesign(JSON.parse(JSON.stringify(saved)), OWNER)
    expect(parsed).not.toBeNull()
    expect(parsed!.snapshot.strokes).toEqual(source.strokes)
    expect(parsed!.snapshot.model).toBe('male')
    expect(parsed!.snapshot.brush).toEqual({ sizeId: 'thick', opacity: 0.6, color: '#1E3A8A' })
    expect(parsed!.snapshot.dimmed).toBe(true)
    expect(parsed!.saveRequestId).toBe('req-saved-1')
  })

  it('snapshot is a deep copy: later edits never change it', () => {
    const source = doc()
    const snapshot = snapshotFromDocument(source)
    source.strokes[0]!.points.push(99, 99, 0.5)
    source.strokes.push({ ...source.strokes[0]!, id: 's3' })
    source.brush.color = '#D63384'
    expect(snapshot.strokes).toHaveLength(2)
    expect(snapshot.strokes[0]!.points).toEqual([10, 20, 0.5, 30, 40, 0.6])
    expect(snapshot.brush.color).toBe('#1E3A8A')
  })

  it('fingerprint ignores object key order (PostgreSQL JSONB reorders keys)', () => {
    const snapshot = snapshotFromDocument(doc())
    const reordered = JSON.parse(
      JSON.stringify({
        dimmed: snapshot.dimmed,
        brush: { color: snapshot.brush.color, opacity: snapshot.brush.opacity, sizeId: snapshot.brush.sizeId },
        model: snapshot.model,
        strokes: snapshot.strokes.map((s) => ({ opacity: s.opacity, size: s.size, color: s.color, points: s.points, tool: s.tool, id: s.id })),
      }),
    )
    expect(snapshotFingerprint(reordered)).toBe(snapshotFingerprint(snapshot))
  })
})

describe('parseSavedDesign safety', () => {
  const good = snapshotFromDocument(doc())

  it('rejects other owners and non-private rows', () => {
    expect(parseSavedDesign(savedRow('a', good, { user_id: 'someone-else' }), OWNER)).toBeNull()
    expect(parseSavedDesign(savedRow('a', good, { visibility: 'public' }), OWNER)).toBeNull()
  })

  it('rejects rows carrying the working-draft marker', () => {
    const r = savedRow('a', good)
    r.metadata = { ...r.metadata, draftKind: STUDIO_DRAFT_KIND }
    expect(parseSavedDesign(r, OWNER)).toBeNull()
  })

  it.each([
    ['NaN point', { strokes: [{ ...good.strokes[0]!, points: [1, Number.NaN] }] }],
    ['unknown tool', { strokes: [{ ...good.strokes[0]!, tool: 'spray' }] }],
    ['script colour', { strokes: [{ ...good.strokes[0]!, color: 'url(javascript:1)' }] }],
    ['unknown model', { model: 'robot' }],
    ['bad brush', { brush: { sizeId: 'huge', opacity: 1, color: '#000000' } }],
    ['strokes not array', { strokes: 'nope' }],
  ])('rejects a malformed snapshot (%s) instead of dropping ink', (_label, patch) => {
    const r = savedRow('a', { ...good, ...(patch as object) } as SavedDesignSnapshot)
    expect(parseSavedDesign(r, OWNER)).toBeNull()
  })

  it('rejects oversized snapshots', () => {
    const many = Array.from({ length: MAX_SNAPSHOT_STROKES + 1 }, (_, i) => ({ ...good.strokes[0]!, id: `s${i}` }))
    expect(parseSavedDesign(savedRow('a', { ...good, strokes: many }), OWNER)).toBeNull()
  })

  it('partitions library rows: saved designs only, damaged listed separately', () => {
    const working = workingDraftRow('draft-1', doc())
    const legacy = row({ id: 'legacy-1', design_data: { template: 'x' } })
    const foreign = savedRow('foreign', good, { user_id: 'other' })
    const older = savedRow('older', good)
    const newer = savedRow('newer', good)
    ;(newer.design_data as Record<string, unknown>).savedAt = '2026-10-20T12:00:00.000Z'
    const damaged = savedRow('broken', good)
    ;(damaged.design_data as Record<string, unknown>).snapshot = { strokes: 5 }
    const lib = partitionSavedDesigns([working, legacy, foreign, older, damaged, newer], OWNER)
    expect(lib.designs.map((d) => d.id)).toEqual(['newer', 'older'])
    expect(lib.damaged.map((d) => d.id)).toEqual(['broken'])
  })

  it('keeps hostile titles as plain data', () => {
    const r = savedRow('a', good, { title: '<img src=x onerror=alert(1)>' })
    expect(parseSavedDesign(r, OWNER)!.title).toBe('<img src=x onerror=alert(1)>')
  })
})

describe('validateDesignTitle', () => {
  it('trims and collapses whitespace', () => {
    expect(validateDesignTitle('  Spring   coat \n ')).toEqual({ ok: true, title: 'Spring coat' })
  })

  it('rejects empty, too long and control characters', () => {
    expect(validateDesignTitle('   ').ok).toBe(false)
    expect(validateDesignTitle('x'.repeat(TITLE_MAX_LENGTH + 1)).ok).toBe(false)
    expect(validateDesignTitle('ok\u0000bad').ok).toBe(false)
    expect(validateDesignTitle('x'.repeat(TITLE_MAX_LENGTH)).ok).toBe(true)
  })

  it('allows non-Latin titles', () => {
    expect(validateDesignTitle('שמלת ערב ✨')).toEqual({ ok: true, title: 'שמלת ערב ✨' })
  })
})

describe('workingDocumentFromSnapshot', () => {
  it('advances strictly above local and server revisions and drops session references', () => {
    const current = doc({ clientRevision: 5, customReferenceUrl: 'blob:x', model: 'custom' })
    const snapshot = snapshotFromDocument(doc({ model: 'female' }))
    const next = workingDocumentFromSnapshot({ current, serverRevision: 9, snapshot })
    expect(next.schema).toBe(STUDIO_DRAFT_SCHEMA)
    expect(next.clientRevision).toBe(10)
    expect(next.customReferenceUrl).toBeNull()
    expect(next.model).toBe('female')
    expect(next.strokes).toEqual(snapshot.strokes)
    expect(next.strokes).not.toBe(snapshot.strokes)
  })
})
