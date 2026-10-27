import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEFAULT_MODEL, type ModelChoice } from '@/assets/modelLibrary'
import { isStudioDualMagicEnabled } from '@/config/studioDualMagic'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import {
  createEmptyDraftDocument,
  draftContentFingerprint,
  normalizeActiveSide,
  rebaseChosenLocalDraft,
  type SaveStatus,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import {
  activeArtwork,
  buildDocumentFromEditor,
  documentHasAnyInk,
  patchActiveSideInk,
  rearReferenceAvailable,
  referenceUrlForModelSide,
  sideStateFromDocument,
  visibleInkFromState,
  type EditorSideState,
} from '@/hooks/studioEditorSides'
import {
  commitKeepDeviceChoice,
  commitReplaceDamagedCloudDraft,
  commitUseCloudChoice,
  persistLocalRecovery,
  persistStudioDraft,
  restoreStudioDraft,
  type DamagedCloudDraft,
} from '@/lib/draftPersistence'
import { documentForCloud } from '@/services/designsApi'
import { isMagicUiEnabled } from '@/config/magicUi'
import {
  downloadBlob,
  exportFilename,
  exportFrontBackSheetPng,
  exportSketchPng,
} from '@/lib/exportCanvas'
import { FabricAssetLoadError } from '@/lib/fabricAssetCache'
import { checkPersistableFill, solidStyle, type FillOp, type FillStyle } from '@/lib/fills'
import { MAX_SNAPSHOT_FILLS } from '@/lib/savedDesign'
import { captureFabricSwatchForMagic } from '@/lib/fabricSwatchCapture'
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
import {
  enqueueSketchPolish,
  fetchJobImageBlob,
  fetchMagicOperationJobs,
  mapMagicOperationJobsBySide,
} from '@/services/ai/magicApi'
import {
  DualPolishUnavailableError,
  enqueueDualPolish,
} from '@/services/ai/magicDualPolish'
import { buildSharedGarmentSpec } from '@/services/ai/magicGarmentSpec'
import { settleMagicJobWithImage } from '@/services/ai/magicPipelineHelpers'
import {
  allocateMagicRetryIdempotencyKey,
  patchMagicOperationJob,
  persistMagicJobId,
  persistMagicOperation,
  readMagicJobId,
  readMagicOperation,
} from '@/services/ai/magicJobStore'
import { resolveDualMagicJobIds } from '@/services/ai/magicOperationRecovery'
import type { StudioPaperSide } from '@/lib/studioSideArtwork'
import { sideHasInk } from '@/lib/studioSideArtwork'
import { recoverMagicJob } from '@/services/ai/pollAiJob'
import {
  isMagicSafetyRefusal,
  toMagicLookResult,
  type MagicLookResult,
} from '@/services/ai/aiJobTypes'
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
import type { MagicPhase, MagicSidePanelState } from '@/shell/components/MagicLookPanel'

const MAGIC_NOTICE = 'AI enhancement will be available in a later milestone.'
const FRONT_BACK_MAGIC_COMING_SOON = 'Front/Back Magic coming soon'

function emptyMagicSide(): MagicSidePanelState {
  return {
    phase: 'idle',
    result: null,
    lookObjectUrl: null,
    sketchObjectUrl: null,
    error: null,
    canRetry: false,
  }
}
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

export type DamagedCloudDraftPrompt = DamagedCloudDraft

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
  const historyFront = useRef(new StrokeHistory())
  const historyBack = useRef(new StrokeHistory())
  const frontBackEnabled = isStudioFrontBackEnabled()
  const dualMagicEnabled = isStudioDualMagicEnabled()
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
  /** Blocks automatic cloud writes while a damaged cloud draft awaits explicit recovery. */
  const damagedCloudBlockRef = useRef(false)
  /** Blocks automatic cloud writes while a saved design replaces the working-draft content. */
  const openingRef = useRef(false)
  const cloudInFlightRef = useRef(0)
  const pendingSaveRef = useRef<PendingSave | null>(null)
  const saveInFlightRef = useRef(false)
  const exportingRef = useRef(false)
  const openRequestRef = useRef(0)

  const [activeSide, setActiveSide] = useState<StudioPaperSide>('front')
  const [frontStrokes, setFrontStrokes] = useState<Stroke[]>([])
  const [frontFills, setFrontFills] = useState<FillOp[]>([])
  const [backStrokes, setBackStrokes] = useState<Stroke[]>([])
  const [backFills, setBackFills] = useState<FillOp[]>([])
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
  const [magicDualActive, setMagicDualActive] = useState(false)
  const [magicOperationId, setMagicOperationId] = useState<string | null>(null)
  const [magicDualViewSide, setMagicDualViewSide] = useState<StudioPaperSide>('front')
  const [magicFront, setMagicFront] = useState<MagicSidePanelState>(emptyMagicSide)
  const [magicBack, setMagicBack] = useState<MagicSidePanelState>(emptyMagicSide)
  const magicAbortRef = useRef<AbortController | null>(null)
  const magicLookUrlRef = useRef<string | null>(null)
  const magicSketchUrlRef = useRef<string | null>(null)
  const magicSideLookUrlsRef = useRef<{ front: string | null; back: string | null }>({
    front: null,
    back: null,
  })
  const magicSideSketchUrlsRef = useRef<{ front: string | null; back: string | null }>({
    front: null,
    back: null,
  })
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
  const [damagedCloud, setDamagedCloud] = useState<DamagedCloudDraftPrompt | null>(null)
  const [damagedCloudDialogOpen, setDamagedCloudDialogOpen] = useState(false)
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

  const activeHistory = useCallback(() => {
    return activeSide === 'back' ? historyBack.current : historyFront.current
  }, [activeSide])

  const syncHistoryFlags = useCallback(() => {
    const h = activeHistory()
    setCanUndo(h.canUndo())
    setCanRedo(h.canRedo())
  }, [activeHistory])

  const editorSideState = useCallback((): EditorSideState => {
    return {
      activeSide,
      frontStrokes,
      frontFills,
      backStrokes,
      backFills,
    }
  }, [activeSide, backFills, backStrokes, frontFills, frontStrokes])

  const strokes = activeSide === 'back' ? backStrokes : frontStrokes
  const fills = activeSide === 'back' ? backFills : frontFills

  const applyDocument = useCallback((doc: StudioDraftDocument, designId: string | null) => {
    authoritativeDocRef.current = doc
    designIdRef.current = designId
    historyFront.current = new StrokeHistory()
    historyBack.current = new StrokeHistory()
    const sides = sideStateFromDocument(doc)
    // Avoid a spurious revision bump when React state mirrors an already-committed doc.
    skipNextAutosaveRef.current = true
    setActiveSide(sides.activeSide)
    setFrontStrokes(sides.frontStrokes)
    setFrontFills(sides.frontFills)
    setBackStrokes(sides.backStrokes)
    setBackFills(sides.backFills)
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
    if (conflictOpenRef.current || damagedCloudBlockRef.current) return
    const doc = authoritativeDocRef.current
    const fingerprint = draftContentFingerprint(documentForCloud(doc))
    cloudDirtyRef.current = false

    const run = async () => {
      // A save queued behind an in-flight request must not run after that
      // request opens a conflict. Check at execution time, before any API call.
      if (conflictOpenRef.current || damagedCloudBlockRef.current || openingRef.current) {
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
        // clearBackIntent is session-only metadata — drop after a successful ACK so
        // later autosaves do not keep replaying the transient clear flag.
        if (stillCurrent && authoritativeDocRef.current.clearBackIntent) {
          const { clearBackIntent: _ackIntent, ...acked } = authoritativeDocRef.current
          authoritativeDocRef.current = acked
        }
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
        const serverFp = draftContentFingerprint(documentForCloud(result.conflict.server))
        const localFp = draftContentFingerprint(documentForCloud(result.conflict.local))
        const authFp = draftContentFingerprint(documentForCloud(authoritativeDocRef.current))
        // Single-session recovery: same-content ACK, or a stale in-flight save whose
        // 409 payload already matches the newer authoritative local (e.g. draw→undo).
        // Genuine multi-tab divergence (server ≠ local and server ≠ auth) still conflicts.
        if (serverFp === localFp || serverFp === authFp) {
          designIdRef.current = result.conflict.designId
          syncedRevisionRef.current = result.conflict.server.clientRevision
          syncedFingerprintRef.current = serverFp
          if (authoritativeDocRef.current.clearBackIntent && serverFp === authFp) {
            const { clearBackIntent: _ackIntent, ...acked } = authoritativeDocRef.current
            authoritativeDocRef.current = acked
          }
          if (authFp === serverFp && !cloudDirtyRef.current) {
            setSaveStatus('saved')
            setSaveError(null)
          } else {
            setSaveStatus('pending')
            scheduleCloudSaveRef.current()
          }
          return
        }
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
    if (conflictOpenRef.current || damagedCloudBlockRef.current || openingRef.current) return
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
      frontStrokes?: Stroke[]
      frontFills?: FillOp[]
      backStrokes?: Stroke[]
      backFills?: FillOp[]
      activeSide?: StudioPaperSide
      model?: ModelChoice
      customReferenceUrl?: string | null
      customReferenceKey?: string | null
      sizeId?: BrushSizeId
      sizePx?: number
      opacity?: number
      color?: string
      dimmed?: boolean
      clearBackIntent?: boolean
    }) => {
      const prev = authoritativeDocRef.current
      const sizePx =
        typeof patch.sizePx === 'number'
          ? snapBrushSizePx(patch.sizePx)
          : patch.sizeId
            ? BRUSH_SIZES[patch.sizeId]
            : resolveBrushSizePx(prev.brush)
      const state: EditorSideState = {
        activeSide: patch.activeSide ?? activeSide,
        frontStrokes: patch.frontStrokes ?? frontStrokes,
        frontFills: patch.frontFills ?? frontFills,
        backStrokes: patch.backStrokes ?? backStrokes,
        backFills: patch.backFills ?? backFills,
      }
      const next = buildDocumentFromEditor({
        prev,
        state,
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
        clearBackIntent: patch.clearBackIntent,
      })
      void commitDocument(next)
      return next
    },
    [activeSide, backFills, backStrokes, commitDocument, frontFills, frontStrokes],
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

      if (restored.damagedCloud || restored.blockAutomaticCloudWrites) {
        damagedCloudBlockRef.current = true
        setDamagedCloud(restored.damagedCloud)
        setDamagedCloudDialogOpen(Boolean(restored.damagedCloud))
        applyDocument(restored.document, restored.designId)
        setSaveStatus(restored.damagedCloud?.hasLocalRecovery ? 'local-only' : 'idle')
      } else if (restored.conflict) {
        conflictOpenRef.current = true
        setDraftConflict(restored.conflict)
        applyDocument(restored.conflict.local, restored.conflict.designId)
        setSaveStatus('local-only')
      } else {
        damagedCloudBlockRef.current = false
        setDamagedCloud(null)
        setDamagedCloudDialogOpen(false)
        applyDocument(restored.document, restored.designId)
        setSaveStatus(restored.designId ? 'saved' : 'idle')
      }
      if (restored.notice) publishStudioNotice(restored.notice)

      bootedRef.current = true
      setReady(true)

      const needsSync =
        restored.conflict === null &&
        !restored.blockAutomaticCloudWrites &&
        !restored.damagedCloud &&
        (restored.designId === null
          ? documentHasAnyInk(restored.document)
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
    const next = buildDocumentFromEditor({
      prev,
      state: editorSideState(),
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
  }, [
    frontStrokes,
    frontFills,
    backStrokes,
    backFills,
    activeSide,
    model,
    customUrl,
    customKey,
    brushSizePx,
    opacity,
    color,
    dimmed,
    ready,
    commitDocument,
    editorSideState,
  ])

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current)
    }
  }, [])

  const brushSize = brushSizePx
  const sizeId = nearestBrushSizeId(brushSizePx)

  const rearAvailable = rearReferenceAvailable(model)
  const referenceUrl = useMemo(() => {
    return referenceUrlForModelSide(model, activeSide, blobUrl ?? customUrl)
  }, [model, customUrl, blobUrl, activeSide])

  const referenceOpacity = dimmed ? 0.4 : 1

  const artwork = useCallback(() => activeArtwork(editorSideState()), [editorSideState])

  const onStrokeComplete = useCallback(
    (stroke: Stroke) => {
      activeHistory().push(artwork())
      const state = editorSideState()
      const ink = visibleInkFromState(state)
      const nextStrokes = [...ink.strokes, stroke]
      const patch = patchActiveSideInk(state, nextStrokes, ink.fills)
      if (patch.activeSide === 'back') {
        setBackStrokes(patch.backStrokes)
        setBackFills(patch.backFills)
      } else {
        setFrontStrokes(patch.frontStrokes)
        setFrontFills(patch.frontFills)
      }
      syncHistoryFlags()
      commitFromEditor({
        frontStrokes: patch.frontStrokes,
        frontFills: patch.frontFills,
        backStrokes: patch.backStrokes,
        backFills: patch.backFills,
        activeSide: patch.activeSide,
      })
    },
    [activeHistory, artwork, commitFromEditor, editorSideState, syncHistoryFlags],
  )

  const onFillComplete = useCallback(
    (fill: FillOp) => {
      // Keep saved designs recoverable: refuse fills past the snapshot limit.
      const visibleFills = visibleInkFromState(editorSideState()).fills
      if (visibleFills.length >= MAX_SNAPSHOT_FILLS) {
        publishStudioNotice(
          `This design already has ${MAX_SNAPSHOT_FILLS} fills (the save limit). Undo some fills before adding more.`,
        )
        return
      }
      // Stamp stroke-list length so earlier erasers cannot punch this new fill.
      const stateForStamp = editorSideState()
      const inkForStamp = visibleInkFromState(stateForStamp)
      const stamped: FillOp = {
        ...fill,
        eraseAfterStrokeIndex: inkForStamp.strokes.length,
      }
      // Contours must satisfy persisted-fill bounds before any state/save write.
      const persistable = checkPersistableFill(stamped)
      if (!persistable.ok) {
        publishStudioNotice(persistable.message)
        return
      }
      activeHistory().push(artwork())
      const state = editorSideState()
      const ink = visibleInkFromState(state)
      const nextFills = [...ink.fills, persistable.fill]
      const patch = patchActiveSideInk(state, ink.strokes, nextFills)
      if (patch.activeSide === 'back') {
        setBackStrokes(patch.backStrokes)
        setBackFills(patch.backFills)
      } else {
        setFrontStrokes(patch.frontStrokes)
        setFrontFills(patch.frontFills)
      }
      syncHistoryFlags()
      commitFromEditor({
        frontStrokes: patch.frontStrokes,
        frontFills: patch.frontFills,
        backStrokes: patch.backStrokes,
        backFills: patch.backFills,
      })
      publishStudioNotice('Region filled. Undo if you need to try again.')
    },
    [activeHistory, artwork, commitFromEditor, editorSideState, publishStudioNotice, syncHistoryFlags],
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

  /**
   * Undo/Redo that empties previously present Back ink is an intentional clear —
   * must stamp clearBackIntent so OCC does not 409 as a false multi-device conflict.
   */
  const backClearIntentForPatch = useCallback(
    (before: EditorSideState, after: EditorSideState): boolean => {
      if (!frontBackEnabled) return false
      const hadBack = sideHasInk({ strokes: before.backStrokes, fills: before.backFills })
      const hasBack = sideHasInk({ strokes: after.backStrokes, fills: after.backFills })
      return hadBack && !hasBack
    },
    [frontBackEnabled],
  )

  const undo = useCallback(() => {
    const prev = activeHistory().undo(artwork())
    if (!prev) return
    const state = editorSideState()
    const patch = patchActiveSideInk(state, prev.strokes, prev.fills)
    const clearBackIntent = backClearIntentForPatch(state, {
      ...state,
      frontStrokes: patch.frontStrokes,
      frontFills: patch.frontFills,
      backStrokes: patch.backStrokes,
      backFills: patch.backFills,
    })
    if (patch.activeSide === 'back') {
      setBackStrokes(patch.backStrokes)
      setBackFills(patch.backFills)
    } else {
      setFrontStrokes(patch.frontStrokes)
      setFrontFills(patch.frontFills)
    }
    syncHistoryFlags()
    commitFromEditor({
      frontStrokes: patch.frontStrokes,
      frontFills: patch.frontFills,
      backStrokes: patch.backStrokes,
      backFills: patch.backFills,
      clearBackIntent,
    })
  }, [
    activeHistory,
    artwork,
    backClearIntentForPatch,
    commitFromEditor,
    editorSideState,
    syncHistoryFlags,
  ])

  const redo = useCallback(() => {
    const next = activeHistory().redo(artwork())
    if (!next) return
    const state = editorSideState()
    const patch = patchActiveSideInk(state, next.strokes, next.fills)
    const clearBackIntent = backClearIntentForPatch(state, {
      ...state,
      frontStrokes: patch.frontStrokes,
      frontFills: patch.frontFills,
      backStrokes: patch.backStrokes,
      backFills: patch.backFills,
    })
    if (patch.activeSide === 'back') {
      setBackStrokes(patch.backStrokes)
      setBackFills(patch.backFills)
    } else {
      setFrontStrokes(patch.frontStrokes)
      setFrontFills(patch.frontFills)
    }
    syncHistoryFlags()
    commitFromEditor({
      frontStrokes: patch.frontStrokes,
      frontFills: patch.frontFills,
      backStrokes: patch.backStrokes,
      backFills: patch.backFills,
      clearBackIntent,
    })
  }, [
    activeHistory,
    artwork,
    backClearIntentForPatch,
    commitFromEditor,
    editorSideState,
    syncHistoryFlags,
  ])

  const clear = useCallback(() => {
    const ink = visibleInkFromState(editorSideState())
    if (ink.strokes.length === 0 && ink.fills.length === 0) return
    activeHistory().push(artwork())
    const state = editorSideState()
    const clearBackIntent =
      frontBackEnabled && state.activeSide === 'back' && sideHasInk({ strokes: backStrokes, fills: backFills })
    if (state.activeSide === 'back') {
      setBackStrokes([])
      setBackFills([])
    } else {
      setFrontStrokes([])
      setFrontFills([])
    }
    syncHistoryFlags()
    commitFromEditor({
      frontStrokes: state.activeSide === 'front' ? [] : frontStrokes,
      frontFills: state.activeSide === 'front' ? [] : frontFills,
      backStrokes: state.activeSide === 'back' ? [] : backStrokes,
      backFills: state.activeSide === 'back' ? [] : backFills,
      clearBackIntent,
    })
  }, [
    activeHistory,
    artwork,
    backFills,
    backStrokes,
    commitFromEditor,
    editorSideState,
    frontBackEnabled,
    frontFills,
    frontStrokes,
    syncHistoryFlags,
  ])

  const designHasInk = useCallback(() => {
    const doc = authoritativeDocRef.current
    return documentHasAnyInk(doc)
  }, [])

  const commitModelChange = useCallback(
    (next: ModelChoice, clearStrokes: boolean) => {
      if (clearStrokes && designHasInk()) {
        historyFront.current.push(artwork())
        historyBack.current.push(artwork())
        setFrontStrokes([])
        setFrontFills([])
        setBackStrokes([])
        setBackFills([])
        syncHistoryFlags()
        setModelState(next)
        if (!rearReferenceAvailable(next) && activeSide === 'back') setActiveSide('front')
        commitFromEditor({
          model: next,
          frontStrokes: [],
          frontFills: [],
          backStrokes: [],
          backFills: [],
          activeSide: rearReferenceAvailable(next) ? activeSide : 'front',
        })
      } else {
        setModelState(next)
        if (!rearReferenceAvailable(next) && activeSide === 'back') {
          setActiveSide('front')
          commitFromEditor({ model: next, activeSide: 'front' })
        }
      }
      setModelSwitchPrompt(null)
    },
    [activeSide, artwork, commitFromEditor, designHasInk, syncHistoryFlags],
  )

  const requestModelChange = useCallback(
    (next: ModelChoice) => {
      if (next === model) return
      if (designHasInk()) {
        setModelSwitchPrompt({ next })
        return
      }
      setModelState(next)
    },
    [designHasInk, model],
  )

  const changeActiveSide = useCallback(
    (side: StudioPaperSide) => {
      if (!frontBackEnabled) return
      if (side === activeSide) return
      if (side === 'back' && !rearReferenceAvailable(model)) return
      skipNextAutosaveRef.current = true
      setActiveSide(side)
      syncHistoryFlags()
      commitFromEditor({ activeSide: side })
    },
    [activeSide, commitFromEditor, frontBackEnabled, model, syncHistoryFlags],
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

      if (designHasInk()) {
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
    [blobUrl, commitFromEditor, designHasInk, publishStudioNotice],
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
    for (const side of ['front', 'back'] as const) {
      const look = magicSideLookUrlsRef.current[side]
      if (look) URL.revokeObjectURL(look)
      magicSideLookUrlsRef.current[side] = null
      const sketch = magicSideSketchUrlsRef.current[side]
      if (sketch) URL.revokeObjectURL(sketch)
      magicSideSketchUrlsRef.current[side] = null
    }
    setMagicLookUrl(null)
    setMagicSketchUrl(null)
    setMagicDualActive(false)
    setMagicOperationId(null)
    setMagicFront(emptyMagicSide())
    setMagicBack(emptyMagicSide())
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

  const referenceUrlForDocument = useCallback(
    (doc: StudioDraftDocument, side: StudioPaperSide = 'front'): string | null => {
      if (doc.model === 'custom') return blobUrl ?? doc.customReferenceUrl
      return referenceUrlForModelSide(doc.model, side, blobUrl ?? doc.customReferenceUrl)
    },
    [blobUrl],
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

    const docGate = authoritativeDocRef.current
    const backBagGate = docGate.back ?? { strokes: [], fills: [] }
    // Dual Magic (and Back-ink Magic) stay off until separately authorized.
    // Front-only Magic continues through the existing single-side polish path.
    if (frontBackEnabled && !dualMagicEnabled && sideHasInk(backBagGate)) {
      setStudioNotice(null)
      setMagicNotice(null)
      setComingSoon(FRONT_BACK_MAGIC_COMING_SOON)
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
      const doc = authoritativeDocRef.current
      const frontBag = { strokes: doc.strokes, fills: doc.fills ?? [] }
      const backBag = doc.back ?? { strokes: [], fills: [] }
      const dual =
        frontBackEnabled &&
        dualMagicEnabled &&
        sideHasInk(frontBag) &&
        sideHasInk(backBag) &&
        rearReferenceAvailable(doc.model)

      const designId = designIdRef.current
      const modelId = doc.model
      const operationId =
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `magic_op_${Date.now()}`

      const captureSide = async (side: StudioPaperSide) => {
        const bag = side === 'front' ? frontBag : backBag
        return captureSketchForMagic({
          strokes: bag.strokes,
          fills: bag.fills,
          referenceUrl: referenceUrlForDocument(doc, side),
          referenceOpacity: doc.dimmed ? 0.4 : 1,
        })
      }

      if (dual) {
        const [frontCap, backCap, frontSwatch, backSwatch] = await Promise.all([
          captureSide('front'),
          captureSide('back'),
          captureFabricSwatchForMagic(frontBag.fills),
          captureFabricSwatchForMagic(backBag.fills),
        ])
        if (controller.signal.aborted) return
        const frontSketchUrl = URL.createObjectURL(frontCap.blob)
        const backSketchUrl = URL.createObjectURL(backCap.blob)
        magicSideSketchUrlsRef.current = { front: frontSketchUrl, back: backSketchUrl }
        magicSketchUrlRef.current = activeSide === 'back' ? backSketchUrl : frontSketchUrl
        setMagicSketchUrl(magicSketchUrlRef.current)
        setMagicDualActive(true)
        setMagicDualViewSide(activeSide)
        setMagicOperationId(operationId)
        setMagicFront({
          phase: 'polling',
          result: null,
          lookObjectUrl: null,
          sketchObjectUrl: frontSketchUrl,
          error: null,
          canRetry: false,
        })
        setMagicBack({
          phase: 'polling',
          result: null,
          lookObjectUrl: null,
          sketchObjectUrl: backSketchUrl,
          error: null,
          canRetry: false,
        })

        setMagicPhase('submitting')
        publishStudioNotice(
          'Magic will polish Front and Back. Two renders may cost more when billing is enabled.',
        )
        const frontIdempotencyKey = `${operationId}:front`
        const backIdempotencyKey = `${operationId}:back`
        const garmentSpec = buildSharedGarmentSpec(doc, 'polish concept')
        const contentFingerprint = draftContentFingerprint(doc)
        const sourceRevision = doc.clientRevision
        persistMagicOperation(user.id, {
          operationId,
          frontIdempotencyKey,
          backIdempotencyKey,
          designId,
          sourceRevision,
          contentFingerprint,
          referenceModelId: modelId,
          sharedGarmentSpec: garmentSpec,
          updatedAt: new Date().toISOString(),
        })
        const enqueued = await enqueueDualPolish({
          design_id: designId,
          magic_operation_id: operationId,
          reference_model_id: modelId,
          notes: 'polish concept',
          shared_garment_spec: garmentSpec,
          source_revision: sourceRevision,
          content_fingerprint: contentFingerprint,
          front: {
            image_base64: frontCap.dataUrl,
            ...(frontSwatch ? { fabric_swatch_base64: frontSwatch.dataUrl } : {}),
            notes: 'polish concept (front)',
            idempotency_key: frontIdempotencyKey,
          },
          back: {
            image_base64: backCap.dataUrl,
            ...(backSwatch ? { fabric_swatch_base64: backSwatch.dataUrl } : {}),
            notes: 'polish concept (back)',
            idempotency_key: backIdempotencyKey,
          },
          signal: controller.signal,
        })
        persistMagicOperation(user.id, {
          operationId: enqueued.magic_operation_id,
          frontJobId: enqueued.front_job_id,
          backJobId: enqueued.back_job_id,
          frontIdempotencyKey,
          backIdempotencyKey,
          designId,
          sourceRevision,
          contentFingerprint,
          referenceModelId: modelId,
          sharedGarmentSpec: garmentSpec,
          updatedAt: new Date().toISOString(),
        })
        setMagicJobId(enqueued.front_job_id)
        persistMagicJobId(user.id, enqueued.front_job_id)

        setMagicPhase('polling')
        const [frontSettled, backSettled] = await Promise.all([
          settleMagicJobWithImage(enqueued.front_job_id, controller.signal),
          settleMagicJobWithImage(enqueued.back_job_id, controller.signal),
        ])

        const applySide = (
          side: StudioPaperSide,
          settled: Awaited<ReturnType<typeof settleMagicJobWithImage>>,
        ): MagicSidePanelState => {
          const failed = settled.look.status === 'failed'
          const safety = failed && isMagicSafetyRefusal(settled.look.summary)
          if (settled.lookObjectUrl) {
            magicSideLookUrlsRef.current[side] = settled.lookObjectUrl
          }
          return {
            phase: failed ? 'failed' : 'ready',
            result: settled.look,
            lookObjectUrl: settled.lookObjectUrl,
            sketchObjectUrl: magicSideSketchUrlsRef.current[side],
            error: failed ? settled.look.summary : null,
            // Safety refusals must not auto-offer identical paid retries.
            canRetry: failed && !safety,
          }
        }
        const nextFront = applySide('front', frontSettled)
        const nextBack = applySide('back', backSettled)
        setMagicFront(nextFront)
        setMagicBack(nextBack)

        const primary = activeSide === 'back' ? nextBack : nextFront
        setMagicResult(primary.result)
        if (primary.lookObjectUrl) {
          magicLookUrlRef.current = primary.lookObjectUrl
          setMagicLookUrl(primary.lookObjectUrl)
        }

        const bothFailed = nextFront.phase === 'failed' && nextBack.phase === 'failed'
        const safetyFail =
          isMagicSafetyRefusal(nextFront.error) || isMagicSafetyRefusal(nextBack.error)
        if (bothFailed) {
          setMagicPhase('failed')
          setMagicError(
            safetyFail
              ? 'Magic could not finish under the image provider safety rules. Edit the sketch, then start a new Front/Back Magic.'
              : 'Front and Back Magic did not finish. Retry the failed side.',
          )
          return
        }
        if (nextFront.phase === 'failed' || nextBack.phase === 'failed') {
          setMagicError(
            safetyFail
              ? 'One side was refused by the image provider safety rules. Edit that side, then start a new Magic operation.'
              : 'One side needs a retry — use Retry front/back below.',
          )
        }
        setMagicPhase('ready')
        return
      }

      const frontOnly = sideHasInk(frontBag) && !sideHasInk(backBag)
      const backOnly = sideHasInk(backBag) && !sideHasInk(frontBag)
      let magicSide: StudioPaperSide = activeSide
      if (backOnly) magicSide = 'back'
      else if (frontOnly) magicSide = 'front'
      else if (!sideHasInk(frontBag) && !sideHasInk(backBag)) {
        setMagicPhase('failed')
        setMagicError('Add ink to your sketch before running Magic.')
        return
      }

      const bagForSide = magicSide === 'back' ? backBag : frontBag
      const [captured, fabricSwatch] = await Promise.all([
        captureSide(magicSide),
        captureFabricSwatchForMagic(bagForSide.fills),
      ])
      if (controller.signal.aborted) return
      const sketchUrl = URL.createObjectURL(captured.blob)
      magicSketchUrlRef.current = sketchUrl
      setMagicSketchUrl(sketchUrl)

      setMagicPhase('submitting')
      // Front-only / single-side: same garment material identity as Dual Magic.
      const garmentSpec = buildSharedGarmentSpec(doc, 'polish concept')
      const job = await enqueueSketchPolish({
        imageBase64: captured.dataUrl,
        ...(fabricSwatch ? { fabricSwatchBase64: fabricSwatch.dataUrl } : {}),
        notes: 'polish concept',
        designId,
        studio_side: magicSide,
        reference_model_id: modelId,
        shared_garment_spec: garmentSpec,
        source_revision: doc.clientRevision,
        content_fingerprint: draftContentFingerprint(doc),
        signal: controller.signal,
      })
      setMagicJobId(job.id)
      persistMagicJobId(user.id, job.id)

      setMagicPhase('polling')
      const settled = await settleMagicJobWithImage(job.id, controller.signal)
      const look = settled.look
      setMagicResult(look)
      if (look.status === 'failed') {
        setMagicPhase('failed')
        setMagicError(look.summary)
        return
      }
      if (settled.lookObjectUrl) {
        magicLookUrlRef.current = settled.lookObjectUrl
        setMagicLookUrl(settled.lookObjectUrl)
      }
      setMagicPhase('ready')
    } catch (err) {
      if (controller.signal.aborted) {
        setMagicPhase('failed')
        setMagicError('Magic wait cancelled. Your sketch is unchanged — recover if the job already finished.')
        return
      }
      if (err instanceof DualPolishUnavailableError) {
        setMagicPhase('failed')
        setMagicError(err.message)
        setMagicDualActive(false)
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
  }, [
    activeSide,
    dualMagicEnabled,
    frontBackEnabled,
    publishStudioNotice,
    referenceOpacity,
    referenceUrl,
    referenceUrlForDocument,
    revokeMagicUrls,
    user?.id,
  ])

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

  const recoverDualMagicOperation = useCallback(
    async (frontJobId: string, backJobId: string, signal: AbortSignal) => {
      setMagicDualActive(true)
      setMagicFront({ ...emptyMagicSide(), phase: 'polling' })
      setMagicBack({ ...emptyMagicSide(), phase: 'polling' })
      const [frontSettled, backSettled] = await Promise.all([
        settleMagicJobWithImage(frontJobId, signal),
        settleMagicJobWithImage(backJobId, signal),
      ])
      const applySide = (
        side: StudioPaperSide,
        settled: Awaited<ReturnType<typeof settleMagicJobWithImage>>,
      ): MagicSidePanelState => {
        const failed = settled.look.status === 'failed'
        if (settled.lookObjectUrl) {
          magicSideLookUrlsRef.current[side] = settled.lookObjectUrl
        }
        return {
          phase: failed ? 'failed' : 'ready',
          result: settled.look,
          lookObjectUrl: settled.lookObjectUrl,
          sketchObjectUrl: magicSideSketchUrlsRef.current[side],
          error: failed ? settled.look.summary : null,
          canRetry: failed,
        }
      }
      const nextFront = applySide('front', frontSettled)
      const nextBack = applySide('back', backSettled)
      setMagicFront(nextFront)
      setMagicBack(nextBack)
      const primary = activeSide === 'back' ? nextBack : nextFront
      setMagicResult(primary.result)
      if (primary.lookObjectUrl) {
        magicLookUrlRef.current = primary.lookObjectUrl
        setMagicLookUrl(primary.lookObjectUrl)
      }
      setMagicPhase('ready')
    },
    [activeSide],
  )

  const recoverLastMagic = useCallback(() => {
    if (!user?.id) return
    if (magicInFlightRef.current) {
      setMagicOpen(true)
      return
    }
    const storedOp = readMagicOperation(user.id)
    const legacyJobId = magicJobId || readMagicJobId(user.id)
    // Dual ops persist operationId before enqueue; job ids may be missing if the
    // POST response was lost — still open recovery and resolve via operations API.
    if (!storedOp?.operationId && !legacyJobId) {
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
    if (storedOp) setMagicOperationId(storedOp.operationId)

    const run = (async () => {
      if (storedOp?.operationId) {
        const dual = await resolveDualMagicJobIds(user.id, controller.signal)
        if (dual) {
          setMagicOperationId(dual.operationId)
          setMagicJobId(dual.frontJobId)
          await recoverDualMagicOperation(dual.frontJobId, dual.backJobId, controller.signal)
          return
        }
        // Operation known but jobs not listed yet (delayed) or incomplete — do not
        // fall through to a misleading single-job recover or re-enqueue.
        throw new Error(
          'Magic jobs for this operation are not ready yet. Wait briefly and recover again — no new render was started.',
        )
      }
      await applySettledMagicJob(legacyJobId!, controller.signal)
    })()

    void run
      .catch((err) => {
        if (controller.signal.aborted) return
        setMagicPhase('failed')
        setMagicError(err instanceof Error ? err.message : 'Unable to recover Magic result.')
      })
      .finally(() => {
        magicInFlightRef.current = false
      })
  }, [applySettledMagicJob, magicJobId, recoverDualMagicOperation, user?.id])

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
    if (magicDualActive) {
      const side = magicDualViewSide
      const url = magicSideLookUrlsRef.current[side]
      if (!url) return
      void fetch(url)
        .then((r) => r.blob())
        .then((blob) => downloadBlob(blob, exportFilename(`look-${side}`)))
        .catch(() => setMagicError('Could not download the look image.'))
      return
    }
    if (!magicLookUrlRef.current) return
    void fetch(magicLookUrlRef.current)
      .then((r) => r.blob())
      .then((blob) => downloadBlob(blob, exportFilename('look')))
      .catch(() => setMagicError('Could not download the look image.'))
  }, [magicDualActive, magicDualViewSide])

  const downloadMagicSide = useCallback(
    (side: StudioPaperSide) => {
      const url = magicSideLookUrlsRef.current[side]
      if (!url) return
      void fetch(url)
        .then((r) => r.blob())
        .then((blob) => downloadBlob(blob, exportFilename(`look-${side}`)))
        .catch(() => setMagicError(`Could not download the ${side} look.`))
    },
    [],
  )

  const retryMagicSide = useCallback(
    (side: StudioPaperSide) => {
      if (!user?.id || magicInFlightRef.current) return
      if (!dualMagicEnabled) {
        setComingSoon(FRONT_BACK_MAGIC_COMING_SOON)
        return
      }
      const stored = readMagicOperation(user.id)
      const operationId = magicOperationId ?? stored?.operationId
      if (!operationId || !stored) {
        setMagicError('No Magic operation to retry.')
        return
      }
      const doc = authoritativeDocRef.current
      const liveFingerprint = draftContentFingerprint(doc)
      if (
        typeof stored.contentFingerprint === 'string' &&
        stored.contentFingerprint &&
        liveFingerprint !== stored.contentFingerprint
      ) {
        setMagicError('Sketch changed since Magic started — start a new Front/Back Magic instead of retrying.')
        return
      }
      if (
        typeof stored.sourceRevision === 'number' &&
        doc.clientRevision !== stored.sourceRevision
      ) {
        setMagicError('Sketch changed since Magic started — start a new Front/Back Magic instead of retrying.')
        return
      }
      if (!stored.sharedGarmentSpec) {
        setMagicError('Missing garment identity for retry. Recover the last result or run Magic again.')
        return
      }

      magicInFlightRef.current = true
      setMagicError(null)
      setMagicOpen(true)
      setMagicPhase('polling')
      const setter = side === 'front' ? setMagicFront : setMagicBack
      setter((prev) => ({ ...prev, phase: 'polling', error: null, canRetry: false }))

      magicAbortRef.current?.abort()
      const controller = new AbortController()
      magicAbortRef.current = controller

      void (async () => {
        try {
          const bag =
            side === 'front'
              ? { strokes: doc.strokes, fills: doc.fills ?? [] }
              : doc.back ?? { strokes: [], fills: [] }
          const [cap, fabricSwatch] = await Promise.all([
            captureSketchForMagic({
              strokes: bag.strokes,
              fills: bag.fills,
              referenceUrl: referenceUrlForDocument(doc, side),
              referenceOpacity: doc.dimmed ? 0.4 : 1,
            }),
            captureFabricSwatchForMagic(bag.fills),
          ])

          // Persist a new per-attempt key before POST so lost responses can replay.
          const idempotencyKey = allocateMagicRetryIdempotencyKey(user.id, side)
          if (!idempotencyKey) {
            throw new Error('Could not allocate a retry idempotency key.')
          }

          let jobId: string
          try {
            const job = await enqueueSketchPolish({
              imageBase64: cap.dataUrl,
              ...(fabricSwatch ? { fabricSwatchBase64: fabricSwatch.dataUrl } : {}),
              notes: `polish concept (${side}) retry`,
              designId: stored.designId ?? designIdRef.current,
              magic_operation_id: operationId,
              studio_side: side,
              reference_model_id: stored.referenceModelId ?? doc.model,
              idempotency_key: idempotencyKey,
              shared_garment_spec: stored.sharedGarmentSpec,
              source_revision: stored.sourceRevision,
              content_fingerprint: stored.contentFingerprint,
              signal: controller.signal,
            })
            jobId = job.id
            patchMagicOperationJob(user.id, side, job.id, idempotencyKey)
          } catch (err) {
            // Uncertain / lost response: recover latest job for this side — never mint a new key.
            if (
              err instanceof ApiError &&
              (err.status === 0 || err.status >= 500 || err.status === 409)
            ) {
              const listed = await fetchMagicOperationJobs(operationId, controller.signal)
              const mapped = mapMagicOperationJobsBySide(listed.jobs ?? [])
              const recoveredId = side === 'front' ? mapped.frontJobId : mapped.backJobId
              if (!recoveredId) throw err
              jobId = recoveredId
              patchMagicOperationJob(user.id, side, recoveredId, idempotencyKey)
            } else {
              throw err
            }
          }

          const settled = await settleMagicJobWithImage(jobId, controller.signal)
          const failed = settled.look.status === 'failed'
          if (magicSideLookUrlsRef.current[side]) {
            URL.revokeObjectURL(magicSideLookUrlsRef.current[side]!)
          }
          if (settled.lookObjectUrl) magicSideLookUrlsRef.current[side] = settled.lookObjectUrl
          const next: MagicSidePanelState = {
            phase: failed ? 'failed' : 'ready',
            result: settled.look,
            lookObjectUrl: settled.lookObjectUrl,
            sketchObjectUrl: magicSideSketchUrlsRef.current[side],
            error: failed ? settled.look.summary : null,
            canRetry: failed,
          }
          setter(next)
          if (magicDualViewSide === side) {
            setMagicResult(settled.look)
            if (settled.lookObjectUrl) {
              magicLookUrlRef.current = settled.lookObjectUrl
              setMagicLookUrl(settled.lookObjectUrl)
            }
          }
          setMagicPhase('ready')
        } catch (err) {
          if (controller.signal.aborted) return
          const message = err instanceof Error ? err.message : 'Retry failed.'
          setter((prev) => ({
            ...prev,
            phase: 'failed',
            error: message,
            canRetry: true,
          }))
          setMagicError(message)
          setMagicPhase('ready')
        } finally {
          magicInFlightRef.current = false
        }
      })()
    },
    [dualMagicEnabled, magicDualViewSide, magicOperationId, referenceUrlForDocument, user?.id],
  )

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

  const resolveDamagedCloudContinueLocal = useCallback(() => {
    if (!damagedCloud) return
    damagedCloudBlockRef.current = true
    setDamagedCloudDialogOpen(false)
    setSaveStatus(damagedCloud.hasLocalRecovery ? 'local-only' : 'idle')
    publishStudioNotice(
      'Automatic cloud sync remains paused. The damaged private draft was not changed. Open recovery again when you are ready to replace it deliberately.',
    )
  }, [damagedCloud, publishStudioNotice])

  const reopenDamagedCloudRecovery = useCallback(() => {
    if (!damagedCloud) return
    setDamagedCloudDialogOpen(true)
  }, [damagedCloud])

  const resolveDamagedCloudReplaceCloud = useCallback(() => {
    if (!damagedCloud || !user?.id) return
    const localDoc = authoritativeDocRef.current
    if (!documentHasAnyInk(localDoc) && !damagedCloud.hasLocalRecovery) {
      setSaveError('Add or restore a sketch on this device before replacing the damaged cloud draft.')
      return
    }
    const expectedRevision = damagedCloud.expectedRevision
    if (expectedRevision == null) {
      setSaveError(
        'Could not determine the cloud draft revision for a safe replace. The damaged cloud copy was left unchanged.',
      )
      return
    }
    damagedCloudBlockRef.current = true
    void (async () => {
      setSaveStatus('saving')
      setSaveError(null)
      const result = await commitReplaceDamagedCloudDraft({
        userId: user.id,
        designId: damagedCloud.designId,
        local: localDoc,
        expectedRevision,
      })
      if (result.ok) {
        damagedCloudBlockRef.current = false
        setDamagedCloud(null)
        setDamagedCloudDialogOpen(false)
        authoritativeDocRef.current = result.document
        designIdRef.current = result.designId
        syncedRevisionRef.current = result.syncedRevision
        syncedFingerprintRef.current = result.fingerprint
        applyDocument(result.document, result.designId)
        setSaveStatus('saved')
        publishStudioNotice('Damaged cloud draft was replaced with this device’s copy after your confirmation.')
        return
      }
      damagedCloudBlockRef.current = true
      setSaveError(result.error)
      setSaveStatus(result.localPersisted ? 'local-only' : 'error')
      if (result.conflict) {
        conflictOpenRef.current = true
        setDraftConflict(result.conflict)
      }
    })()
  }, [applyDocument, damagedCloud, publishStudioNotice, user?.id])

  /** Export the authoritative document (plus any session-only custom reference) as PNG. */
  const exportSidePng = useCallback(
    async (side: StudioPaperSide | 'visible' | 'sheet') => {
      if (exportingRef.current) return
      exportingRef.current = true
      setExporting(true)
      const doc = authoritativeDocRef.current
      const visibleSide = normalizeActiveSide(doc)
      const targetSide = side === 'visible' ? visibleSide : side
      try {
        if (side === ('sheet' as const) && frontBackEnabled && documentHasAnyInk(doc)) {
          const backBag = doc.back ?? { strokes: [], fills: [] }
          const { blob, referenceIncluded } = await exportFrontBackSheetPng({
            front: {
              strokes: doc.strokes,
              fills: doc.fills ?? [],
              referenceUrl: referenceUrlForDocument(doc, 'front'),
              referenceOpacity: doc.dimmed ? 0.4 : 1,
            },
            back: {
              strokes: backBag.strokes,
              fills: backBag.fills ?? [],
              referenceUrl: referenceUrlForDocument(doc, 'back'),
              referenceOpacity: doc.dimmed ? 0.4 : 1,
            },
          })
          downloadBlob(blob, exportFilename(null).replace('.png', '-front-back.png'))
          publishStudioNotice(
            referenceIncluded
              ? 'Front + back sheet exported. Check your downloads.'
              : EXPORT_NO_REFERENCE,
          )
          return
        }
        const bag =
          targetSide === 'back'
            ? doc.back ?? { strokes: [], fills: [] }
            : { strokes: doc.strokes, fills: doc.fills ?? [] }
        const refSide: StudioPaperSide = targetSide === 'back' ? 'back' : 'front'
        const { blob, referenceIncluded } = await exportSketchPng({
          strokes: bag.strokes,
          fills: bag.fills,
          referenceUrl: referenceUrlForDocument(doc, refSide),
          referenceOpacity: doc.dimmed ? 0.4 : 1,
        })
        const suffix =
          side === 'back' ? '-back' : side === 'front' ? '-front' : ''
        downloadBlob(blob, exportFilename(null).replace('.png', `${suffix}.png`))
        const wantedReference = referenceUrlForDocument(doc, refSide) !== null
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
    },
    [frontBackEnabled, publishStudioNotice, referenceUrlForDocument],
  )

  const exportPng = useCallback(async () => {
    await exportSidePng('visible')
  }, [exportSidePng])

  const beginSaveDesign = useCallback(() => {
    if (!ready || saveInFlightRef.current) return
    const doc = authoritativeDocRef.current
    if (!documentHasAnyInk(doc)) {
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
    if (conflictOpenRef.current || damagedCloudBlockRef.current) return 'conflict'
    if (!bootedRef.current) return 'unsynced'
    if (cloudDirtyRef.current || cloudInFlightRef.current > 0) return 'unsynced'
    const doc = authoritativeDocRef.current
    if (designIdRef.current === null) {
      return documentHasAnyInk(doc) ? 'unsynced' : 'clean-empty'
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
        !documentHasAnyInk(authoritativeDocRef.current)
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
    frontBackEnabled,
    activeSide,
    rearAvailable,
    changeActiveSide,
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
    magicCanRecover: Boolean(
      magicJobId ||
        (user?.id &&
          (readMagicJobId(user.id) || Boolean(readMagicOperation(user.id)?.operationId))),
    ),
    closeMagicPanel,
    cancelMagicWait,
    recoverLastMagic,
    downloadMagicLook,
    downloadMagicSide,
    magicDualActive,
    magicOperationId,
    magicDualViewSide,
    setMagicDualViewSide,
    magicFront,
    magicBack,
    retryMagicSide,
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
    damagedCloud,
    damagedCloudDialogOpen,
    resolveDamagedCloudContinueLocal,
    resolveDamagedCloudReplaceCloud,
    reopenDamagedCloudRecovery,
    exporting,
    exportPng,
    exportSidePng,
    hasBackInk: sideHasInk({ strokes: backStrokes, fills: backFills }),
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
