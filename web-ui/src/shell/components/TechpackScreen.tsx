import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Sparkles } from 'lucide-react'
import { useAuthJobImage } from '@/hooks/useAuthJobImage'
import {
  fetchTechpackPdfBlob,
  generateTechpackAiProfessionalOneTap,
  getLatestTechpackAiRun,
  getTechpackAiRun,
  getTechpackAiStatus,
  getTechpackDraft,
  updateTechpackDraft,
  type TechpackAiProgress,
  type TechpackAiRun,
  type TechpackAiStatus,
  type TechpackDraft,
  type TechpackPiece,
  type TechpackSpecV2,
} from '@/services/techpacksApi'
import { DetailsEditorSheet } from '@/shell/components/techpack/DetailsEditorSheet'
import { GenerateAiPdfOverlay } from '@/shell/components/techpack/GenerateAiPdfOverlay'
import {
  buildEditorPersistSnapshot,
  editorPersistFingerprint,
} from '@/shell/components/techpack/editorPersistSnapshot'
import {
  asRecord,
  wrapSpecForEditing,
} from '@/shell/components/techpack/pieceHelpers'
import styles from './TechpackScreen.module.css'

const BUILD_VERSION =
  (import.meta.env.VITE_BUILD_SHA as string | undefined)?.slice(0, 8) ||
  (import.meta.env.VITE_APP_VERSION as string | undefined) ||
  'unknown'

type Props = {
  draftId: string
  onBack: () => void
}

type WorkflowStage = 'understand' | 'customize' | 'measurements' | 'generate'

