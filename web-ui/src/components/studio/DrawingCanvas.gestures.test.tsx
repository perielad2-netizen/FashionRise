import { useState, type ComponentProps } from 'react'
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

type ControlledOpts = {
  tool?: 'draw' | 'fill' | 'erase' | 'eyedropper'
  panTool?: boolean
  strokes?: Stroke[]
  onStrokeComplete?: ReturnType<typeof vi.fn>
  onFillComplete?: ReturnType<typeof vi.fn>
}

/**
 * Mirrors CreatorWorkspace: viewport lives in React state so pan/pinch
 * re-renders DrawingCanvas with a new viewport prop (the P1 #51 path).
 */
function ControlledImmersiveCanvas({
  tool = 'draw',
  panTool = false,
  strokes = [],
  onStrokeComplete,
  onFillComplete,
}: ControlledOpts & {
  onStrokeComplete: NonNullable<ComponentProps<typeof DrawingCanvas>['onStrokeComplete']>
  onFillComplete: NonNullable<ComponentProps<typeof DrawingCanvas>['onFillComplete']>
}) {
  const [viewport, setViewport] = useState<ViewportState>(() => fitPage({ width: 800, height: 600 }))
  return (
    <DrawingCanvas
      strokes={strokes}
      activeTool={tool}
      brushColor="#111111"
      brushSize={2}
      referenceUrl={null}
      referenceOpacity={0.5}
      onStrokeComplete={onStrokeComplete}
      onFillComplete={onFillComplete}
      framed={false}
      immersive
      panTool={panTool}
      viewport={viewport}
      onViewportChange={setViewport}
    />
  )
}

function renderControlledImmersive(opts: ControlledOpts = {}) {
  const onStrokeComplete = opts.onStrokeComplete ?? vi.fn()
  const onFillComplete = opts.onFillComplete ?? vi.fn()
  const view = render(
    <ControlledImmersiveCanvas
      {...opts}
      onStrokeComplete={onStrokeComplete}
      onFillComplete={onFillComplete}
    />,
  )
  return { ...view, onStrokeComplete, onFillComplete }
}

async function drawStroke(
  content: Element,
  pointerId: number,
  from: { x: number; y: number },
  to: { x: number; y: number },
) {
  await act(async () => {
    firePointer(content, 'pointerdown', { pointerId, clientX: from.x, clientY: from.y })
    firePointer(content, 'pointermove', {
      pointerId,
      clientX: from.x + (to.x - from.x) / 2,
      clientY: from.y + (to.y - from.y) / 2,
    })
    firePointer(content, 'pointermove', { pointerId, clientX: to.x, clientY: to.y })
    firePointer(content, 'pointerup', { pointerId, clientX: to.x, clientY: to.y })
  })
}

async function waitCooldownSettle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 200))
  })
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

