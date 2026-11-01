import { describe, expect, it } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
  parseStudioDraftDocument,
} from '@/lib/draftDocument'
import { documentForCloud } from '@/services/designsApi'
import { parseSavedDesignSnapshot, snapshotFromDocument, snapshotFingerprint } from '@/lib/savedDesign'
import { normalizeModelChoice, isModelChoice } from '@/assets/modelLibrary'
import { fitContainDestRect } from '@/lib/croquisGeometry'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

describe('personal croquis model + pins', () => {
  it('treats personal as a first-class ModelChoice (never remaps to female-straight)', () => {
    expect(isModelChoice('personal')).toBe(true)
    expect(normalizeModelChoice('personal')).toBe('personal')
    expect(normalizeModelChoice('not-a-model')).toBe('female-straight')
  })

  it('parses draft with exact personal pins and rejects personal without pins', () => {
    const base = createEmptyDraftDocument()
    const ok = parseStudioDraftDocument({
      ...base,
      model: 'personal',
      personalCroquisId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      personalCroquisVersion: 2,
    })
    expect(ok?.model).toBe('personal')
    expect(ok?.personalCroquisId).toBe('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee')
    expect(ok?.personalCroquisVersion).toBe(2)

    expect(
      parseStudioDraftDocument({
        ...base,
        model: 'personal',
        personalCroquisId: null,
        personalCroquisVersion: null,
      }),
    ).toBeNull()
  })

  it('fingerprint changes when personal pin version changes', () => {
    const a = createEmptyDraftDocument()
    a.model = 'personal'
    a.personalCroquisId = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    a.personalCroquisVersion = 1
    const b = { ...a, personalCroquisVersion: 2 }
    expect(draftContentFingerprint(a)).not.toBe(draftContentFingerprint(b))
  })

  it('fingerprint changes when switching personal croquis A→B (same strokes)', () => {
    const a = createEmptyDraftDocument()
    a.model = 'personal'
    a.personalCroquisId = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    a.personalCroquisVersion = 1
    a.strokes = [
      {
        id: 's1',
        tool: 'draw',
        points: [1, 2, 0.5, 3, 4, 0.6],
        color: '#1C1C1E',
        size: 2,
        opacity: 1,
      },
    ]
    const b = {
      ...a,
      personalCroquisId: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
      personalCroquisVersion: 2,
    }
    expect(draftContentFingerprint(documentForCloud(a))).not.toBe(
      draftContentFingerprint(documentForCloud(b)),
    )
    // Round-trip parse of B must keep B pins so PUT 200 extract matches send.
    const parsed = parseStudioDraftDocument(documentForCloud(b))
    expect(parsed?.personalCroquisId).toBe('bbbbbbbb-cccc-4ddd-8eee-ffffffffffff')
    expect(draftContentFingerprint(documentForCloud(parsed!))).toBe(
      draftContentFingerprint(documentForCloud(b)),
    )
  })

  it('ignores stray personal pins on builtin models for fingerprints and parse', () => {
    const clean = bumpDraftDocument(createEmptyDraftDocument(), { model: 'female-hand-hip' })
    const stray = {
      ...clean,
      personalCroquisId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      personalCroquisVersion: 2,
    }
    expect(draftContentFingerprint(clean)).toBe(draftContentFingerprint(stray))
    const parsed = parseStudioDraftDocument(stray)
    expect(parsed?.personalCroquisId).toBeNull()
    expect(parsed?.personalCroquisVersion).toBeNull()
    expect(draftContentFingerprint(parsed!)).toBe(draftContentFingerprint(clean))
    // Cloud writes must strip pins so PUT 200 + extract cannot false-conflict.
    expect(documentForCloud(stray).personalCroquisId).toBeNull()
    expect(documentForCloud(stray).personalCroquisVersion).toBeNull()
  })

  it('saved design snapshot keeps personal pins (unlike session custom URLs)', () => {
    const doc = createEmptyDraftDocument()
    doc.model = 'personal'
    doc.personalCroquisId = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    doc.personalCroquisVersion = 3
    doc.customReferenceUrl = 'blob:ignore'
    const snap = snapshotFromDocument(doc)
    expect(snap.model).toBe('personal')
    expect(snap.personalCroquisId).toBe('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee')
    expect(snap.personalCroquisVersion).toBe(3)
    const parsed = parseSavedDesignSnapshot(snap)
    expect(parsed?.personalCroquisVersion).toBe(3)
    expect(snapshotFingerprint(snap)).toContain('personal')
  })

  it('fit-contain into 768×1024 never crops the subject plane', () => {
    const tall = fitContainDestRect(500, 2000)
    expect(tall.h).toBeCloseTo(DESIGN_HEIGHT)
    expect(tall.w).toBeLessThan(DESIGN_WIDTH)
    expect(tall.x).toBeGreaterThan(0)
    const wide = fitContainDestRect(2000, 500)
    expect(wide.w).toBeCloseTo(DESIGN_WIDTH)
    expect(wide.h).toBeLessThan(DESIGN_HEIGHT)
    expect(wide.y).toBeGreaterThan(0)
  })
})
