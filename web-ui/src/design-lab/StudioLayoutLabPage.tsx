import { useEffect, useMemo, useState } from 'react'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import type { StudioEditor } from '@/hooks/useStudioEditor'
import { customGradientStyle, solidStyle, type FillStyle } from '@/lib/fills'
import { floodFillRegion } from '@/lib/floodFill'
import { canvasSrcForModel, DEFAULT_MODEL } from '@/assets/modelLibrary'
import {
  BRUSH_SIZES,
  INK_SWATCHES,
  nearestBrushSizeId,
  snapBrushSizePx,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import '@/shell/shellTokens.css'

/**
 * DEV-only harness that mounts the real shell CreatorWorkspace + DrawingWorkspace
 * with a local mock editor (no auth / backend). Used for tablet layout + materials QA.
 *
 * Query `?v4gCustomFill=1` seeds a deterministic closed outline + custom gradient fill
 * for visual acceptance screenshots (no paid Magic).
 */
export function StudioLayoutLabPage() {
  const editor = useLayoutLabEditor()
  return (
    <div
      className="studioShellRoot studio-chrome"
      style={{ height: '100dvh', display: 'flex', flexDirection: 'column' }}
      data-testid="studio-layout-lab"
    >
      <CreatorWorkspace editor={editor} />
    </div>
  )
}

/** Flattened freehand points: [x, y, pressure, ...] (stride 3 — required by strokeToSvgPath). */
function denseEdge(x0: number, y0: number, x1: number, y1: number, steps = 64): number[] {
  const pts: number[] = []
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps
    pts.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0.5)
  }
  return pts
}

/**
 * Deterministic closed rectangle far from paper edges (design 768×1024).
 * One continuous freehand loop with start/end overlap seals perfect-freehand taper.
 */
function closedRectStrokes(): Stroke[] {
  const x0 = 220
  const y0 = 280
  const x1 = 540
  const y1 = 720
  const ink = { color: '#1C1C1E', size: 6, opacity: 1 } as const
  const loopPts = [
    ...denseEdge(x0, y0, x1, y0, 80).slice(0, -3),
    ...denseEdge(x1, y0, x1, y1, 80).slice(0, -3),
    ...denseEdge(x1, y1, x0, y1, 80).slice(0, -3),
    ...denseEdge(x0, y1, x0, y0, 80),
    // Overlap past the start so freehand end taper does not open a corner leak.
    ...denseEdge(x0, y0, x0 + 48, y0, 16).slice(3),
  ]
  return [{ id: 'v4g-closed-rect', tool: 'draw', points: loopPts, ...ink }]
}