describe('DrawingCanvas P1 #51 Hand→Pencil after viewport rerenders', () => {
  beforeEach(() => {
    mockCanvasApis()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('draws after Hand single-finger pan then Pencil (controlled viewport rerenders)', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: true,
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const host = container.querySelector('[data-testid="drawing-canvas-host"]')!
    const content = bindHostMetrics(host)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 101, clientX: 240, clientY: 240 })
      firePointer(content, 'pointermove', { pointerId: 101, clientX: 300, clientY: 280 })
      firePointer(content, 'pointermove', { pointerId: 101, clientX: 360, clientY: 320 })
      firePointer(content, 'pointerup', { pointerId: 101, clientX: 360, clientY: 320 })
    })

    rerender(
      <ControlledImmersiveCanvas
        panTool={false}
        tool="draw"
        onStrokeComplete={onStrokeComplete}
        onFillComplete={vi.fn()}
      />,
    )
    const contentAfter = bindHostMetrics(
      container.querySelector('[data-testid="drawing-canvas-host"]')!,
    )

    await drawStroke(contentAfter, 102, { x: 220, y: 220 }, { x: 300, y: 300 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('draws after two-finger pinch/zoom then Hand→Pencil (cooldown survives viewport remount)', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: true,
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 111, clientX: 280, clientY: 220 })
      firePointer(content, 'pointerdown', { pointerId: 112, clientX: 400, clientY: 300 })
      firePointer(content, 'pointermove', { pointerId: 111, clientX: 240, clientY: 180 })
      firePointer(content, 'pointermove', { pointerId: 112, clientX: 480, clientY: 360 })
      firePointer(content, 'pointerup', { pointerId: 111, clientX: 240, clientY: 180 })
      firePointer(content, 'pointerup', { pointerId: 112, clientX: 480, clientY: 360 })
    })

    // Flush React viewport updates that remount the window-listener effect mid-cooldown.
    await act(async () => {
      await Promise.resolve()
    })
    await waitCooldownSettle()

    rerender(
      <ControlledImmersiveCanvas
        panTool={false}
        tool="draw"
        onStrokeComplete={onStrokeComplete}
        onFillComplete={vi.fn()}
      />,
    )
    const contentAfter = bindHostMetrics(
      container.querySelector('[data-testid="drawing-canvas-host"]')!,
    )

    await drawStroke(contentAfter, 113, { x: 250, y: 250 }, { x: 310, y: 310 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('survives repeated Hand/Pencil switching after pan + pinch', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: false,
      tool: 'draw',
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    let content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await drawStroke(content, 121, { x: 200, y: 200 }, { x: 260, y: 260 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)

    for (let i = 0; i < 3; i++) {
      rerender(
        <ControlledImmersiveCanvas
          panTool
          tool="draw"
          onStrokeComplete={onStrokeComplete}
          onFillComplete={vi.fn()}
        />,
      )
      content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)
      await act(async () => {
        firePointer(content, 'pointerdown', { pointerId: 130 + i, clientX: 220, clientY: 220 })
        firePointer(content, 'pointermove', {
          pointerId: 130 + i,
          clientX: 260 + i * 10,
          clientY: 250,
        })
        firePointer(content, 'pointerup', {
          pointerId: 130 + i,
          clientX: 260 + i * 10,
          clientY: 250,
        })
      })

      await act(async () => {
        firePointer(content, 'pointerdown', { pointerId: 140 + i, clientX: 300, clientY: 240 })
        firePointer(content, 'pointerdown', { pointerId: 150 + i, clientX: 420, clientY: 300 })
        firePointer(content, 'pointermove', { pointerId: 140 + i, clientX: 270, clientY: 200 })
        firePointer(content, 'pointermove', { pointerId: 150 + i, clientX: 470, clientY: 350 })
        firePointer(content, 'pointerup', { pointerId: 140 + i, clientX: 270, clientY: 200 })
        firePointer(content, 'pointerup', { pointerId: 150 + i, clientX: 470, clientY: 350 })
      })
      await waitCooldownSettle()

      rerender(
        <ControlledImmersiveCanvas
          panTool={false}
          tool="draw"
          onStrokeComplete={onStrokeComplete}
          onFillComplete={vi.fn()}
        />,
      )
      content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)
      await drawStroke(
        content,
        160 + i,
        { x: 210 + i * 5, y: 210 },
        { x: 280 + i * 5, y: 280 },
      )
    }

    expect(onStrokeComplete).toHaveBeenCalledTimes(4)
  })

  it('recovers after pointer release outside the canvas during Hand pan', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: true,
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 201, clientX: 250, clientY: 250 })
      firePointer(content, 'pointermove', { pointerId: 201, clientX: 320, clientY: 300 })
      window.dispatchEvent(
        new PointerEvent('pointerup', {
          bubbles: true,
          pointerId: 201,
          pointerType: 'touch',
          clientX: 8,
          clientY: 8,
        }),
      )
    })

    rerender(
      <ControlledImmersiveCanvas
        panTool={false}
        tool="draw"
        onStrokeComplete={onStrokeComplete}
        onFillComplete={vi.fn()}
      />,
    )
    const contentAfter = bindHostMetrics(
      container.querySelector('[data-testid="drawing-canvas-host"]')!,
    )
    await drawStroke(contentAfter, 202, { x: 240, y: 240 }, { x: 300, y: 300 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('recovers after pointercancel / lostpointercapture during pinch then Pencil', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: true,
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 211, clientX: 260, clientY: 220 })
      firePointer(content, 'pointerdown', { pointerId: 212, clientX: 400, clientY: 300 })
      firePointer(content, 'pointermove', { pointerId: 211, clientX: 230, clientY: 190 })
      firePointer(content, 'pointercancel', { pointerId: 211, clientX: 230, clientY: 190 })
      window.dispatchEvent(
        new PointerEvent('lostpointercapture', {
          bubbles: true,
          pointerId: 212,
          pointerType: 'touch',
          clientX: 400,
          clientY: 300,
        }),
      )
    })
    await waitCooldownSettle()

    rerender(
      <ControlledImmersiveCanvas
        panTool={false}
        tool="draw"
        onStrokeComplete={onStrokeComplete}
        onFillComplete={vi.fn()}
      />,
    )
    const contentAfter = bindHostMetrics(
      container.querySelector('[data-testid="drawing-canvas-host"]')!,
    )
    await drawStroke(contentAfter, 213, { x: 255, y: 255 }, { x: 305, y: 305 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('does not permanently block drawing when cooldown timer is cleared by viewport effect remount', async () => {
    const onStrokeComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: false,
      tool: 'draw',
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    // Pinch arms cooldown; controlled setViewport re-renders remount the listener effect
    // whose cleanup historically cleared the timer while leaving gestureCooldown true.
    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 221, clientX: 300, clientY: 250 })
      firePointer(content, 'pointerdown', { pointerId: 222, clientX: 420, clientY: 310 })
      firePointer(content, 'pointermove', { pointerId: 221, clientX: 250, clientY: 200 })
      firePointer(content, 'pointermove', { pointerId: 222, clientX: 500, clientY: 380 })
      firePointer(content, 'pointerup', { pointerId: 221, clientX: 250, clientY: 200 })
      firePointer(content, 'pointerup', { pointerId: 222, clientX: 500, clientY: 380 })
    })

    // Force an extra controlled remount while cooldown would still be armed (<80ms).
    await act(async () => {
      rerender(
        <ControlledImmersiveCanvas
          panTool={false}
          tool="draw"
          onStrokeComplete={onStrokeComplete}
          onFillComplete={vi.fn()}
        />,
      )
    })

    await waitCooldownSettle()
    const contentAfter = bindHostMetrics(
      container.querySelector('[data-testid="drawing-canvas-host"]')!,
    )
    await drawStroke(contentAfter, 223, { x: 270, y: 270 }, { x: 330, y: 330 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('draws immediately after all pinch pointers are released (no residual finger stroke)', async () => {
    const onStrokeComplete = vi.fn()
    const { container } = renderControlledImmersive({
      panTool: false,
      tool: 'draw',
      onStrokeComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    const content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 231, clientX: 280, clientY: 220 })
      firePointer(content, 'pointerdown', { pointerId: 232, clientX: 400, clientY: 300 })
      firePointer(content, 'pointerup', { pointerId: 232, clientX: 400, clientY: 300 })
      // Residual finger must not commit a stroke.
      firePointer(content, 'pointermove', { pointerId: 231, clientX: 340, clientY: 280 })
      firePointer(content, 'pointerup', { pointerId: 231, clientX: 340, clientY: 280 })
    })
    expect(onStrokeComplete).not.toHaveBeenCalled()

    await waitCooldownSettle()
    await drawStroke(content, 233, { x: 260, y: 260 }, { x: 320, y: 320 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })

  it('Hand→Pencil recovers across Eraser / Fill / Eyedropper tool transitions', async () => {
    const onStrokeComplete = vi.fn()
    const onFillComplete = vi.fn()
    const { container, rerender } = renderControlledImmersive({
      panTool: true,
      onStrokeComplete,
      onFillComplete,
    })
    await waitFor(() => expect(container.querySelector('.konvajs-content')).toBeTruthy())
    let content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)

    await act(async () => {
      firePointer(content, 'pointerdown', { pointerId: 241, clientX: 300, clientY: 250 })
      firePointer(content, 'pointerdown', { pointerId: 242, clientX: 420, clientY: 310 })
      firePointer(content, 'pointermove', { pointerId: 241, clientX: 260, clientY: 210 })
      firePointer(content, 'pointermove', { pointerId: 242, clientX: 480, clientY: 360 })
      firePointer(content, 'pointerup', { pointerId: 241, clientX: 260, clientY: 210 })
      firePointer(content, 'pointerup', { pointerId: 242, clientX: 480, clientY: 360 })
    })
    await waitCooldownSettle()

    for (const tool of ['erase', 'fill', 'eyedropper', 'draw'] as const) {
      rerender(
        <ControlledImmersiveCanvas
          panTool={false}
          tool={tool}
          onStrokeComplete={onStrokeComplete}
          onFillComplete={onFillComplete}
        />,
      )
      content = bindHostMetrics(container.querySelector('[data-testid="drawing-canvas-host"]')!)
    }

    await drawStroke(content, 243, { x: 250, y: 250 }, { x: 310, y: 310 })
    expect(onStrokeComplete).toHaveBeenCalledTimes(1)
  })
})
