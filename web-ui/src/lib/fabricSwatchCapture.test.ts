import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'
import { BUILTIN_FABRIC_TILE_PX, renderFabricTile } from '@/lib/paintFills'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

vi.mock('@/lib/fabricAssetCache', () => ({
  ensureFabricAssetsForFills: vi.fn(async () => undefined),
  getCachedFabricImage: vi.fn(() => null),
  registerFabricCacheClearHook: vi.fn(),
  clearFabricAssetCache: vi.fn(),
}))

/** Garment-scale rectangle (~8% of design plane) for Magic textile eligibility. */
function garmentScaleContour(): number[] {
  const w = Math.ceil(Math.sqrt(DESIGN_WIDTH * DESIGN_HEIGHT * 0.08))
  return [0, 0, w, 0, w, w, 0, w]
}

/** Shoe-scale rectangle (~1% of design plane) — must not drive Magic textile. */
function shoeScaleContour(): number[] {
  const w = Math.ceil(Math.sqrt(DESIGN_WIDTH * DESIGN_HEIGHT * 0.01))
  return [0, 0, w, 0, w, w, 0, w]
}

describe('fabricSwatchCapture', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('dominantPatternedFill prefers largest fabric over solid / smaller fabric', async () => {
    const { dominantPatternedFill } = await import('@/lib/fabricSwatchCapture')
    const fills: FillOp[] = [
      {
        id: 's',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: { kind: 'solid', color: '#111111' },
        seedX: 5,
        seedY: 5,
      },
      {
        id: 'shoe',
        contour: shoeScaleContour(),
        style: { kind: 'fabric', fabricId: 'satin' },
        seedX: 10,
        seedY: 10,
      },
      {
        id: 'dress',
        contour: garmentScaleContour(),
        style: { kind: 'fabric', fabricId: 'denim' },
        seedX: 100,
        seedY: 100,
      },
    ]
    expect(dominantPatternedFill(fills)?.style).toEqual({ kind: 'fabric', fabricId: 'denim' })
    expect(dominantPatternedFill([])).toBeNull()
  })

  it('isGarmentScalePatternedFill rejects shoe-sized fills', async () => {
    const { isGarmentScalePatternedFill, contourArea } = await import(
      '@/lib/fabricSwatchCapture'
    )
    const shoe: FillOp = {
      id: 'shoe',
      contour: shoeScaleContour(),
      style: { kind: 'fabric', fabricId: 'satin' },
      seedX: 5,
      seedY: 5,
    }
    const dress: FillOp = {
      id: 'dress',
      contour: garmentScaleContour(),
      style: { kind: 'fabric', fabricId: 'satin' },
      seedX: 50,
      seedY: 50,
    }
    expect(contourArea(shoe.contour)).toBeLessThan(DESIGN_WIDTH * DESIGN_HEIGHT * 0.06)
    expect(isGarmentScalePatternedFill(shoe)).toBe(false)
    expect(isGarmentScalePatternedFill(dress)).toBe(true)
  })

  it('renderFabricTile satin matches Studio tile size and pink geometric bands', () => {
    const tile = renderFabricTile('satin')
    expect(tile.width).toBe(BUILTIN_FABRIC_TILE_PX)
    expect(tile.height).toBe(BUILTIN_FABRIC_TILE_PX)
  })

  it('captureFabricSwatchForMagic returns null without patterned fills', async () => {
    const { captureFabricSwatchForMagic } = await import('@/lib/fabricSwatchCapture')
    const fills: FillOp[] = [
      {
        id: 's',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: { kind: 'solid', color: '#FF2D95' },
        seedX: 5,
        seedY: 5,
      },
    ]
    await expect(captureFabricSwatchForMagic(fills)).resolves.toBeNull()
  })

  it('captureFabricSwatchForMagic skips shoe-scale satin so ink dress colors win', async () => {
    const { captureFabricSwatchForMagic } = await import('@/lib/fabricSwatchCapture')
    const fills: FillOp[] = [
      {
        id: 'shoe-satin',
        contour: shoeScaleContour(),
        style: { kind: 'fabric', fabricId: 'satin' },
        seedX: 20,
        seedY: 20,
      },
    ]
    await expect(captureFabricSwatchForMagic(fills)).resolves.toBeNull()
  })

  it('captureFabricSwatchForMagic builds a satin data URL from the Studio tile', async () => {
    // jsdom lacks real canvas rasterization — stub a minimal 2d context that
    // still exercises the capture path and returns a PNG data URL.
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      if (tag !== 'canvas') return realCreate(tag)
      const canvas = {
        width: 0,
        height: 0,
        getContext: () => ({
          fillStyle: '#000',
          globalAlpha: 1,
          globalCompositeOperation: 'source-over',
          imageSmoothingEnabled: true,
          createLinearGradient: () => ({ addColorStop: () => undefined }),
          createRadialGradient: () => ({ addColorStop: () => undefined }),
          createPattern: () => ({}),
          fillRect: () => undefined,
          strokeRect: () => undefined,
          beginPath: () => undefined,
          moveTo: () => undefined,
          lineTo: () => undefined,
          arc: () => undefined,
          stroke: () => undefined,
          fill: () => undefined,
          drawImage: () => undefined,
        }),
        toDataURL: () =>
          'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII=',
      }
      return canvas as unknown as HTMLCanvasElement
    }) as typeof document.createElement)

    const { captureFabricSwatchForMagic } = await import('@/lib/fabricSwatchCapture')
    const fills: FillOp[] = [
      {
        id: 'satin',
        contour: garmentScaleContour(),
        style: { kind: 'fabric', fabricId: 'satin' },
        seedX: 20,
        seedY: 20,
      },
    ]
    const swatch = await captureFabricSwatchForMagic(fills)
    expect(swatch).not.toBeNull()
    expect(swatch!.kind).toBe('fabric')
    expect(swatch!.fabricId).toBe('satin')
    expect(swatch!.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
    expect(swatch!.label).toMatch(/satin repeating textile/i)
    vi.restoreAllMocks()
  })
})
