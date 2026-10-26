import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useAuthJobImage } from '@/hooks/useAuthJobImage'
import {
  confirmTechpackAi,
  exportTechpackPdf,
  fetchTechpackArtifactBlob,
  fetchTechpackPdfBlob,
  generateTechpackAi,
  getTechpackAiStatus,
  getTechpackDraft,
  updateTechpackDraft,
  type TechpackAiConfirmResponse,
  type TechpackAiMode,
  type TechpackAiStatus,
  type TechpackArtifact,
  type TechpackDraft,
  type TechpackPiece,
  type TechpackSpecV2,
} from '@/services/techpacksApi'
import { FieldHelp } from '@/shell/components/techpack/FieldHelp'
import { MeasuredField } from '@/shell/components/techpack/MeasuredField'
import { MeasurementsSheet } from '@/shell/components/techpack/MeasurementsSheet'
import { StageSheet } from '@/shell/components/techpack/StageSheet'
import {
  CLOSURE_SUGGESTIONS,
  FIT_PREFERENCES,
  getFieldHelp,
  PIECE_CATEGORIES,
  POM_HELP_KEY,
  POM_LABELS,
  SHELL_SUGGESTIONS,
  SILHOUETTE_SUGGESTIONS,
} from '@/shell/components/techpack/fieldHelpContent'
import {
  asRecord,
  createEmptyPiece,
  measured,
  pieceTabLabel,
  retargetFinishedMeasurements,
  wrapSpecForEditing,
} from '@/shell/components/techpack/pieceHelpers'
import styles from './TechpackScreen.module.css'

const MOBILE_MEASURE_MQ = '(max-width: 720px)'
const BUILD_VERSION =
  (import.meta.env.VITE_BUILD_SHA as string | undefined)?.slice(0, 8) ||
  (import.meta.env.VITE_APP_VERSION as string | undefined) ||
  'dev'

type Props = {
  draftId: string
  onBack: () => void
}

type WorkflowStage = 'understand' | 'customize' | 'measurements' | 'generate'
type PackChoice = 'basic' | 'professional'

type ArtifactPreview = {
  id: string
  kind: string
  piece_id?: string | null
  review_state?: string | null
  url: string
}

const STAGES: Array<{ id: WorkflowStage; label: string }> = [
  { id: 'understand', label: 'Understand My Design' },
  { id: 'customize', label: 'Customize Each Piece' },
  { id: 'measurements', label: 'Measurements' },
  { id: 'generate', label: 'Generate Technical Design' },
]

const STAGE_INDEX: Record<WorkflowStage, number> = {
  understand: 0,
  customize: 1,
  measurements: 2,
  generate: 3,
}

