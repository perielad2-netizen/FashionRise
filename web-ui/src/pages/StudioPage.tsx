import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import { ModelPanel, type ModelChoice } from '@/components/studio/ModelPanel'
import { StudioHeader } from '@/components/studio/StudioHeader'
import { StudioInspector } from '@/components/studio/StudioInspector'
import { ToolRail } from '@/components/studio/ToolRail'
import { StrokeHistory } from '@/lib/history'
import { validateReferenceImageFile } from '@/lib/referenceFile'
import {
  BRUSH_SIZES,
  INK_SWATCHES,
  type BrushSizeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './StudioPage.module.css'

const FEMALE_URL = '/models/female_model.png'
const MALE_URL = '/models/male_model.png'

export function StudioPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const history = useRef(new StrokeHistory())
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [sizeId, setSizeId] = useState<BrushSizeId>('medium')
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [model, setModel] = useState<ModelChoice>('female')
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [isNarrow, setIsNarrow] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 900px)')
    const apply = () => setIsNarrow(mq.matches)
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    return () => {
      if (customUrl) URL.revokeObjectURL(customUrl)
    }
  }, [customUrl])

  const syncHistoryFlags = useCallback(() => {
    setCanUndo(history.current.canUndo())
    setCanRedo(history.current.canRedo())
  }, [])

  const referenceUrl = useMemo(() => {
    switch (model) {
      case 'female':
        return FEMALE_URL
      case 'male':
        return MALE_URL
      case 'custom':
        return customUrl
      case 'blank':
        return null
    }
  }, [model, customUrl])

  const referenceOpacity = dimmed ? 0.4 : 1

  const onStrokeComplete = useCallback(
    (stroke: Stroke) => {
      history.current.push(strokes)
      setStrokes((prev) => [...prev, stroke])
      syncHistoryFlags()
    },
    [strokes, syncHistoryFlags],
  )

  const undo = useCallback(() => {
    const prev = history.current.undo(strokes)
    if (!prev) return
    setStrokes(prev)
    syncHistoryFlags()
  }, [strokes, syncHistoryFlags])

  const redo = useCallback(() => {
    const next = history.current.redo(strokes)
    if (!next) return
    setStrokes(next)
    syncHistoryFlags()
  }, [strokes, syncHistoryFlags])

  const clear = useCallback(() => {
    if (strokes.length === 0) return
    history.current.push(strokes)
    setStrokes([])
    syncHistoryFlags()
  }, [strokes, syncHistoryFlags])

  const onCustomFile = useCallback(
    (file: File) => {
      const validated = validateReferenceImageFile(file)
      if (!validated.ok) {
        setStudioNotice(validated.message)
        return
      }
      if (customUrl) URL.revokeObjectURL(customUrl)
      const url = URL.createObjectURL(file)
      setCustomUrl(url)
      setModel('custom')
      setStudioNotice(null)
    },
    [customUrl],
  )

  const onMagic = useCallback(() => {
    setMagicNotice('Magic integration coming in the next milestone.')
  }, [])

  const onLogout = useCallback(() => {
    logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  return (
    <div className={`${styles.page} studio-chrome`}>
      <StudioHeader
        username={user?.username ?? 'Creator'}
        savedLabel="Local draft"
        onMagic={onMagic}
        onLogout={onLogout}
      />

      <div className={isNarrow ? styles.bodyNarrow : styles.body}>
        <ModelPanel
          selected={model}
          customPreviewUrl={customUrl}
          onSelect={setModel}
          onCustomFile={onCustomFile}
        />

        {!isNarrow ? (
          <ToolRail
            tool={tool}
            canUndo={canUndo}
            canRedo={canRedo}
            onTool={setTool}
            onUndo={undo}
            onRedo={redo}
            onClear={clear}
          />
        ) : null}

        <div className={styles.canvasCol}>
          <DrawingCanvas
            strokes={strokes}
            activeTool={tool}
            brushColor={color}
            brushSize={BRUSH_SIZES[sizeId]}
            referenceUrl={referenceUrl}
            referenceOpacity={referenceOpacity}
            onStrokeComplete={onStrokeComplete}
          />
          {isNarrow ? (
            <ToolRail
              tool={tool}
              canUndo={canUndo}
              canRedo={canRedo}
              onTool={setTool}
              onUndo={undo}
              onRedo={redo}
              onClear={clear}
              orientation="horizontal"
            />
          ) : null}
        </div>

        <StudioInspector
          sizeId={sizeId}
          color={color}
          dimmed={dimmed}
          studioNotice={studioNotice}
          magicNotice={magicNotice}
          onSize={setSizeId}
          onColor={setColor}
          onToggleDim={() => setDimmed((v) => !v)}
          onMagic={onMagic}
          onDismissStudioNotice={() => setStudioNotice(null)}
          onDismissMagic={() => setMagicNotice(null)}
        />
      </div>
    </div>
  )
}
