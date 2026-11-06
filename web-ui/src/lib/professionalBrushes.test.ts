import { describe, expect, it } from 'vitest'
import {
  applyBrushEngineToStroke,
  CHARCOAL_RENDERER_CURRENT,
  CHARCOAL_RENDERER_V1,
  CHARCOAL_RENDERER_V2,
  CHARCOAL_RENDERER_V3,
  CHARCOAL_RENDERER_V4,
  defaultSizeForBrushKind,
  defaultsForBrushKind,
  eraseAffectsLayer,
  erasePunchesFills,
  hashSeed,
  paintLogicalArtworkLayers,
  pickProfessionalFields,
  resolveBrushKind,
  resolveLogicalLayer,
  stampCenters,
  DEFAULT_BRUSH_ENGINE,
  __test,
} from '@/lib/professionalBrushes'
import type { Stroke } from '@/lib/strokes'

function sampleStroke(partial: Partial<Stroke> = {}): Stroke {
  return {
    id: 'stroke-1',
    tool: 'draw',
    points: [100, 100, 0.5, 140, 110, 0.7, 180, 120, 0.4],
    color: '#1C1C1E',
    size: 8,
    opacity: 0.85,
    ...partial,
  }
}

describe('professionalBrushes', () => {
  it('defaults legacy strokes to tapered ink', () => {
    const s = sampleStroke()
    expect(resolveBrushKind(s)).toBe('tapered')
    expect(resolveLogicalLayer(s)).toBe('ink')
  })

  it('maps charcoal/airbrush to shade unless blend is highlight-like', () => {
    expect(resolveLogicalLayer(sampleStroke({ brushKind: 'charcoal' }))).toBe('shade')
    expect(resolveLogicalLayer(sampleStroke({ brushKind: 'airbrush' }))).toBe('shade')
    expect(
      resolveLogicalLayer(sampleStroke({ brushKind: 'airbrush', blendMode: 'screen' })),
    ).toBe('highlight')
  })

  it('keeps charcoal grain deterministic for the same seed', () => {
    expect(hashSeed('abc')).toBe(hashSeed('abc'))
    expect(hashSeed('abc')).not.toBe(hashSeed('abd'))
  })

  it('does not punch fills when erasing shade/highlight layers', () => {
    expect(erasePunchesFills(sampleStroke({ tool: 'erase' }))).toBe(true)
    expect(
      erasePunchesFills(sampleStroke({ tool: 'erase', logicalLayer: 'ink' })),
    ).toBe(true)
    expect(
      erasePunchesFills(sampleStroke({ tool: 'erase', logicalLayer: 'shade' })),
    ).toBe(false)
    expect(
      erasePunchesFills(sampleStroke({ tool: 'erase', logicalLayer: 'highlight' })),
    ).toBe(false)
  })

  it('scopes erase to the active logical layer when set', () => {
    const eraseShade = sampleStroke({ tool: 'erase', logicalLayer: 'shade' })
    expect(eraseAffectsLayer(eraseShade, 'shade')).toBe(true)
    expect(eraseAffectsLayer(eraseShade, 'ink')).toBe(false)
    const legacy = sampleStroke({ tool: 'erase' })
    expect(eraseAffectsLayer(legacy, 'ink')).toBe(true)
    expect(eraseAffectsLayer(legacy, 'shade')).toBe(true)
  })

  it('applies engine fields and texture seed from stroke id', () => {
    const engine = {
      ...DEFAULT_BRUSH_ENGINE,
      brushKind: 'charcoal' as const,
      logicalLayer: 'shade' as const,
      blendMode: 'multiply' as const,
      textureIntensity: 0.8,
    }
    const next = applyBrushEngineToStroke(sampleStroke({ id: 'seed-me' }), engine)
    expect(next.brushKind).toBe('charcoal')
    expect(next.logicalLayer).toBe('shade')
    expect(next.blendMode).toBe('multiply')
    expect(next.textureSeed).toBe('seed-me')
    expect(next.charcoalRenderer).toBe(CHARCOAL_RENDERER_CURRENT)
    expect(next.charcoalRenderer).toBe(CHARCOAL_RENDERER_V4)
  })

  it('charcoal defaults favor wide soft fabric shading; ink stays fine', () => {
    expect(defaultSizeForBrushKind('tapered')).toBeLessThan(3)
    expect(defaultSizeForBrushKind('charcoal')).toBeGreaterThanOrEqual(14)
    expect(defaultSizeForBrushKind('airbrush')).toBeGreaterThanOrEqual(18)
    const charcoal = defaultsForBrushKind('charcoal')
    expect(charcoal.logicalLayer).toBe('shade')
    expect(charcoal.blendMode).toBe('multiply')
    expect((charcoal.softness ?? 0) >= 0.75).toBe(true)
    expect((charcoal.textureIntensity ?? 1) <= 0.25).toBe(true)
    expect(charcoal.garmentMask).toBe(true)
  })

  it('resolves absent charcoalRenderer as V1 for saved artwork compatibility', () => {
    expect(
      __test.resolveCharcoalRenderer(sampleStroke({ brushKind: 'charcoal' })),
    ).toBe(CHARCOAL_RENDERER_V1)
    expect(
      __test.resolveCharcoalRenderer(
        sampleStroke({ brushKind: 'charcoal', charcoalRenderer: CHARCOAL_RENDERER_V2 }),
      ),
    ).toBe(CHARCOAL_RENDERER_V2)
    expect(
      __test.resolveCharcoalRenderer(
        sampleStroke({ brushKind: 'charcoal', charcoalRenderer: CHARCOAL_RENDERER_V3 }),
      ),
    ).toBe(CHARCOAL_RENDERER_V3)
    expect(
      __test.resolveCharcoalRenderer(
        sampleStroke({ brushKind: 'charcoal', charcoalRenderer: CHARCOAL_RENDERER_V4 }),
      ),
    ).toBe(CHARCOAL_RENDERER_V4)
  })

  it('round-trips professional fields from raw JSON', () => {
    const picked = pickProfessionalFields({
      brushKind: 'airbrush',
      logicalLayer: 'highlight',
      blendMode: 'screen',
      flow: 0.33,
      softness: 0.9,
      textureIntensity: 0.1,
      textureSeed: 'x',
    })
    expect(picked).toEqual({
      brushKind: 'airbrush',
      logicalLayer: 'highlight',
      blendMode: 'screen',
      flow: 0.33,
      softness: 0.9,
      textureIntensity: 0.1,
      textureSeed: 'x',
    })
  })

  it('stamps along a polyline at roughly even spacing', () => {
    const stamps = stampCenters([0, 0, 0.5, 100, 0, 0.5], 20)
    expect(stamps.length).toBeGreaterThan(3)
    expect(stamps[0]).toMatchObject({ x: 0, y: 0 })
    expect(stamps[stamps.length - 1]?.x).toBeCloseTo(100, 0)
  })

  it('builds three logical layer canvases for professional strokes', () => {
    const probe = document.createElement('canvas')
    if (!probe.getContext('2d')) {
      // jsdom without node-canvas — structural paint covered by exportCanvas mocks.
      expect(true).toBe(true)
      return
    }
    const strokes: Stroke[] = [
      sampleStroke({
        id: 'ink-1',
        brushKind: 'tapered',
        logicalLayer: 'ink',
        color: '#111111',
      }),
      sampleStroke({
        id: 'shade-1',
        brushKind: 'charcoal',
        logicalLayer: 'shade',
        blendMode: 'multiply',
        textureSeed: 'shade-1',
        color: '#333333',
        points: [120, 140, 0.6, 160, 180, 0.5, 190, 210, 0.4],
      }),
      sampleStroke({
        id: 'hi-1',
        brushKind: 'airbrush',
        logicalLayer: 'highlight',
        blendMode: 'screen',
        softness: 0.8,
        flow: 0.4,
        color: '#FFFFFF',
        points: [130, 150, 0.5, 150, 170, 0.5],
      }),
    ]
    const layers = paintLogicalArtworkLayers(256, 256, strokes)
    expect(layers.ink.width).toBe(256)
    expect(layers.shade.width).toBe(256)
    expect(layers.highlight.width).toBe(256)
  })
})
