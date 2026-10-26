import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Path, Rect } from 'react-konva'
import type Konva from 'konva'
import { appendPoint, strokeToSvgPath } from '@/lib/freehand'
import { decidePointer, pressureForPointer } from '@/lib/pointerSession'
import { floodFillRegion } from '@/lib/floodFill'
import type { FillOp, FillStyle } from '@/lib/fills'
import { ensureFabricAssetsForFills } from '@/lib/fabricAssetCache'
import { paintFillsWithErasers } from '@/lib/exportCanvas'
import { sampleArtworkPixel } from '@/lib/sampleArtworkPixel'
import {
  BRUSH_SIZE_STEP_PX,
  DESIGN_HEIGHT,
  DESIGN_WIDTH,
  createStrokeId,
  formatBrushSizePx,
  snapBrushSizePx,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import {
  clampPan,
  distance,
  fitPage,
  midpoint,
  panBy,
  pinchPan,
  safeViewport,
  screenToDesign,
  type ViewportState,
  zoomAt,
} from '@/lib/viewportTransform'
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
  /** Optional: Alt + mouse wheel adjusts brush size without drawing. */
  onBrushSize?: (px: number) => void
  /** When false, host fills its parent frame (shell drawing workspace). */
  framed?: boolean
  /**
   * Immersive viewport: Stage fills the host; content uses pan/scale transform.
   * When false/undefined, keep classic Fit-Page ResizeObserver sizing.
   */
  immersive?: boolean
  /** Hand/pan tool — drag pans instead of drawing. */
  panTool?: boolean
  viewport?: ViewportState
  onViewportChange?: (next: ViewportState) => void
}

/** Rasterize fills with chronological eraser punches (never includes croquis). */
function renderFillsImage(fills: FillOp[], strokes: Stroke[]): HTMLImageElement | null {
  if (fills.length === 0) return null
  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  paintFillsWithErasers(ctx, fills, strokes)
  const img = new window.Image()
  img.src = canvas.toDataURL('image/png')
  return img
}

