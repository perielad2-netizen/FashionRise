import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Path, Rect } from 'react-konva'
import type Konva from 'konva'
import { appendPoint, strokeToSvgPath } from '@/lib/freehand'
import { decidePointer, pressureForPointer } from '@/lib/pointerSession'
import { floodFillRegion } from '@/lib/floodFill'
import type { FillOp, FillStyle } from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import { sampleColorFromStyle } from '@/lib/paintFills'
import {
  DESIGN_HEIGHT,
  DESIGN_WIDTH,
  createStrokeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import styles from './DrawingCanvas.module.css'

type Props = {
  strokes: Stroke[]
  fills?: FillOp[]
  activeTool: ToolKind
  brushColor: string
  brushSize: number
  /** Opacity for new ink strokes (0–1). Older strokes keep their saved opacity. */
  brushOpacity?: number
  /** Style applied when the Fill tool succeeds. */
  fillStyle?: FillStyle
  referenceUrl: string | null
  referenceOpacity: number
  onStrokeComplete: (stroke: Stroke) => void
  onFillComplete?: (fill: FillOp) => void
  onFillError?: (message: string) => void
  onEyedropperSample?: (color: string) => void
  /** When false, host fills its parent frame (shell drawing workspace). */
  framed?: boolean
}

function renderFillsImage(fills: FillOp[]): HTMLImageElement | null {
  if (fills.length === 0) return null
  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  paintFillOps(ctx, fills)
  const img = new window.Image()
  img.src = canvas.toDataURL('image/png')
  return img
}

/**
 * Pointer Events only. A stroke lives only while the pointer is down.
 * Window-level pointerup/cancel and a mouse buttons check stop a lost release
 * from leaving drawing armed.
 */
export function DrawingCanvas({
  strokes,
  fills = [],
  activeTool,
  brushColor,
  brushSize,
  brushOpacity = 1,
  fillStyle,
  referenceUrl,
  referenceOpacity,
  onStrokeComplete,
  onFillComplete,
  onFillError,
  onEyedropperSample,
  framed = true,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: DESIGN_WIDTH, h: DESIGN_HEIGHT })
  const [draft, setDraft] = useState<Stroke | null>(null)
  const [refImage, setRefImage] = useState<HTMLImageElement | null>(null)
  const [fillsImage, setFillsImage] = useState<HTMLImageElement | null>(null)
  const drawing = useRef(false)
  const activePointerId = useRef<number | null>(null)
  const stageRef = useRef<Konva.Stage | null>(null)
  const draftRef = useRef<Stroke | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const measure = () => {
      const rect = host.getBoundingClientRect()
      const pad = 16
      const availW = Math.max(120, rect.width - pad * 2)
      const availH = Math.max(120, rect.height - pad * 2)
      const scale = Math.min(availW / DESIGN_WIDTH, availH / DESIGN_HEIGHT)
      setSize({
        w: Math.floor(DESIGN_WIDTH * scale),
        h: Math.floor(DESIGN_HEIGHT * scale),
      })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(host)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!referenceUrl) {
      setRefImage(null)
      return
    }
    let cancelled = false
    const img = new window.Image()
    img.onload = () => {
      if (!cancelled) setRefImage(img)
    }
    img.onerror = () => {
      if (!cancelled) setRefImage(null)
    }
    img.src = referenceUrl
    return () => {
      cancelled = true
    }
  }, [referenceUrl])

  useEffect(() => {
    let cancelled = false
    const img = renderFillsImage(fills)
    if (!img) {
      setFillsImage(null)
      return
    }
    img.onload = () => {
      if (!cancelled) setFillsImage(img)
    }
    return () => {
      cancelled = true
    }
  }, [fills])

  const scale = size.w / DESIGN_WIDTH

  const refFit = useMemo(() => {
    if (!refImage) return null
    const s = Math.min(DESIGN_WIDTH / refImage.width, DESIGN_HEIGHT / refImage.height)
    const w = refImage.width * s
    const h = refImage.height * s
    return {
      x: (DESIGN_WIDTH - w) / 2,
      y: (DESIGN_HEIGHT - h) / 2,
      w,
      h,
    }
  }, [refImage])

  const session = useCallback(
    () => ({ drawing: drawing.current, activePointerId: activePointerId.current }),
    [],
  )

  const finish = useCallback(
    (pointerId?: number) => {
      if (!drawing.current) return
      if (
        pointerId !== undefined &&
        activePointerId.current !== null &&
        pointerId !== activePointerId.current
      ) {
        return
      }
      drawing.current = false
      activePointerId.current = null
      const stage = stageRef.current
      if (stage && pointerId !== undefined) {
        try {
          stage.content.releasePointerCapture(pointerId)
        } catch {
          /* already released */
        }
      }
      const prev = draftRef.current
      draftRef.current = null
      setDraft(null)
      if (prev && prev.points.length >= 3) onStrokeComplete(prev)
    },
    [onStrokeComplete],
  )

  const pointFrom = useCallback(
    (stage: Konva.Stage, evt: PointerEvent) => {
      stage.setPointersPositions(evt)
      const pos = stage.getPointerPosition()
      if (!pos) return null
      return {
        x: pos.x / scale,
        y: pos.y / scale,
        pressure: pressureForPointer(evt.pointerType, evt.pressure),
      }
    },
    [scale],
  )

  const extendDraft = useCallback((point: { x: number; y: number; pressure: number }) => {
    const prev = draftRef.current
    if (!prev) return
    const next = { ...prev, points: appendPoint(prev.points, point) }
    draftRef.current = next
    setDraft(next)
  }, [])

  useEffect(() => {
    const onWindowPointer = (evt: PointerEvent) => {
      if (!drawing.current) return
      if (activePointerId.current !== null && evt.pointerId !== activePointerId.current) {
        return
      }

      if (
        evt.type === 'pointerup' ||
        evt.type === 'pointercancel' ||
        evt.type === 'lostpointercapture'
      ) {
        finish(evt.pointerId)
        return
      }

      if (evt.type !== 'pointermove') return

      const decision = decidePointer(session(), {
        type: 'move',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision === 'end') {
        finish(evt.pointerId)
        return
      }
      if (decision !== 'append') return

      const stage = stageRef.current
      const content = stage?.content
      const onSurface =
        !!content &&
        evt.target instanceof Node &&
        (evt.target === content || content.contains(evt.target))
      if (onSurface || !stage) return

      const point = pointFrom(stage, evt)
      if (!point) return
      extendDraft(point)
    }

    window.addEventListener('pointermove', onWindowPointer)
    window.addEventListener('pointerup', onWindowPointer)
    window.addEventListener('pointercancel', onWindowPointer)
    window.addEventListener('lostpointercapture', onWindowPointer)
    return () => {
      window.removeEventListener('pointermove', onWindowPointer)
      window.removeEventListener('pointerup', onWindowPointer)
      window.removeEventListener('pointercancel', onWindowPointer)
      window.removeEventListener('lostpointercapture', onWindowPointer)
    }
  }, [extendDraft, finish, pointFrom, session])

  const applyFillAt = useCallback(
    (x: number, y: number) => {
      const style = fillStyle ?? { kind: 'solid' as const, color: brushColor }
      const result = floodFillRegion({ strokes, x, y, style })
      if (!result.ok) {
        onFillError?.(result.message)
        return
      }
      onFillComplete?.(result.fill)
    },
    [brushColor, fillStyle, onFillComplete, onFillError, strokes],
  )

  const sampleAt = useCallback(
    (x: number, y: number) => {
      // Prefer topmost fill containing the point; else nearest ink; else brush color.
      for (let i = fills.length - 1; i >= 0; i -= 1) {
        const fill = fills[i]!
        if (pointInContour(x, y, fill.contour)) {
          onEyedropperSample?.(sampleColorFromStyle(fill.style))
          return
        }
      }
      // Sample from a tiny raster of ink at the point.
      const canvas = document.createElement('canvas')
      canvas.width = DESIGN_WIDTH
      canvas.height = DESIGN_HEIGHT
      const ctx = canvas.getContext('2d')
      if (ctx) {
        for (const stroke of strokes) {
          if (stroke.tool !== 'draw') continue
          const d = strokeToSvgPath(stroke)
          if (!d) continue
          ctx.fillStyle = stroke.color
          ctx.globalAlpha = stroke.opacity
          ctx.fill(new Path2D(d))
        }
        const px = Math.round(x)
        const py = Math.round(y)
        if (px >= 0 && py >= 0 && px < DESIGN_WIDTH && py < DESIGN_HEIGHT) {
          const data = ctx.getImageData(px, py, 1, 1).data
          if (data[3]! > 20) {
            const hex = `#${[data[0]!, data[1]!, data[2]!]
              .map((n) => n.toString(16).padStart(2, '0'))
              .join('')
              .toUpperCase()}`
            onEyedropperSample?.(hex)
            return
          }
        }
      }
      onEyedropperSample?.(brushColor)
    },
    [brushColor, fills, onEyedropperSample, strokes],
  )

  const onPointerDown = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      const decision = decidePointer(session(), {
        type: 'down',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision !== 'begin') return
      const stage = e.target.getStage()
      if (!stage) return
      const point = pointFrom(stage, evt)
      if (!point) return

      if (activeTool === 'fill') {
        applyFillAt(point.x, point.y)
        return
      }
      if (activeTool === 'eyedropper') {
        sampleAt(point.x, point.y)
        return
      }

      drawing.current = true
      activePointerId.current = evt.pointerId
      stageRef.current = stage
      try {
        stage.content.setPointerCapture(evt.pointerId)
      } catch {
        /* capture optional */
      }
      const stroke: Stroke = {
        id: createStrokeId(),
        tool: activeTool,
        points: appendPoint([], point),
        color: brushColor,
        size: brushSize,
        opacity: activeTool === 'erase' ? 1 : brushOpacity,
      }
      draftRef.current = stroke
      setDraft(stroke)
    },
    [
      activeTool,
      applyFillAt,
      brushColor,
      brushOpacity,
      brushSize,
      pointFrom,
      sampleAt,
      session,
    ],
  )

  const onPointerMove = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      const decision = decidePointer(session(), {
        type: 'move',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision === 'end') {
        finish(evt.pointerId)
        return
      }
      if (decision !== 'append') return
      const stage = e.target.getStage()
      if (!stage) return
      const point = pointFrom(stage, evt)
      if (!point) return
      extendDraft(point)
    },
    [extendDraft, finish, pointFrom, session],
  )

  const onPointerEnd = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      const decision = decidePointer(session(), {
        type: e.type === 'pointercancel' ? 'cancel' : 'up',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision === 'end') finish(evt.pointerId)
    },
    [finish, session],
  )

  const all = draft ? [...strokes, draft] : strokes
  const cursor =
    activeTool === 'fill' ? 'cell' : activeTool === 'eyedropper' ? 'crosshair' : 'crosshair'

  return (
    <div
      ref={hostRef}
      className={`${framed ? styles.host : styles.hostFlush} studio-draw-surface`}
      style={{ cursor }}
    >
      <div className={framed ? styles.frame : styles.frameFlush} style={{ width: size.w, height: size.h }}>
        <Stage
          width={size.w}
          height={size.h}
          scaleX={scale}
          scaleY={scale}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
        >
          <Layer listening={false}>
            <Rect x={0} y={0} width={DESIGN_WIDTH} height={DESIGN_HEIGHT} fill="#F8F4F0" />
            {refImage && refFit ? (
              <KonvaImage
                image={refImage}
                x={refFit.x}
                y={refFit.y}
                width={refFit.w}
                height={refFit.h}
                opacity={referenceOpacity}
              />
            ) : null}
            {fillsImage ? (
              <KonvaImage image={fillsImage} x={0} y={0} width={DESIGN_WIDTH} height={DESIGN_HEIGHT} />
            ) : null}
          </Layer>
          <Layer>
            {all.map((stroke) => {
              const data = strokeToSvgPath(stroke)
              if (!data) return null
              return (
                <Path
                  key={stroke.id}
                  data={data}
                  fill={stroke.tool === 'erase' ? '#F8F4F0' : stroke.color}
                  opacity={stroke.tool === 'erase' ? 1 : stroke.opacity}
                  globalCompositeOperation={
                    stroke.tool === 'erase' ? 'destination-out' : 'source-over'
                  }
                  listening={false}
                />
              )
            })}
          </Layer>
        </Stage>
      </div>
    </div>
  )
}

function pointInContour(x: number, y: number, contour: number[]): boolean {
  // Ray casting
  let inside = false
  for (let i = 0, j = contour.length - 2; i < contour.length; i += 2) {
    const xi = contour[i]!
    const yi = contour[i + 1]!
    const xj = contour[j]!
    const yj = contour[j + 1]!
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 0.0000001) + xi
    if (intersect) inside = !inside
    j = i
  }
  return inside
}
