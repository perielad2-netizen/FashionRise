import { act, cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import { fitPage, type ViewportState } from '@/lib/viewportTransform'
import type { Stroke } from '@/lib/strokes'

/**
 * Real DrawingCanvas + Konva Stage multitouch lifecycle (WEB-V4H Correction C).
 * Emulated PointerEvents in jsdom — not Apple Pencil / physical multitouch hardware.
 */

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function mockCanvasApis() {
  ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
    ResizeObserverStub as unknown as typeof ResizeObserver

  HTMLCanvasElement.prototype.getContext = vi.fn(function getContext(this: HTMLCanvasElement) {
    const ctx = {
      canvas: this,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      lineCap: 'butt',
      lineJoin: 'miter',
      miterLimit: 10,
      globalAlpha: 1,
      globalCompositeOperation: 'source-over',
      imageSmoothingEnabled: true,
      font: '10px sans-serif',
      textAlign: 'start',
      textBaseline: 'alphabetic',
      shadowColor: '',
      shadowBlur: 0,
      shadowOffsetX: 0,
      shadowOffsetY: 0,
      setTransform: vi.fn(),
      resetTransform: vi.fn(),
      transform: vi.fn(),
      scale: vi.fn(),
      translate: vi.fn(),
      rotate: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      closePath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      quadraticCurveTo: vi.fn(),
      bezierCurveTo: vi.fn(),
      arc: vi.fn(),
      arcTo: vi.fn(),
      ellipse: vi.fn(),
      rect: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      clip: vi.fn(),
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      drawImage: vi.fn(),
      getImageData: vi.fn(() => ({
        data: new Uint8ClampedArray(4),
        width: 1,
        height: 1,
        colorSpace: 'srgb',
      })),
      putImageData: vi.fn(),
      createImageData: vi.fn(() => ({
        data: new Uint8ClampedArray(4),
        width: 1,
        height: 1,
      })),
      createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      createPattern: vi.fn(() => null),
      measureText: vi.fn(() => ({ width: 0 })),
      setLineDash: vi.fn(),
      getLineDash: vi.fn(() => []),
      isPointInPath: vi.fn(() => false),
      isPointInStroke: vi.fn(() => false),
    }
    return ctx as unknown as CanvasRenderingContext2D
  }) as unknown as typeof HTMLCanvasElement.prototype.getContext
}

function firePointer(
  el: Element,
  type: string,
  init: Partial<PointerEventInit> & { clientX: number; clientY: number; pointerId: number },
) {
  el.dispatchEvent(
    new PointerEvent(type, {
      bubbles: true,
      cancelable: true,
      pointerType: 'touch',
      isPrimary: init.pointerId === 1,
      buttons: type === 'pointerup' || type === 'pointercancel' ? 0 : 1,
      button: 0,
      ...init,
    }),
  )
}

function bindHostMetrics(host: HTMLElement) {
  const rect = {
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    bottom: 600,
    right: 800,
    width: 800,
    height: 600,
    toJSON() {
      return {}
    },
  } as DOMRect
  host.getBoundingClientRect = () => rect
  Object.defineProperty(host, 'clientWidth', { configurable: true, get: () => 800 })
  Object.defineProperty(host, 'clientHeight', { configurable: true, get: () => 600 })
  const content = host.querySelector('.konvajs-content') as HTMLElement | null
  if (!content) throw new Error('Konva stage content missing')
  content.getBoundingClientRect = () => rect
  return content
}

function renderImmersive(opts: {
  tool?: 'draw' | 'fill' | 'erase' | 'eyedropper'
  strokes?: Stroke[]
  onStrokeComplete?: ReturnType<typeof vi.fn>
  onFillComplete?: ReturnType<typeof vi.fn>
}) {
  const onStrokeComplete = opts.onStrokeComplete ?? vi.fn()
  const onFillComplete = opts.onFillComplete ?? vi.fn()
  let viewport: ViewportState = fitPage({ width: 800, height: 600 })
  const view = render(
    <DrawingCanvas
      strokes={opts.strokes ?? []}
      activeTool={opts.tool ?? 'draw'}
      brushColor="#111111"
      brushSize={2}
      referenceUrl={null}
      referenceOpacity={0.5}
      onStrokeComplete={onStrokeComplete}
      onFillComplete={onFillComplete}
      framed={false}
      immersive
      viewport={viewport}
      onViewportChange={(next) => {
        viewport = next
      }}
    />,
  )
  return {
    ...view,
    onStrokeComplete,
    onFillComplete,
    getViewport: () => viewport,
  }
}

describe('DrawingCanvas immersive multitouch lifecycle', () => {
  beforeEach(() => {
    mockCanvasApis()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('cancels an unfinished draft when a second finger lands — zero committed strokes', async () => {
    const { container, onStrokeComplete } = renderImmersive({})
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 1, clientX: 200, clientY: 200 })
      firePointer(content, 'pointermove', { pointerId: 1, clientX: 220, clientY: 210 })
      firePointer(content, 'pointerdown', { pointerId: 2, clientX: 280, clientY: 240 })
      firePointer(content, 'pointerup', { pointerId: 2, clientX: 280, clientY: 240 })
      firePointer(content, 'pointerup', { pointerId: 1, clientX: 220, clientY: 210 })
    })

    expect(onStrokeComplete).not.toHaveBeenCalled()
  })

  it('requires a fresh pointer-down after gesture; remaining finger does not resume the draft', async () => {
    const { container, onStrokeComplete } = renderImmersive({})
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 1, clientX: 200, clientY: 200 })
      firePointer(content, 'pointerdown', { pointerId: 2, clientX: 300, clientY: 250 })
      firePointer(content, 'pointerup', { pointerId: 2, clientX: 300, clientY: 250 })
      firePointer(content, 'pointermove', { pointerId: 1, clientX: 260, clientY: 260 })
      firePointer(content, 'pointerup', { pointerId: 1, clientX: 260, clientY: 260 })
    })
    expect(onStrokeComplete).not.toHaveBeenCalled()
  })

  it('clears stuck gesture pointers when release happens outside the Stage', async () => {
    const { container, onStrokeComplete } = renderImmersive({})
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 11, clientX: 180, clientY: 180 })
      firePointer(content, 'pointerdown', { pointerId: 12, clientX: 320, clientY: 220 })
      window.dispatchEvent(
        new PointerEvent('pointerup', {
          bubbles: true,
          pointerId: 12,
          pointerType: 'touch',
          clientX: 10,
          clientY: 10,
        }),
      )
      window.dispatchEvent(
        new PointerEvent('pointerup', {
          bubbles: true,
          pointerId: 11,
          pointerType: 'touch',
          clientX: 12,
          clientY: 12,
        }),
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 120))
    })

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 21, clientX: 240, clientY: 240 })
      firePointer(content, 'pointermove', { pointerId: 21, clientX: 280, clientY: 280 })
      firePointer(content, 'pointermove', { pointerId: 21, clientX: 300, clientY: 300 })
      firePointer(content, 'pointerup', { pointerId: 21, clientX: 300, clientY: 300 })
    })

    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
    const stroke = onStrokeComplete.mock.calls[0]![0] as Stroke
    expect(stroke.points.length).toBeGreaterThanOrEqual(3)
  })

  it('handles pointercancel / lostpointercapture without stuck gesture mode', async () => {
    const { container, onStrokeComplete } = renderImmersive({})
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 31, clientX: 200, clientY: 200 })
      firePointer(content, 'pointerdown', { pointerId: 32, clientX: 300, clientY: 240 })
      firePointer(content, 'pointercancel', { pointerId: 31, clientX: 200, clientY: 200 })
      window.dispatchEvent(
        new PointerEvent('lostpointercapture', {
          bubbles: true,
          pointerId: 32,
          pointerType: 'touch',
          clientX: 300,
          clientY: 240,
        }),
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 120))
    })

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 41, clientX: 250, clientY: 250 })
      firePointer(content, 'pointermove', { pointerId: 41, clientX: 270, clientY: 270 })
      firePointer(content, 'pointermove', { pointerId: 41, clientX: 290, clientY: 290 })
      firePointer(content, 'pointerup', { pointerId: 41, clientX: 290, clientY: 290 })
    })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('does not fill on the first touch of an intended two-finger gesture', async () => {
    const closed: Stroke = {
      id: 'box',
      tool: 'draw',
      color: '#000000',
      size: 4,
      opacity: 1,
      points: [
        100, 100, 0.5, 300, 100, 0.5, 300, 300, 0.5, 100, 300, 0.5, 100, 100, 0.5, 100, 100, 0.5,
      ],
    }
    const { container, onFillComplete, onStrokeComplete } = renderImmersive({
      tool: 'fill',
      strokes: [closed],
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 51, clientX: 400, clientY: 300 })
      firePointer(content, 'pointerdown', { pointerId: 52, clientX: 480, clientY: 340 })
      firePointer(content, 'pointerup', { pointerId: 52, clientX: 480, clientY: 340 })
      firePointer(content, 'pointerup', { pointerId: 51, clientX: 400, clientY: 300 })
    })

    expect(onFillComplete).not.toHaveBeenCalled()
    expect(onStrokeComplete).not.toHaveBeenCalled()
  })

  it('applies combined pinch scale + midpoint pan via viewport updates', async () => {
    const { container, onStrokeComplete, getViewport } = renderImmersive({})
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)
    const before = { ...getViewport() }

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 61, clientX: 300, clientY: 250 })
      firePointer(content, 'pointerdown', { pointerId: 62, clientX: 420, clientY: 310 })
      firePointer(content, 'pointermove', { pointerId: 61, clientX: 260, clientY: 200 })
      firePointer(content, 'pointermove', { pointerId: 62, clientX: 500, clientY: 380 })
      firePointer(content, 'pointerup', { pointerId: 61, clientX: 260, clientY: 200 })
      firePointer(content, 'pointerup', { pointerId: 62, clientX: 500, clientY: 380 })
    })

    expect(getViewport().scale).not.toBeCloseTo(before.scale, 4)
    expect(onStrokeComplete).not.toHaveBeenCalled()
  })
})