function ChipRow({
  options,
  value,
  onPick,
}: {
  options: readonly string[]
  value: string
  onPick: (next: string) => void
}) {
  return (
    <div className={styles.chips} role="group">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={value === opt ? `${styles.chip} ${styles.chipActive}` : styles.chip}
          onClick={() => onPick(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

function LabelWithHelp({
  htmlFor,
  label,
  helpKey,
}: {
  htmlFor: string
  label: string
  helpKey: string
}) {
  const help = getFieldHelp(helpKey)
  return (
    <div className={styles.fieldLabelRow}>
      <label htmlFor={htmlFor}>{label}</label>
      <FieldHelp
        title={help.title}
        explanation={help.explanation}
        examples={help.examples}
        diagram={help.diagram}
      />
    </div>
  )
}

export function TechpackScreen({ draftId, onBack }: Props) {
  const [draft, setDraft] = useState<TechpackDraft | null>(null)
  const [title, setTitle] = useState('')
  const [styleCode, setStyleCode] = useState('')
  const [spec, setSpec] = useState<TechpackSpecV2 | null>(null)
  const [wasV1, setWasV1] = useState(false)
  const [stage, setStage] = useState<WorkflowStage>('understand')
  const [activePieceId, setActivePieceId] = useState<string | 'overview'>('overview')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [aiStatus, setAiStatus] = useState<TechpackAiStatus | null>(null)
  const [packChoice, setPackChoice] = useState<PackChoice>('basic')
  const [confirm, setConfirm] = useState<TechpackAiConfirmResponse | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [proposeBack, setProposeBack] = useState(false)
  const [generateProgress, setGenerateProgress] = useState<string | null>(null)
  const [lastWarnings, setLastWarnings] = useState<string[]>([])
  const [failedSections, setFailedSections] = useState<string[]>([])
  const [analysisSummary, setAnalysisSummary] = useState<string | null>(null)
  const [artifactPreviews, setArtifactPreviews] = useState<ArtifactPreview[]>([])
  const [lastGenerateMode, setLastGenerateMode] = useState<TechpackAiMode | null>(null)
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  const [lastActualCostCents, setLastActualCostCents] = useState<number | null>(null)
  const [isMobileViewport, setIsMobileViewport] = useState(false)
  const [measureSheetOpen, setMeasureSheetOpen] = useState(false)
  const [measureSheetSnapshot, setMeasureSheetSnapshot] = useState<TechpackSpecV2 | null>(null)
  /** Mobile: full-screen modal for steps 1 / 2 / 4 (step 3 uses MeasurementsSheet). */
  const [stageSheetOpen, setStageSheetOpen] = useState(false)
  const [intentIdempotencyKey, setIntentIdempotencyKey] = useState<string | null>(null)
  const formPaneRef = useRef<HTMLDivElement>(null)
  const stageSectionRef = useRef<HTMLElement | null>(null)
  const aiErrorRef = useRef<HTMLParagraphElement>(null)
  const activePieceIdRef = useRef(activePieceId)

  const frontImg = useAuthJobImage(draft?.front_job_id ?? null, Boolean(draft?.front_job_id))
  const backImg = useAuthJobImage(draft?.back_job_id ?? null, Boolean(draft?.back_job_id))

  useEffect(() => {
    activePieceIdRef.current = activePieceId
  }, [activePieceId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const apply = () => {
      const mqNarrow =
        typeof window.matchMedia === 'function'
          ? window.matchMedia(MOBILE_MEASURE_MQ).matches
          : false
      const mqCoarse =
        typeof window.matchMedia === 'function'
          ? window.matchMedia('(pointer: coarse)').matches
          : false
      // Samsung Internet / zoomed viewports / desktop-site mode: trust several signals.
      const width = window.visualViewport?.width ?? window.innerWidth
      const touch = (navigator.maxTouchPoints || 0) > 0
      setIsMobileViewport(mqNarrow || width <= 720 || (touch && (mqCoarse || width <= 920)))
    }
    apply()
    const mq = typeof window.matchMedia === 'function' ? window.matchMedia(MOBILE_MEASURE_MQ) : null
    mq?.addEventListener?.('change', apply)
    window.addEventListener('resize', apply)
    window.visualViewport?.addEventListener('resize', apply)
    return () => {
      mq?.removeEventListener?.('change', apply)
      window.removeEventListener('resize', apply)
      window.visualViewport?.removeEventListener('resize', apply)
    }
  }, [])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const prev = document.title
    document.title = `FashionRise · App ${BUILD_VERSION}`
    return () => {
      document.title = prev
    }
  }, [])

  const professionalAvailable = Boolean(
    aiStatus?.enabled && (aiStatus.professional_available ?? false),
  )

  const professionalDisabledReason = useMemo(() => {
    if (!aiStatus) {
      return 'AI Professional status unavailable — Basic Technical Pack still works at $0.'
    }
    if (!aiStatus.enabled || !aiStatus.professional_available) {
      if (aiStatus.owner_allowlisted === false) {
        return 'AI Professional unavailable — your account is not on the owner allowlist.'
      }
      if (aiStatus.max_usd_per_run == null && aiStatus.spend_ceiling_usd == null) {
        return 'AI Professional unavailable — owner allowlist / spend ceiling not configured.'
      }
      return (
        aiStatus.note ||
        'AI Professional unavailable — owner allowlist / spend ceiling not configured.'
      )
    }
    return null
  }, [aiStatus])

  const pieces = spec?.outfit?.pieces ?? []
  const activePiece =
    activePieceId !== 'overview' ? pieces.find((p) => p.id === activePieceId) ?? null : null

  const hydrate = useCallback((row: TechpackDraft) => {
    setDraft(row)
    setTitle(row.title)
    setStyleCode(row.style_code)
    const wrapped = wrapSpecForEditing(asRecord(row.spec))
    setSpec(wrapped.spec)
    setWasV1(wrapped.wasV1)
    const wf = String(wrapped.spec.workflow_stage || 'understand') as WorkflowStage
    setStage(STAGE_INDEX[wf] != null ? wf : 'understand')
    const pieceIds = new Set((wrapped.spec.outfit?.pieces ?? []).map((p) => p.id))
    const current = activePieceIdRef.current
    if (current === 'overview' || (typeof current === 'string' && pieceIds.has(current))) {
      setActivePieceId(current)
    } else {
      setActivePieceId(wrapped.spec.outfit?.pieces?.[0]?.id ?? 'overview')
    }
    const ai = wrapped.spec.ai
    const mode = ai?.last_mode
    if (mode === 'professional' || mode === 'heuristic' || mode === 'ai') {
      setLastGenerateMode(mode)
    }
    if (ai?.last_run_id) setLastRunId(String(ai.last_run_id))
    if (typeof ai?.actual_cost_usd_cents === 'number') {
      setLastActualCostCents(ai.actual_cost_usd_cents)
    } else if (typeof ai?.estimated_cost_usd_cents === 'number' && mode === 'heuristic') {
      setLastActualCostCents(0)
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
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  useEffect(() => {
    return () => {
      artifactPreviews.forEach((a) => URL.revokeObjectURL(a.url))
    }
    // Only revoke on unmount / when replacing the whole set via clearArtifactPreviews.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const clearArtifactPreviews = useCallback(() => {
    setArtifactPreviews((prev) => {
      prev.forEach((a) => URL.revokeObjectURL(a.url))
      return []
    })
  }, [])

  const loadArtifactPreviews = useCallback(async (artifacts: TechpackArtifact[]) => {
    clearArtifactPreviews()
    const next: ArtifactPreview[] = []
    for (const art of artifacts) {
      try {
        const blob = await fetchTechpackArtifactBlob(art.id)
        next.push({
          id: art.id,
          kind: art.kind,
          piece_id: art.piece_id,
          review_state: art.review_state,
          url: URL.createObjectURL(blob),
        })
      } catch {
        // Skip missing/failed artifact images; warnings surface elsewhere.
      }
    }
    setArtifactPreviews(next)
  }, [clearArtifactPreviews])

  const statusLabel = useMemo(() => {
    if (!draft) return 'DRAFT / UNVERIFIED'
    return `${draft.status} / ${draft.verification}`
  }, [draft])

  const professionalCompleted = useMemo(() => {
    const mode = lastGenerateMode ?? spec?.ai?.last_mode
    const hasArtifacts =
      artifactPreviews.length > 0 ||
      pieces.some((p) => {
        const ill = p.illustrations as { mode?: string; artifacts?: Record<string, unknown> } | undefined
        return ill?.mode === 'professional' && Boolean(ill.artifacts && Object.keys(ill.artifacts).length)
      })
    return mode === 'professional' && hasArtifacts
  }, [lastGenerateMode, spec?.ai?.last_mode, artifactPreviews.length, pieces])

  const generationProvenanceLabel = useMemo(() => {
    if (professionalCompleted) {
      const run = lastRunId || spec?.ai?.last_run_id || '—'
      const cost =
        lastActualCostCents ??
        (typeof spec?.ai?.actual_cost_usd_cents === 'number' ? spec.ai.actual_cost_usd_cents : null)
      return {
        kind: 'professional' as const,
        title: 'AI Professional generation completed',
        detail: `Run ${run}${cost != null ? ` · ${cost}¢ actual` : ''} · still DRAFT / UNVERIFIED`,
      }
    }
    const mode = lastGenerateMode ?? spec?.ai?.last_mode
    if (mode === 'heuristic') {
      return {
        kind: 'basic' as const,
        title: 'Basic / No AI Professional generated',
        detail: 'Heuristic schematics only · $0 · Preview/Download do not run paid AI',
      }
    }
    return {
      kind: 'none' as const,
      title: 'Basic / No AI generated',
      detail:
        'No technical generation yet. Preview or Download exports a Basic PDF and never runs paid AI.',
    }
  }, [
    professionalCompleted,
    lastRunId,
    lastActualCostCents,
    lastGenerateMode,
    spec?.ai?.last_run_id,
    spec?.ai?.actual_cost_usd_cents,
    spec?.ai?.last_mode,
  ])

  const completion = useMemo(() => {
    const pieceCount = pieces.length
    const customized = pieces.filter((p) => {
      const shell = p.materials?.shell?.name?.trim()
      const silhouette = p.fit?.silhouette?.trim()
      return Boolean(shell || silhouette || p.closures?.type?.trim())
    }).length
    const body = spec?.body ?? {}
    const bodyFilled = ['height', 'bust', 'waist', 'hip'].filter((k) => {
      const v = body[k]?.value
      return v !== null && v !== undefined && String(v).trim() !== ''
    }).length
    return {
      pieces: pieceCount > 0,
      customize: customized > 0,
      measurements: bodyFilled > 0,
      generate: Boolean(draft?.latest_export || spec?.ai?.last_run_id),
    }
  }, [pieces, spec, draft])

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

  const buildSpecPatch = (workflow: WorkflowStage = stage): TechpackSpecV2 => {
    const current = spec ?? wrapSpecForEditing({}).spec
    return {
      ...current,
      schema_version: '2.0',
      workflow_stage: workflow,
      designer_notes: current.designer_notes ?? '',
      look_notes: current.look_notes ?? '',
      units: current.units || 'cm',
      size_system: current.size_system || 'EU',
      sample_size: current.sample_size || '',
      outfit: {
        piece_count: current.outfit?.pieces?.length ?? 0,
        pieces: current.outfit?.pieces ?? [],
        detection_confidence: current.outfit?.detection_confidence,
        needs_user_confirm: current.outfit?.needs_user_confirm,
        note: current.outfit?.note,
      },
      body: current.body ?? {},
      preferences: current.preferences ?? { fit_preference: 'regular', notes: '' },
      warnings: current.warnings ?? [],
      qc_checklist: current.qc_checklist,
      ai: current.ai,
    }
  }

  const save = async (opts: { bump?: boolean; workflow?: WorkflowStage; silent?: boolean } = {}) => {
    setBusy(true)
    if (!opts.silent) {
      setError(null)
      setNotice(null)
    }
    try {
      const next = await updateTechpackDraft(draftId, {
        title: title.trim(),
        style_code: styleCode.trim(),
        spec: buildSpecPatch(opts.workflow ?? stage),
        bump_revision: opts.bump,
      })
      hydrate(next)
      if (!opts.silent) setNotice(opts.bump ? 'Saved and bumped revision.' : 'Draft saved.')
      return next
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save draft')
      return null
    } finally {
      setBusy(false)
    }
  }

  const scrollStageIntoView = useCallback(() => {
    const pane = formPaneRef.current
    const section = stageSectionRef.current
    if (!section) return
    if (pane && typeof pane.scrollTo === 'function') {
      const top = Math.max(0, section.offsetTop - 12)
      pane.scrollTo({ top, behavior: 'smooth' })
      return
    }
    if (typeof section.scrollIntoView === 'function') {
      section.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
  }, [])

  const openMeasureSheet = useCallback(() => {
    setSpec((prev) => {
      if (!prev) return prev
      setMeasureSheetSnapshot(structuredClone(prev))
      return prev
    })
    setMeasureSheetOpen(true)
    setStageSheetOpen(false)
  }, [])

  const openStageSheet = useCallback(
    (next: WorkflowStage) => {
      if (next === 'measurements') {
        openMeasureSheet()
        return
      }
      setMeasureSheetOpen(false)
      setStageSheetOpen(true)
    },
    [openMeasureSheet],
  )

  const goStage = async (next: WorkflowStage) => {
    setStage(next)
    setSpec((prev) => (prev ? { ...prev, workflow_stage: next } : prev))
    if (next === 'customize') {
      const first = pieces[0]
      if (first && (activePieceId === 'overview' || !pieces.some((p) => p.id === activePieceId))) {
        setActivePieceId(first.id)
      }
    }
    if (next === 'measurements') {
      // Body overview first — finished POMs remain one tap away.
      setActivePieceId('overview')
    }
    if (isMobileViewport) {
      // Samsung / small screens: every step opens a full-screen modal form.
      openStageSheet(next)
    } else {
      setStageSheetOpen(false)
    }
    await save({ workflow: next, silent: true })
    if (!isMobileViewport) {
      window.requestAnimationFrame(() => scrollStageIntoView())
    }
  }

  const addPiece = () => {
    const piece = createEmptyPiece({
      category: 'other',
      label: `Piece ${(pieces.length || 0) + 1}`,
      units: spec?.units || 'cm',
    })
    setSpec((prev) => {
      if (!prev) return prev
      const nextPieces = [...(prev.outfit?.pieces ?? []), piece]
      return {
        ...prev,
        outfit: {
          ...(prev.outfit ?? { piece_count: 0, pieces: [] }),
          pieces: nextPieces,
          piece_count: nextPieces.length,
          needs_user_confirm: true,
        },
      }
    })
    setActivePieceId(piece.id)
  }

  const removePiece = (pieceId: string) => {
    setSpec((prev) => {
      if (!prev?.outfit) return prev
      const nextPieces = prev.outfit.pieces.filter((p) => p.id !== pieceId)
      return {
        ...prev,
        outfit: { ...prev.outfit, pieces: nextPieces, piece_count: nextPieces.length },
      }
    })
    setActivePieceId((cur) => (cur === pieceId ? 'overview' : cur))
  }

  const selectPackChoice = (choice: PackChoice) => {
    if (choice === 'professional' && !professionalAvailable) return
    setPackChoice(choice)
    setConfirm(null)
    setConfirmed(false)
    setGenerateProgress(null)
    setError(null)
    setNotice(null)
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
      return (
        'AI Professional generation failed. Your design is safe. ' +
        'If no illustrations appear, confirm cost again before retrying.'
      )
    }
    return raw
  }

  const prepareGenerate = async (mode: TechpackAiMode) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    setConfirmed(false)
    setGenerateProgress('Requesting confirm token…')
    try {
      await save({ workflow: 'generate', silent: true })
      const challenge = await confirmTechpackAi(draftId, 'generate', mode)
      setConfirm(challenge)
      // Stable key for this confirm intent — retries/double-clicks reuse it.
      setIntentIdempotencyKey(`intent-${draftId}-${challenge.confirm_token}`)
      setNotice(challenge.message)
      setGenerateProgress('Confirm token ready — review cost and confirm to generate.')
      window.requestAnimationFrame(() => scrollStageIntoView())
    } catch (err) {
      setError(mapGenerationError(err))
      setConfirm(null)
      setIntentIdempotencyKey(null)
      setGenerateProgress(null)
      window.requestAnimationFrame(() => {
        const node = aiErrorRef.current
        if (node && typeof node.scrollIntoView === 'function') {
          node.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }
      })
    } finally {
      setBusy(false)
    }
  }

  const runGenerate = async (opts: { sections?: string[]; retry?: boolean } = {}) => {
    const mode: TechpackAiMode =
      packChoice === 'professional' ? 'professional' : 'heuristic'
    if (packChoice === 'professional' && !professionalAvailable) {
      setError('AI Professional is not available for this account.')
      return
    }
    if (!confirm?.confirm_token) {
      setError('Get a cost estimate / confirm token first.')
      return
    }
    if (!confirmed) {
      setError('Check the confirmation box before generating.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    setGenerateProgress(
      opts.retry
        ? `Retrying failed sections (${(opts.sections ?? []).join(', ') || 'all'})…`
        : mode === 'professional'
          ? 'Generating AI Professional Technical Pack…'
          : 'Generating Basic Technical Pack…',
    )
    try {
      await save({ workflow: 'generate', silent: true })
      const idem =
        intentIdempotencyKey ||
        `intent-${draftId}-${confirm.confirm_token}${opts.retry ? '-retry-sections' : ''}`
      const result = await generateTechpackAi(draftId, {
        confirm_token: confirm.confirm_token,
        idempotency_key: idem,
        mode,
        propose_back: mode === 'professional' ? proposeBack : undefined,
        sections: opts.sections,
      })
      const warns = (result.warnings ?? [])
        .map((w) =>
          typeof w === 'string'
            ? w
            : String((w as { message?: string }).message || JSON.stringify(w)),
        )
        .filter(Boolean)
      setLastWarnings(warns)
      setAnalysisSummary(result.analysis_summary ?? null)
      setLastGenerateMode(mode)
      setLastRunId(result.run_id ?? null)
      setLastActualCostCents(result.actual_cost_usd_cents ?? result.cost_usd_cents ?? 0)
      const failed =
        result.failed_sections ??
        (result.status === 'partial' || result.status === 'failed'
          ? (opts.sections ?? [])
          : [])
      setFailedSections(failed)
      if (result.artifacts?.length) {
        setGenerateProgress('Loading technical illustrations…')
        await loadArtifactPreviews(result.artifacts)
      } else if (mode === 'heuristic') {
        clearArtifactPreviews()
      }
      const refreshed = await getTechpackDraft(draftId)
      hydrate(refreshed)
      const actual =
        result.actual_cost_usd_cents ?? result.cost_usd_cents ?? 0
      if (result.status === 'partial' || failed.length > 0) {
        setNotice(
          `Professional pack partially completed · ${actual}¢ · retry failed sections below · still DRAFT/UNVERIFIED`,
        )
        setGenerateProgress('Partial success — some sections need retry.')
      } else if (mode === 'professional') {
        setNotice(
          `AI Professional Technical Pack ready · ${actual}¢ · still DRAFT/UNVERIFIED`,
        )
        setGenerateProgress('Professional generation complete.')
      } else {
        setNotice('Basic Technical Pack ready · $0 · still DRAFT/UNVERIFIED')
        setGenerateProgress('Basic generation complete.')
      }
      setConfirm(null)
      setConfirmed(false)
      setIntentIdempotencyKey(null)
    } catch (err) {
      setError(mapGenerationError(err))
      setGenerateProgress(null)
      window.requestAnimationFrame(() => {
        const node = aiErrorRef.current
        if (node && typeof node.scrollIntoView === 'function') {
          node.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }
      })
    } finally {
      setBusy(false)
    }
  }

  const retryFailedSections = async () => {
    if (!failedSections.length) {
      setError('No failed sections to retry.')
      return
    }
    // Fresh confirm + new intent key for a deliberate section retry (not a network replay).
    setBusy(true)
    setError(null)
    try {
      const challenge = await confirmTechpackAi(draftId, 'generate', 'professional')
      setConfirm(challenge)
      setIntentIdempotencyKey(
        `intent-${draftId}-${challenge.confirm_token}-sections-${failedSections.join('_')}`,
      )
      setConfirmed(true)
      setBusy(false)
      await runGenerate({ sections: failedSections, retry: true })
    } catch (err) {
      setError(mapGenerationError(err))
      setBusy(false)
    }
  }

  const discardMeasureSheet = () => {
    if (measureSheetSnapshot) setSpec(measureSheetSnapshot)
    setMeasureSheetSnapshot(null)
    setMeasureSheetOpen(false)
  }

  const saveMeasureSheet = async () => {
    const saved = await save({ workflow: 'measurements', silent: false })
    if (saved) {
      setMeasureSheetSnapshot(null)
      setMeasureSheetOpen(false)
      setNotice('Measurements saved. Unknown fields may stay empty — continue when ready.')
    }
  }

  const exportAndPreview = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await updateTechpackDraft(draftId, {
        title: title.trim(),
        style_code: styleCode.trim(),
        spec: buildSpecPatch('generate'),
      })
      const exported = await exportTechpackPdf(draftId)
      const blob = await fetchTechpackPdfBlob(exported.id)
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      const url = URL.createObjectURL(blob)
      setPreviewUrl(url)
      const refreshed = await getTechpackDraft(draftId)
      hydrate(refreshed)
      const provenance = professionalCompleted
        ? 'AI Professional PDF (from completed run)'
        : 'Basic PDF · No AI Professional · Preview did not run paid AI'
      setNotice(
        `${provenance} · ${exported.page_count} pages · ${exported.status}/${exported.verification}`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not export PDF')
    } finally {
      setBusy(false)
    }
  }

  const downloadPdf = async () => {
    const exportId = draft?.latest_export?.id
    if (!exportId) {
      setError('Export a PDF preview first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const blob = await fetchTechpackPdfBlob(exportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = draft?.latest_export?.filename || `${styleCode}_techpack.pdf`
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download PDF')
    } finally {
      setBusy(false)
    }
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
          <button type="button" className={styles.ghostBtn} onClick={onBack}>
            <ArrowLeft size={14} aria-hidden />
            Back to My Looks
          </button>
          <p className={styles.error}>{error || 'Tech pack not found'}</p>
        </div>
      </div>
    )
  }

  const stageIdx = STAGE_INDEX[stage]

  return (
    <div className={styles.screen}>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>Create Real Design</h1>
          <p className={styles.subtitle}>
            {draft.style_code} · Rev {draft.revision} · guided tech-pack from your Magic look
          </p>
        </div>
        <div className={styles.actions}>
          <span
            className={styles.appVersionPill}
            title="If this is not the latest App id from support, refresh or clear site data"
            data-testid="app-version"
          >
            App {BUILD_VERSION}
          </span>
          <span className={styles.statusPill}>{statusLabel}</span>
          <button type="button" className={styles.ghostBtn} onClick={onBack} disabled={busy}>
            <ArrowLeft size={14} aria-hidden />
            My Looks
          </button>
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => void save({ bump: false })}
            disabled={busy}
          >
            <Save size={14} aria-hidden />
            Save draft
          </button>
        </div>
      </div>

      <p className={styles.banner}>
        {statusLabel} — detection and measurements are starting points, not guaranteed. Patternmaker
        review required before production. Missing Front/Back sides are never invented.
      </p>
      {wasV1 ? (
        <p className={styles.noticeBanner}>
          This draft started in an older format. You can keep editing; saving migrates it to the
          multi-piece studio (or wraps it as a single piece for now).
        </p>
      ) : null}

      <nav className={styles.stepper} aria-label="Create Real Design stages">
        {STAGES.map((s, idx) => {
          const done =
            (s.id === 'understand' && completion.pieces) ||
            (s.id === 'customize' && completion.customize) ||
            (s.id === 'measurements' && completion.measurements) ||
            (s.id === 'generate' && completion.generate)
          const className = [
            styles.step,
            stage === s.id ? styles.stepActive : '',
            done && stage !== s.id ? styles.stepDone : '',
          ]
            .filter(Boolean)
            .join(' ')
          return (
            <button
              key={s.id}
              type="button"
              className={className}
              aria-current={stage === s.id ? 'step' : undefined}
              aria-haspopup={isMobileViewport ? 'dialog' : undefined}
              title={isMobileViewport ? `Open step ${idx + 1} form` : undefined}
              onClick={() => void goStage(s.id)}
              disabled={busy}
            >
              <span className={styles.stepIndex}>{done && stage !== s.id ? <Check size={12} /> : idx + 1}</span>
              <span>{s.label}</span>
            </button>
          )
        })}
      </nav>
      {isMobileViewport ? (
        <p className={styles.mobileHubLead} style={{ margin: '10px 16px 0' }}>
          Tap a step to open its form (full-screen on this phone).
        </p>
      ) : null}

      <div className={styles.outfitBrief}>
        <div className={styles.briefThumb}>
          {frontImg.url ? <img src={frontImg.url} alt="Front look" /> : <span>Front</span>}
        </div>
        <div className={styles.briefThumb}>
          {backImg.url ? (
            <img src={backImg.url} alt="Back look" />
          ) : (
            <span>{draft.back_job_id ? '…' : 'No back'}</span>
          )}
        </div>
        <div className={styles.briefMeta}>
          <strong>{title || 'Untitled look'}</strong>
          <p>
            {pieces.length} piece{pieces.length === 1 ? '' : 's'} detected · edit freely — AI is not
            guaranteed correct
          </p>
        </div>
      </div>

      <div className={styles.body}>
        {!isMobileViewport ? (
        <div className={styles.formPane} ref={formPaneRef}>
          {stage === 'understand' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-understand"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-understand" className={styles.sectionTitle}>
                1 · Understand My Design
              </h2>
              <p className={styles.sectionLead}>
                Review Magic Front/Back and correct outfit pieces. Detection is a starting point —
                never treat categories as guaranteed.
              </p>

              <div className={styles.lookThumbs}>
                <div>
                  <p className={styles.lookLabel}>Front</p>
                  <div className={styles.lookThumb}>
                    {frontImg.url ? (
                      <img src={frontImg.url} alt="Front look" />
                    ) : (
                      <span>{draft.front_job_id ? 'Loading…' : 'Not available'}</span>
                    )}
                  </div>
                </div>
                <div>
                  <p className={styles.lookLabel}>Back</p>
                  <div className={styles.lookThumb}>
                    {backImg.url ? (
                      <img src={backImg.url} alt="Back look" />
                    ) : (
                      <span>{draft.back_job_id ? 'Loading…' : 'Not fabricated'}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className={styles.grid2}>
                <div className={styles.field}>
                  <label htmlFor="tp-title">Title</label>
                  <input
                    id="tp-title"
                    value={title}
                    maxLength={160}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div className={styles.field}>
                  <label htmlFor="tp-style">Style code</label>
                  <input
                    id="tp-style"
                    value={styleCode}
                    maxLength={64}
                    onChange={(e) => setStyleCode(e.target.value.toUpperCase())}
                  />
                </div>
              </div>

              <h3 className={styles.sectionTitle} style={{ marginTop: 16 }}>
                Outfit · {pieces.length} piece{pieces.length === 1 ? '' : 's'}
              </h3>
              {spec.outfit?.note ? <p className={styles.sectionLead}>{spec.outfit.note}</p> : null}

              {pieces.map((piece) => (
                <div key={piece.id} className={styles.pieceCard}>
                  <div className={styles.pieceCardHead}>
                    <strong>{pieceTabLabel(piece)}</strong>
                    <button
                      type="button"
                      className={styles.dangerBtn}
                      onClick={() => removePiece(piece.id)}
                      disabled={busy || pieces.length <= 1}
                      aria-label={`Remove ${piece.label}`}
                    >
                      <Trash2 size={14} aria-hidden />
                      Remove
                    </button>
                  </div>
                  <div className={styles.grid2}>
                    <div className={styles.field}>
                      <label htmlFor={`cat-${piece.id}`}>Category</label>
                      <select
                        id={`cat-${piece.id}`}
                        value={piece.category}
                        onChange={(e) => {
                          const cat = e.target.value
                          updatePiece(piece.id, (p) =>
                            retargetFinishedMeasurements(
                              { ...p, category: cat, role: cat },
                              cat,
                              spec.units || 'cm',
                            ),
                          )
                        }}
                      >
                        {PIECE_CATEGORIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className={styles.field}>
                      <label htmlFor={`label-${piece.id}`}>Label</label>
                      <input
                        id={`label-${piece.id}`}
                        value={piece.label}
                        onChange={(e) =>
                          updatePiece(piece.id, (p) => ({ ...p, label: e.target.value }))
                        }
                      />
                    </div>
                    <div className={styles.field}>
                      <label htmlFor={`color-${piece.id}`}>Color hint</label>
                      <input
                        id={`color-${piece.id}`}
                        value={piece.color_hint ?? ''}
                        onChange={(e) =>
                          updatePiece(piece.id, (p) => ({ ...p, color_hint: e.target.value }))
                        }
                      />
                    </div>
                  </div>
                </div>
              ))}

              <button type="button" className={styles.ghostBtn} onClick={addPiece} disabled={busy}>
                <Plus size={14} aria-hidden />
                Add piece
              </button>
            </section>
          ) : null}

          {stage === 'customize' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-customize"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-customize" className={styles.sectionTitle}>
                2 · Customize Each Piece
              </h2>
              <p className={styles.sectionLead}>
                Set shell fabric, composition, closure, and silhouette per piece. Shared notes live
                under Outfit Overview.
              </p>
              <div className={styles.garmentTabs} role="tablist" aria-label="Garment pieces">
                <button
                  type="button"
                  role="tab"
                  aria-selected={activePieceId === 'overview'}
                  className={
                    activePieceId === 'overview'
                      ? `${styles.garmentTab} ${styles.garmentTabActive}`
                      : styles.garmentTab
                  }
                  onClick={() => setActivePieceId('overview')}
                >
                  Outfit Overview
                </button>
                {pieces.map((piece) => (
                  <button
                    key={piece.id}
                    type="button"
                    role="tab"
                    aria-selected={activePieceId === piece.id}
                    className={
                      activePieceId === piece.id
                        ? `${styles.garmentTab} ${styles.garmentTabActive}`
                        : styles.garmentTab
                    }
                    onClick={() => setActivePieceId(piece.id)}
                  >
                    {pieceTabLabel(piece)}
                  </button>
                ))}
              </div>

              {activePieceId === 'overview' ? (
                <div className={styles.pieceCard}>
                  <div className={styles.grid2}>
                    <div className={styles.field}>
                      <label htmlFor="tp-size-system">Size system</label>
                      <select
                        id="tp-size-system"
                        value={spec.size_system || 'EU'}
                        onChange={(e) => setSpec((p) => (p ? { ...p, size_system: e.target.value } : p))}
                      >
                        <option value="EU">EU</option>
                        <option value="US">US</option>
                        <option value="UK">UK</option>
                        <option value="Alpha">Alpha</option>
                      </select>
                    </div>
                    <div className={styles.field}>
                      <label htmlFor="tp-units">Units</label>
                      <select
                        id="tp-units"
                        value={spec.units || 'cm'}
                        onChange={(e) => setSpec((p) => (p ? { ...p, units: e.target.value } : p))}
                      >
                        <option value="cm">cm</option>
                        <option value="in">in</option>
                      </select>
                    </div>
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <label htmlFor="tp-look-notes">Shared look notes</label>
                    <textarea
                      id="tp-look-notes"
                      value={spec.look_notes ?? ''}
                      onChange={(e) =>
                        setSpec((p) => (p ? { ...p, look_notes: e.target.value } : p))
                      }
                      placeholder="Overall outfit notes shared across pieces…"
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <label htmlFor="tp-designer-notes">Designer notes</label>
                    <textarea
                      id="tp-designer-notes"
                      value={spec.designer_notes ?? ''}
                      onChange={(e) =>
                        setSpec((p) => (p ? { ...p, designer_notes: e.target.value } : p))
                      }
                      placeholder="Construction preferences, trims, fit intent…"
                    />
                  </div>
                </div>
              ) : activePiece ? (
                <div className={styles.pieceCard}>
                  <div className={styles.field}>
                    <LabelWithHelp
                      htmlFor={`shell-${activePiece.id}`}
                      label="Shell fabric"
                      helpKey="shell_fabric"
                    />
                    <input
                      id={`shell-${activePiece.id}`}
                      value={activePiece.materials?.shell?.name ?? ''}
                      onChange={(e) => {
                        const name = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: {
                              ...p.materials?.shell,
                              name,
                              source: name.trim() ? 'designer' : 'empty',
                            },
                          },
                        }))
                      }}
                    />
                    <ChipRow
                      options={SHELL_SUGGESTIONS}
                      value={activePiece.materials?.shell?.name ?? ''}
                      onPick={(name) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: { ...p.materials?.shell, name, source: 'designer' },
                          },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`comp-${activePiece.id}`}
                      label="Composition"
                      helpKey="composition"
                    />
                    <input
                      id={`comp-${activePiece.id}`}
                      value={activePiece.materials?.shell?.composition ?? ''}
                      onChange={(e) => {
                        const composition = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: { ...p.materials?.shell, composition },
                          },
                        }))
                      }}
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`closure-${activePiece.id}`}
                      label="Closure"
                      helpKey="closure"
                    />
                    <input
                      id={`closure-${activePiece.id}`}
                      value={activePiece.closures?.type ?? ''}
                      onChange={(e) => {
                        const type = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: {
                            ...p.closures,
                            type,
                            source: type.trim() ? 'designer' : 'empty',
                          },
                        }))
                      }}
                    />
                    <ChipRow
                      options={CLOSURE_SUGGESTIONS}
                      value={activePiece.closures?.type ?? ''}
                      onPick={(type) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: { ...p.closures, type, source: 'designer' },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`sil-${activePiece.id}`}
                      label="Silhouette"
                      helpKey="silhouette"
                    />
                    <input
                      id={`sil-${activePiece.id}`}
                      value={activePiece.fit?.silhouette ?? ''}
                      onChange={(e) => {
                        const silhouette = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...p.fit, silhouette },
                        }))
                      }}
                    />
                    <ChipRow
                      options={SILHOUETTE_SUGGESTIONS}
                      value={activePiece.fit?.silhouette ?? ''}
                      onPick={(silhouette) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...p.fit, silhouette },
                        }))
                      }
                    />
                  </div>
                  <details className={styles.advanced}>
                    <summary>Advanced details</summary>
                    <div className={styles.advancedBody}>
                      <div className={styles.field}>
                        <label htmlFor={`closure-notes-${activePiece.id}`}>Closure notes</label>
                        <textarea
                          id={`closure-notes-${activePiece.id}`}
                          value={activePiece.closures?.notes ?? ''}
                          onChange={(e) =>
                            updatePiece(activePiece.id, (p) => ({
                              ...p,
                              closures: { ...p.closures, notes: e.target.value },
                            }))
                          }
                        />
                      </div>
                      <div className={styles.field} style={{ marginTop: 8 }}>
                        <label htmlFor={`ease-${activePiece.id}`}>Ease note</label>
                        <input
                          id={`ease-${activePiece.id}`}
                          value={activePiece.fit?.ease_note ?? ''}
                          onChange={(e) =>
                            updatePiece(activePiece.id, (p) => ({
                              ...p,
                              fit: { ...p.fit, ease_note: e.target.value },
                            }))
                          }
                        />
                      </div>
                    </div>
                  </details>
                </div>
              ) : null}
            </section>
          ) : null}

          {stage === 'measurements' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-meas"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-meas" className={styles.sectionTitle}>
                3 · Measurements and Preferences
              </h2>
              <p className={styles.sectionLead}>
                Body measurements are about the person. Finished POMs are garment-specific — trousers
                never show bust or sleeve fields. Unknown values may stay empty; Stage 4 does not
                require every field.
              </p>

              {isMobileViewport ? (
                <div className={styles.mobileMeasureCard}>
                  <button
                    type="button"
                    className={`${styles.primaryBtn} ${styles.mobileMeasureCta}`}
                    onClick={openMeasureSheet}
                    disabled={busy}
                    autoFocus
                  >
                    Edit Measurements
                  </button>
                  <p>
                    Full-screen editor with large number fields. Unit and source stay one tap away.
                    Empty fields are fine — continue to Step 4 when ready.
                  </p>
                  <ul className={styles.mobileMeasureSummary}>
                    <li>
                      Body fields started:{' '}
                      {['height', 'bust', 'waist', 'hip'].filter((k) => {
                        const v = spec.body?.[k]?.value
                        return v !== null && v !== undefined && String(v).trim() !== ''
                      }).length}
                      /4 (empty OK)
                    </li>
                    <li>Garment pieces with finished POMs: {pieces.length}</li>
                    <li>Units: {spec.units || 'cm'}</li>
                  </ul>
                </div>
              ) : (
                <>
                  <div className={styles.garmentTabs} role="tablist" aria-label="Measurement focus">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activePieceId === 'overview'}
                      className={
                        activePieceId === 'overview'
                          ? `${styles.garmentTab} ${styles.garmentTabActive}`
                          : styles.garmentTab
                      }
                      onClick={() => setActivePieceId('overview')}
                    >
                      Body & preferences
                    </button>
                    {pieces.map((piece) => (
                      <button
                        key={piece.id}
                        type="button"
                        role="tab"
                        aria-selected={activePieceId === piece.id}
                        className={
                          activePieceId === piece.id
                            ? `${styles.garmentTab} ${styles.garmentTabActive}`
                            : styles.garmentTab
                        }
                        onClick={() => setActivePieceId(piece.id)}
                      >
                        {pieceTabLabel(piece)}
                      </button>
                    ))}
                  </div>

                  {activePieceId === 'overview' ? (
                    <>
                      <h3 className={styles.sectionTitle}>Body measurements</h3>
                      {(
                        [
                          ['height', 'Height', 'height'],
                          ['bust', 'Bust', 'bust'],
                          ['waist', 'Waist', 'waist'],
                          ['hip', 'Hip', 'hip'],
                          ['inseam', 'Inseam', 'body_inseam'],
                        ] as const
                      ).map(([key, label, helpKey]) => (
                        <MeasuredField
                          key={key}
                          label={label}
                          helpKey={helpKey}
                          value={spec.body?.[key] ?? measured(null, spec.units || 'cm')}
                          onChange={(next) =>
                            setSpec((prev) =>
                              prev
                                ? { ...prev, body: { ...(prev.body ?? {}), [key]: next } }
                                : prev,
                            )
                          }
                        />
                      ))}
                      <div className={styles.grid2} style={{ marginTop: 12 }}>
                        <div className={styles.field}>
                          <label htmlFor="tp-fit-pref">Fit preference</label>
                          <select
                            id="tp-fit-pref"
                            value={spec.preferences?.fit_preference || 'regular'}
                            onChange={(e) =>
                              setSpec((prev) =>
                                prev
                                  ? {
                                      ...prev,
                                      preferences: {
                                        ...(prev.preferences ?? {}),
                                        fit_preference: e.target.value,
                                      },
                                    }
                                  : prev,
                              )
                            }
                          >
                            {FIT_PREFERENCES.map((f) => (
                              <option key={f} value={f}>
                                {f}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="tp-sample-size">Sample size</label>
                          <input
                            id="tp-sample-size"
                            value={spec.sample_size ?? ''}
                            onChange={(e) =>
                              setSpec((prev) =>
                                prev ? { ...prev, sample_size: e.target.value } : prev,
                              )
                            }
                            placeholder="e.g. 36 / M"
                          />
                        </div>
                      </div>
                      <details className={styles.advanced}>
                        <summary>Advanced preferences</summary>
                        <div className={styles.advancedBody}>
                          <div className={styles.field}>
                            <label htmlFor="tp-pref-notes">Preference notes</label>
                            <textarea
                              id="tp-pref-notes"
                              value={spec.preferences?.notes ?? ''}
                              onChange={(e) =>
                                setSpec((prev) =>
                                  prev
                                    ? {
                                        ...prev,
                                        preferences: {
                                          ...(prev.preferences ?? {}),
                                          notes: e.target.value,
                                        },
                                      }
                                    : prev,
                                )
                              }
                            />
                          </div>
                        </div>
                      </details>
                    </>
                  ) : activePiece ? (
                    <>
                      <h3 className={styles.sectionTitle}>
                        Finished measurements · {pieceTabLabel(activePiece)}
                      </h3>
                      {Object.keys(activePiece.finished_measurements ?? {}).length === 0 ? (
                        <p className={styles.sectionLead}>
                          No finished POMs for this category (e.g. set). Add piece-level notes
                          instead.
                        </p>
                      ) : (
                        Object.entries(activePiece.finished_measurements ?? {}).map(
                          ([key, value]) => (
                            <MeasuredField
                              key={key}
                              label={POM_LABELS[key] ?? key.replace(/_/g, ' ')}
                              helpKey={POM_HELP_KEY[key]}
                              value={value}
                              onChange={(next) =>
                                updatePiece(activePiece.id, (p) => ({
                                  ...p,
                                  finished_measurements: {
                                    ...(p.finished_measurements ?? {}),
                                    [key]: next,
                                  },
                                }))
                              }
                            />
                          ),
                        )
                      )}
                    </>
                  ) : null}
                </>
              )}
            </section>
          ) : null}

          {stage === 'generate' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-gen"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-gen" className={styles.sectionTitle}>
                4 · Generate Technical Design
              </h2>
              <p className={styles.sectionLead}>
                Choose Basic ($0) or AI Professional (paid). Preview and Download never run paid AI —
                they only export what already exists for this draft.
              </p>

              {error ? (
                <div className={styles.aiErrorPanel} role="alert">
                  <p ref={aiErrorRef} className={styles.aiErrorText}>
                    {error}
                  </p>
                  {/server configuration problem|design is safe/i.test(error) ? (
                    <p className={styles.aiErrorHint}>
                      No chargeable AI work ran for this attempt. You can request a new cost estimate
                      after the fix is live.
                    </p>
                  ) : null}
                </div>
              ) : null}

              <div
                className={
                  generationProvenanceLabel.kind === 'professional'
                    ? `${styles.provenanceBanner} ${styles.provenanceProfessional}`
                    : `${styles.provenanceBanner} ${styles.provenanceBasic}`
                }
                role="status"
              >
                <strong>{generationProvenanceLabel.title}</strong>
                <span>{generationProvenanceLabel.detail}</span>
                {professionalCompleted ? (
                  <span className={styles.provenanceMeta}>
                    Models:{' '}
                    {[aiStatus?.vision_model || spec?.ai?.vision_model, aiStatus?.image_model || spec?.ai?.image_model]
                      .filter(Boolean)
                      .join(' + ') || '—'}
                  </span>
                ) : null}
              </div>

              <ol className={styles.workflowSteps} aria-label="AI Professional workflow">
                <li>Select pack type</li>
                <li>Cost estimate</li>
                <li>Confirm</li>
                <li>Generate</li>
                <li>Review illustrations</li>
                <li>Export PDF</li>
              </ol>

              <p className={styles.diffNote}>
                <strong style={{ color: 'var(--fr-text)' }}>Basic PDF / $0</strong> — local
                heuristics and lightweight schematics. No paid model calls.{' '}
                <strong style={{ color: 'var(--fr-text)' }}>AI Professional / paid</strong> —
                analyzes your Magic image and generates design-specific technical drawings after an
                explicit cost confirmation.
              </p>

              <div className={styles.packChoices} role="radiogroup" aria-label="Technical pack type">
                <button
                  type="button"
                  role="radio"
                  aria-checked={packChoice === 'basic'}
                  className={
                    packChoice === 'basic'
                      ? `${styles.packCard} ${styles.packCardActive}`
                      : styles.packCard
                  }
                  onClick={() => selectPackChoice('basic')}
                  disabled={busy}
                >
                  <span className={styles.packCardTitle}>Basic Technical Pack — Free</span>
                  <span className={styles.packCardBody}>
                    Existing heuristic generate. Lightweight schematics. No paid calls.
                  </span>
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={packChoice === 'professional'}
                  aria-disabled={!professionalAvailable}
                  className={[
                    styles.packCard,
                    packChoice === 'professional' ? styles.packCardActive : '',
                    !professionalAvailable ? styles.packCardDisabled : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => selectPackChoice('professional')}
                  disabled={busy || !professionalAvailable}
                >
                  <span className={styles.packCardTitle}>AI Professional Technical Pack</span>
                  <span className={styles.packCardBody}>
                    Paid AI technical illustrations (flat front / related). Requires confirm +
                    allowance.
                  </span>
                  {!professionalAvailable ? (
                    <span className={styles.packCardHint}>
                      {professionalDisabledReason ||
                        'Unavailable — owner allowlist / spend ceiling not configured.'}
                    </span>
                  ) : (
                    <span className={styles.packCardHint}>
                      Est.{' '}
                      {aiStatus?.estimate_professional_cents_min ?? '—'}–
                      {aiStatus?.estimate_professional_cents_max ??
                        aiStatus?.estimate_chat_cents ??
                        '—'}
                      ¢ · max ${aiStatus?.max_usd_per_run ?? '—'} / run
                    </span>
                  )}
                </button>
              </div>

              <div className={styles.aiPanel}>
                {packChoice === 'basic' ? (
                  <>
                    <p>
                      Basic pack always available at <strong style={{ color: 'var(--fr-text)' }}>$0</strong>.
                      Prepare a confirm token, then generate heuristic content.
                    </p>
                    {confirm && confirm.mode !== 'professional' ? (
                      <div className={styles.confirmBox}>
                        <p>
                          Estimated cost:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            {confirm.estimated_cost_usd_cents}¢
                          </strong>{' '}
                          (heuristic / $0)
                        </p>
                        <p>{confirm.message}</p>
                        <label>
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                          />
                          <span>
                            I confirm generating a Basic Technical Pack. Output remains DRAFT /
                            UNVERIFIED.
                          </span>
                        </label>
                      </div>
                    ) : null}
                    <div className={styles.actions} style={{ marginTop: 12 }}>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        disabled={busy}
                        onClick={() => void prepareGenerate('heuristic')}
                      >
                        <Sparkles size={14} aria-hidden />
                        Get confirm token
                      </button>
                      <button
                        type="button"
                        className={styles.primaryBtn}
                        disabled={busy || !confirm || !confirmed || packChoice !== 'basic'}
                        onClick={() => void runGenerate()}
                      >
                        <Sparkles size={14} aria-hidden />
                        {busy ? 'Working…' : 'Generate Basic Pack'}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p>
                      AI Professional uses vision + image models when your account is allowlisted
                      and a spend ceiling is configured.
                    </p>
                    <p className={styles.costLine}>
                      {confirm ? (
                        <>
                          Estimated cost:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            {confirm.estimated_cost_usd_cents}¢
                          </strong>
                          {' · '}
                          Max allowance:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            ${confirm.max_usd_per_run ?? aiStatus?.max_usd_per_run ?? '—'}
                          </strong>
                          {' / run'}
                        </>
                      ) : (
                        <>
                          Status estimate:{' '}
                          {aiStatus?.estimate_professional_cents_min ?? '—'}–
                          {aiStatus?.estimate_professional_cents_max ?? '—'}¢ · max $
                          {aiStatus?.max_usd_per_run ?? '—'} / run
                          {aiStatus?.vision_model || aiStatus?.image_model
                            ? ` · ${[aiStatus.vision_model, aiStatus.image_model]
                                .filter(Boolean)
                                .join(' + ')}`
                            : ''}
                        </>
                      )}
                    </p>
                    <label className={styles.checkRow}>
                      <input
                        type="checkbox"
                        checked={proposeBack}
                        onChange={(e) => setProposeBack(e.target.checked)}
                      />
                      <span>Propose unverified back view (only if no Magic back)</span>
                    </label>
                    {confirm ? (
                      <div className={styles.confirmBox}>
                        <p>{confirm.message}</p>
                        <label>
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                          />
                          <span>
                            I confirm generating an AI Professional Technical Pack and accept the
                            estimated cost. Output remains DRAFT / UNVERIFIED.
                          </span>
                        </label>
                      </div>
                    ) : null}
                    <div className={styles.actions} style={{ marginTop: 12 }}>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        disabled={busy || !professionalAvailable}
                        onClick={() => void prepareGenerate('professional')}
                      >
                        <Sparkles size={14} aria-hidden />
                        Get cost estimate
                      </button>
                      <button
                        type="button"
                        className={styles.primaryBtn}
                        disabled={
                          busy ||
                          !professionalAvailable ||
                          !confirm ||
                          !confirmed ||
                          packChoice !== 'professional'
                        }
                        onClick={() => void runGenerate()}
                      >
                        <Sparkles size={14} aria-hidden />
                        {busy ? 'Working…' : 'Generate Professional Pack'}
                      </button>
                    </div>
                  </>
                )}
                {generateProgress ? (
                  <p className={styles.progressStatus} role="status">
                    {generateProgress}
                  </p>
                ) : null}
              </div>

              {artifactPreviews.length > 0 ? (
                <div className={styles.artifactGrid} aria-label="Generated technical illustrations">
                  <h3 className={styles.sectionTitle}>Technical illustrations</h3>
                  {analysisSummary ? (
                    <p className={styles.sectionLead}>{analysisSummary}</p>
                  ) : null}
                  <div className={styles.artifactThumbs}>
                    {artifactPreviews.map((art) => (
                      <figure key={art.id} className={styles.artifactThumb}>
                        <img src={art.url} alt={`${art.kind} technical illustration`} />
                        <figcaption>
                          {art.kind}
                          {art.review_state ? ` · ${art.review_state}` : ''}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                </div>
              ) : null}

              {failedSections.length > 0 ? (
                <div className={styles.actions} style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    disabled={busy || !professionalAvailable}
                    onClick={() => void retryFailedSections()}
                  >
                    Retry failed sections ({failedSections.join(', ')})
                  </button>
                </div>
              ) : null}

              {lastWarnings.length > 0 || (spec.warnings && spec.warnings.length > 0) ? (
                <div className={styles.warnings} role="status">
                  <strong>Warnings</strong>
                  <ul>
                    {(lastWarnings.length
                      ? lastWarnings
                      : (spec.warnings ?? []).map((w) =>
                          typeof w === 'string'
                            ? w
                            : String((w as { message?: string }).message || JSON.stringify(w)),
                        )
                    ).map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <h3 className={styles.sectionTitle} style={{ marginTop: 16 }}>
                Progress
              </h3>
              <ul className={styles.progressList}>
                <li data-done={completion.pieces ? 'true' : 'false'}>
                  {completion.pieces ? <Check size={14} /> : '·'} Outfit pieces reviewed
                </li>
                <li data-done={completion.customize ? 'true' : 'false'}>
                  {completion.customize ? <Check size={14} /> : '·'} Piece materials / silhouette started
                </li>
                <li data-done={completion.measurements ? 'true' : 'false'}>
                  {completion.measurements ? <Check size={14} /> : '·'} Body measurements started
                </li>
                <li data-done={completion.generate ? 'true' : 'false'}>
                  {completion.generate ? <Check size={14} /> : '·'} Technical generation or PDF export
                </li>
              </ul>

              <p className={styles.exportNote} role="note">
                Preview / Download / Save never execute AI. They only assemble a PDF from the current
                draft
                {professionalCompleted
                  ? ' including completed AI Professional illustrations.'
                  : ' as a Basic / No AI Professional export.'}
              </p>

              <div className={styles.actions} style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className={styles.primaryBtn}
                  onClick={() => void exportAndPreview()}
                  disabled={busy || (packChoice === 'professional' && !professionalCompleted)}
                  title={
                    packChoice === 'professional' && !professionalCompleted
                      ? 'Generate AI Professional illustrations first'
                      : undefined
                  }
                >
                  <FileText size={14} aria-hidden />
                  {busy
                    ? 'Working…'
                    : professionalCompleted
                      ? 'Export Professional PDF'
                      : 'Preview Basic PDF ($0 · No AI)'}
                </button>
                {packChoice === 'professional' && !professionalCompleted ? (
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={() => void exportAndPreview()}
                    disabled={busy}
                  >
                    <FileText size={14} aria-hidden />
                    Preview Basic PDF anyway ($0 · No AI)
                  </button>
                ) : null}
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => void downloadPdf()}
                  disabled={busy || !draft.latest_export}
                >
                  <Download size={14} aria-hidden />
                  Download last PDF
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => void save({ bump: false })}
                  disabled={busy}
                >
                  <Save size={14} aria-hidden />
                  Save draft
                </button>
              </div>
            </section>
          ) : null}

          <div className={styles.navRow}>
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={busy || stageIdx === 0}
              onClick={() => void goStage(STAGES[stageIdx - 1].id)}
            >
              <ChevronLeft size={14} aria-hidden />
              Back
            </button>
            {stageIdx < STAGES.length - 1 ? (
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={busy}
                onClick={() => void goStage(STAGES[stageIdx + 1].id)}
              >
                Continue
                <ChevronRight size={14} aria-hidden />
              </button>
            ) : null}
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={busy}
              onClick={() => void save({ bump: true })}
            >
              Save + bump revision
            </button>
          </div>
          {error && stage !== 'generate' ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          {notice ? <p className={styles.notice}>{notice}</p> : null}
        </div>
        ) : (
        <div className={styles.mobileHub} ref={formPaneRef}>
          <p className={styles.mobileHubLead}>
            Tap a step above to open its full-screen form. On phones, each step is a modal so fields are not buried under the look preview.
          </p>
          <button
            type="button"
            className={`${styles.primaryBtn} ${styles.mobileMeasureCta}`}
            onClick={() => openStageSheet(stage)}
            disabled={busy}
          >
            Open Step {stageIdx + 1}: {STAGES[stageIdx]?.label}
          </button>
          <ul className={styles.mobileHubHints}>
            <li>Step 1 — title, style code, outfit pieces</li>
            <li>Step 2 — fabric, closure, silhouette</li>
            <li>Step 3 — body & finished measurements</li>
            <li>Step 4 — Basic or AI Professional pack</li>
          </ul>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          {notice ? <p className={styles.notice}>{notice}</p> : null}
        </div>
        )}

        {isMobileViewport ? (
          <StageSheet
            open={stageSheetOpen && stage !== 'measurements'}
            stepIndex={stageIdx + 1}
            title={STAGES[stageIdx]?.label ?? 'Step'}
            subtitle="Fill this step, then Save or Continue. Empty measurement fields are OK."
            busy={busy}
            onClose={() => setStageSheetOpen(false)}
            onSave={async () => {
              const saved = await save({ workflow: stage, silent: false })
              if (saved) setStageSheetOpen(false)
            }}
            onContinue={async () => {
              await save({ workflow: stage, silent: true })
              if (stageIdx < STAGES.length - 1) {
                await goStage(STAGES[stageIdx + 1].id)
              } else {
                setStageSheetOpen(false)
              }
            }}
            continueLabel={stageIdx < STAGES.length - 1 ? 'Save & next step' : 'Done'}
            showContinue
          >
          {stage === 'understand' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-understand"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-understand" className={styles.sectionTitle}>
                1 · Understand My Design
              </h2>
              <p className={styles.sectionLead}>
                Review Magic Front/Back and correct outfit pieces. Detection is a starting point —
                never treat categories as guaranteed.
              </p>

              <div className={styles.lookThumbs}>
                <div>
                  <p className={styles.lookLabel}>Front</p>
                  <div className={styles.lookThumb}>
                    {frontImg.url ? (
                      <img src={frontImg.url} alt="Front look" />
                    ) : (
                      <span>{draft.front_job_id ? 'Loading…' : 'Not available'}</span>
                    )}
                  </div>
                </div>
                <div>
                  <p className={styles.lookLabel}>Back</p>
                  <div className={styles.lookThumb}>
                    {backImg.url ? (
                      <img src={backImg.url} alt="Back look" />
                    ) : (
                      <span>{draft.back_job_id ? 'Loading…' : 'Not fabricated'}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className={styles.grid2}>
                <div className={styles.field}>
                  <label htmlFor="tp-title">Title</label>
                  <input
                    id="tp-title"
                    value={title}
                    maxLength={160}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div className={styles.field}>
                  <label htmlFor="tp-style">Style code</label>
                  <input
                    id="tp-style"
                    value={styleCode}
                    maxLength={64}
                    onChange={(e) => setStyleCode(e.target.value.toUpperCase())}
                  />
                </div>
              </div>

              <h3 className={styles.sectionTitle} style={{ marginTop: 16 }}>
                Outfit · {pieces.length} piece{pieces.length === 1 ? '' : 's'}
              </h3>
              {spec.outfit?.note ? <p className={styles.sectionLead}>{spec.outfit.note}</p> : null}

              {pieces.map((piece) => (
                <div key={piece.id} className={styles.pieceCard}>
                  <div className={styles.pieceCardHead}>
                    <strong>{pieceTabLabel(piece)}</strong>
                    <button
                      type="button"
                      className={styles.dangerBtn}
                      onClick={() => removePiece(piece.id)}
                      disabled={busy || pieces.length <= 1}
                      aria-label={`Remove ${piece.label}`}
                    >
                      <Trash2 size={14} aria-hidden />
                      Remove
                    </button>
                  </div>
                  <div className={styles.grid2}>
                    <div className={styles.field}>
                      <label htmlFor={`cat-${piece.id}`}>Category</label>
                      <select
                        id={`cat-${piece.id}`}
                        value={piece.category}
                        onChange={(e) => {
                          const cat = e.target.value
                          updatePiece(piece.id, (p) =>
                            retargetFinishedMeasurements(
                              { ...p, category: cat, role: cat },
                              cat,
                              spec.units || 'cm',
                            ),
                          )
                        }}
                      >
                        {PIECE_CATEGORIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className={styles.field}>
                      <label htmlFor={`label-${piece.id}`}>Label</label>
                      <input
                        id={`label-${piece.id}`}
                        value={piece.label}
                        onChange={(e) =>
                          updatePiece(piece.id, (p) => ({ ...p, label: e.target.value }))
                        }
                      />
                    </div>
                    <div className={styles.field}>
                      <label htmlFor={`color-${piece.id}`}>Color hint</label>
                      <input
                        id={`color-${piece.id}`}
                        value={piece.color_hint ?? ''}
                        onChange={(e) =>
                          updatePiece(piece.id, (p) => ({ ...p, color_hint: e.target.value }))
                        }
                      />
                    </div>
                  </div>
                </div>
              ))}

              <button type="button" className={styles.ghostBtn} onClick={addPiece} disabled={busy}>
                <Plus size={14} aria-hidden />
                Add piece
              </button>
            </section>
          ) : null}

          {stage === 'customize' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-customize"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-customize" className={styles.sectionTitle}>
                2 · Customize Each Piece
              </h2>
              <p className={styles.sectionLead}>
                Set shell fabric, composition, closure, and silhouette per piece. Shared notes live
                under Outfit Overview.
              </p>
              <div className={styles.garmentTabs} role="tablist" aria-label="Garment pieces">
                <button
                  type="button"
                  role="tab"
                  aria-selected={activePieceId === 'overview'}
                  className={
                    activePieceId === 'overview'
                      ? `${styles.garmentTab} ${styles.garmentTabActive}`
                      : styles.garmentTab
                  }
                  onClick={() => setActivePieceId('overview')}
                >
                  Outfit Overview
                </button>
                {pieces.map((piece) => (
                  <button
                    key={piece.id}
                    type="button"
                    role="tab"
                    aria-selected={activePieceId === piece.id}
                    className={
                      activePieceId === piece.id
                        ? `${styles.garmentTab} ${styles.garmentTabActive}`
                        : styles.garmentTab
                    }
                    onClick={() => setActivePieceId(piece.id)}
                  >
                    {pieceTabLabel(piece)}
                  </button>
                ))}
              </div>

              {activePieceId === 'overview' ? (
                <div className={styles.pieceCard}>
                  <div className={styles.grid2}>
                    <div className={styles.field}>
                      <label htmlFor="tp-size-system">Size system</label>
                      <select
                        id="tp-size-system"
                        value={spec.size_system || 'EU'}
                        onChange={(e) => setSpec((p) => (p ? { ...p, size_system: e.target.value } : p))}
                      >
                        <option value="EU">EU</option>
                        <option value="US">US</option>
                        <option value="UK">UK</option>
                        <option value="Alpha">Alpha</option>
                      </select>
                    </div>
                    <div className={styles.field}>
                      <label htmlFor="tp-units">Units</label>
                      <select
                        id="tp-units"
                        value={spec.units || 'cm'}
                        onChange={(e) => setSpec((p) => (p ? { ...p, units: e.target.value } : p))}
                      >
                        <option value="cm">cm</option>
                        <option value="in">in</option>
                      </select>
                    </div>
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <label htmlFor="tp-look-notes">Shared look notes</label>
                    <textarea
                      id="tp-look-notes"
                      value={spec.look_notes ?? ''}
                      onChange={(e) =>
                        setSpec((p) => (p ? { ...p, look_notes: e.target.value } : p))
                      }
                      placeholder="Overall outfit notes shared across pieces…"
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <label htmlFor="tp-designer-notes">Designer notes</label>
                    <textarea
                      id="tp-designer-notes"
                      value={spec.designer_notes ?? ''}
                      onChange={(e) =>
                        setSpec((p) => (p ? { ...p, designer_notes: e.target.value } : p))
                      }
                      placeholder="Construction preferences, trims, fit intent…"
                    />
                  </div>
                </div>
              ) : activePiece ? (
                <div className={styles.pieceCard}>
                  <div className={styles.field}>
                    <LabelWithHelp
                      htmlFor={`shell-${activePiece.id}`}
                      label="Shell fabric"
                      helpKey="shell_fabric"
                    />
                    <input
                      id={`shell-${activePiece.id}`}
                      value={activePiece.materials?.shell?.name ?? ''}
                      onChange={(e) => {
                        const name = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: {
                              ...p.materials?.shell,
                              name,
                              source: name.trim() ? 'designer' : 'empty',
                            },
                          },
                        }))
                      }}
                    />
                    <ChipRow
                      options={SHELL_SUGGESTIONS}
                      value={activePiece.materials?.shell?.name ?? ''}
                      onPick={(name) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: { ...p.materials?.shell, name, source: 'designer' },
                          },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`comp-${activePiece.id}`}
                      label="Composition"
                      helpKey="composition"
                    />
                    <input
                      id={`comp-${activePiece.id}`}
                      value={activePiece.materials?.shell?.composition ?? ''}
                      onChange={(e) => {
                        const composition = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...p.materials,
                            shell: { ...p.materials?.shell, composition },
                          },
                        }))
                      }}
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`closure-${activePiece.id}`}
                      label="Closure"
                      helpKey="closure"
                    />
                    <input
                      id={`closure-${activePiece.id}`}
                      value={activePiece.closures?.type ?? ''}
                      onChange={(e) => {
                        const type = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: {
                            ...p.closures,
                            type,
                            source: type.trim() ? 'designer' : 'empty',
                          },
                        }))
                      }}
                    />
                    <ChipRow
                      options={CLOSURE_SUGGESTIONS}
                      value={activePiece.closures?.type ?? ''}
                      onPick={(type) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: { ...p.closures, type, source: 'designer' },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.field} style={{ marginTop: 10 }}>
                    <LabelWithHelp
                      htmlFor={`sil-${activePiece.id}`}
                      label="Silhouette"
                      helpKey="silhouette"
                    />
                    <input
                      id={`sil-${activePiece.id}`}
                      value={activePiece.fit?.silhouette ?? ''}
                      onChange={(e) => {
                        const silhouette = e.target.value
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...p.fit, silhouette },
                        }))
                      }}
                    />
                    <ChipRow
                      options={SILHOUETTE_SUGGESTIONS}
                      value={activePiece.fit?.silhouette ?? ''}
                      onPick={(silhouette) =>
                        updatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...p.fit, silhouette },
                        }))
                      }
                    />
                  </div>
                  <details className={styles.advanced}>
                    <summary>Advanced details</summary>
                    <div className={styles.advancedBody}>
                      <div className={styles.field}>
                        <label htmlFor={`closure-notes-${activePiece.id}`}>Closure notes</label>
                        <textarea
                          id={`closure-notes-${activePiece.id}`}
                          value={activePiece.closures?.notes ?? ''}
                          onChange={(e) =>
                            updatePiece(activePiece.id, (p) => ({
                              ...p,
                              closures: { ...p.closures, notes: e.target.value },
                            }))
                          }
                        />
                      </div>
                      <div className={styles.field} style={{ marginTop: 8 }}>
                        <label htmlFor={`ease-${activePiece.id}`}>Ease note</label>
                        <input
                          id={`ease-${activePiece.id}`}
                          value={activePiece.fit?.ease_note ?? ''}
                          onChange={(e) =>
                            updatePiece(activePiece.id, (p) => ({
                              ...p,
                              fit: { ...p.fit, ease_note: e.target.value },
                            }))
                          }
                        />
                      </div>
                    </div>
                  </details>
                </div>
              ) : null}
            </section>
          ) : null}

          {stage === 'measurements' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-meas"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-meas" className={styles.sectionTitle}>
                3 · Measurements and Preferences
              </h2>
              <p className={styles.sectionLead}>
                Body measurements are about the person. Finished POMs are garment-specific — trousers
                never show bust or sleeve fields. Unknown values may stay empty; Stage 4 does not
                require every field.
              </p>

              {isMobileViewport ? (
                <div className={styles.mobileMeasureCard}>
                  <button
                    type="button"
                    className={`${styles.primaryBtn} ${styles.mobileMeasureCta}`}
                    onClick={openMeasureSheet}
                    disabled={busy}
                    autoFocus
                  >
                    Edit Measurements
                  </button>
                  <p>
                    Full-screen editor with large number fields. Unit and source stay one tap away.
                    Empty fields are fine — continue to Step 4 when ready.
                  </p>
                  <ul className={styles.mobileMeasureSummary}>
                    <li>
                      Body fields started:{' '}
                      {['height', 'bust', 'waist', 'hip'].filter((k) => {
                        const v = spec.body?.[k]?.value
                        return v !== null && v !== undefined && String(v).trim() !== ''
                      }).length}
                      /4 (empty OK)
                    </li>
                    <li>Garment pieces with finished POMs: {pieces.length}</li>
                    <li>Units: {spec.units || 'cm'}</li>
                  </ul>
                </div>
              ) : (
                <>
                  <div className={styles.garmentTabs} role="tablist" aria-label="Measurement focus">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activePieceId === 'overview'}
                      className={
                        activePieceId === 'overview'
                          ? `${styles.garmentTab} ${styles.garmentTabActive}`
                          : styles.garmentTab
                      }
                      onClick={() => setActivePieceId('overview')}
                    >
                      Body & preferences
                    </button>
                    {pieces.map((piece) => (
                      <button
                        key={piece.id}
                        type="button"
                        role="tab"
                        aria-selected={activePieceId === piece.id}
                        className={
                          activePieceId === piece.id
                            ? `${styles.garmentTab} ${styles.garmentTabActive}`
                            : styles.garmentTab
                        }
                        onClick={() => setActivePieceId(piece.id)}
                      >
                        {pieceTabLabel(piece)}
                      </button>
                    ))}
                  </div>

                  {activePieceId === 'overview' ? (
                    <>
                      <h3 className={styles.sectionTitle}>Body measurements</h3>
                      {(
                        [
                          ['height', 'Height', 'height'],
                          ['bust', 'Bust', 'bust'],
                          ['waist', 'Waist', 'waist'],
                          ['hip', 'Hip', 'hip'],
                          ['inseam', 'Inseam', 'body_inseam'],
                        ] as const
                      ).map(([key, label, helpKey]) => (
                        <MeasuredField
                          key={key}
                          label={label}
                          helpKey={helpKey}
                          value={spec.body?.[key] ?? measured(null, spec.units || 'cm')}
                          onChange={(next) =>
                            setSpec((prev) =>
                              prev
                                ? { ...prev, body: { ...(prev.body ?? {}), [key]: next } }
                                : prev,
                            )
                          }
                        />
                      ))}
                      <div className={styles.grid2} style={{ marginTop: 12 }}>
                        <div className={styles.field}>
                          <label htmlFor="tp-fit-pref">Fit preference</label>
                          <select
                            id="tp-fit-pref"
                            value={spec.preferences?.fit_preference || 'regular'}
                            onChange={(e) =>
                              setSpec((prev) =>
                                prev
                                  ? {
                                      ...prev,
                                      preferences: {
                                        ...(prev.preferences ?? {}),
                                        fit_preference: e.target.value,
                                      },
                                    }
                                  : prev,
                              )
                            }
                          >
                            {FIT_PREFERENCES.map((f) => (
                              <option key={f} value={f}>
                                {f}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="tp-sample-size">Sample size</label>
                          <input
                            id="tp-sample-size"
                            value={spec.sample_size ?? ''}
                            onChange={(e) =>
                              setSpec((prev) =>
                                prev ? { ...prev, sample_size: e.target.value } : prev,
                              )
                            }
                            placeholder="e.g. 36 / M"
                          />
                        </div>
                      </div>
                      <details className={styles.advanced}>
                        <summary>Advanced preferences</summary>
                        <div className={styles.advancedBody}>
                          <div className={styles.field}>
                            <label htmlFor="tp-pref-notes">Preference notes</label>
                            <textarea
                              id="tp-pref-notes"
                              value={spec.preferences?.notes ?? ''}
                              onChange={(e) =>
                                setSpec((prev) =>
                                  prev
                                    ? {
                                        ...prev,
                                        preferences: {
                                          ...(prev.preferences ?? {}),
                                          notes: e.target.value,
                                        },
                                      }
                                    : prev,
                                )
                              }
                            />
                          </div>
                        </div>
                      </details>
                    </>
                  ) : activePiece ? (
                    <>
                      <h3 className={styles.sectionTitle}>
                        Finished measurements · {pieceTabLabel(activePiece)}
                      </h3>
                      {Object.keys(activePiece.finished_measurements ?? {}).length === 0 ? (
                        <p className={styles.sectionLead}>
                          No finished POMs for this category (e.g. set). Add piece-level notes
                          instead.
                        </p>
                      ) : (
                        Object.entries(activePiece.finished_measurements ?? {}).map(
                          ([key, value]) => (
                            <MeasuredField
                              key={key}
                              label={POM_LABELS[key] ?? key.replace(/_/g, ' ')}
                              helpKey={POM_HELP_KEY[key]}
                              value={value}
                              onChange={(next) =>
                                updatePiece(activePiece.id, (p) => ({
                                  ...p,
                                  finished_measurements: {
                                    ...(p.finished_measurements ?? {}),
                                    [key]: next,
                                  },
                                }))
                              }
                            />
                          ),
                        )
                      )}
                    </>
                  ) : null}
                </>
              )}
            </section>
          ) : null}

          {stage === 'generate' ? (
            <section
              className={styles.section}
              aria-labelledby="stage-gen"
              ref={(node) => {
                stageSectionRef.current = node
              }}
            >
              <h2 id="stage-gen" className={styles.sectionTitle}>
                4 · Generate Technical Design
              </h2>
              <p className={styles.sectionLead}>
                Choose Basic ($0) or AI Professional (paid). Preview and Download never run paid AI —
                they only export what already exists for this draft.
              </p>

              {error ? (
                <div className={styles.aiErrorPanel} role="alert">
                  <p ref={aiErrorRef} className={styles.aiErrorText}>
                    {error}
                  </p>
                  {/server configuration problem|design is safe/i.test(error) ? (
                    <p className={styles.aiErrorHint}>
                      No chargeable AI work ran for this attempt. You can request a new cost estimate
                      after the fix is live.
                    </p>
                  ) : null}
                </div>
              ) : null}

              <div
                className={
                  generationProvenanceLabel.kind === 'professional'
                    ? `${styles.provenanceBanner} ${styles.provenanceProfessional}`
                    : `${styles.provenanceBanner} ${styles.provenanceBasic}`
                }
                role="status"
              >
                <strong>{generationProvenanceLabel.title}</strong>
                <span>{generationProvenanceLabel.detail}</span>
                {professionalCompleted ? (
                  <span className={styles.provenanceMeta}>
                    Models:{' '}
                    {[aiStatus?.vision_model || spec?.ai?.vision_model, aiStatus?.image_model || spec?.ai?.image_model]
                      .filter(Boolean)
                      .join(' + ') || '—'}
                  </span>
                ) : null}
              </div>

              <ol className={styles.workflowSteps} aria-label="AI Professional workflow">
                <li>Select pack type</li>
                <li>Cost estimate</li>
                <li>Confirm</li>
                <li>Generate</li>
                <li>Review illustrations</li>
                <li>Export PDF</li>
              </ol>

              <p className={styles.diffNote}>
                <strong style={{ color: 'var(--fr-text)' }}>Basic PDF / $0</strong> — local
                heuristics and lightweight schematics. No paid model calls.{' '}
                <strong style={{ color: 'var(--fr-text)' }}>AI Professional / paid</strong> —
                analyzes your Magic image and generates design-specific technical drawings after an
                explicit cost confirmation.
              </p>

              <div className={styles.packChoices} role="radiogroup" aria-label="Technical pack type">
                <button
                  type="button"
                  role="radio"
                  aria-checked={packChoice === 'basic'}
                  className={
                    packChoice === 'basic'
                      ? `${styles.packCard} ${styles.packCardActive}`
                      : styles.packCard
                  }
                  onClick={() => selectPackChoice('basic')}
                  disabled={busy}
                >
                  <span className={styles.packCardTitle}>Basic Technical Pack — Free</span>
                  <span className={styles.packCardBody}>
                    Existing heuristic generate. Lightweight schematics. No paid calls.
                  </span>
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={packChoice === 'professional'}
                  aria-disabled={!professionalAvailable}
                  className={[
                    styles.packCard,
                    packChoice === 'professional' ? styles.packCardActive : '',
                    !professionalAvailable ? styles.packCardDisabled : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => selectPackChoice('professional')}
                  disabled={busy || !professionalAvailable}
                >
                  <span className={styles.packCardTitle}>AI Professional Technical Pack</span>
                  <span className={styles.packCardBody}>
                    Paid AI technical illustrations (flat front / related). Requires confirm +
                    allowance.
                  </span>
                  {!professionalAvailable ? (
                    <span className={styles.packCardHint}>
                      {professionalDisabledReason ||
                        'Unavailable — owner allowlist / spend ceiling not configured.'}
                    </span>
                  ) : (
                    <span className={styles.packCardHint}>
                      Est.{' '}
                      {aiStatus?.estimate_professional_cents_min ?? '—'}–
                      {aiStatus?.estimate_professional_cents_max ??
                        aiStatus?.estimate_chat_cents ??
                        '—'}
                      ¢ · max ${aiStatus?.max_usd_per_run ?? '—'} / run
                    </span>
                  )}
                </button>
              </div>

              <div className={styles.aiPanel}>
                {packChoice === 'basic' ? (
                  <>
                    <p>
                      Basic pack always available at <strong style={{ color: 'var(--fr-text)' }}>$0</strong>.
                      Prepare a confirm token, then generate heuristic content.
                    </p>
                    {confirm && confirm.mode !== 'professional' ? (
                      <div className={styles.confirmBox}>
                        <p>
                          Estimated cost:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            {confirm.estimated_cost_usd_cents}¢
                          </strong>{' '}
                          (heuristic / $0)
                        </p>
                        <p>{confirm.message}</p>
                        <label>
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                          />
                          <span>
                            I confirm generating a Basic Technical Pack. Output remains DRAFT /
                            UNVERIFIED.
                          </span>
                        </label>
                      </div>
                    ) : null}
                    <div className={styles.actions} style={{ marginTop: 12 }}>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        disabled={busy}
                        onClick={() => void prepareGenerate('heuristic')}
                      >
                        <Sparkles size={14} aria-hidden />
                        Get confirm token
                      </button>
                      <button
                        type="button"
                        className={styles.primaryBtn}
                        disabled={busy || !confirm || !confirmed || packChoice !== 'basic'}
                        onClick={() => void runGenerate()}
                      >
                        <Sparkles size={14} aria-hidden />
                        {busy ? 'Working…' : 'Generate Basic Pack'}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p>
                      AI Professional uses vision + image models when your account is allowlisted
                      and a spend ceiling is configured.
                    </p>
                    <p className={styles.costLine}>
                      {confirm ? (
                        <>
                          Estimated cost:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            {confirm.estimated_cost_usd_cents}¢
                          </strong>
                          {' · '}
                          Max allowance:{' '}
                          <strong style={{ color: 'var(--fr-text)' }}>
                            ${confirm.max_usd_per_run ?? aiStatus?.max_usd_per_run ?? '—'}
                          </strong>
                          {' / run'}
                        </>
                      ) : (
                        <>
                          Status estimate:{' '}
                          {aiStatus?.estimate_professional_cents_min ?? '—'}–
                          {aiStatus?.estimate_professional_cents_max ?? '—'}¢ · max $
                          {aiStatus?.max_usd_per_run ?? '—'} / run
                          {aiStatus?.vision_model || aiStatus?.image_model
                            ? ` · ${[aiStatus.vision_model, aiStatus.image_model]
                                .filter(Boolean)
                                .join(' + ')}`
                            : ''}
                        </>
                      )}
                    </p>
                    <label className={styles.checkRow}>
                      <input
                        type="checkbox"
                        checked={proposeBack}
                        onChange={(e) => setProposeBack(e.target.checked)}
                      />
                      <span>Propose unverified back view (only if no Magic back)</span>
                    </label>
                    {confirm ? (
                      <div className={styles.confirmBox}>
                        <p>{confirm.message}</p>
                        <label>
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                          />
                          <span>
                            I confirm generating an AI Professional Technical Pack and accept the
                            estimated cost. Output remains DRAFT / UNVERIFIED.
                          </span>
                        </label>
                      </div>
                    ) : null}
                    <div className={styles.actions} style={{ marginTop: 12 }}>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        disabled={busy || !professionalAvailable}
                        onClick={() => void prepareGenerate('professional')}
                      >
                        <Sparkles size={14} aria-hidden />
                        Get cost estimate
                      </button>
                      <button
                        type="button"
                        className={styles.primaryBtn}
                        disabled={
                          busy ||
                          !professionalAvailable ||
                          !confirm ||
                          !confirmed ||
                          packChoice !== 'professional'
                        }
                        onClick={() => void runGenerate()}
                      >
                        <Sparkles size={14} aria-hidden />
                        {busy ? 'Working…' : 'Generate Professional Pack'}
                      </button>
                    </div>
                  </>
                )}
                {generateProgress ? (
                  <p className={styles.progressStatus} role="status">
                    {generateProgress}
                  </p>
                ) : null}
              </div>

              {artifactPreviews.length > 0 ? (
                <div className={styles.artifactGrid} aria-label="Generated technical illustrations">
                  <h3 className={styles.sectionTitle}>Technical illustrations</h3>
                  {analysisSummary ? (
                    <p className={styles.sectionLead}>{analysisSummary}</p>
                  ) : null}
                  <div className={styles.artifactThumbs}>
                    {artifactPreviews.map((art) => (
                      <figure key={art.id} className={styles.artifactThumb}>
                        <img src={art.url} alt={`${art.kind} technical illustration`} />
                        <figcaption>
                          {art.kind}
                          {art.review_state ? ` · ${art.review_state}` : ''}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                </div>
              ) : null}

              {failedSections.length > 0 ? (
                <div className={styles.actions} style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    disabled={busy || !professionalAvailable}
                    onClick={() => void retryFailedSections()}
                  >
                    Retry failed sections ({failedSections.join(', ')})
                  </button>
                </div>
              ) : null}

              {lastWarnings.length > 0 || (spec.warnings && spec.warnings.length > 0) ? (
                <div className={styles.warnings} role="status">
                  <strong>Warnings</strong>
                  <ul>
                    {(lastWarnings.length
                      ? lastWarnings
                      : (spec.warnings ?? []).map((w) =>
                          typeof w === 'string'
                            ? w
                            : String((w as { message?: string }).message || JSON.stringify(w)),
                        )
                    ).map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <h3 className={styles.sectionTitle} style={{ marginTop: 16 }}>
                Progress
              </h3>
              <ul className={styles.progressList}>
                <li data-done={completion.pieces ? 'true' : 'false'}>
                  {completion.pieces ? <Check size={14} /> : '·'} Outfit pieces reviewed
                </li>
                <li data-done={completion.customize ? 'true' : 'false'}>
                  {completion.customize ? <Check size={14} /> : '·'} Piece materials / silhouette started
                </li>
                <li data-done={completion.measurements ? 'true' : 'false'}>
                  {completion.measurements ? <Check size={14} /> : '·'} Body measurements started
                </li>
                <li data-done={completion.generate ? 'true' : 'false'}>
                  {completion.generate ? <Check size={14} /> : '·'} Technical generation or PDF export
                </li>
              </ul>

              <p className={styles.exportNote} role="note">
                Preview / Download / Save never execute AI. They only assemble a PDF from the current
                draft
                {professionalCompleted
                  ? ' including completed AI Professional illustrations.'
                  : ' as a Basic / No AI Professional export.'}
              </p>

              <div className={styles.actions} style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className={styles.primaryBtn}
                  onClick={() => void exportAndPreview()}
                  disabled={busy || (packChoice === 'professional' && !professionalCompleted)}
                  title={
                    packChoice === 'professional' && !professionalCompleted
                      ? 'Generate AI Professional illustrations first'
                      : undefined
                  }
                >
                  <FileText size={14} aria-hidden />
                  {busy
                    ? 'Working…'
                    : professionalCompleted
                      ? 'Export Professional PDF'
                      : 'Preview Basic PDF ($0 · No AI)'}
                </button>
                {packChoice === 'professional' && !professionalCompleted ? (
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={() => void exportAndPreview()}
                    disabled={busy}
                  >
                    <FileText size={14} aria-hidden />
                    Preview Basic PDF anyway ($0 · No AI)
                  </button>
                ) : null}
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => void downloadPdf()}
                  disabled={busy || !draft.latest_export}
                >
                  <Download size={14} aria-hidden />
                  Download last PDF
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => void save({ bump: false })}
                  disabled={busy}
                >
                  <Save size={14} aria-hidden />
                  Save draft
                </button>
              </div>
            </section>
          ) : null}

          </StageSheet>
        ) : null}

        <div className={styles.previewPane}>
          <h2 className={styles.sectionTitle}>PDF preview</h2>
          <p className={styles.previewProvenance}>
            {professionalCompleted
              ? 'Export will label AI Professional when illustrations exist for this draft.'
              : 'Exports without a completed Professional run are labeled Basic / No AI generated.'}
          </p>
          {previewUrl ? (
            <iframe className={styles.previewFrame} title="Tech pack PDF preview" src={previewUrl} />
          ) : (
            <div className={styles.previewEmpty}>
              Complete the stages, optionally generate technical content, then Preview PDF.
              <br />
              Preview never runs paid AI. Every export starts as DRAFT / UNVERIFIED.
            </div>
          )}
        </div>
      </div>

      {spec ? (
        <MeasurementsSheet
          open={measureSheetOpen}
          draftKey={draft.id}
          spec={spec}
          pieces={pieces}
          busy={busy}
          onChangeSpec={(updater) => setSpec((prev) => (prev ? updater(prev) : prev))}
          onUpdatePiece={updatePiece}
          onSaveAndDone={saveMeasureSheet}
          onDiscardAndClose={discardMeasureSheet}
        />
      ) : null}
    </div>
  )
}

export type { WorkflowStage }
