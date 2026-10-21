import { describe, expect, it, vi } from 'vitest'
import { captureSketchForMagic, MAGIC_MAX_SKETCH_BYTES } from '@/lib/sketchCapture'

vi.mock('@/lib/exportCanvas', () => ({
  exportSketchPng: vi.fn(async () => {
    const blob = new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' })
    return { blob, referenceIncluded: false }
  }),
}))

describe('captureSketchForMagic', () => {
  it('rejects empty canvas', async () => {
    await expect(
      captureSketchForMagic({ strokes: [], referenceUrl: null }),
    ).rejects.toThrow(/Draw a sketch/i)
  })

  it('returns a png data URL for strokes', async () => {
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
    // FileReader in jsdom
    const result = await captureSketchForMagic({ strokes: [stroke], referenceUrl: null })
    expect(result.byteLength).toBeGreaterThan(0)
    expect(result.byteLength).toBeLessThanOrEqual(MAGIC_MAX_SKETCH_BYTES)
    expect(result.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
  })
})
