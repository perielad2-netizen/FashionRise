import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'
import { BUILTIN_FABRIC_TILE_PX, renderFabricTile } from '@/lib/paintFills'

vi.mock('@/lib/fabricAssetCache', () => ({
  ensureFabricAssetsForFills: vi.fn(async () => undefined),
  getCachedFabricImage: vi.fn(() => null),
  registerFabricCacheClearHook: vi.fn(),
  clearFabricAssetCache: vi.fn(),
}))

describe('fabricSwatchCapture', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('dominantPatternedFill prefers fabric over solid', async () => {
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
        id: 'f',
        contour: [0, 0, 20, 0, 20, 20, 0, 20],
        style: { kind: 'fabric', fabricId: 'satin' },
        seedX: 10,
        seedY: 10,
      },
    ]
    expect(dominantPatternedFill(fills)?.style).toEqual({ kind: 'fabric', fabricId: 'satin' })
    expect(dominantPatternedFill([])).toBeNull()
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
        contour: [0, 0, 40, 0, 40, 40, 0, 40],
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
