import { useMemo, useState } from 'react'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import type { StudioEditor } from '@/hooks/useStudioEditor'
import { solidStyle } from '@/lib/fills'
import { DEFAULT_MODEL } from '@/assets/modelLibrary'
import {
  BRUSH_SIZES,
  INK_SWATCHES,
  type BrushSizeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import '@/shell/shellTokens.css'

/**
 * DEV-only harness that mounts the real shell CreatorWorkspace + DrawingWorkspace
 * with a local mock editor (no auth / backend). Used for tablet Focus + materials QA.
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

function useLayoutLabEditor(): StudioEditor {
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [fills, setFills] = useState<StudioEditor['fills']>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [sizeId, setSizeId] = useState<BrushSizeId>('medium')
  const [opacity, setOpacity] = useState(0.92)
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [fillStyle, setFillStyle] = useState(solidStyle(INK_SWATCHES[0]!.color))
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [comingSoon, setComingSoon] = useState<string | null>(null)

  const brushSize = BRUSH_SIZES[sizeId]

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
      setSizeId,
      brushSize,
      setBrushSizePx: (px: number) => {
        const nearest = (Object.entries(BRUSH_SIZES) as [BrushSizeId, number][]).reduce(
          (best, cur) => (Math.abs(cur[1] - px) < Math.abs(best[1] - px) ? cur : best),
        )
        setSizeId(nearest[0])
      },
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
      referenceUrl: null,
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