export function TechpackScreen({ draftId, onBack }: Props) {
  const [draft, setDraft] = useState<TechpackDraft | null>(null)
  const [title, setTitle] = useState('')
  const [styleCode, setStyleCode] = useState('')
  const [spec, setSpec] = useState<TechpackSpecV2 | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [aiStatus, setAiStatus] = useState<TechpackAiStatus | null>(null)
  const [generateProgress, setGenerateProgress] = useState<string | null>(null)
  const [progressPhase, setProgressPhase] = useState<string | null>(null)
  const [progressOpen, setProgressOpen] = useState(false)
  const [progressReady, setProgressReady] = useState(false)
  const [progressReconnect, setProgressReconnect] = useState(false)
  const [, setLastRunId] = useState<string | null>(null)
  const [readyExportId, setReadyExportId] = useState<string | null>(null)
  const [readyFilename, setReadyFilename] = useState<string | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [intentIdempotencyKey, setIntentIdempotencyKey] = useState<string | null>(null)
  /** Bumps when the saved fingerprint changes so React can recompute editorDirty. */
  const [savedTick, setSavedTick] = useState(0)
  const pollAbortRef = useRef<AbortController | null>(null)
  const autosaveTimer = useRef<number | null>(null)
  const savedFingerprintRef = useRef<string | null>(null)
  const titleRef = useRef(title)
  const styleCodeRef = useRef(styleCode)
  const specRef = useRef(spec)
  const saveInFlightRef = useRef(false)
  const saveEpochRef = useRef(0)
  const rerunAfterFlightRef = useRef(false)
  const aiErrorRef = useRef<HTMLParagraphElement>(null)

  titleRef.current = title
  styleCodeRef.current = styleCode
  specRef.current = spec

  const markSavedFingerprint = useCallback(
    (nextTitle: string, nextStyleCode: string, nextSpec: TechpackSpecV2 | null | undefined) => {
      savedFingerprintRef.current = editorPersistFingerprint(nextTitle, nextStyleCode, nextSpec)
      setSavedTick((n) => n + 1)
    },
    [],
  )

  const frontImg = useAuthJobImage(draft?.front_job_id ?? null, Boolean(draft?.front_job_id))

  const professionalAvailable = Boolean(
    aiStatus?.enabled && (aiStatus.professional_available ?? false),
  )

  const professionalDisabledReason = useMemo(() => {
    if (!aiStatus) return 'AI Professional status unavailable — try again in a moment.'
    if (!aiStatus.enabled || !aiStatus.professional_available) {
      if (!aiStatus.api_key_present) {
        return 'AI Professional unavailable — provider credentials are not configured.'
      }
      if (!(aiStatus.spend_ceiling_usd && aiStatus.spend_ceiling_usd > 0)) {
        return 'AI Professional unavailable — spend ceiling is not configured.'
      }
      if (!aiStatus.configured_flag) {
        return 'AI Professional unavailable — feature flag is off.'
      }
      return (
        aiStatus.note ||
        'AI Professional unavailable — check enablement, API key, and spend ceiling.'
      )
    }
    return null
  }, [aiStatus])

  const pieces = spec?.outfit?.pieces ?? []
  // Reactive dirty vs last-saved editable values (excludes server-owned ai metadata).
  const editorDirty = useMemo(() => {
    // savedTick forces recompute after markSavedFingerprint updates the ref.
    void savedTick
    if (savedFingerprintRef.current == null) return false
    return editorPersistFingerprint(title, styleCode, spec) !== savedFingerprintRef.current
  }, [title, styleCode, spec, savedTick])
  // PDF is outdated if the server says so OR the designer has local unsaved edits.
  const dirtySinceGeneration =
    Boolean(spec?.ai?.dirty_since_generation) || editorDirty
  const hasReadyPdf = Boolean(readyExportId) && !dirtySinceGeneration

  const hydrate = useCallback(
    (row: TechpackDraft, opts: { markSaved?: boolean } = {}) => {
      setDraft(row)
      setTitle(row.title)
      setStyleCode(row.style_code)
      const wrapped = wrapSpecForEditing(asRecord(row.spec))
      setSpec(wrapped.spec)
      if (opts.markSaved !== false) {
        markSavedFingerprint(row.title, row.style_code, wrapped.spec)
      }
      const ai = wrapped.spec.ai
      if (ai?.last_run_id) setLastRunId(String(ai.last_run_id))
      const exportFromAi = ai && typeof ai === 'object' ? (ai as { export_id?: string }).export_id : null
      if (exportFromAi && !ai?.dirty_since_generation) {
        setReadyExportId(String(exportFromAi))
      }
      const latest = row.latest_export
      const meta = latest?.metadata ?? {}
      if (
        latest &&
        meta &&
        typeof meta === 'object' &&
        Boolean((meta as { is_professional?: boolean }).is_professional) &&
        !ai?.dirty_since_generation
      ) {
        setReadyExportId(latest.id)
        setReadyFilename(latest.filename)
      }
    },
    [markSavedFingerprint],
  )

  /**
   * Update server bookkeeping + AI validity/lineage without replacing editable form values.
   * Preserves focus/caret and must not change the editable dirty fingerprint.
   */
  const applyServerMetaOnly = useCallback((row: TechpackDraft) => {
    setDraft((prev) => {
      if (!prev) return row
      return {
        ...prev,
        revision: row.revision,
        updated_at: row.updated_at,
        status: row.status,
        verification: row.verification,
        latest_export: row.latest_export,
      }
    })
    const serverAi = wrapSpecForEditing(asRecord(row.spec)).spec.ai
    setSpec((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        ai: {
          ...(prev.ai ?? {}),
          ...(serverAi ?? {}),
        },
      }
    })
    const serverAiRec = serverAi && typeof serverAi === 'object' ? serverAi : null
    if (serverAiRec?.last_run_id) setLastRunId(String(serverAiRec.last_run_id))
    // Keep export identity for outdated-PDF messaging; Download gating uses dirtySinceGeneration.
    const exportFromAi =
      serverAiRec && typeof serverAiRec.export_id === 'string' ? serverAiRec.export_id : null
    if (exportFromAi) setReadyExportId(String(exportFromAi))
    const latest = row.latest_export
    const meta = latest?.metadata ?? {}
    if (
      latest &&
      meta &&
      typeof meta === 'object' &&
      Boolean((meta as { is_professional?: boolean }).is_professional)
    ) {
      setReadyExportId(latest.id)
      setReadyFilename(latest.filename)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    Promise.all([
      getTechpackDraft(draftId, controller.signal),
      getTechpackAiStatus(controller.signal).catch(() => null),
    ])
      .then(([row, status]) => {
        if (controller.signal.aborted) return
        hydrate(row)
        if (status) setAiStatus(status)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Could not load tech pack')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [draftId, hydrate])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const prev = document.title
    document.title = `FashionRise · App ${BUILD_VERSION}`
    return () => {
      document.title = prev
    }
  }, [])

  const isEditorDirty = useCallback(() => {
    if (savedFingerprintRef.current == null) return false
    return (
      editorPersistFingerprint(titleRef.current, styleCodeRef.current, specRef.current) !==
      savedFingerprintRef.current
    )
  }, [])

  const persist = useCallback(
    async (opts: { silent?: boolean; force?: boolean } = {}) => {
      if (!opts.force && !isEditorDirty()) {
        return draft
      }
      if (saveInFlightRef.current) {
        rerunAfterFlightRef.current = true
        return null
      }

      const epoch = ++saveEpochRef.current
      const snapshot = buildEditorPersistSnapshot(
        titleRef.current,
        styleCodeRef.current,
        specRef.current,
      )

      saveInFlightRef.current = true
      if (!opts.silent) setBusy(true)
      try {
        const next = await updateTechpackDraft(draftId, {
          title: snapshot.title,
          style_code: snapshot.style_code,
          spec: snapshot.spec,
        })
        // Ignore stale responses that finished after a newer save started.
        if (epoch !== saveEpochRef.current) {
          return null
        }
        // Mark clean from editable values only (ai metadata excluded from fingerprint).
        markSavedFingerprint(snapshot.title, snapshot.style_code, snapshot.spec)
        // Sync server-owned AI validity (dirty_since_generation, export_id, …) without form replace.
        applyServerMetaOnly(next)
        setSaveError(null)
        return next
      } catch (err) {
        if (epoch !== saveEpochRef.current) {
          return null
        }
        const message = err instanceof Error ? err.message : 'Could not save draft'
        setSaveError(message)
        if (!opts.silent) {
          setError(message)
        }
        return null
      } finally {
        saveInFlightRef.current = false
        if (!opts.silent) setBusy(false)
        if (rerunAfterFlightRef.current) {
          rerunAfterFlightRef.current = false
          if (isEditorDirty()) {
            void persist({ silent: true })
          }
        }
      }
    },
    [applyServerMetaOnly, draft, draftId, isEditorDirty, markSavedFingerprint],
  )

  // Quiet autosave: only when editable values actually differ from last saved snapshot.
  useEffect(() => {
    if (!detailsOpen || !spec) return
    if (!isEditorDirty()) return
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
    autosaveTimer.current = window.setTimeout(() => {
      if (!isEditorDirty()) return
      void persist({ silent: true })
    }, 700)
    return () => {
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current)
    }
  }, [detailsOpen, spec, title, styleCode, persist, isEditorDirty])

  const updatePiece = (pieceId: string, updater: (piece: TechpackPiece) => TechpackPiece) => {
    setSpec((prev) => {
      if (!prev?.outfit) return prev
      const nextPieces = prev.outfit.pieces.map((p) => (p.id === pieceId ? updater(p) : p))
      return {
        ...prev,
        outfit: { ...prev.outfit, pieces: nextPieces, piece_count: nextPieces.length },
      }
    })
  }

  const applyProgress = (progress?: TechpackAiProgress | null, fallback?: string) => {
    if (progress?.phase) setProgressPhase(progress.phase)
    if (progress?.message) setGenerateProgress(progress.message)
    else if (fallback) setGenerateProgress(fallback)
  }

  const bindReadyFromRun = (row: {
    export_id?: string | null
    pdf_ready?: boolean
    pdf_filename?: string | null
    result?: Record<string, unknown> | null
    progress?: TechpackAiProgress | null
  }) => {
    const exportId =
      row.export_id ||
      (typeof row.result?.export_id === 'string' ? row.result.export_id : null)
    const pdfReady = Boolean(row.pdf_ready ?? row.result?.pdf_ready)
    if (pdfReady && exportId) {
      setReadyExportId(String(exportId))
      setReadyFilename(
        row.pdf_filename ||
          (typeof row.result?.pdf_filename === 'string' ? row.result.pdf_filename : null),
      )
      setProgressReady(true)
      setProgressPhase('ready')
      setGenerateProgress('Your AI Technical Pack is ready')
      setProgressOpen(true)
      return true
    }
    return false
  }

  const pollRunUntilSettled = async (runId: string) => {
    pollAbortRef.current?.abort()
    const ac = new AbortController()
    pollAbortRef.current = ac
    let consecutiveErrors = 0
    for (let i = 0; i < 600; i += 1) {
      if (ac.signal.aborted) return null
      await new Promise((r) => window.setTimeout(r, 1500))
      try {
        const row = await getTechpackAiRun(runId, ac.signal)
        consecutiveErrors = 0
        setProgressReconnect(false)
        applyProgress(row.progress ?? null)
        if (
          row.status === 'completed' ||
          row.status === 'failed' ||
          row.status === 'reconciliation_required'
        ) {
          return row
        }
      } catch {
        consecutiveErrors += 1
        if (consecutiveErrors >= 2) setProgressReconnect(true)
      }
    }
    return null
  }

  const finishFromGenerateResult = async (result: {
    run_id: string
    status: string
    artifacts?: TechpackAiRun['artifacts']
    analysis_summary?: string | null
    failed_sections?: string[]
    actual_cost_usd_cents?: number
    cost_usd_cents?: number
    progress?: TechpackAiProgress | null
    error_message?: string | null
    export_id?: string | null
    pdf_ready?: boolean
    pdf_filename?: string | null
    result?: Record<string, unknown> | null
  }) => {
    setLastRunId(result.run_id ?? null)
    applyProgress(result.progress ?? null, 'Your AI Technical Pack is ready')
    const refreshed = await getTechpackDraft(draftId)
    hydrate(refreshed)

    if (result.status === 'failed') {
      setProgressReady(false)
      setProgressOpen(false)
      setError(
        result.error_message ||
          'AI Professional generation failed. Your design is safe. Try again when ready.',
      )
      setGenerateProgress(null)
      return
    }

    if (result.status === 'reconciliation_required') {
      // Attempt PDF recovery via status fields; otherwise keep waiting UI honest.
      if (bindReadyFromRun(result)) {
        setNotice('Recovered your AI Technical Pack.')
        return
      }
      setProgressReady(false)
      setProgressOpen(true)
      setError(
        result.error_message ||
          'Generation needs recovery. Your design is safe — do not press Generate again.',
      )
      return
    }

    if (result.status === 'completed') {
      if (bindReadyFromRun(result)) {
        setNotice(null)
        setError(null)
        return
      }
      // Completed illustrations but PDF not yet bound — keep assembling state.
      setProgressReady(false)
      setProgressOpen(true)
      setProgressPhase('assembling')
      setGenerateProgress('Preparing your PDF…')
      // One recovery poll via GET run (server assembles PDF from existing art, $0 AI).
      try {
        const recovered = await getTechpackAiRun(result.run_id)
        if (bindReadyFromRun(recovered)) {
          setNotice(null)
          setError(null)
          return
        }
      } catch {
        /* keep assembling message */
      }
      setError('Illustrations are ready, but the PDF is still preparing. Reopen this screen shortly.')
    }
  }

  const mapGenerationError = (err: unknown): string => {
    const raw = err instanceof Error ? err.message : String(err || 'Generation failed')
    if (/REASONING_EFFORT|server configuration problem/i.test(raw)) {
      return (
        'AI Professional could not start because of a server configuration problem. ' +
        'Your design is safe. Please try again after the issue is fixed.'
      )
    }
    if (/Technical generation failed:/i.test(raw)) {
      return 'AI Professional generation failed. Your design is safe.'
    }
    return raw
  }

  const runOneTapGenerate = async () => {
    if (!professionalAvailable) {
      setError(professionalDisabledReason || 'AI Professional is not available for this account.')
      return
    }
    if (busy) return

    // Already have a valid Professional PDF for this revision — show Download, no paid call.
    if (hasReadyPdf && readyExportId) {
      setProgressOpen(true)
      setProgressReady(true)
      setProgressPhase('ready')
      setGenerateProgress('Your AI Technical Pack is ready')
      return
    }

    setBusy(true)
    setError(null)
    setNotice(null)
    setProgressOpen(true)
    setProgressReady(false)
    setProgressReconnect(false)
    setProgressPhase('preparing')
    setGenerateProgress('Analyzing your design…')
    try {
      await persist({ silent: true })
      const revision = draft?.revision ?? 1
      const idem =
        intentIdempotencyKey || `one-tap-${draftId}-r${revision}`
      setIntentIdempotencyKey(idem)
      const accepted = await generateTechpackAiProfessionalOneTap(draftId, {
        idempotency_key: idem,
        propose_back: true,
      })
      const runId = accepted.run_id
      setLastRunId(runId)
      applyProgress(accepted.progress ?? null, 'Analyzing your design…')

      if (accepted.status === 'completed') {
        await finishFromGenerateResult(accepted)
        setIntentIdempotencyKey(null)
        return
      }
      if (accepted.status === 'failed' || accepted.status === 'reconciliation_required') {
        await finishFromGenerateResult(accepted)
        setIntentIdempotencyKey(null)
        return
      }

      const settled = await pollRunUntilSettled(runId)
      if (!settled) {
        setNotice(
          'Still working on FashionRise servers. Reopen Create Real Design to resume this same run.',
        )
        setProgressReconnect(true)
        return
      }
      await finishFromGenerateResult({
        run_id: settled.id,
        status: settled.status,
        artifacts: settled.artifacts,
        analysis_summary:
          typeof settled.result?.analysis_summary === 'string'
            ? settled.result.analysis_summary
            : null,
        failed_sections: Array.isArray(settled.result?.failed_sections)
          ? (settled.result?.failed_sections as string[])
          : [],
        actual_cost_usd_cents: settled.cost_usd_cents,
        progress: settled.progress,
        error_message: settled.error_message,
        export_id: settled.export_id,
        pdf_ready: settled.pdf_ready,
        pdf_filename: settled.pdf_filename,
        result: settled.result,
      })
      if (settled.status === 'completed' && settled.pdf_ready) setIntentIdempotencyKey(null)
    } catch (err) {
      try {
        const latest = await getLatestTechpackAiRun(draftId)
        if (
          latest &&
          (latest.status === 'queued' ||
            latest.status === 'running' ||
            latest.status === 'completed')
        ) {
          setLastRunId(latest.id)
          applyProgress(latest.progress ?? null)
          if (latest.status === 'completed') {
            await finishFromGenerateResult({
              run_id: latest.id,
              status: latest.status,
              artifacts: latest.artifacts,
              progress: latest.progress,
              export_id: latest.export_id,
              pdf_ready: latest.pdf_ready,
              pdf_filename: latest.pdf_filename,
              result: latest.result,
              actual_cost_usd_cents: latest.cost_usd_cents,
            })
            setIntentIdempotencyKey(null)
            return
          }
          const settled = await pollRunUntilSettled(latest.id)
          if (settled) {
            await finishFromGenerateResult({
              run_id: settled.id,
              status: settled.status,
              artifacts: settled.artifacts,
              progress: settled.progress,
              export_id: settled.export_id,
              pdf_ready: settled.pdf_ready,
              pdf_filename: settled.pdf_filename,
              result: settled.result,
              actual_cost_usd_cents: settled.cost_usd_cents,
              error_message: settled.error_message,
            })
            if (settled.status === 'completed') setIntentIdempotencyKey(null)
            return
          }
        }
      } catch {
        /* fall through */
      }
      setError(mapGenerationError(err))
      setProgressOpen(false)
      setProgressReady(false)
      setGenerateProgress(null)
      window.requestAnimationFrame(() => {
        aiErrorRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
      })
    } finally {
      setBusy(false)
    }
  }

  // Resume in-flight / completed Professional run after reload (never auto-starts paid work).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const latest = await getLatestTechpackAiRun(draftId)
        if (cancelled || !latest) return
        if (latest.status === 'queued' || latest.status === 'running') {
          setLastRunId(latest.id)
          setProgressOpen(true)
          setProgressReady(false)
          applyProgress(latest.progress ?? null, 'Analyzing your design…')
          setBusy(true)
          const settled = await pollRunUntilSettled(latest.id)
          if (cancelled) return
          if (settled) {
            await finishFromGenerateResult({
              run_id: settled.id,
              status: settled.status,
              artifacts: settled.artifacts,
              progress: settled.progress,
              export_id: settled.export_id,
              pdf_ready: settled.pdf_ready,
              pdf_filename: settled.pdf_filename,
              result: settled.result,
              actual_cost_usd_cents: settled.cost_usd_cents,
              error_message: settled.error_message,
            })
          } else {
            setProgressReconnect(true)
          }
          setBusy(false)
        } else if (latest.status === 'completed' && latest.stage === 'professional') {
          setLastRunId(latest.id)
          if (latest.pdf_ready && latest.export_id) {
            setReadyExportId(latest.export_id)
            setReadyFilename(latest.pdf_filename ?? null)
            // Show Download immediately when reopening a completed Professional design.
            if (!dirtySinceGeneration) {
              setProgressOpen(true)
              setProgressReady(true)
              setProgressPhase('ready')
              setGenerateProgress('Your AI Technical Pack is ready')
            }
          } else {
            // Recover PDF from existing illustrations (zero AI).
            try {
              const recovered = await getTechpackAiRun(latest.id)
              if (!cancelled && recovered.pdf_ready && recovered.export_id) {
                setReadyExportId(recovered.export_id)
                setReadyFilename(recovered.pdf_filename ?? null)
                if (!dirtySinceGeneration) {
                  setProgressOpen(true)
                  setProgressReady(true)
                  setProgressPhase('ready')
                  setGenerateProgress('Your AI Technical Pack is ready')
                }
              }
            } catch {
              /* ignore */
            }
          }
        }
      } catch {
        /* ignore resume errors */
      }
    })()
    return () => {
      cancelled = true
      pollAbortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId])

  const downloadPdf = async () => {
    const exportId = readyExportId
    if (!exportId) {
      setError('Your AI Technical Pack PDF is not ready yet.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const blob = await fetchTechpackPdfBlob(exportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = readyFilename || `${styleCode || 'FashionRise'}_techpack.pdf`
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setNotice('PDF downloaded.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download PDF')
    } finally {
      setBusy(false)
    }
  }

  const closeDetails = async () => {
    if (autosaveTimer.current) {
      window.clearTimeout(autosaveTimer.current)
      autosaveTimer.current = null
    }
    // Nothing changed — close immediately with zero network writes.
    if (!isEditorDirty() && !saveInFlightRef.current) {
      setSaveError(null)
      setDetailsOpen(false)
      return
    }
    setBusy(true)
    try {
      // Coordinate with an in-flight autosave; never discard newer local edits.
      const started = Date.now()
      while (saveInFlightRef.current && Date.now() - started < 15000) {
        await new Promise((r) => window.setTimeout(r, 40))
      }
      if (!isEditorDirty()) {
        setSaveError(null)
        setDetailsOpen(false)
        return
      }
      const saved = await persist({ silent: false })
      if (saved || !isEditorDirty()) {
        setSaveError(null)
        setDetailsOpen(false)
      }
    } finally {
      setBusy(false)
    }
  }

  const retrySave = () => {
    setSaveError(null)
    void persist({ silent: true })
  }

  if (loading) {
    return (
      <div className={styles.screen}>
        <div className={styles.head}>
          <p className={styles.subtitle}>Loading Create Real Design…</p>
        </div>
      </div>
    )
  }

  if (!draft || !spec) {
    return (
      <div className={styles.screen}>
        <div className={styles.head}>
          <button type="button" className={styles.backBtn} onClick={onBack}>
            <ArrowLeft size={18} aria-hidden /> Back to My Looks
          </button>
          <p className={styles.subtitle} role="alert">
            {error || 'Could not open this design.'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.screen} ${styles.simpleScreen}`}>
      <div className={styles.head}>
        <div>
          <button type="button" className={styles.backBtn} onClick={onBack}>
            <ArrowLeft size={18} aria-hidden /> Back to My Looks
          </button>
          <h1 className={styles.title}>Create Real Design</h1>
          <p className={styles.subtitle}>
            Turn your Magic look into a professional AI technical pack.
          </p>
        </div>
        <span className={styles.pill} data-testid="app-version" title={`App ${BUILD_VERSION}`}>
          App {BUILD_VERSION}
        </span>
      </div>

      {error ? (
        <p ref={aiErrorRef} className={styles.banner} role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className={styles.noticeBanner}>{notice}</p> : null}
      {dirtySinceGeneration && readyExportId ? (
        <p className={styles.noticeBanner}>
          Details changed since your last AI Technical Pack. Generate again to create an updated PDF.
        </p>
      ) : null}

      <div className={styles.simpleBody}>
        <div className={styles.heroVisual}>
          {frontImg.url ? (
            <img src={frontImg.url} alt={title || 'Magic look'} className={styles.heroImage} />
          ) : (
            <div className={styles.heroPlaceholder} aria-hidden />
          )}
        </div>

        <button
          type="button"
          className={styles.detailsLink}
          onClick={() => setDetailsOpen(true)}
        >
          Edit measurements & details
        </button>

        {hasReadyPdf ? (
          <button
            type="button"
            className={styles.primaryCta}
            disabled={busy}
            onClick={() => {
              setProgressOpen(true)
              setProgressReady(true)
              setProgressPhase('ready')
              setGenerateProgress('Your AI Technical Pack is ready')
            }}
          >
            <Sparkles size={18} aria-hidden /> Download PDF
          </button>
        ) : (
          <button
            type="button"
            className={styles.primaryCta}
            disabled={busy || !professionalAvailable}
            onClick={() => void runOneTapGenerate()}
          >
            <Sparkles size={18} aria-hidden />
            {busy && progressOpen && !progressReady ? 'Working…' : 'Generate AI PDF'}
          </button>
        )}

        {!professionalAvailable && professionalDisabledReason ? (
          <p className={styles.subtleHint}>{professionalDisabledReason}</p>
        ) : null}
      </div>

      <GenerateAiPdfOverlay
        open={progressOpen}
        message={generateProgress || 'Analyzing your design…'}
        phase={progressPhase}
        thumbnailUrl={frontImg.url}
        ready={progressReady}
        reconnecting={progressReconnect}
        busyActions={busy}
        onDownloadPdf={() => {
          void downloadPdf()
        }}
        onBackToLooks={onBack}
      />

      <DetailsEditorSheet
        open={detailsOpen}
        draftKey={draft.id}
        title={title}
        styleCode={styleCode}
        spec={spec}
        pieces={pieces}
        busy={busy}
        saveError={saveError}
        lookThumbnailUrl={frontImg.url}
        onChangeTitle={setTitle}
        onChangeStyleCode={setStyleCode}
        onChangeSpec={(updater) => setSpec((prev) => (prev ? updater(prev) : prev))}
        onUpdatePiece={updatePiece}
        onRetrySave={retrySave}
        onClose={closeDetails}
      />
    </div>
  )
}

export type { WorkflowStage }
