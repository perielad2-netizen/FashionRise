import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Path, Rect } from 'react-konva'
import type Konva from 'konva'
import { appendPoint, strokeToSvgPath } from '@/lib/freehand'
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

  const toDesign = useCallback(
    (stage: Konva.Stage) => {
      const pos = stage.getPointerPosition()
      if (!pos) return null
      return {
        x: pos.x / scale,
        y: pos.y / scale,
        pressure: readPressure(stage),
      }
    },
    [scale],
  )

  const begin = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent | TouchEvent | MouseEvent>) => {
      const stage = e.target.getStage()
      if (!stage) return
      // Ensure touch events populate pointer position before reading.
      if ('touches' in e.evt || 'pointerId' in e.evt) {
        stage.setPointersPositions(e.evt)
      }
      const point = toDesign(stage)
      if (!point) return
      drawing.current = true
      setDraft({
        id: createStrokeId(),
        tool: activeTool,
        points: appendPoint([], point),
        color: brushColor,
        size: brushSize,
        opacity: 1,
      })
    },
    [activeTool, brushColor, brushSize, toDesign],
  )

  const move = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent | TouchEvent | MouseEvent>) => {
      if (!drawing.current) return
      const stage = e.target.getStage()
      if (!stage) return
      if ('touches' in e.evt || 'pointerId' in e.evt) {
        stage.setPointersPositions(e.evt)
      }
      const point = toDesign(stage)
      if (!point) return
      setDraft((prev) => (prev ? { ...prev, points: appendPoint(prev.points, point) } : prev))
    },
    [toDesign],
  )

  const end = useCallback(() => {
    if (!drawing.current) return
    drawing.current = false
    setDraft((prev) => {
      if (prev && prev.points.length >= 3) {
        onStrokeComplete(prev)
      }
      return null
    })
  }, [onStrokeComplete])

  const all = draft ? [...strokes, draft] : strokes

  return (
    <div ref={hostRef} className={`${styles.host} studio-draw-surface`}>
      <div className={styles.frame} style={{ width: size.w, height: size.h }}>
        <Stage
          width={size.w}
          height={size.h}
          scaleX={scale}
          scaleY={scale}
          onMouseDown={begin}
          onMousemove={move}
          onMouseup={end}
          onMouseLeave={end}
          onTouchStart={begin}
          onTouchMove={move}
          onTouchEnd={end}
          onPointerDown={begin}
          onPointerMove={move}
          onPointerUp={end}
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

function readPressure(stage: Konva.Stage): number {
  const evt = stage.getPointerPosition()
  void evt
  // Konva does not expose pressure directly on all events; default mid pressure.
  return 0.5
}