function useLayoutLabEditor(): StudioEditor {
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [fills, setFills] = useState<StudioEditor['fills']>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [brushSize, setBrushSize] = useState(BRUSH_SIZES.medium)
  const [opacity, setOpacity] = useState(0.92)
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [fillStyle, setFillStyle] = useState<FillStyle>(solidStyle(INK_SWATCHES[0]!.color))
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [comingSoon, setComingSoon] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (params.get('v4gCustomFill') !== '1') return
    const outline = closedRectStrokes()
    const style = customGradientStyle(['#FF2D8A', '#0F172A'], 45)
    if (!style) return
    // Real Studio flood-fill against freehand ink (no contour stub). Prior failure was
    // fixture points missing pressure triples — not the mature flood-fill algorithm.
    const result = floodFillRegion({
      strokes: outline,
      x: 380,
      y: 500,
      style,
      gapClose: 3,
    })
    setStrokes(outline)
    setFillStyle(style)
    setTool('fill')
    if (result.ok) {
      setFills([result.fill])
      setStudioNotice(null)
    } else {
      setFills([])
      setStudioNotice(`V4G custom-gradient seed flood-fill failed: ${result.message}`)
    }
  }, [])

  const sizeId = nearestBrushSizeId(brushSize)

  return useMemo(() => {
    const noop = () => undefined
    const editor = {
      user: { id: 'lab', username: 'LayoutLab' },
      ready: true,
      strokes,
      fills,
      tool,
      setTool,
      sizeId,
      setSizeId: (id: keyof typeof BRUSH_SIZES) => setBrushSize(BRUSH_SIZES[id]),
      brushSize,
      setBrushSizePx: (px: number) => setBrushSize(snapBrushSizePx(px)),
      nudgeBrushSizePx: (steps: number) =>
        setBrushSize((prev) => snapBrushSizePx(prev + steps * 0.25)),
      opacity,
      setBrushOpacity: setOpacity,
      color,
      setColor: (next: string) => {
        setColor(next)
        setFillStyle(solidStyle(next))
      },
      setColorHex: (raw: string) => {
        const hex = raw.trim().toUpperCase()
        if (!/^#[0-9A-F]{6}$/.test(hex)) return false
        setColor(hex)
        setFillStyle(solidStyle(hex))
        return true
      },
      fillStyle,
      setFillStyle: (style: typeof fillStyle) => {
        setFillStyle(style)
        if (style.kind === 'solid') setColor(style.color)
        else setTool('fill')
      },
      model,
      setModel: (next: typeof model) => setModel(next),
      customUrl: null,
      onCustomFile: noop,
      dimmed,
      setDimmed,
      // Real croquis artwork for immersive paper/garment measurement QA (mocked editor; no AI).
      referenceUrl: canvasSrcForModel(model),
      referenceOpacity: dimmed ? 0.35 : 0.55,
      onStrokeComplete: (stroke: Stroke) => setStrokes((prev) => [...prev, stroke]),
      onFillComplete: (fill: (typeof fills)[number]) => setFills((prev) => [...prev, fill]),
      onFillError: (message: string) => setStudioNotice(message),
      onEyedropperSample: (sampled: string) => {
        setColor(sampled)
        setFillStyle(solidStyle(sampled))
      },
      undo: () => setStrokes((prev) => prev.slice(0, -1)),
      redo: noop,
      clear: () => {
        setStrokes([])
        setFills([])
      },
      canUndo: strokes.length > 0,
      canRedo: false,
      onMagic: noop,
      onLogout: noop,
      magicNotice,
      setMagicNotice,
      magicEnabled: false,
      magicOpen: false,
      magicPhase: 'idle' as const,
      magicBusy: false,
      magicResult: null,
      magicError: null,
      magicLookUrl: null,
      magicSketchUrl: null,
      magicCanRecover: false,
      closeMagicPanel: noop,
      cancelMagicWait: noop,
      recoverLastMagic: noop,
      downloadMagicLook: noop,
      backToSketchFromMagic: noop,
      studioNotice,
      setStudioNotice,
      publishStudioNotice: setStudioNotice,
      comingSoon,
      setComingSoon,
      showComingSoon: setComingSoon,
      magicNoticeText: '',
      saveStatus: 'idle' as const,
      saveStatusLabel: 'Ready',
      saveError: null,
      retrySave: noop,
      modelSwitchPrompt: null,
      confirmModelKeepStrokes: noop,
      confirmModelClearStrokes: noop,
      cancelModelSwitch: noop,
      draftConflict: null,
      resolveConflictKeepLocal: noop,
      resolveConflictUseServer: noop,
      exporting: false,
      exportPng: async () => undefined,
      saveDesignDialog: null,
      beginSaveDesign: noop,
      confirmSaveDesign: async () => undefined,
      cancelSaveDesign: noop,
      libraryVersion: 0,
      openDesign: null,
      requestOpenDesign: async () => undefined,
      confirmOpenDesign: noop,
      retryOpenDesign: noop,
      cancelOpenDesign: noop,
    }
    return editor as unknown as StudioEditor
  }, [
    brushSize,
    color,
    comingSoon,
    dimmed,
    fillStyle,
    fills,
    magicNotice,
    model,
    opacity,
    sizeId,
    strokes,
    studioNotice,
    tool,
  ])
}
