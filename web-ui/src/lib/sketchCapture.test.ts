import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  captureGarmentArtworkForTryOn,
  captureSketchForMagic,
  MAGIC_MAX_SKETCH_BYTES,
  TRY_ON_GARMENT_CAPTURE_SCALE,
} from '@/lib/sketchCapture'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import { exportSketchPng } from '@/lib/exportCanvas'
import { FabricAssetLoadError } from '@/lib/fabricAssetCache'

vi.mock('@/lib/exportCanvas', () => ({
  exportSketchPng: vi.fn(),
}))

const exportMock = vi.mocked(exportSketchPng)

describe('captureSketchForMagic', () => {
  beforeEach(() => {
    exportMock.mockReset()
  })

  it('rejects empty canvas', async () => {
    await expect(
      captureSketchForMagic({ strokes: [], fills: [], referenceUrl: null }),
    ).rejects.toThrow(/Draw a sketch/i)
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('captures fills-only artwork for Magic without paid enqueue', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    const result = await captureSketchForMagic({
      strokes: [],
      fills: [
        {
          id: 'f1',
          contour: [10, 10, 40, 10, 40, 40, 10, 40],
          style: { kind: 'solid', color: '#B91C1C' },
          seedX: 20,
          seedY: 20,
        },
      ],
      referenceUrl: null,
    })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({
        fills: expect.arrayContaining([expect.objectContaining({ id: 'f1' })]),
        frame: 'legacy',
        onReferenceError: 'skip',
        onFabricError: 'throw',
      }),
    )
    expect(result.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
  })

  it('returns a png data URL for strokes without reference', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    const stroke = {
      id: 's1',
      tool: 'draw' as const,
      color: '#111111',
      size: 4,
      opacity: 1,
      points: [
        { x: 10, y: 10, p: 0.5 },
        { x: 20, y: 24, p: 0.5 },
      ],
    }
    const result = await captureSketchForMagic({ strokes: [stroke], referenceUrl: null })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({ onReferenceError: 'skip' }),
    )
    expect(result.byteLength).toBeGreaterThan(0)
    expect(result.byteLength).toBeLessThanOrEqual(MAGIC_MAX_SKETCH_BYTES)
    expect(result.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
  })

  it('does not enqueue-ready capture when an expected reference fails to load', async () => {
    exportMock.mockRejectedValue(new Error('Failed to load reference image'))
    const stroke = {
      id: 's1',
      tool: 'draw' as const,
      color: '#111111',
      size: 4,
      opacity: 1,
      points: [
        { x: 10, y: 10, p: 0.5 },
        { x: 12, y: 14, p: 0.5 },
      ],
    }
    await expect(
      captureSketchForMagic({
        strokes: [stroke],
        referenceUrl: 'https://example.com/model.png',
      }),
    ).rejects.toThrow(/Could not capture the model reference/i)
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({ onReferenceError: 'throw' }),
    )
  })

  it('fails closed when a custom fabric cannot be loaded (no paid enqueue)', async () => {
    exportMock.mockRejectedValue(
      new FabricAssetLoadError('33333333-3333-4333-8333-333333333333', 'missing'),
    )
    await expect(
      captureSketchForMagic({
        strokes: [],
        fills: [
          {
            id: 'f1',
            contour: [10, 10, 40, 10, 40, 40, 10, 40],
            style: {
              kind: 'uploaded-fabric',
              assetId: '33333333-3333-4333-8333-333333333333',
              scale: 1,
            },
            seedX: 20,
            seedY: 20,
          },
        ],
        referenceUrl: null,
      }),
    ).rejects.toThrow(/custom fabric|Magic was not started/i)
    expect(exportMock).toHaveBeenCalledWith(expect.objectContaining({ onFabricError: 'throw' }))
  })

  it('fails closed when expected reference is omitted from the export result', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([9, 9, 9])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    await expect(
      captureSketchForMagic({
        strokes: [
          {
            id: 's1',
            tool: 'draw',
            color: '#111111',
            size: 4,
            opacity: 1,
            points: [
              { x: 1, y: 1, p: 0.5 },
              { x: 2, y: 2, p: 0.5 },
            ],
          },
        ],
        referenceUrl: 'https://example.com/model.png',
      }),
    ).rejects.toThrow(/Could not capture the model reference/i)
  })
})

