import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEFAULT_MODEL, canvasSrcForModel, type ModelChoice } from '@/assets/modelLibrary'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  documentFromEditorState,
  rebaseChosenLocalDraft,
  type SaveStatus,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  commitKeepDeviceChoice,
  commitUseCloudChoice,
  persistLocalRecovery,
  persistStudioDraft,
  restoreStudioDraft,
} from '@/lib/draftPersistence'
import { documentForCloud } from '@/services/designsApi'
import { isMagicUiEnabled } from '@/config/magicUi'
import { downloadBlob, exportFilename, exportSketchPng } from '@/lib/exportCanvas'
import { FabricAssetLoadError } from '@/lib/fabricAssetCache'
import { checkPersistableFill, solidStyle, type FillOp, type FillStyle } from '@/lib/fills'
import { MAX_SNAPSHOT_FILLS } from '@/lib/savedDesign'
import { captureSketchForMagic } from '@/lib/sketchCapture'
import {
  createSaveRequestId,
  defaultDesignTitle,
  snapshotFromDocument,
  validateDesignTitle,
  workingDocumentFromSnapshot,
  type SavedDesignRecord,
  type SavedDesignSnapshot,
} from '@/lib/savedDesign'
import { fetchSavedDesign, saveDesignSnapshot } from '@/services/savedDesignsApi'
import { ApiError } from '@/services/api/client'
import { enqueueSketchPolish, fetchJobImageBlob } from '@/services/ai/magicApi'
import { persistMagicJobId, readMagicJobId } from '@/services/ai/magicJobStore'
import { pollAiJobUntilSettled, recoverMagicJob } from '@/services/ai/pollAiJob'
import { toMagicLookResult, type MagicLookResult } from '@/services/ai/aiJobTypes'
import { StrokeHistory } from '@/lib/history'
import { validateReferenceImageFile } from '@/lib/referenceFile'
import {
  BRUSH_SIZE_DEFAULT_PX,
  BRUSH_SIZES,
  INK_SWATCHES,
  nearestBrushSizeId,
  resolveBrushSizePx,
  snapBrushSizePx,
  type BrushSizeId,
  type Stroke,
  type ToolKind,
} from '@/lib/strokes'
import { useAuth } from '@/services/auth/AuthProvider'
import type { MagicPhase } from '@/shell/components/MagicLookPanel'

const MAGIC_NOTICE = 'AI enhancement will be available in a later milestone.'
const AUTOSAVE_MS = 1600
const CUSTOM_REF_BETA_NOTICE =
  'Custom reference images stay on this device for the session only in private beta. They are not uploaded to the server (uploads are not owner-private yet).'

export { nearestBrushSizeId }

export type ModelSwitchPrompt = {
  next: ModelChoice
}

export type DraftConflictPrompt = {
  local: StudioDraftDocument
  server: StudioDraftDocument
  designId: string
}

export type SaveDesignDialogState = {
  defaultTitle: string
  saving: boolean
  error: string | null
  customReferenceOmitted: boolean
}

export type OpenDesignState =
  | { phase: 'loading'; designId: string }
  | { phase: 'confirm'; record: SavedDesignRecord }
  | { phase: 'unsynced'; record: SavedDesignRecord; message: string }
  | { phase: 'conflict'; record: SavedDesignRecord }
  | { phase: 'opening'; record: SavedDesignRecord }
  | { phase: 'error'; designId: string; record: SavedDesignRecord | null; message: string; canRetry: boolean }

type PendingSave = {
  saveRequestId: string
  snapshot: SavedDesignSnapshot
  sourceRevision: number | null
  uncertain: boolean
}

const EXPORT_FAILED =
  'PNG export failed. Your sketch is unchanged. Try again, or reload the page if it keeps failing.'
const EXPORT_NO_REFERENCE =
  'PNG exported without the reference image because it could not be loaded. Your ink is included.'
