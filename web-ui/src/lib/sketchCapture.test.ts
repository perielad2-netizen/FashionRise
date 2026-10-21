import { beforeEach, describe, expect, it, vi } from 'vitest'
import { captureSketchForMagic, MAGIC_MAX_SKETCH_BYTES } from '@/lib/sketchCapture'
import { exportSketchPng } from '@/lib/exportCanvas'

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
      captureSketchForMagic({ strokes: [], referenceUrl: null }),
    ).rejects.toThrow(/Draw a sketch/i)
    expect(exportMock).not.toHaveBeenCalled()
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
