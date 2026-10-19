import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import type { ModelChoice } from '@/shell/modelTypes'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  type SaveStatus,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  documentFromEditorState,
  persistStudioDraft,
  restoreStudioDraft,
} from '@/lib/draftPersistence'
import { writeLocalDraft } from '@/lib/localDraftStore'
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
import { uploadReferenceImage } from '@/services/uploadsApi'
import { ApiError } from '@/services/api/client'

const FEMALE_URL = UI_ASSETS.canvas.female
const MALE_URL = UI_ASSETS.canvas.male
const MAGIC_NOTICE = 'AI enhancement will be available in a later milestone.'
const AUTOSAVE_MS = 1600

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

export type ModelSwitchPrompt = {
  next: ModelChoice
}

export type DraftConflictPrompt = {
  local: StudioDraftDocument
  server: StudioDraftDocument
  designId: string
}

export function useStudioEditor() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const history = useRef(new StrokeHistory())
  const draftBaseRef = useRef<StudioDraftDocument>(createEmptyDraftDocument())
  const designIdRef = useRef<string | null>(null)
  const fingerprintRef = useRef<string | null>(null)
  const saveTimerRef = useRef<number | null>(null)
  const saveChainRef = useRef<Promise<void>>(Promise.resolve())
  const dirtyRef = useRef(false)
  const bootedRef = useRef(false)

  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [sizeId, setSizeId] = useState<BrushSizeId>('thin')
  const [opacity, setOpacity] = useState(1)
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [model, setModelState] = useState<ModelChoice>('female')
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [customKey, setCustomKey] = useState<string | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [comingSoon, setComingSoon] = useState<string | null>(null)
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('restoring')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [modelSwitchPrompt, setModelSwitchPrompt] = useState<ModelSwitchPrompt | null>(null)
  const [draftConflict, setDraftConflict] = useState<DraftConflictPrompt | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [blobUrl])

  const syncHistoryFlags = useCallback(() => {
    setCanUndo(history.current.canUndo())
    setCanRedo(history.current.canRedo())
  }, [])

  const applyDocument = useCallback((doc: StudioDraftDocument, designId: string | null) => {
    draftBaseRef.current = doc
    designIdRef.current = designId
    fingerprintRef.current = draftContentFingerprint(doc)
    history.current = new StrokeHistory()
    setStrokes(doc.strokes)
    setModelState(doc.model)
    setCustomUrl(doc.customReferenceUrl)
    setCustomKey(doc.customReferenceKey)
    setSizeId(doc.brush.sizeId)
    setOpacity(doc.brush.opacity)
    setColor(doc.brush.color)
    setDimmed(doc.dimmed)
    setCanUndo(false)
    setCanRedo(false)
    setBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
  }, [])

  const buildDocument = useCallback((): StudioDraftDocument => {
    return documentFromEditorState({
      prev: draftBaseRef.current,
      strokes,
      model,
      customReferenceUrl: customUrl,
      customReferenceKey: customKey,
      sizeId,
      opacity,
      color,
      dimmed,
    })
  }, [strokes, model, customUrl, customKey, sizeId, opacity, color, dimmed])

  const flushSave = useCallback(async () => {
    if (!user?.id || !bootedRef.current) return
    const doc = buildDocument()
    draftBaseRef.current = doc
    dirtyRef.current = false

    const run = async () => {
      setSaveStatus('saving')
      setSaveError(null)
      try {
        await writeLocalDraft({
          userId: user.id,
          designId: designIdRef.current,
          document: doc,
          savedAt: new Date().toISOString(),
        })
        const result = await persistStudioDraft({
          userId: user.id,
          designId: designIdRef.current,
          document: doc,
          lastFingerprint: fingerprintRef.current,
        })
        designIdRef.current = result.designId
        fingerprintRef.current = result.fingerprint
        draftBaseRef.current = result.document
        setSaveStatus('saved')
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : 'Save failed. Your latest edits are kept on this device.'
        setSaveError(message)
        setSaveStatus(designIdRef.current ? 'error' : 'local-only')
      }
    }

    saveChainRef.current = saveChainRef.current.then(run, run)
    await saveChainRef.current
  }, [buildDocument, user?.id])

  const scheduleSave = useCallback(() => {
    if (!bootedRef.current || !user?.id) return
    dirtyRef.current = true
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    setSaveStatus((prev) => (prev === 'saving' || prev === 'restoring' ? prev : 'idle'))
    saveTimerRef.current = window.setTimeout(() => {
      void flushSave()
    }, AUTOSAVE_MS)
  }, [flushSave, user?.id])

  useEffect(() => {
    if (!user?.id) return
    let cancelled = false
    ;(async () => {
      setSaveStatus('restoring')
      const restored = await restoreStudioDraft(user.id)
      if (cancelled) return
      if (restored.conflict) {
        setDraftConflict(restored.conflict)
        applyDocument(restored.conflict.local, restored.conflict.designId)
      } else {
        applyDocument(restored.document, restored.designId)
      }
      if (restored.notice) setStudioNotice(restored.notice)
      bootedRef.current = true
      setReady(true)
      setSaveStatus(restored.designId ? 'saved' : 'idle')
      if (restored.conflict === null && restored.designId === null && restored.document.strokes.length > 0) {
        void flushSave()
      } else if (restored.conflict === null && restored.notice?.includes('Syncing')) {
        void flushSave()
      }
    })()
    return () => {
      cancelled = true
    }
    // Intentionally boot once per user session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  const skipNextAutosaveRef = useRef(true)
  useEffect(() => {
    if (!ready) return
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false
      return
    }
    scheduleSave()
  }, [strokes, model, customUrl, customKey, sizeId, opacity, color, dimmed, ready, scheduleSave])

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    }
  }, [])

  const brushSize = BRUSH_SIZES[sizeId]

  const referenceUrl = useMemo(() => {
    switch (model) {
      case 'female':
        return FEMALE_URL
      case 'male':
        return MALE_URL
      case 'custom':
        return blobUrl ?? customUrl
      case 'blank':
        return null
    }
  }, [model, customUrl, blobUrl])

  const referenceOpacity = dimmed ? 0.4 : 1

  useEffect(() => {
    if (model !== 'custom') return
    const url = blobUrl ?? customUrl
    if (!url || url.startsWith('blob:')) return
    let cancelled = false
    const img = new window.Image()
    img.onload = () => {
      if (!cancelled) setStudioNotice((prev) =>
        prev?.includes('could not be loaded') ? null : prev,
      )
    }
    img.onerror = () => {
      if (cancelled) return
      setStudioNotice(
        'Custom reference image could not be loaded. Your strokes are safe; choose another reference or re-upload.',
      )
    }
    img.src = url
    return () => {
      cancelled = true
    }
  }, [model, customUrl, blobUrl])

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

  const commitModelChange = useCallback((next: ModelChoice, clearStrokes: boolean) => {
    if (clearStrokes && strokes.length > 0) {
      history.current.push(strokes)
      setStrokes([])
      syncHistoryFlags()
    }
    setModelState(next)
    setModelSwitchPrompt(null)
  }, [strokes, syncHistoryFlags])

  const requestModelChange = useCallback(
    (next: ModelChoice) => {
      if (next === model) return
      if (strokes.length > 0) {
        setModelSwitchPrompt({ next })
        return
      }
      setModelState(next)
    },
    [model, strokes.length],
  )

  const onCustomFile = useCallback(
    async (file: File) => {
      const validated = validateReferenceImageFile(file)
      if (!validated.ok) {
        setStudioNotice(validated.message)
        return
      }

      const applyLocalPreview = () => {
        if (blobUrl) URL.revokeObjectURL(blobUrl)
        const url = URL.createObjectURL(file)
        setBlobUrl(url)
      }

      const switchToCustom = () => {
        if (strokes.length > 0) {
          setModelSwitchPrompt({ next: 'custom' })
        } else {
          setModelState('custom')
        }
      }

      applyLocalPreview()
      setStudioNotice('Uploading custom reference…')
      try {
        const uploaded = await uploadReferenceImage(file)
        setCustomUrl(uploaded.url)
        setCustomKey(uploaded.stored_key)
        setStudioNotice('Custom reference uploaded to your private library.')
        switchToCustom()
      } catch (err) {
        setCustomUrl(null)
        setCustomKey(null)
        const message =
          err instanceof ApiError
            ? `${err.message} Preview is local-only until upload succeeds.`
            : 'Upload failed. Preview is local-only for this session.'
        setStudioNotice(message)
        switchToCustom()
      }
    },
    [blobUrl, strokes.length],
  )

  const onMagic = useCallback(() => {
    setMagicNotice(MAGIC_NOTICE)
  }, [])

  const onLogout = useCallback(() => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    if (dirtyRef.current) void flushSave()
    logout()
    navigate('/login', { replace: true })
  }, [flushSave, logout, navigate])

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

  const resolveConflictKeepLocal = useCallback(() => {
    if (!draftConflict) return
    applyDocument(draftConflict.local, draftConflict.designId)
    setDraftConflict(null)
    void flushSave()
  }, [applyDocument, draftConflict, flushSave])

  const resolveConflictUseServer = useCallback(() => {
    if (!draftConflict) return
    applyDocument(draftConflict.server, draftConflict.designId)
    setDraftConflict(null)
    setSaveStatus('saved')
  }, [applyDocument, draftConflict])

  const saveStatusLabel = useMemo(() => {
    switch (saveStatus) {
      case 'restoring':
        return 'Restoring draft…'
      case 'saving':
        return 'Saving…'
      case 'saved':
        return 'Saved'
      case 'error':
        return 'Save failed'
      case 'local-only':
        return 'Saved on this device'
      default:
        return dirtyRef.current ? 'Unsaved changes' : 'Ready'
    }
  }, [saveStatus])

  return {
    user,
    ready,
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
    setModel: requestModelChange,
    customUrl: blobUrl ?? customUrl,
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
    saveStatus,
    saveStatusLabel,
    saveError,
    retrySave: flushSave,
    modelSwitchPrompt,
    confirmModelKeepStrokes: () =>
      modelSwitchPrompt ? commitModelChange(modelSwitchPrompt.next, false) : undefined,
    confirmModelClearStrokes: () =>
      modelSwitchPrompt ? commitModelChange(modelSwitchPrompt.next, true) : undefined,
    cancelModelSwitch: () => setModelSwitchPrompt(null),
    draftConflict,
    resolveConflictKeepLocal,
    resolveConflictUseServer,
  }
}

export type StudioEditor = ReturnType<typeof useStudioEditor>