const OPEN_CUSTOM_REFERENCE_NOTE =
  ' Custom reference images are not saved with designs. Choose the image again if you need it.'

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
  /** Blocks automatic cloud writes until the operator resolves a conflict. */
  const conflictOpenRef = useRef(false)
  /** Blocks automatic cloud writes while a saved design replaces the working-draft content. */
  const openingRef = useRef(false)
  const cloudInFlightRef = useRef(0)
  const pendingSaveRef = useRef<PendingSave | null>(null)
  const saveInFlightRef = useRef(false)
  const exportingRef = useRef(false)
  const openRequestRef = useRef(0)

  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [fills, setFills] = useState<FillOp[]>([])
  const [tool, setTool] = useState<ToolKind>('draw')
  const [brushSizePx, setBrushSizePxState] = useState(BRUSH_SIZE_DEFAULT_PX)
  const [opacity, setOpacity] = useState(1)
  const [color, setColor] = useState<string>(INK_SWATCHES[0]!.color)
  const [fillStyle, setFillStyle] = useState<FillStyle>(() => solidStyle(INK_SWATCHES[0]!.color))
  const [model, setModelState] = useState<ModelChoice>(DEFAULT_MODEL)
  const [customUrl, setCustomUrl] = useState<string | null>(null)
  const [customKey, setCustomKey] = useState<string | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [dimmed, setDimmed] = useState(false)
  const [magicNotice, setMagicNotice] = useState<string | null>(null)
  const [magicOpen, setMagicOpen] = useState(false)
  const [magicPhase, setMagicPhase] = useState<MagicPhase>('idle')
  const [magicResult, setMagicResult] = useState<MagicLookResult | null>(null)
  const [magicError, setMagicError] = useState<string | null>(null)
  const [magicLookUrl, setMagicLookUrl] = useState<string | null>(null)
  const [magicSketchUrl, setMagicSketchUrl] = useState<string | null>(null)
  const [magicJobId, setMagicJobId] = useState<string | null>(null)
  const magicAbortRef = useRef<AbortController | null>(null)
  const magicLookUrlRef = useRef<string | null>(null)
  const magicSketchUrlRef = useRef<string | null>(null)
  const magicInFlightRef = useRef(false)
  const magicEnabled = isMagicUiEnabled()
  const magicBusy =
    magicPhase === 'capturing' || magicPhase === 'submitting' || magicPhase === 'polling'
  const [studioNotice, setStudioNotice] = useState<string | null>(null)
  const [comingSoon, setComingSoon] = useState<string | null>(null)

  const publishStudioNotice = useCallback((message: string) => {
    setMagicNotice(null)
    setComingSoon(null)
    setStudioNotice(message)
  }, [])
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('restoring')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [modelSwitchPrompt, setModelSwitchPrompt] = useState<ModelSwitchPrompt | null>(null)
  const [draftConflict, setDraftConflict] = useState<DraftConflictPrompt | null>(null)
  const [ready, setReady] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [saveDesignDialog, setSaveDesignDialog] = useState<SaveDesignDialogState | null>(null)
  const [openDesign, setOpenDesign] = useState<OpenDesignState | null>(null)
  /** Bumped after each acknowledged Save as design so My Designs refetches. */
  const [libraryVersion, setLibraryVersion] = useState(0)

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
    // Avoid a spurious revision bump when React state mirrors an already-committed doc.
    skipNextAutosaveRef.current = true
    setStrokes(doc.strokes)
    setFills(doc.fills ?? [])
    setModelState(doc.model)
    setCustomUrl(doc.customReferenceUrl)
    setCustomKey(doc.customReferenceKey)
    setBrushSizePxState(resolveBrushSizePx(doc.brush))
    setOpacity(doc.brush.opacity)
    setColor(doc.brush.color)
    setFillStyle(solidStyle(doc.brush.color))
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
    if (conflictOpenRef.current) return
    const doc = authoritativeDocRef.current
    const fingerprint = draftContentFingerprint(documentForCloud(doc))
    cloudDirtyRef.current = false

    const run = async () => {
      // A save queued behind an in-flight request must not run after that
      // request opens a conflict. Check at execution time, before any API call.
      if (conflictOpenRef.current || openingRef.current) {
        return
      }
      setSaveStatus((prev) => (prev === 'pending' ? 'pending' : 'saving'))
      setSaveError(null)
      cloudInFlightRef.current += 1
      let result: Awaited<ReturnType<typeof persistStudioDraft>>
      try {
        result = await persistStudioDraft({
          userId: user.id,
          designId: designIdRef.current,
          document: doc,
          fingerprint,
          lastSyncedFingerprint: syncedFingerprintRef.current,
          expectedRevision: syncedRevisionRef.current,
          skipLocalWrite: localPersistedFpRef.current === draftContentFingerprint(doc),
        })
      } finally {
        cloudInFlightRef.current -= 1
      }

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
        conflictOpenRef.current = true
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
    if (conflictOpenRef.current || openingRef.current) return
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
      fills?: FillOp[]
      model?: ModelChoice
      customReferenceUrl?: string | null
      customReferenceKey?: string | null
      sizeId?: BrushSizeId
      sizePx?: number
      opacity?: number
      color?: string
      dimmed?: boolean
    }) => {
      const prev = authoritativeDocRef.current
      const sizePx =
        typeof patch.sizePx === 'number'
          ? snapBrushSizePx(patch.sizePx)
          : patch.sizeId
            ? BRUSH_SIZES[patch.sizeId]
            : resolveBrushSizePx(prev.brush)
      const next = documentFromEditorState({
        prev,
        strokes: patch.strokes ?? prev.strokes,
        fills: patch.fills ?? prev.fills ?? [],
        model: patch.model ?? prev.model,
        customReferenceUrl:
          patch.customReferenceUrl !== undefined ? patch.customReferenceUrl : prev.customReferenceUrl,
        customReferenceKey:
          patch.customReferenceKey !== undefined ? patch.customReferenceKey : prev.customReferenceKey,
        sizeId: nearestBrushSizeId(sizePx),
        sizePx,
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
        conflictOpenRef.current = true
        setDraftConflict(restored.conflict)
        applyDocument(restored.conflict.local, restored.conflict.designId)
        setSaveStatus('local-only')
      } else {
        applyDocument(restored.document, restored.designId)
        setSaveStatus(restored.designId ? 'saved' : 'idle')
      }
      if (restored.notice) publishStudioNotice(restored.notice)

      bootedRef.current = true
      setReady(true)

      const needsSync =
        restored.conflict === null &&
        (restored.designId === null
          ? restored.document.strokes.length > 0 || (restored.document.fills?.length ?? 0) > 0
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
      fills,
      model,
      customReferenceUrl: customUrl,
      customReferenceKey: customKey,
      sizeId: nearestBrushSizeId(brushSizePx),
      sizePx: brushSizePx,
      opacity,
      color,
      dimmed,
    })
    if (draftContentFingerprint(prev) === draftContentFingerprint(next)) return
    void commitDocument(next)
  }, [strokes, fills, model, customUrl, customKey, brushSizePx, opacity, color, dimmed, ready, commitDocument])

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    }
  }, [])

  const brushSize = brushSizePx
  const sizeId = nearestBrushSizeId(brushSizePx)

  const referenceUrl = useMemo(() => {
    if (model === 'custom') return blobUrl ?? customUrl
    if (model === 'blank') return null
    return canvasSrcForModel(model)
  }, [model, customUrl, blobUrl])

  const referenceOpacity = dimmed ? 0.4 : 1

  const artwork = useCallback(
    () => ({ strokes, fills }),
    [fills, strokes],
  )

  const onStrokeComplete = useCallback(
    (stroke: Stroke) => {
      history.current.push(artwork())
      const nextStrokes = [...strokes, stroke]
      setStrokes(nextStrokes)
      syncHistoryFlags()
      commitFromEditor({ strokes: nextStrokes, fills })
    },
    [artwork, commitFromEditor, fills, strokes, syncHistoryFlags],
  )

  const onFillComplete = useCallback(
    (fill: FillOp) => {
      // Keep saved designs recoverable: refuse fills past the snapshot limit.
      if (fills.length >= MAX_SNAPSHOT_FILLS) {
        publishStudioNotice(
          `This design already has ${MAX_SNAPSHOT_FILLS} fills (the save limit). Undo some fills before adding more.`,
        )
        return
      }
      // Contours must satisfy persisted-fill bounds before any state/save write.
      const persistable = checkPersistableFill(fill)
      if (!persistable.ok) {
        publishStudioNotice(persistable.message)
        return
      }
      history.current.push(artwork())
      const nextFills = [...fills, persistable.fill]
      setFills(nextFills)
      syncHistoryFlags()
      commitFromEditor({ strokes, fills: nextFills })
      publishStudioNotice('Region filled. Undo if you need to try again.')
    },
    [artwork, commitFromEditor, fills, publishStudioNotice, strokes, syncHistoryFlags],
  )

  const onFillError = useCallback(
    (message: string) => {
      publishStudioNotice(message)
    },
    [publishStudioNotice],
  )

  const onEyedropperSample = useCallback(
    (sampled: string) => {
      setColor(sampled)
      setFillStyle(solidStyle(sampled))
      setTool('draw')
      publishStudioNotice(`Color set to ${sampled}`)
    },
    [publishStudioNotice],
  )

  const undo = useCallback(() => {
    const prev = history.current.undo(artwork())
    if (!prev) return
    setStrokes(prev.strokes)
    setFills(prev.fills)
    syncHistoryFlags()
    commitFromEditor({ strokes: prev.strokes, fills: prev.fills })
  }, [artwork, commitFromEditor, syncHistoryFlags])

  const redo = useCallback(() => {
    const next = history.current.redo(artwork())
    if (!next) return
    setStrokes(next.strokes)
    setFills(next.fills)
    syncHistoryFlags()
    commitFromEditor({ strokes: next.strokes, fills: next.fills })
  }, [artwork, commitFromEditor, syncHistoryFlags])

  const clear = useCallback(() => {
    if (strokes.length === 0 && fills.length === 0) return
    history.current.push(artwork())
    setStrokes([])
    setFills([])
    syncHistoryFlags()
    commitFromEditor({ strokes: [], fills: [] })
  }, [artwork, commitFromEditor, fills.length, strokes.length, syncHistoryFlags])

  const commitModelChange = useCallback(
    (next: ModelChoice, clearStrokes: boolean) => {
      if (clearStrokes && (strokes.length > 0 || fills.length > 0)) {
        history.current.push(artwork())
        setStrokes([])
        setFills([])
        syncHistoryFlags()
        setModelState(next)
        commitFromEditor({ model: next, strokes: [], fills: [] })
      } else {
        setModelState(next)
      }
      setModelSwitchPrompt(null)
    },
    [artwork, commitFromEditor, fills.length, strokes.length, syncHistoryFlags],
  )

  const requestModelChange = useCallback(
    (next: ModelChoice) => {
      if (next === model) return
      if (strokes.length > 0 || fills.length > 0) {
        setModelSwitchPrompt({ next })
        return
      }
      setModelState(next)
    },
    [fills.length, model, strokes.length],
  )

  const onCustomFile = useCallback(
    async (file: File) => {
      const validated = validateReferenceImageFile(file)
      if (!validated.ok) {
        publishStudioNotice(validated.message)
        return
      }

      if (blobUrl) URL.revokeObjectURL(blobUrl)
      const url = URL.createObjectURL(file)
      setBlobUrl(url)
      // Persistent uploads disabled for private beta — /static/uploads is not owner-private.
      setCustomUrl(null)
      setCustomKey(null)
      publishStudioNotice(CUSTOM_REF_BETA_NOTICE)

      if (strokes.length > 0 || fills.length > 0) {
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
    [blobUrl, commitFromEditor, fills.length, publishStudioNotice, strokes.length],
  )

  const revokeMagicUrls = useCallback(() => {
    if (magicLookUrlRef.current) {
      URL.revokeObjectURL(magicLookUrlRef.current)
      magicLookUrlRef.current = null
    }
    if (magicSketchUrlRef.current) {
      URL.revokeObjectURL(magicSketchUrlRef.current)
      magicSketchUrlRef.current = null
    }
    setMagicLookUrl(null)
    setMagicSketchUrl(null)
  }, [])

  const closeMagicPanel = useCallback(() => {
    magicAbortRef.current?.abort()
    magicAbortRef.current = null
    setMagicOpen(false)
    setMagicPhase('idle')
    setMagicError(null)
  }, [])

  const applySettledMagicJob = useCallback(
    async (jobId: string, signal?: AbortSignal) => {
      const job = await recoverMagicJob(jobId, signal)
      const look = toMagicLookResult(job)
      setMagicResult(look)
      setMagicJobId(job.id)
      if (user?.id) persistMagicJobId(user.id, job.id)
      if (look.status === 'failed') {
        setMagicPhase('failed')
        setMagicError(look.summary)
        return
      }
      if (look.hasImage) {
        const blob = await fetchJobImageBlob(job.id, signal)
        if (magicLookUrlRef.current) URL.revokeObjectURL(magicLookUrlRef.current)
        const url = URL.createObjectURL(blob)
        magicLookUrlRef.current = url
        setMagicLookUrl(url)
      }
      setMagicPhase('ready')
      setMagicError(null)
    },
    [user?.id],
  )

  const runMagicPipeline = useCallback(async () => {
    if (!user?.id) {
      setMagicNotice('Sign in to use Magic.')
      return
    }
    if (magicInFlightRef.current) {
      setMagicOpen(true)
      return
    }
    magicInFlightRef.current = true
    setStudioNotice(null)
    setComingSoon(null)
    setMagicNotice(null)
    setMagicError(null)
    setMagicResult(null)
    revokeMagicUrls()
    setMagicOpen(true)
    setMagicPhase('capturing')

    magicAbortRef.current?.abort()
    const controller = new AbortController()
    magicAbortRef.current = controller

    try {
      // Snapshot the selected croquis with the sketch so a mid-flight model switch
      // cannot desync the Magic identity contract from the captured reference.
      const referenceModelId = model
      const captured = await captureSketchForMagic({
        strokes,
        fills,
        referenceUrl,
        referenceOpacity,
      })
      if (controller.signal.aborted) return
      const sketchUrl = URL.createObjectURL(captured.blob)
      magicSketchUrlRef.current = sketchUrl
      setMagicSketchUrl(sketchUrl)

      setMagicPhase('submitting')
      const job = await enqueueSketchPolish({
        imageBase64: captured.dataUrl,
        referenceModelId,
        notes: 'polish concept',
        signal: controller.signal,
      })
      setMagicJobId(job.id)
      persistMagicJobId(user.id, job.id)

      setMagicPhase('polling')
      const settled = await pollAiJobUntilSettled({
        jobId: job.id,
        signal: controller.signal,
      })
      const look = toMagicLookResult(settled)
      setMagicResult(look)
      if (look.status === 'failed') {
        setMagicPhase('failed')
        setMagicError(look.summary)
        return
      }
      if (look.hasImage) {
        const blob = await fetchJobImageBlob(settled.id, controller.signal)
        if (magicLookUrlRef.current) URL.revokeObjectURL(magicLookUrlRef.current)
        const url = URL.createObjectURL(blob)
        magicLookUrlRef.current = url
        setMagicLookUrl(url)
      }
      setMagicPhase('ready')
    } catch (err) {
      if (controller.signal.aborted) {
        setMagicPhase('failed')
        setMagicError('Magic wait cancelled. Your sketch is unchanged — recover if the job already finished.')
        return
      }
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Magic could not complete.'
      setMagicPhase('failed')
      setMagicError(message)
    } finally {
      magicInFlightRef.current = false
    }
  }, [fills, model, referenceOpacity, referenceUrl, revokeMagicUrls, strokes, user?.id])

  const onMagic = useCallback(() => {
    if (!magicEnabled) {
      setStudioNotice(null)
      setComingSoon(null)
      setMagicNotice(MAGIC_NOTICE)
      return
    }
    if (magicInFlightRef.current || magicBusy) {
      setMagicOpen(true)
      return
    }
    void runMagicPipeline()
  }, [magicBusy, magicEnabled, runMagicPipeline])

  const recoverLastMagic = useCallback(() => {
    if (!user?.id) return
    if (magicInFlightRef.current) {
      setMagicOpen(true)
      return
    }
    const jobId = magicJobId || readMagicJobId(user.id)
    if (!jobId) {
      setMagicError('No previous Magic job to recover.')
      setMagicPhase('failed')
      setMagicOpen(true)
      return
    }
    magicInFlightRef.current = true
    setMagicOpen(true)
    setMagicPhase('polling')
    setMagicError(null)
    setStudioNotice(null)
    setComingSoon(null)
    setMagicNotice(null)
    magicAbortRef.current?.abort()
    const controller = new AbortController()
    magicAbortRef.current = controller
    void applySettledMagicJob(jobId, controller.signal)
      .catch((err) => {
        if (controller.signal.aborted) return
        setMagicPhase('failed')
        setMagicError(err instanceof Error ? err.message : 'Unable to recover Magic result.')
      })
      .finally(() => {
        magicInFlightRef.current = false
      })
  }, [applySettledMagicJob, magicJobId, user?.id])

  // After refresh, restore the stored job id for "See last result" without enqueue.
  useEffect(() => {
    if (!user?.id) return
    const stored = readMagicJobId(user.id)
    if (stored && !magicJobId) setMagicJobId(stored)
  }, [magicJobId, user?.id])

  const cancelMagicWait = useCallback(() => {
    magicAbortRef.current?.abort()
  }, [])

  const downloadMagicLook = useCallback(() => {
    if (!magicLookUrlRef.current) return
    void fetch(magicLookUrlRef.current)
      .then((r) => r.blob())
      .then((blob) => downloadBlob(blob, exportFilename('look')))
      .catch(() => setMagicError('Could not download the look image.'))
  }, [])

  const backToSketchFromMagic = useCallback(() => {
    closeMagicPanel()
    // Keep job id for recovery; never clear strokes — original sketch remains.
  }, [closeMagicPanel])

  useEffect(() => {
    return () => {
      magicAbortRef.current?.abort()
      if (magicLookUrlRef.current) URL.revokeObjectURL(magicLookUrlRef.current)
      if (magicSketchUrlRef.current) URL.revokeObjectURL(magicSketchUrlRef.current)
    }
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
    setBrushSizePxState(snapBrushSizePx(px))
  }, [])

  const setSizeId = useCallback((id: BrushSizeId) => {
    setBrushSizePxState(BRUSH_SIZES[id])
  }, [])

  const nudgeBrushSizePx = useCallback((deltaSteps: number) => {
    setBrushSizePxState((prev) => snapBrushSizePx(prev + deltaSteps * 0.25))
  }, [])

  const setBrushOpacity = useCallback((value: number) => {
    const clamped = Math.min(1, Math.max(0.05, value))
    setOpacity(clamped)
  }, [])

  const selectColor = useCallback((next: string) => {
    const hex = next.toUpperCase()
    setColor(hex)
    setFillStyle(solidStyle(hex))
  }, [])

  const setColorHex = useCallback((raw: string) => {
    const hex = raw.trim()
    if (!/^#([0-9a-fA-F]{6})$/.test(hex)) return false
    selectColor(hex)
    return true
  }, [selectColor])

  const selectFillStyle = useCallback((style: FillStyle) => {
    setFillStyle(style)
    if (style.kind === 'solid') {
      setColor(style.color)
      return
    }
    // Fabric / uploaded fabric / gradient selections imply Fill for the next tap.
    setTool('fill')
  }, [])

  const showComingSoon = useCallback((label: string) => {
    setMagicNotice(null)
    setStudioNotice(null)
    setComingSoon(`${label} — coming later`)
  }, [])

  const resolveConflictKeepLocal = useCallback(() => {
    if (!draftConflict || !user?.id) return
    const prompt = draftConflict
    conflictOpenRef.current = true
    void (async () => {
      setSaveStatus('saving')
      setSaveError(null)
      const result = await commitKeepDeviceChoice({
        userId: user.id,
        designId: prompt.designId,
        local: prompt.local,
        serverRevision: prompt.server.clientRevision,
      })
      const rebased = rebaseChosenLocalDraft(prompt.local, prompt.server.clientRevision)
      if (result.ok) {
        const expectedFp = draftContentFingerprint(documentForCloud(rebased))
        if (result.fingerprint !== expectedFp) {
          conflictOpenRef.current = true
          setDraftConflict({
            local: rebased,
            server: result.document,
            designId: result.designId,
          })
          setSaveError('Server draft content differs from this device.')
          setSaveStatus('error')
          return
        }
        conflictOpenRef.current = false
        authoritativeDocRef.current = rebased
        designIdRef.current = result.designId
        syncedRevisionRef.current = result.syncedRevision
        syncedFingerprintRef.current = result.fingerprint
        applyDocument(rebased, result.designId)
        setDraftConflict(null)
        setSaveStatus('saved')
        return
      }
      conflictOpenRef.current = true
      if (result.conflict) {
        setDraftConflict(result.conflict)
        setSaveError(result.error)
        setSaveStatus('error')
        return
      }
      setSaveError(result.error)
      setSaveStatus('error')
    })()
  }, [applyDocument, draftConflict, user?.id])

  const resolveConflictUseServer = useCallback(() => {
    if (!draftConflict || !user?.id) return
    const prompt = draftConflict
    conflictOpenRef.current = true
    void (async () => {
      setSaveStatus('saving')
      setSaveError(null)
      const replaced = await commitUseCloudChoice({
        userId: user.id,
        designId: prompt.designId,
        server: prompt.server,
      })
      if (!replaced.ok) {
        conflictOpenRef.current = true
        setSaveError(replaced.error)
        setSaveStatus('error')
        return
      }
      conflictOpenRef.current = false
      authoritativeDocRef.current = prompt.server
      designIdRef.current = prompt.designId
      syncedRevisionRef.current = prompt.server.clientRevision
      syncedFingerprintRef.current = draftContentFingerprint(documentForCloud(prompt.server))
      applyDocument(prompt.server, prompt.designId)
      setDraftConflict(null)
      setSaveStatus('saved')
    })()
  }, [applyDocument, draftConflict, user?.id])

  const referenceUrlForDocument = useCallback(
    (doc: StudioDraftDocument): string | null => {
      if (doc.model === 'custom') return blobUrl ?? doc.customReferenceUrl
      if (doc.model === 'blank') return null
      return canvasSrcForModel(doc.model)
    },
    [blobUrl],
  )

  /** Export the authoritative document (plus any session-only custom reference) as PNG. */
  const exportPng = useCallback(async () => {
    if (exportingRef.current) return
    exportingRef.current = true
    setExporting(true)
    const doc = authoritativeDocRef.current
    try {
      const { blob, referenceIncluded } = await exportSketchPng({
        strokes: doc.strokes,
        fills: doc.fills ?? [],
        referenceUrl: referenceUrlForDocument(doc),
        referenceOpacity: doc.dimmed ? 0.4 : 1,
      })
      downloadBlob(blob, exportFilename(null))
      const wantedReference = referenceUrlForDocument(doc) !== null
      publishStudioNotice(
        wantedReference && !referenceIncluded
          ? EXPORT_NO_REFERENCE
          : 'PNG exported (768 × 1024). Check your downloads.',
      )
    } catch (err) {
      if (err instanceof FabricAssetLoadError) {
        publishStudioNotice(
          'A custom fabric in this sketch could not be loaded. Check your connection or re-upload the fabric, then export again.',
        )
      } else {
        publishStudioNotice(EXPORT_FAILED)
      }
    } finally {
      exportingRef.current = false
      setExporting(false)
    }
  }, [publishStudioNotice, referenceUrlForDocument])

  const beginSaveDesign = useCallback(() => {
    if (!ready || saveInFlightRef.current) return
    const doc = authoritativeDocRef.current
    if (doc.strokes.length === 0 && (doc.fills?.length ?? 0) === 0) {
      publishStudioNotice('Draw something before saving a design.')
      return
    }
    pendingSaveRef.current = {
      saveRequestId: createSaveRequestId(),
      snapshot: snapshotFromDocument(doc),
      sourceRevision: syncedRevisionRef.current,
      uncertain: false,
    }
    setSaveDesignDialog({
      defaultTitle: defaultDesignTitle(),
      saving: false,
      error: null,
      customReferenceOmitted: doc.model === 'custom',
    })
  }, [publishStudioNotice, ready])

  const cancelSaveDesign = useCallback(() => {
    if (saveInFlightRef.current) return
    pendingSaveRef.current = null
    setSaveDesignDialog(null)
  }, [])

  const confirmSaveDesign = useCallback(
    async (rawTitle: string) => {
      const pending = pendingSaveRef.current
      if (!pending || !user?.id || saveInFlightRef.current) return
      const validated = validateDesignTitle(rawTitle)
      if (!validated.ok) {
        setSaveDesignDialog((prev) => (prev ? { ...prev, error: validated.message } : prev))
        return
      }
      saveInFlightRef.current = true
      setSaveDesignDialog((prev) => (prev ? { ...prev, saving: true, error: null } : prev))
      try {
        const result = await saveDesignSnapshot({
          ownerId: user.id,
          title: validated.title,
          snapshot: pending.snapshot,
          saveRequestId: pending.saveRequestId,
          sourceRevision: pending.sourceRevision,
          previousAttemptUncertain: pending.uncertain,
        })
        if (result.ok) {
          pendingSaveRef.current = null
          setSaveDesignDialog(null)
          setLibraryVersion((v) => v + 1)
          publishStudioNotice(
            `Saved “${result.record.title}” to My Designs. Your Studio sketch is unchanged.`,
          )
          return
        }
        pending.uncertain = pending.uncertain || result.outcomeUncertain
        setSaveDesignDialog((prev) =>
          prev ? { ...prev, saving: false, error: result.error } : prev,
        )
      } finally {
        saveInFlightRef.current = false
      }
    },
    [publishStudioNotice, user?.id],
  )

  /** The working copy matches the last server-acknowledged revision, with nothing queued. */
  const workingCopyState = useCallback((): 'clean' | 'clean-empty' | 'unsynced' | 'conflict' => {
    if (conflictOpenRef.current) return 'conflict'
    if (!bootedRef.current) return 'unsynced'
    if (cloudDirtyRef.current || cloudInFlightRef.current > 0) return 'unsynced'
    const doc = authoritativeDocRef.current
    if (designIdRef.current === null) {
      return doc.strokes.length === 0 && (doc.fills?.length ?? 0) === 0
        ? 'clean-empty'
        : 'unsynced'
    }
    if (syncedRevisionRef.current === null) return 'unsynced'
    return syncedFingerprintRef.current === draftContentFingerprint(documentForCloud(doc))
      ? 'clean'
      : 'unsynced'
  }, [])

  const finishOpen = useCallback(
    (record: SavedDesignRecord, doc: StudioDraftDocument, designId: string, syncedRevision: number) => {
      applyDocument(doc, designId)
      syncedRevisionRef.current = syncedRevision
      syncedFingerprintRef.current = draftContentFingerprint(documentForCloud(doc))
      localPersistedFpRef.current = draftContentFingerprint(doc)
      cloudDirtyRef.current = false
      setSaveStatus('saved')
      setSaveError(null)
      setOpenDesign(null)
      publishStudioNotice(
        `Opened “${record.title}” in Studio. The saved design stays unchanged.${
          record.snapshot.model === 'custom' ? OPEN_CUSTOM_REFERENCE_NOTE : ''
        }`,
      )
      navigate('/studio')
    },
    [applyDocument, navigate, publishStudioNotice],
  )

  /**
   * Replace the singleton working draft's content with a saved snapshot.
   * Runs on the serialized save chain, writes the server first with the last acknowledged
   * revision as the OCC token, and only then updates the editor and IndexedDB.
   * Any failure leaves the editor, IndexedDB and the server draft as they were.
   */
  const performOpen = useCallback(
    (record: SavedDesignRecord) => {
      if (!user?.id || openingRef.current) return
      const userId = user.id
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current)
        saveTimerRef.current = null
      }
      setOpenDesign({ phase: 'opening', record })

      const op = async () => {
        const state = workingCopyState()
        if (state === 'conflict') {
          setOpenDesign({ phase: 'conflict', record })
          return
        }
        if (state === 'unsynced') {
          setOpenDesign({
            phase: 'unsynced',
            record,
            message: 'Your Studio sketch changed before the design could be opened.',
          })
          if (cloudDirtyRef.current) scheduleCloudSaveRef.current()
          return
        }
        openingRef.current = true
        // No known draft id: createOnly creates, recovers identical content, or conflicts —
        // never overwrites another device's draft. No separate list preflight: that blocked
        // same-content recovery after a committed create whose response was lost.
        const createOnly = designIdRef.current === null
        try {
          const current = authoritativeDocRef.current
          const next = workingDocumentFromSnapshot({
            current,
            serverRevision: syncedRevisionRef.current,
            snapshot: record.snapshot,
          })
          const nextCloudFp = draftContentFingerprint(documentForCloud(next))
          const result = await persistStudioDraft({
            userId,
            designId: designIdRef.current,
            document: next,
            fingerprint: nextCloudFp,
            lastSyncedFingerprint: null,
            expectedRevision: syncedRevisionRef.current,
            skipLocalWrite: true,
            createOnly,
          })
          if (result.ok) {
            finishOpen(record, next, result.designId, result.syncedRevision)
            return
          }
          if (result.conflict) {
            const server = result.conflict.server
            if (draftContentFingerprint(documentForCloud(server)) === nextCloudFp) {
              // An earlier attempt reached the server but its response was lost.
              const local = await persistLocalRecovery({
                userId,
                designId: result.conflict.designId,
                document: server,
                syncedRevision: server.clientRevision,
              })
              if (!local.ok) {
                setOpenDesign({
                  phase: 'error',
                  designId: record.id,
                  record,
                  canRetry: true,
                  message: local.error,
                })
                return
              }
              finishOpen(record, server, result.conflict.designId, server.clientRevision)
              return
            }
            conflictOpenRef.current = true
            setDraftConflict({
              local: current,
              server,
              designId: result.conflict.designId,
            })
            setSaveStatus('local-only')
            setOpenDesign(null)
            publishStudioNotice(
              'Your working draft changed on another device, so the design was not opened. Choose which draft to keep, then open the design again.',
            )
            navigate('/studio')
            return
          }
          // Network / 5xx: the server write may have committed before the response was lost.
          setOpenDesign({
            phase: 'error',
            designId: record.id,
            record,
            canRetry: true,
            message: `${result.error} Whether the server draft changed could not be confirmed. Studio on this device was left unchanged. Try again — FashionRise will reconcile safely.`,
          })
        } catch {
          setOpenDesign({
            phase: 'error',
            designId: record.id,
            record,
            canRetry: true,
            message:
              'Could not reach FashionRise. Whether the server draft changed could not be confirmed. Studio on this device was left unchanged. Try again — FashionRise will reconcile safely.',
          })
        } finally {
          openingRef.current = false
        }
      }

      saveChainRef.current = saveChainRef.current.then(op, op)
    },
    [finishOpen, navigate, publishStudioNotice, user?.id, workingCopyState],
  )

  const evaluateOpen = useCallback(
    (record: SavedDesignRecord) => {
      const state = workingCopyState()
      if (state === 'conflict') {
        setOpenDesign({ phase: 'conflict', record })
      } else if (state === 'unsynced') {
        setOpenDesign({
          phase: 'unsynced',
          record,
          message: !bootedRef.current
            ? 'Studio is still restoring your working draft.'
            : 'Your Studio sketch has changes that are not saved to your account yet.',
        })
      } else if (
        authoritativeDocRef.current.strokes.length === 0 &&
        (authoritativeDocRef.current.fills?.length ?? 0) === 0
      ) {
        performOpen(record)
      } else {
        setOpenDesign({ phase: 'confirm', record })
      }
    },
    [performOpen, workingCopyState],
  )

  const requestOpenDesign = useCallback(
    async (designId: string) => {
      if (!user?.id || openingRef.current) return
      const token = ++openRequestRef.current
      setOpenDesign({ phase: 'loading', designId })
      const fetched = await fetchSavedDesign(user.id, designId)
      if (token !== openRequestRef.current) return
      if (!fetched.ok) {
        setOpenDesign({
          phase: 'error',
          designId,
          record: null,
          canRetry: fetched.reason === 'network',
          message: fetched.error,
        })
        return
      }
      evaluateOpen(fetched.record)
    },
    [evaluateOpen, user?.id],
  )

  const retryOpenDesign = useCallback(async () => {
    const current = openDesign
    if (!current) return
    if (current.phase === 'unsynced') {
      const token = ++openRequestRef.current
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
      if (bootedRef.current && !conflictOpenRef.current) await flushCloudSave()
      else await saveChainRef.current
      if (token !== openRequestRef.current) return
      evaluateOpen(current.record)
      return
    }
    if (current.phase === 'error' && current.canRetry) {
      if (current.record) evaluateOpen(current.record)
      else await requestOpenDesign(current.designId)
    }
  }, [evaluateOpen, flushCloudSave, openDesign, requestOpenDesign])

  const confirmOpenDesign = useCallback(() => {
    if (openDesign?.phase === 'confirm') performOpen(openDesign.record)
  }, [openDesign, performOpen])

  const cancelOpenDesign = useCallback(() => {
    if (openDesign?.phase === 'opening') return
    openRequestRef.current += 1
    setOpenDesign(null)
  }, [openDesign])

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
    fills,
    tool,
    setTool,
    sizeId,
    setSizeId,
    brushSize,
    setBrushSizePx,
    nudgeBrushSizePx,
    opacity,
    setBrushOpacity,
    color,
    setColor: selectColor,
    setColorHex,
    fillStyle,
    setFillStyle: selectFillStyle,
    model,
    setModel: requestModelChange,
    customUrl: blobUrl ?? customUrl,
    onCustomFile,
    dimmed,
    setDimmed,
    referenceUrl,
    referenceOpacity,
    onStrokeComplete,
    onFillComplete,
    onFillError,
    onEyedropperSample,
    undo,
    redo,
    clear,
    canUndo,
    canRedo,
    onMagic,
    onLogout,
    magicNotice,
    setMagicNotice,
    magicEnabled,
    magicOpen,
    magicPhase,
    magicBusy,
    magicResult,
    magicError,
    magicLookUrl,
    magicSketchUrl,
    magicCanRecover: Boolean(magicJobId || (user?.id && readMagicJobId(user.id))),
    closeMagicPanel,
    cancelMagicWait,
    recoverLastMagic,
    downloadMagicLook,
    backToSketchFromMagic,
    studioNotice,
    setStudioNotice,
    publishStudioNotice,
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
    exporting,
    exportPng,
    saveDesignDialog,
    beginSaveDesign,
    confirmSaveDesign,
    cancelSaveDesign,
    libraryVersion,
    openDesign,
    requestOpenDesign,
    confirmOpenDesign,
    retryOpenDesign,
    cancelOpenDesign,
  }
}

export type StudioEditor = ReturnType<typeof useStudioEditor>