/**
 * Pointer Events only. A stroke lives only while the pointer is down.
 * Window-level pointerup/cancel and a mouse buttons check stop a lost release
 * from leaving drawing armed.
 *
 * Immersive mode adds a Konva Layer transform (scale + pan) with inverse
 * pointer mapping; multitouch pinch/pan cancels uncommitted drafts safely.
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
  onBrushSize,
  framed = true,
  immersive = false,
  panTool = false,
  viewport,
  onViewportChange,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: DESIGN_WIDTH, h: DESIGN_HEIGHT })
  const [draft, setDraft] = useState<Stroke | null>(null)
  const [refImage, setRefImage] = useState<HTMLImageElement | null>(null)
  const [fillsImage, setFillsImage] = useState<HTMLImageElement | null>(null)
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null)
  const [wheelHint, setWheelHint] = useState(false)
  const drawing = useRef(false)
  const activePointerId = useRef<number | null>(null)
  const stageRef = useRef<Konva.Stage | null>(null)
  const draftRef = useRef<Stroke | null>(null)
  const wheelHintTimer = useRef<number | null>(null)
  const brushSizeRef = useRef(brushSize)
  const spaceDown = useRef(false)
  const panning = useRef(false)
  const panLast = useRef<{ x: number; y: number } | null>(null)
  const gestureMode = useRef(false)
  const gestureCooldown = useRef(false)
  const gestureCooldownTimer = useRef<number | null>(null)
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const pinchPrev = useRef<{ dist: number; midX: number; midY: number } | null>(null)
  /** Touch fill/eyedropper: commit on confirmed single-pointer up (not on first down). */
  const pendingTap = useRef<{
    pointerId: number
    x: number
    y: number
    tool: 'fill' | 'eyedropper'
  } | null>(null)
  const viewportRef = useRef<ViewportState>(viewport ?? fitPage({ width: DESIGN_WIDTH, height: DESIGN_HEIGHT }))
  const onViewportChangeRef = useRef(onViewportChange)
  const sizeRef = useRef(size)
  /** Latest handlers for the long-lived window pointer listeners (must not remount on pan/zoom). */
  const windowPointerApiRef = useRef({
    armGestureCooldown: () => {},
    cancelDraft: () => {},
    extendDraft: (_point: { x: number; y: number; pressure: number }) => {},
    finish: (_pointerId?: number) => {},
    pointFrom: (_stage: Konva.Stage, _evt: PointerEvent) =>
      null as { x: number; y: number; pressure: number } | null,
    session: () => ({ drawing: false, activePointerId: null as number | null }),
    updateViewport: (_next: ViewportState) => {},
  })

  useEffect(() => {
    brushSizeRef.current = brushSize
  }, [brushSize])

  useEffect(() => {
    sizeRef.current = size
  }, [size])

  useEffect(() => {
    if (viewport) viewportRef.current = viewport
  }, [viewport])

  useEffect(() => {
    onViewportChangeRef.current = onViewportChange
  }, [onViewportChange])

  // Leaving Hand must drop pan capture state so Pencil can begin immediately.
  useEffect(() => {
    if (panTool) return
    panning.current = false
    panLast.current = null
  }, [panTool])

  // Cooldown timer is owned by gesture lifecycle, not by listener effect identity.
  useEffect(() => {
    return () => {
      if (gestureCooldownTimer.current !== null) {
        window.clearTimeout(gestureCooldownTimer.current)
        gestureCooldownTimer.current = null
      }
    }
  }, [])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const measure = () => {
      const rect = host.getBoundingClientRect()
      if (immersive) {
        const w = Math.max(1, Math.floor(rect.width))
        const h = Math.max(1, Math.floor(rect.height))
        setSize({ w, h })
        if (onViewportChangeRef.current) {
          const next = clampPan(viewportRef.current, safeViewport({ width: w, height: h }))
          viewportRef.current = next
          onViewportChangeRef.current(next)
        }
        return
      }
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
  }, [immersive])

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
    if (fills.length === 0) {
      setFillsImage(null)
      return
    }
    void (async () => {
      await ensureFabricAssetsForFills(fills, { required: false }).catch(() => undefined)
      if (cancelled) return
      // Committed strokes only — live erase draft punches via Konva Path below.
      const img = renderFillsImage(fills, strokes)
      if (!img) {
        setFillsImage(null)
        return
      }
      img.onload = () => {
        if (!cancelled) setFillsImage(img)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [fills, strokes])

  const fitScale = size.w / DESIGN_WIDTH
  const contentScale = immersive && viewport ? viewport.scale : fitScale
  const panX = immersive && viewport ? viewport.panX : 0
  const panY = immersive && viewport ? viewport.panY : 0

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

  const releaseCapture = useCallback((pointerId?: number | null) => {
    const stage = stageRef.current
    if (!stage || pointerId === undefined || pointerId === null) return
    try {
      stage.content.releasePointerCapture(pointerId)
    } catch {
      /* already released */
    }
  }, [])

  const cancelDraft = useCallback(() => {
    const captured = activePointerId.current
    drawing.current = false
    activePointerId.current = null
    draftRef.current = null
    setDraft(null)
    panning.current = false
    panLast.current = null
    pendingTap.current = null
    releaseCapture(captured)
  }, [releaseCapture])

  const armGestureCooldown = useCallback(() => {
    gestureCooldown.current = true
    if (gestureCooldownTimer.current !== null) {
      window.clearTimeout(gestureCooldownTimer.current)
      gestureCooldownTimer.current = null
    }
    // Never clear cooldown while an old gesture pointer is still down.
    const tick = () => {
      if (pointers.current.size > 0) {
        gestureCooldownTimer.current = window.setTimeout(tick, 80)
        return
      }
      gestureCooldown.current = false
      gestureCooldownTimer.current = null
    }
    gestureCooldownTimer.current = window.setTimeout(tick, 80)
  }, [])

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
      const captured = activePointerId.current
      activePointerId.current = null
      releaseCapture(pointerId ?? captured)
      const prev = draftRef.current
      draftRef.current = null
      setDraft(null)
      if (prev && prev.points.length >= 3) onStrokeComplete(prev)
    },
    [onStrokeComplete, releaseCapture],
  )

  const pointFrom = useCallback(
    (stage: Konva.Stage, evt: PointerEvent) => {
      stage.setPointersPositions(evt)
      const pos = stage.getPointerPosition()
      if (!pos) return null
      if (immersive && viewport) {
        const design = screenToDesign(pos.x, pos.y, viewport)
        return {
          x: design.x,
          y: design.y,
          pressure: pressureForPointer(evt.pointerType, evt.pressure),
        }
      }
      return {
        x: pos.x / fitScale,
        y: pos.y / fitScale,
        pressure: pressureForPointer(evt.pointerType, evt.pressure),
      }
    },
    [fitScale, immersive, viewport],
  )

  const extendDraft = useCallback((point: { x: number; y: number; pressure: number }) => {
    const prev = draftRef.current
    if (!prev) return
    const next = { ...prev, points: appendPoint(prev.points, point) }
    draftRef.current = next
    setDraft(next)
  }, [])

  const updateViewport = useCallback((next: ViewportState) => {
    const host = hostRef.current
    const box = host
      ? safeViewport({
          width: host.clientWidth,
          height: host.clientHeight,
        })
      : safeViewport({ width: size.w, height: size.h })
    const clamped = clampPan(next, box)
    viewportRef.current = clamped
    onViewportChangeRef.current?.(clamped)
  }, [size.h, size.w])

  useEffect(() => {
    windowPointerApiRef.current = {
      armGestureCooldown,
      cancelDraft,
      extendDraft,
      finish,
      pointFrom,
      session,
      updateViewport,
    }
  }, [
    armGestureCooldown,
    cancelDraft,
    extendDraft,
    finish,
    pointFrom,
    session,
    updateViewport,
  ])

  useEffect(() => {
    const endTrackedPointer = (pointerId: number) => {
      pointers.current.delete(pointerId)
      if (pendingTap.current?.pointerId === pointerId) {
        pendingTap.current = null
      }
      const api = windowPointerApiRef.current
      if (gestureMode.current && pointers.current.size < 2) {
        gestureMode.current = false
        pinchPrev.current = null
        api.armGestureCooldown()
      }
      if (pointers.current.size === 0 && gestureCooldown.current) {
        api.armGestureCooldown()
      }
    }

    const onWindowPointer = (evt: PointerEvent) => {
      const api = windowPointerApiRef.current
      const box = sizeRef.current
      // Immersive multitouch: always clear / update tracked pointers even when
      // releases happen outside the Konva Stage (otherwise gesture mode sticks).
      if (immersive) {
        const ending =
          evt.type === 'pointerup' ||
          evt.type === 'pointercancel' ||
          evt.type === 'lostpointercapture'
        if (ending && pointers.current.has(evt.pointerId)) {
          endTrackedPointer(evt.pointerId)
          if (gestureMode.current || pointers.current.size > 0) {
            // Still in / finishing a gesture — do not resume stroke handling.
            return
          }
        } else if (evt.type === 'pointermove' && pointers.current.has(evt.pointerId)) {
          const host = hostRef.current
          if (host) {
            const rect = host.getBoundingClientRect()
            pointers.current.set(evt.pointerId, {
              x: evt.clientX - rect.left,
              y: evt.clientY - rect.top,
            })
          }
          if (gestureMode.current && pointers.current.size >= 2) {
            const pts = [...pointers.current.values()]
            const mid = midpoint(pts[0]!, pts[1]!)
            const dist = distance(pts[0]!, pts[1]!)
            const prev = pinchPrev.current
            if (prev && prev.dist > 0) {
              const factor = dist / prev.dist
              api.updateViewport(
                pinchPan(
                  viewportRef.current,
                  { width: box.w, height: box.h },
                  viewportRef.current.scale * factor,
                  prev.midX,
                  prev.midY,
                  mid.x,
                  mid.y,
                ),
              )
            }
            pinchPrev.current = { dist, midX: mid.x, midY: mid.y }
            return
          }
        }
        if (gestureMode.current) return
      }

      if (panning.current && (evt.type === 'pointermove' || evt.type === 'pointerup' || evt.type === 'pointercancel')) {
        if (evt.type === 'pointermove' && panLast.current && immersive) {
          const dx = evt.clientX - panLast.current.x
          const dy = evt.clientY - panLast.current.y
          panLast.current = { x: evt.clientX, y: evt.clientY }
          api.updateViewport(panBy(viewportRef.current, { width: box.w, height: box.h }, dx, dy))
          return
        }
        if (evt.type !== 'pointermove') {
          panning.current = false
          panLast.current = null
        }
        return
      }

      if (!drawing.current) return
      if (activePointerId.current !== null && evt.pointerId !== activePointerId.current) {
        return
      }

      if (
        evt.type === 'pointerup' ||
        evt.type === 'pointercancel' ||
        evt.type === 'lostpointercapture'
      ) {
        api.finish(evt.pointerId)
        return
      }

      if (evt.type !== 'pointermove') return

      const decision = decidePointer(api.session(), {
        type: 'move',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision === 'end') {
        api.finish(evt.pointerId)
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

      const point = api.pointFrom(stage, evt)
      if (!point) return
      api.extendDraft(point)
    }

    const onBlurOrHide = () => {
      const api = windowPointerApiRef.current
      pointers.current.clear()
      pendingTap.current = null
      if (gestureMode.current) {
        gestureMode.current = false
        pinchPrev.current = null
        api.armGestureCooldown()
      }
      if (drawing.current) api.cancelDraft()
      panning.current = false
      panLast.current = null
    }

    window.addEventListener('pointermove', onWindowPointer)
    window.addEventListener('pointerup', onWindowPointer)
    window.addEventListener('pointercancel', onWindowPointer)
    window.addEventListener('lostpointercapture', onWindowPointer)
    window.addEventListener('blur', onBlurOrHide)
    document.addEventListener('visibilitychange', onBlurOrHide)
    return () => {
      // Listener identity only — never clear gestureCooldownTimer here.
      // Viewport-driven remounts used to cancel the timer while leaving
      // gestureCooldown.current true, permanently blocking Pencil (P1 #51).
      window.removeEventListener('pointermove', onWindowPointer)
      window.removeEventListener('pointerup', onWindowPointer)
      window.removeEventListener('pointercancel', onWindowPointer)
      window.removeEventListener('lostpointercapture', onWindowPointer)
      window.removeEventListener('blur', onBlurOrHide)
      document.removeEventListener('visibilitychange', onBlurOrHide)
    }
  }, [immersive])

  useEffect(() => {
    if (!immersive) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat) {
        const t = e.target as HTMLElement | null
        if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
        spaceDown.current = true
      }
    }
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        spaceDown.current = false
        panning.current = false
        panLast.current = null
      }
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [immersive])

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
      const sampled = sampleArtworkPixel({ fills, strokes, x, y })
      onEyedropperSample?.(sampled.hit ? sampled.hex : brushColor)
    },
    [brushColor, fills, onEyedropperSample, strokes],
  )

  const hostPoint = (evt: PointerEvent) => {
    const host = hostRef.current
    if (!host) return { x: evt.clientX, y: evt.clientY }
    const rect = host.getBoundingClientRect()
    return { x: evt.clientX - rect.left, y: evt.clientY - rect.top }
  }

  const beginGestureFromPointers = useCallback(() => {
    const pts = [...pointers.current.values()]
    if (pts.length < 2) return
    cancelDraft()
    pendingTap.current = null
    gestureMode.current = true
    gestureCooldown.current = true
    const mid = midpoint(pts[0]!, pts[1]!)
    pinchPrev.current = { dist: distance(pts[0]!, pts[1]!), midX: mid.x, midY: mid.y }
  }, [cancelDraft])

  const onPointerDown = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      const stage = e.target.getStage()
      if (!stage) return
      stageRef.current = stage

      if (immersive) {
        const hp = hostPoint(evt)
        pointers.current.set(evt.pointerId, hp)
        if (pointers.current.size >= 2) {
          beginGestureFromPointers()
          evt.preventDefault()
          return
        }
      }

      if (gestureCooldown.current || gestureMode.current) {
        return
      }

      const wantPan = immersive && (panTool || spaceDown.current || (evt.button === 1 && evt.pointerType === 'mouse'))
      if (wantPan) {
        cancelDraft()
        panning.current = true
        panLast.current = { x: evt.clientX, y: evt.clientY }
        try {
          stage.content.setPointerCapture(evt.pointerId)
        } catch {
          /* optional */
        }
        return
      }

      const decision = decidePointer(session(), {
        type: 'down',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision !== 'begin') return
      const point = pointFrom(stage, evt)
      if (!point) return

      if (activeTool === 'fill' || activeTool === 'eyedropper') {
        // Touch: defer until pointer-up confirms a single-pointer tap so the
        // first finger of an intended pinch cannot flood-fill / sample.
        if (evt.pointerType === 'touch') {
          pendingTap.current = {
            pointerId: evt.pointerId,
            x: point.x,
            y: point.y,
            tool: activeTool,
          }
          try {
            stage.content.setPointerCapture(evt.pointerId)
          } catch {
            /* optional */
          }
          return
        }
        if (activeTool === 'fill') applyFillAt(point.x, point.y)
        else sampleAt(point.x, point.y)
        return
      }

      drawing.current = true
      activePointerId.current = evt.pointerId
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
      cancelDraft,
      immersive,
      panTool,
      pointFrom,
      sampleAt,
      session,
      beginGestureFromPointers,
    ],
  )

  const onPointerMove = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      const stage = e.target.getStage()
      if (!stage) return

      if (immersive && pointers.current.has(evt.pointerId)) {
        pointers.current.set(evt.pointerId, hostPoint(evt))
      }

      if (immersive && gestureMode.current && pointers.current.size >= 2) {
        const pts = [...pointers.current.values()]
        const mid = midpoint(pts[0]!, pts[1]!)
        const dist = distance(pts[0]!, pts[1]!)
        const prev = pinchPrev.current
        if (prev && prev.dist > 0) {
          const factor = dist / prev.dist
          updateViewport(
            pinchPan(
              viewportRef.current,
              { width: size.w, height: size.h },
              viewportRef.current.scale * factor,
              prev.midX,
              prev.midY,
              mid.x,
              mid.y,
            ),
          )
        }
        pinchPrev.current = { dist, midX: mid.x, midY: mid.y }
        evt.preventDefault()
        return
      }

      if (panning.current && panLast.current && immersive) {
        const dx = evt.clientX - panLast.current.x
        const dy = evt.clientY - panLast.current.y
        panLast.current = { x: evt.clientX, y: evt.clientY }
        updateViewport(panBy(viewportRef.current, { width: size.w, height: size.h }, dx, dy))
        return
      }

      if (pendingTap.current) return

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
      const point = pointFrom(stage, evt)
      if (!point) return
      extendDraft(point)
    },
    [extendDraft, finish, immersive, pointFrom, session, size.h, size.w, updateViewport],
  )

  const onPointerEnd = useCallback(
    (e: Konva.KonvaEventObject<PointerEvent>) => {
      const evt = e.evt
      pointers.current.delete(evt.pointerId)

      if (gestureMode.current) {
        if (pointers.current.size < 2) {
          gestureMode.current = false
          pinchPrev.current = null
          pendingTap.current = null
          // Require a fresh pointer-down; keep cooldown while residual pointers remain.
          armGestureCooldown()
        }
        return
      }

      if (panning.current) {
        panning.current = false
        panLast.current = null
        return
      }

      const tap = pendingTap.current
      if (tap && tap.pointerId === evt.pointerId) {
        pendingTap.current = null
        releaseCapture(evt.pointerId)
        // Only commit when this was a confirmed single-pointer interaction.
        if (
          e.type !== 'pointercancel' &&
          pointers.current.size === 0 &&
          !gestureMode.current &&
          !gestureCooldown.current
        ) {
          if (tap.tool === 'fill') applyFillAt(tap.x, tap.y)
          else sampleAt(tap.x, tap.y)
        }
        return
      }

      const decision = decidePointer(session(), {
        type: e.type === 'pointercancel' ? 'cancel' : 'up',
        pointerId: evt.pointerId,
        pointerType: evt.pointerType,
        button: evt.button,
        buttons: evt.buttons,
      })
      if (decision === 'end') finish(evt.pointerId)
    },
    [applyFillAt, armGestureCooldown, finish, releaseCapture, sampleAt, session],
  )

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const onWheel = (evt: WheelEvent) => {
      // Alt+wheel: brush size only (WEB-V4G) — never hijack ordinary scroll / pinch / zoom.
      if (evt.altKey) {
        if (!onBrushSize) return
        evt.preventDefault()
        evt.stopPropagation()
        const dir = evt.deltaY < 0 ? 1 : evt.deltaY > 0 ? -1 : 0
        if (!dir) return
        onBrushSize(snapBrushSizePx(brushSizeRef.current + dir * BRUSH_SIZE_STEP_PX))
        setWheelHint(true)
        if (wheelHintTimer.current) window.clearTimeout(wheelHintTimer.current)
        wheelHintTimer.current = window.setTimeout(() => setWheelHint(false), 700)
        return
      }

      // Immersive: Ctrl/Cmd + wheel zooms around the cursor. Ordinary wheel is left alone.
      if (immersive && (evt.ctrlKey || evt.metaKey) && onViewportChangeRef.current) {
        evt.preventDefault()
        evt.stopPropagation()
        const rect = host.getBoundingClientRect()
        const ax = evt.clientX - rect.left
        const ay = evt.clientY - rect.top
        const factor = evt.deltaY < 0 ? 1.08 : evt.deltaY > 0 ? 1 / 1.08 : 1
        if (factor === 1) return
        updateViewport(
          zoomAt(
            viewportRef.current,
            { width: size.w, height: size.h },
            viewportRef.current.scale * factor,
            ax,
            ay,
          ),
        )
      }
    }
    host.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      host.removeEventListener('wheel', onWheel)
      if (wheelHintTimer.current) window.clearTimeout(wheelHintTimer.current)
    }
  }, [immersive, onBrushSize, size.h, size.w, updateViewport])

  // Prevent page scroll while intentionally pinching on the immersive surface.
  useEffect(() => {
    const host = hostRef.current
    if (!host || !immersive) return
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length >= 2 || gestureMode.current) e.preventDefault()
    }
    host.addEventListener('touchmove', onTouchMove, { passive: false })
    return () => host.removeEventListener('touchmove', onTouchMove)
  }, [immersive])

  const all = draft ? [...strokes, draft] : strokes
  const inkTool = !panTool && (activeTool === 'draw' || activeTool === 'erase')
  // Space+drag pan uses a ref in handlers; cursor grab reflects the Hand tool only (avoid render-time refs).
  const cursor = panTool
    ? 'grab'
    : activeTool === 'fill'
      ? 'cell'
      : activeTool === 'eyedropper'
        ? 'crosshair'
        : 'none'
  const tipScreen = Math.max(2, brushSize * contentScale)
  const showBrushCursor = inkTool && hover && !draft

  const stageW = size.w
  const stageH = size.h
  const stageScaleX = immersive ? 1 : fitScale
  const stageScaleY = immersive ? 1 : fitScale

  const content = (
    <>
      <Layer listening={false} x={immersive ? panX : 0} y={immersive ? panY : 0} scaleX={immersive ? contentScale : 1} scaleY={immersive ? contentScale : 1}>
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
        {draft && draft.tool === 'erase'
          ? (() => {
              const data = strokeToSvgPath(draft)
              if (!data) return null
              return (
                <Path
                  key={`fill-erase-${draft.id}`}
                  data={data}
                  fill="#F8F4F0"
                  opacity={1}
                  globalCompositeOperation="destination-out"
                  listening={false}
                />
              )
            })()
          : null}
      </Layer>
      <Layer x={immersive ? panX : 0} y={immersive ? panY : 0} scaleX={immersive ? contentScale : 1} scaleY={immersive ? contentScale : 1}>
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
    </>
  )

  return (
    <div
      ref={hostRef}
      className={`${framed ? styles.host : styles.hostFlush} studio-draw-surface${immersive ? ` ${styles.hostImmersive}` : ''}`}
      style={{ cursor }}
      data-immersive={immersive ? 'true' : 'false'}
      data-testid="drawing-canvas-host"
    >
      <div
        ref={frameRef}
        className={framed ? styles.frame : styles.frameFlush}
        style={immersive ? { width: '100%', height: '100%' } : { width: size.w, height: size.h }}
        onPointerMove={(e) => {
          if (e.pointerType !== 'mouse') {
            setHover(null)
            return
          }
          const rect = e.currentTarget.getBoundingClientRect()
          setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top })
        }}
        onPointerLeave={() => setHover(null)}
      >
        <Stage
          width={stageW}
          height={stageH}
          scaleX={stageScaleX}
          scaleY={stageScaleY}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
        >
          {content}
        </Stage>
        {showBrushCursor ? (
          <div
            className={styles.brushCursor}
            style={{
              left: hover.x,
              top: hover.y,
              width: tipScreen,
              height: tipScreen,
              borderColor: activeTool === 'erase' ? 'rgba(107,114,128,0.95)' : 'rgba(214,51,132,0.9)',
            }}
            aria-hidden
          />
        ) : null}
        {wheelHint && hover ? (
          <div
            className={styles.sizeHint}
            style={{ left: hover.x + 14, top: hover.y + 14 }}
            aria-live="polite"
          >
            {formatBrushSizePx(brushSize)} px
          </div>
        ) : null}
      </div>
    </div>
  )
}
