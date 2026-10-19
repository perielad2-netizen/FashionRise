import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import type { ModelChoice } from '@/shell/modelTypes'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  documentFromEditorState,
  type SaveStatus,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  persistLocalRecovery,
  persistStudioDraft,
  restoreStudioDraft,
} from '@/lib/draftPersistence'
import { documentForCloud } from '@/services/designsApi'
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
const AUTOSAVE_MS = 1600
const CUSTOM_REF_BETA_NOTICE =
  'Custom reference images stay on this device for the session only in private beta. They are not uploaded to the server (uploads are not owner-private yet).'

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
  /** Last committed document snapshot — never rebuild saves from uncommitted React state. */
  const authoritativeDocRef = useRef<StudioDraftDocument>(createEmptyDraftDocument())
  const designIdRef = useRef<string | null>(null)
  const syncedRevisionRef = useRef<number | null>(null)
  const syncedFingerprintRef = useRef<string | null>(null)
  const localPersistedFpRef = useRef<string | null>(null)
  const saveTimerRef = useRef<number | null>(null)
  const saveChainRef = useRef<Promise<void>>(Promise.resolve())
  const cloudDirtyRef = useRef(false)
  const bootedRef = useRef(false)
  const skipNextAutosaveRef = useRef(true)
  const scheduleCloudSaveRef = useRef<() => void>(() => {})

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
    authoritativeDocRef.current = doc
    designIdRef.current = designId
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

  const flushCloudSave = useCallback(async () => {
    if (!user?.id || !bootedRef.current) return
    const doc = authoritativeDocRef.current
    const fingerprint = draftContentFingerprint(documentForCloud(doc))
    cloudDirtyRef.current = false

    const run = async () => {
      setSaveStatus((prev) => (prev === 'pending' ? 'pending' : 'saving'))
      setSaveError(null)
      const result = await persistStudioDraft({
        userId: user.id,
        designId: designIdRef.current,
        document: doc,
        fingerprint,
        lastSyncedFingerprint: syncedFingerprintRef.current,
        expectedRevision: syncedRevisionRef.current,
        skipLocalWrite: localPersistedFpRef.current === draftContentFingerprint(doc),
      })

      // A newer edit may have landed while this request was in flight.
      const stillCurrent =
        draftContentFingerprint(authoritativeDocRef.current) === draftContentFingerprint(doc)

      if (result.ok) {
        designIdRef.current = result.designId
        // Record what the server acknowledged for this request's document (even if stale).
        syncedRevisionRef.current = result.syncedRevision
        syncedFingerprintRef.current = result.fingerprint
        if (stillCurrent && !cloudDirtyRef.current) {
          setSaveStatus('saved')
          setSaveError(null)
        } else {
          // Newer local edits remain; keep honest status and schedule their cloud save.
          if (localPersistedFpRef.current === draftContentFingerprint(authoritativeDocRef.current)) {
            setSaveStatus('local-only')
          } else {
            setSaveStatus('pending')
          }
          if (!stillCurrent || cloudDirtyRef.current) {
            scheduleCloudSaveRef.current()
          }
        }
        return
      }

      if (result.conflict) {
        setDraftConflict(result.conflict)
        setSaveError(result.error)
        setSaveStatus(result.localPersisted ? 'local-only' : 'error')
        return
      }

      setSaveError(result.error)
      if (result.localPersisted && stillCurrent) {
        setSaveStatus('local-only')
      } else if (!stillCurrent) {
        setSaveStatus('pending')
      } else {
        setSaveStatus('error')
      }
    }

    saveChainRef.current = saveChainRef.current.then(run, run)
    await saveChainRef.current
  }, [user?.id])

  const scheduleCloudSave = useCallback(() => {
    if (!bootedRef.current || !user?.id) return
    cloudDirtyRef.current = true
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => {
      void flushCloudSave()
    }, AUTOSAVE_MS)
  }, [flushCloudSave, user?.id])

  scheduleCloudSaveRef.current = scheduleCloudSave

  /**
   * Commit an authoritative document snapshot: update the ref first, mirror to React,
   * durable local write, then debounce the API save from the ref only.
   */
  const commitDocument = useCallback(
    async (doc: StudioDraftDocument, options?: { syncCloudImmediately?: boolean }) => {
      authoritativeDocRef.current = doc
      if (!user?.id || !bootedRef.current) return

      setSaveStatus('pending')
      setSaveError(null)
      const local = await persistLocalRecovery({
        userId: user.id,
        designId: designIdRef.current,
        document: doc,
        syncedRevision: syncedRevisionRef.current,
      })
      if (!local.ok) {
        setSaveError(local.error)
        setSaveStatus('error')
      } else {
        localPersistedFpRef.current = draftContentFingerprint(doc)
        setSaveStatus('local-only')
      }

      if (options?.syncCloudImmediately) {
        if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
        await flushCloudSave()
      } else {
        scheduleCloudSave()
      }
    },
    [flushCloudSave, scheduleCloudSave, user?.id],
  )

  const commitFromEditor = useCallback(
    (patch: {
      strokes?: Stroke[]
      model?: ModelChoice
      customReferenceUrl?: string | null
      customReferenceKey?: string | null
      sizeId?: BrushSizeId
      opacity?: number
      color?: string
      dimmed?: boolean
    }) => {
      const prev = authoritativeDocRef.current
      const next = documentFromEditorState({
        prev,
        strokes: patch.strokes ?? prev.strokes,
        model: patch.model ?? prev.model,
        customReferenceUrl:
          patch.customReferenceUrl !== undefined ? patch.customReferenceUrl : prev.customReferenceUrl,
        customReferenceKey:
          patch.customReferenceKey !== undefined ? patch.customReferenceKey : prev.customReferenceKey,
        sizeId: patch.sizeId ?? prev.brush.sizeId,
        opacity: patch.opacity ?? prev.brush.opacity,
        color: patch.color ?? prev.brush.color,
        dimmed: patch.dimmed ?? prev.dimmed,
      })
      void commitDocument(next)
      return next
    },
    [commitDocument],
  )

  useEffect(() => {
    if (!user?.id) return
    let cancelled = false
    ;(async () => {
      setSaveStatus('restoring')
      const restored = await restoreStudioDraft(user.id)
      if (cancelled) return

      // Authoritative ref BEFORE React state — any immediate flush uses this snapshot.
      authoritativeDocRef.current = restored.conflict
        ? restored.conflict.local
        : restored.document
      designIdRef.current = restored.designId
      syncedRevisionRef.current = restored.syncedRevision
      if (restored.syncedRevision != null && !restored.conflict) {
        syncedFingerprintRef.current = draftContentFingerprint(
          documentForCloud(restored.document),
        )
      }

      if (restored.conflict) {
        setDraftConflict(restored.conflict)
        applyDocument(restored.conflict.local, restored.conflict.designId)
        setSaveStatus('local-only')
      } else {
        applyDocument(restored.document, restored.designId)
        setSaveStatus(restored.designId ? 'saved' : 'idle')
      }
      if (restored.notice) setStudioNotice(restored.notice)

      bootedRef.current = true
      setReady(true)

      const needsSync =
        restored.conflict === null &&
        (restored.designId === null
          ? restored.document.strokes.length > 0
          : restored.notice?.includes('Syncing') === true)
      if (needsSync) {
        void flushCloudSave()
      }
    })()
    return () => {
      cancelled = true
    }
    // Intentionally boot once per user session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  // Mirror React brush/model edits into the authoritative snapshot after the boot skip.
  useEffect(() => {
    if (!ready) return
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false
      return
    }
    const prev = authoritativeDocRef.current
    const next = documentFromEditorState({
      prev,
      strokes,
      model,
      customReferenceUrl: customUrl,
      customReferenceKey: customKey,
      sizeId,
      opacity,
      color,
      dimmed,
    })
    if (draftContentFingerprint(prev) === draftContentFingerprint(next)) return
    void commitDocument(next)
  }, [strokes, model, customUrl, customKey, sizeId, opacity, color, dimmed, ready, commitDocument])

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

  const onStrokeComplete = useCallback(
    (stroke: Stroke) => {
      history.current.push(strokes)
      const nextStrokes = [...strokes, stroke]
      setStrokes(nextStrokes)
      syncHistoryFlags()
      // Effect will commit; also commit immediately for stroke durability before debounce.
      commitFromEditor({ strokes: nextStrokes })
    },
    [commitFromEditor, strokes, syncHistoryFlags],
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

  const commitModelChange = useCallback(
    (next: ModelChoice, clearStrokes: boolean) => {
      if (clearStrokes && strokes.length > 0) {
        history.current.push(strokes)
        setStrokes([])
        syncHistoryFlags()
        setModelState(next)
        commitFromEditor({ model: next, strokes: [] })
      } else {
        setModelState(next)
      }
      setModelSwitchPrompt(null)
    },
    [commitFromEditor, strokes, syncHistoryFlags],
  )

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

      if (blobUrl) URL.revokeObjectURL(blobUrl)
      const url = URL.createObjectURL(file)
      setBlobUrl(url)
      // Persistent uploads disabled for private beta — /static/uploads is not owner-private.
      setCustomUrl(null)
      setCustomKey(null)
      setStudioNotice(CUSTOM_REF_BETA_NOTICE)

      if (strokes.length > 0) {
        setModelSwitchPrompt({ next: 'custom' })
      } else {
        setModelState('custom')
        commitFromEditor({
          model: 'custom',
          customReferenceUrl: null,
          customReferenceKey: null,
        })
      }
    },
    [blobUrl, commitFromEditor, strokes.length],
  )

  const onMagic = useCallback(() => {
    setMagicNotice(MAGIC_NOTICE)
  }, [])

  const onLogout = useCallback(() => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    if (cloudDirtyRef.current || saveStatus === 'pending' || saveStatus === 'local-only') {
      void flushCloudSave()
    }
    logout()
    navigate('/login', { replace: true })
  }, [flushCloudSave, logout, navigate, saveStatus])

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
    const local = draftConflict.local
    const designId = draftConflict.designId
    // Explicit operator choice: overwrite cloud using the server's current revision as the token.
    syncedRevisionRef.current = draftConflict.server.clientRevision
    syncedFingerprintRef.current = null
    authoritativeDocRef.current = local
    designIdRef.current = designId
    applyDocument(local, designId)
    setDraftConflict(null)
    void commitDocument(local, { syncCloudImmediately: true })
  }, [applyDocument, commitDocument, draftConflict])

  const resolveConflictUseServer = useCallback(() => {
    if (!draftConflict) return
    const server = draftConflict.server
    const designId = draftConflict.designId
    authoritativeDocRef.current = server
    designIdRef.current = designId
    syncedRevisionRef.current = server.clientRevision
    syncedFingerprintRef.current = draftContentFingerprint(documentForCloud(server))
    applyDocument(server, designId)
    setDraftConflict(null)
    setSaveStatus('saved')
    if (user?.id) {
      void persistLocalRecovery({
        userId: user.id,
        designId,
        document: server,
        syncedRevision: server.clientRevision,
      })
    }
  }, [applyDocument, draftConflict, user?.id])

  const saveStatusLabel = useMemo(() => {
    switch (saveStatus) {
      case 'restoring':
        return 'Restoring draft…'
      case 'pending':
        return 'Saving on this device…'
      case 'saving':
        return 'Saving…'
      case 'saved':
        return 'Saved'
      case 'error':
        return 'Save failed'
      case 'local-only':
        return 'Saved on this device'
      case 'idle':
        return 'Ready'
      default:
        return 'Ready'
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
    retrySave: flushCloudSave,
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