describe('captureGarmentArtworkForTryOn', () => {
  beforeEach(() => {
    exportMock.mockReset()
  })

  it('rejects empty garment artwork', async () => {
    await expect(captureGarmentArtworkForTryOn({ strokes: [], fills: [] })).rejects.toThrow(
      /Draw a garment/i,
    )
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('captures transparent garment-only PNG without croquis underlay', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    const stroke = {
      id: 's1',
      tool: 'draw' as const,
      color: '#111111',
      size: 4,
      opacity: 1,
      points: [
        { x: 10, y: 10, p: 0.5 },
        { x: 20, y: 24, p: 0.5 },
      ],
    }
    const result = await captureGarmentArtworkForTryOn({ strokes: [stroke], fills: [] })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({
        referenceUrl: null,
        garmentOnly: true,
        width: DESIGN_WIDTH * TRY_ON_GARMENT_CAPTURE_SCALE,
        height: DESIGN_HEIGHT * TRY_ON_GARMENT_CAPTURE_SCALE,
        frame: 'legacy',
        onReferenceError: 'skip',
        onFabricError: 'throw',
      }),
    )
    expect(result.referenceIncluded).toBe(false)
    expect(result.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
  })

  it('fails closed if export unexpectedly includes a croquis underlay', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }),
      referenceIncluded: true,
    })
    await expect(
      captureGarmentArtworkForTryOn({
        strokes: [
          {
            id: 's1',
            tool: 'draw',
            color: '#111',
            size: 4,
            opacity: 1,
            points: [
              { x: 1, y: 1, p: 0.5 },
              { x: 2, y: 2, p: 0.5 },
            ],
          },
        ],
      }),
    ).rejects.toThrow(/croquis underlay/i)
  })

  it('does not block Try On when only shade-layer erasers overshoot the legacy frame', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    // Prod incident 2026-11-05: shade erase tips at y≈-13 / y≈1098 blocked all Try On.
    const ink = {
      id: 'ink1',
      tool: 'draw' as const,
      color: '#111111',
      size: 4,
      opacity: 1,
      brushKind: 'tapered' as const,
      logicalLayer: 'ink' as const,
      points: [100, 100, 0.5, 120, 140, 0.5],
    }
    const shadeEraseOutside = {
      id: 'shade-erase-out',
      tool: 'erase' as const,
      color: '#000000',
      size: 8,
      opacity: 1,
      brushKind: 'tapered' as const,
      logicalLayer: 'shade' as const,
      points: [449, -3, 0.5, 459, -13, 0.5, 310, 1076, 0.5],
    }
    await expect(
      captureGarmentArtworkForTryOn({
        strokes: [ink, shadeEraseOutside],
        fills: [
          {
            id: 'f1',
            contour: [80, 80, 200, 80, 200, 400, 80, 400],
            style: { kind: 'solid', color: '#B91C1C' },
            seedX: 120,
            seedY: 200,
          },
        ],
      }),
    ).resolves.toMatchObject({ referenceIncluded: false })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({ frame: 'legacy', garmentOnly: true }),
    )
  })

  it('still blocks Try On when ink strokes leave the legacy frame', async () => {
    await expect(
      captureGarmentArtworkForTryOn({
        strokes: [
          {
            id: 'ink-out',
            tool: 'draw',
            color: '#111111',
            size: 4,
            opacity: 1,
            brushKind: 'tapered',
            logicalLayer: 'ink',
            points: [100, 100, 0.5, 900, 500, 0.5],
          },
        ],
        fills: [],
      }),
    ).rejects.toThrow(/extends beyond the standard try-on frame/i)
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('allows shoe fill a few px past legacy frame (under-ink soft pad)', async () => {
    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    await expect(
      captureGarmentArtworkForTryOn({
        strokes: [],
        fills: [
          {
            id: 'suit',
            contour: [200, 200, 500, 200, 500, 700, 200, 700],
            style: { kind: 'solid', color: '#B91C1C' },
            seedX: 350,
            seedY: 400,
          },
          {
            id: 'shoe',
            contour: [300, 980, 360, 980, 360, 1026, 300, 1026],
            style: { kind: 'solid', color: '#111111' },
            seedX: 330,
            seedY: 1000,
          },
        ],
      }),
    ).resolves.toMatchObject({ referenceIncluded: false })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({ frame: 'legacy', garmentOnly: true }),
    )
  })
})
