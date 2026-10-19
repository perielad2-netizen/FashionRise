import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import type { ModelChoice } from '@/shell/modelTypes'
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

const FEMALE_URL = UI_ASSETS.canvas.female
const MALE_URL = UI_ASSETS.canvas.male

const MAGIC_NOTICE = 'AI enhancement will be available in a later milestone.'

export function nearestBrushSizeId(px: number): BrushSizeId {
  const entries = Object.entries(BRUSH_SIZES) as [BrushSizeId, number][]
  let best: BrushSizeId = 'medium'
  let bestDist = Number.POSITIVE_INFINITY
  for (const [id, size] of entries) {
    const dist = Math.abs(size - px)
    if (dist < bestDist) {
      best = id
      bestDist = dist
    }
  }
  return best
}

export function useStudioEditor() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const history = useRef(new StrokeHistory())
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [sizeId, setSizeId] = useState<BrushSizeId>('thin')
  const [opacity, setOpacity] = useState(1)
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [model, setModel] = useState<ModelChoice>('female')
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [comingSoon, setComingSoon] = useState<string | null>(null)
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)

  useEffect(() => {
    return () => {
      if (customUrl) URL.revokeObjectURL(customUrl)
    }
  }, [customUrl])

  const syncHistoryFlags = useCallback(() => {
    setCanUndo(history.current.canUndo())
    setCanRedo(history.current.canRedo())
  }, [])

  const brushSize = BRUSH_SIZES[sizeId]

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
    setMagicNotice(MAGIC_NOTICE)
  }, [])

  const onLogout = useCallback(() => {
    logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  const setBrushSizePx = useCallback((px: number) => {
    setSizeId(nearestBrushSizeId(px))
  }, [])

  const setBrushOpacity = useCallback((value: number) => {
    const clamped = Math.min(1, Math.max(0.05, value))
    setOpacity(clamped)
  }, [])

  const setColorHex = useCallback((raw: string) => {
    const hex = raw.trim()
    if (!/^#([0-9a-fA-F]{6})$/.test(hex)) return false
    setColor(hex.toUpperCase())
    return true
  }, [])

  const showComingSoon = useCallback((label: string) => {
    setComingSoon(`${label} — coming later`)
  }, [])

  return {
    user,
    strokes,
    tool,
    setTool,
    sizeId,
    setSizeId,
    brushSize,
    setBrushSizePx,
    opacity,
    setBrushOpacity,
    color,
    setColor,
    setColorHex,
    model,
    setModel,
    customUrl,
    onCustomFile,
    dimmed,
    setDimmed,
    referenceUrl,
    referenceOpacity,
    onStrokeComplete,
    undo,
    redo,
    clear,
    canUndo,
    canRedo,
    onMagic,
    onLogout,
    magicNotice,
    setMagicNotice,
    studioNotice,
    setStudioNotice,
    comingSoon,
    setComingSoon,
    showComingSoon,
    magicNoticeText: MAGIC_NOTICE,
  }
}

export type StudioEditor = ReturnType<typeof useStudioEditor>
