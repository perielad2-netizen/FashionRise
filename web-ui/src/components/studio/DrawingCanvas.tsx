import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Path, Rect } from 'react-konva'
import type Konva from 'konva'
import { appendPoint, strokeToSvgPath } from '@/lib/freehand'
import { decidePointer, pressureForPointer } from '@/lib/pointerSession'
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
  activeTool: ToolKind
  brushColor: string
  brushSize: number
  referenceUrl: string | null
  referenceOpacity: number
  onStrokeComplete: (stroke: Stroke) => void
}

/**
 * Pointer Events only. A stroke lives only while the pointer is down.
 * Window-level pointerup/cancel and a mouse buttons check stop a lost release
 * from leaving drawing armed.
 */
export function DrawingCanvas({
  strokes,
  activeTool,
  brushColor,
  brushSize,
  referenceUrl,
  referenceOpacity,
  onStrokeComplete,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: DESIGN_WIDTH, h: DESIGN_HEIGHT })
  const [draft, setDraft] = useState<Stroke | null>(null)
  const [refImage, setRefImage] = useState<HTMLImageElement | null>(null)
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
          // Capture lives on the Konva content node (the element that receives
          // pointer events), not the outer stage container.
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
      // Moves aimed at the drawing surface are appended by the stage handler.
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
      drawing.current = true
      activePointerId.current = evt.pointerId
      stageRef.current = stage
      try {
        // Konva listens on `.konvajs-content`. Capturing the outer container
        // retargets later moves away from that node, so the stroke never grows.
        stage.content.setPointerCapture(evt.pointerId)
      } catch {
        /* capture optional; window listeners still end the stroke */
      }
      const stroke: Stroke = {
        id: createStrokeId(),
        tool: activeTool,
        points: appendPoint([], point),
        color: brushColor,
        size: brushSize,
        opacity: 1,
      }
      draftRef.current = stroke
      setDraft(stroke)
    },
    [activeTool, brushColor, brushSize, pointFrom, session],
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

  return (
    <div ref={hostRef} className={`${styles.host} studio-draw-surface`}>
      <div className={styles.frame} style={{ width: size.w, height: size.h }}>
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
