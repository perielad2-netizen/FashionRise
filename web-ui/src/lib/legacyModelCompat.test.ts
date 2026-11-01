import { describe, expect, it } from 'vitest'
import {
  LEGACY_MODEL_CANVAS,
  canvasSrcForModel,
  normalizeModelChoice,
} from '@/assets/modelLibrary'
import { createEmptyDraftDocument, parseStudioDraftDocument } from '@/lib/draftDocument'
import { parseSavedDesignSnapshot, snapshotFromDocument } from '@/lib/savedDesign'
import { previewReferenceUrl } from '@/lib/designPreview'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'

const stroke: Stroke = {
  id: 'ink-1',
  tool: 'draw',
  points: [120, 200, 0.5, 140, 240, 0.6, 160, 280, 0.5],
  color: '#B91C1C',
  size: 2,
  opacity: 1,
}

const fill: FillOp = {
  id: 'fill-1',
  contour: [100, 180, 180, 180, 180, 320, 100, 320],
  style: { kind: 'solid', color: '#F472B6' },
  seedX: 140,
  seedY: 240,
}

describe('legacy model geometry compatibility (WEB-V4D)', () => {
  it('keeps pre-V4D female/male documents on the original croquis URLs', () => {
    const raw = {
      schema: 'fashionrise.studio.draft.v1',
      strokes: [stroke],
      fills: [fill],
      model: 'female',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 4,
      updatedAt: '2026-10-21T12:00:00.000Z',
    }
    const doc = parseStudioDraftDocument(raw)
    expect(doc).not.toBeNull()
    expect(doc!.model).toBe('female')
    expect(doc!.strokes).toEqual([stroke])
    expect(doc!.fills).toEqual([fill])
    expect(canvasSrcForModel(doc!.model)).toBe('/models/female_model.png')
    expect(canvasSrcForModel(doc!.model)).toBe(LEGACY_MODEL_CANVAS.female)
    expect(canvasSrcForModel(doc!.model)).not.toContain('/models/library/')
  })

  it('keeps pre-V4D male documents on the original male display croquis', () => {
    const raw = {
      schema: 'fashionrise.studio.draft.v1',
      strokes: [stroke],
      fills: [fill],
      model: 'male',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'medium', opacity: 1, color: '#1C1C1E' },
      dimmed: true,
      clientRevision: 2,
      updatedAt: '2026-10-21T12:00:00.000Z',
    }
    const doc = parseStudioDraftDocument(raw)
    expect(doc!.model).toBe('male')
    expect(canvasSrcForModel(doc!.model)).toBe('/models/male_model_display.png')
    expect(previewReferenceUrl({ model: doc!.model })).toBe('/models/male_model_display.png')
  })

  it('does not rewrite legacy model ids when normalizing', () => {
    expect(normalizeModelChoice('female')).toBe('female')
    expect(normalizeModelChoice('male')).toBe('male')
  })

  it('uses the new straight-standing default for empty / new drafts', () => {
    const empty = createEmptyDraftDocument()
    expect(empty.model).toBe('female-straight')
    expect(canvasSrcForModel(empty.model)).toBe('/models/library/female-straight.png')
  })

  it('saved-design snapshots retain legacy model + stroke geometry for preview/export/Magic', () => {
    const doc = parseStudioDraftDocument({
      schema: 'fashionrise.studio.draft.v1',
      strokes: [stroke],
      fills: [fill],
      model: 'female',
      customReferenceUrl: null,
      customReferenceKey: null,
      brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
      dimmed: false,
      clientRevision: 1,
      updatedAt: '2026-10-21T12:00:00.000Z',
    })!
    const snap = snapshotFromDocument(doc)
    expect(snap.model).toBe('female')
    expect(snap.strokes[0]?.points).toEqual(stroke.points)
    expect(snap.fills?.[0]?.contour).toEqual(fill.contour)
    const parsed = parseSavedDesignSnapshot(snap)
    expect(parsed?.model).toBe('female')
    expect(previewReferenceUrl(parsed!)).toBe('/models/female_model.png')
    // Magic / export share the same reference resolver for built-ins.
    expect(canvasSrcForModel(parsed!.model)).toBe(previewReferenceUrl(parsed!))
  })
})
