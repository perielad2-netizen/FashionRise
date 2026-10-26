import { useCallback, useEffect, useMemo, useState } from 'react'
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
  fetchTechpackPdfBlob,
  generateTechpackAi,
  getTechpackAiStatus,
  getTechpackDraft,
  updateTechpackDraft,
  type MeasuredValue,
  type TechpackAiConfirmResponse,
  type TechpackAiStatus,
  type TechpackDraft,
  type TechpackPiece,
  type TechpackSpecV2,
} from '@/services/techpacksApi'
import { FieldHelp } from '@/shell/components/techpack/FieldHelp'
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

type Props = {
  draftId: string
  onBack: () => void
}

type WorkflowStage = 'understand' | 'customize' | 'measurements' | 'generate'

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

function MeasuredField({
  label,
  value,
  onChange,
  helpKey,
}: {
  label: string
  value: MeasuredValue
  onChange: (next: MeasuredValue) => void
  helpKey?: string
}) {
  const help = helpKey ? getFieldHelp(helpKey) : null
  return (
    <div className={styles.measureRow}>
      <div className={styles.field}>
        <div className={styles.fieldLabelRow}>
          <label>{label}</label>
          {help ? (
            <FieldHelp
              title={help.title}
              explanation={help.explanation}
              examples={help.examples}
              diagram={help.diagram}
            />
          ) : null}
        </div>
        <input
          type="text"
          inputMode="decimal"
          value={value.value ?? ''}
          placeholder="—"
          onChange={(e) => {
            const raw = e.target.value.trim()
            onChange({
              ...value,
              value: raw === '' ? null : Number.isFinite(Number(raw)) ? Number(raw) : raw,
              source: raw === '' ? 'empty' : value.source === 'empty' ? 'designer' : value.source,
            })
          }}
        />
      </div>
      <div className={styles.field}>
        <label>Unit</label>
        <input
          type="text"
          value={value.unit ?? ''}
          onChange={(e) => onChange({ ...value, unit: e.target.value })}
        />
      </div>
      <div className={styles.field}>
        <label>Source</label>
        <select
          value={value.source}
          onChange={(e) =>
            onChange({ ...value, source: e.target.value as MeasuredValue['source'] })
          }
        >
          <option value="empty">Empty</option>
          <option value="designer">Designer</option>
          <option value="estimate">Estimate</option>
          <option value="look">Look</option>
          <option value="calculated">Calculated</option>
          <option value="unknown">Unknown</option>
          <option value="ai">AI (unverified)</option>
        </select>
      </div>
    </div>
  )
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
  const [confirm, setConfirm] = useState<TechpackAiConfirmResponse | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [lastWarnings, setLastWarnings] = useState<string[]>([])

  const frontImg = useAuthJobImage(draft?.front_job_id ?? null, Boolean(draft?.front_job_id))
  const backImg = useAuthJobImage(draft?.back_job_id ?? null, Boolean(draft?.back_job_id))

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
    const first = wrapped.spec.outfit?.pieces?.[0]
    setActivePieceId(first?.id ?? 'overview')
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

  const statusLabel = useMemo(() => {
    if (!draft) return 'DRAFT / UNVERIFIED'
    return `${draft.status} / ${draft.verification}`
  }, [draft])

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

  const goStage = async (next: WorkflowStage) => {
    setStage(next)
    setSpec((prev) => (prev ? { ...prev, workflow_stage: next } : prev))
    if (next === 'customize' || next === 'measurements') {
      const first = pieces[0]
      if (first && (activePieceId === 'overview' || !pieces.some((p) => p.id === activePieceId))) {
        setActivePieceId(first.id)
      }
    }
    await save({ workflow: next, silent: true })
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

  const prepareGenerate = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    setConfirmed(false)
    try {
      await save({ workflow: 'generate', silent: true })
      const challenge = await confirmTechpackAi(draftId, 'generate')
      setConfirm(challenge)
      setNotice(challenge.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not prepare generation')
      setConfirm(null)
    } finally {
      setBusy(false)
    }
  }

  const runGenerate = async () => {
    if (!confirm?.confirm_token) {
      setError('Confirm generation first.')
      return
    }
    if (!confirmed) {
      setError('Check the confirmation box before generating.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await save({ workflow: 'generate', silent: true })
      const mode = confirm.ai_enabled ? 'ai' : 'heuristic'
      const result = await generateTechpackAi(draftId, {
        confirm_token: confirm.confirm_token,
        idempotency_key: `gen-${draftId}-${Date.now()}`,
        mode,
      })
      const warns = (result.warnings ?? [])
        .map((w) => (typeof w === 'string' ? w : String((w as { message?: string }).message || JSON.stringify(w))))
        .filter(Boolean)
      setLastWarnings(warns)
      const refreshed = await getTechpackDraft(draftId)
      hydrate(refreshed)
      setNotice(
        result.mode === 'ai'
          ? `AI technical pack ready · ${result.cost_usd_cents}¢ · still DRAFT/UNVERIFIED`
          : 'Heuristic technical pack ready · $0 · still DRAFT/UNVERIFIED',
      )
      setConfirm(null)
      setConfirmed(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed')
    } finally {
      setBusy(false)
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
      setNotice(
        `PDF ready · ${exported.page_count} pages · ${exported.status}/${exported.verification}`,
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
              onClick={() => void goStage(s.id)}
              disabled={busy}
            >
              <span className={styles.stepIndex}>{done && stage !== s.id ? <Check size={12} /> : idx + 1}</span>
              <span>{s.label}</span>
            </button>
          )
        })}
      </nav>

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
        <div className={styles.formPane}>
          {stage === 'understand' ? (
            <section className={styles.section} aria-labelledby="stage-understand">
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
            <section className={styles.section} aria-labelledby="stage-customize">
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
            <section className={styles.section} aria-labelledby="stage-meas">
              <h2 id="stage-meas" className={styles.sectionTitle}>
                3 · Measurements and Preferences
              </h2>
              <p className={styles.sectionLead}>
                Body measurements are about the person. Finished POMs are garment-specific — trousers
                never show bust or sleeve fields.
              </p>

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
                          setSpec((prev) => (prev ? { ...prev, sample_size: e.target.value } : prev))
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
                      No finished POMs for this category (e.g. set). Add piece-level notes instead.
                    </p>
                  ) : (
                    Object.entries(activePiece.finished_measurements ?? {}).map(([key, value]) => (
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
                    ))
                  )}
                </>
              ) : null}
            </section>
          ) : null}

          {stage === 'generate' ? (
            <section className={styles.section} aria-labelledby="stage-gen">
              <h2 id="stage-gen" className={styles.sectionTitle}>
                4 · Generate Technical Design
              </h2>
              <p className={styles.sectionLead}>
                Heuristic generation is always available at $0. Paid AI only runs when enabled and
                after explicit confirmation — this screen never invents a payment UI.
              </p>

              <div className={styles.aiPanel}>
                <p>
                  <strong style={{ color: 'var(--fr-text)' }}>AI status:</strong>{' '}
                  {aiStatus
                    ? aiStatus.enabled
                      ? `Enabled · estimate ~${aiStatus.estimate_chat_cents ?? confirm?.estimated_cost_usd_cents ?? '—'}¢ · ${aiStatus.model || 'model n/a'}`
                      : 'Paid AI disabled — heuristic technical pack available at $0'
                    : 'Status unavailable — you can still try heuristic generate after confirm'}
                </p>
                {aiStatus?.note ? <p>{aiStatus.note}</p> : null}
                {confirm ? (
                  <div className={styles.confirmBox}>
                    <p>
                      Estimated cost:{' '}
                      <strong style={{ color: 'var(--fr-text)' }}>
                        {confirm.estimated_cost_usd_cents}¢
                      </strong>
                      {confirm.ai_enabled ? ' (paid AI available)' : ' (heuristic / $0)'}
                    </p>
                    <p>{confirm.message}</p>
                    <label>
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(e) => setConfirmed(e.target.checked)}
                      />
                      <span>
                        I confirm generating a technical design for this draft. Output remains DRAFT /
                        UNVERIFIED and needs patternmaker review.
                      </span>
                    </label>
                  </div>
                ) : null}
                <div className={styles.actions} style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    disabled={busy}
                    onClick={() => void prepareGenerate()}
                  >
                    <Sparkles size={14} aria-hidden />
                    Get cost & confirm token
                  </button>
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    disabled={busy || !confirm || !confirmed}
                    onClick={() => void runGenerate()}
                  >
                    <Sparkles size={14} aria-hidden />
                    {busy ? 'Working…' : confirm?.ai_enabled ? 'Generate with AI' : 'Generate heuristic'}
                  </button>
                </div>
              </div>

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

              <div className={styles.actions} style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className={styles.primaryBtn}
                  onClick={() => void exportAndPreview()}
                  disabled={busy}
                >
                  <FileText size={14} aria-hidden />
                  {busy ? 'Working…' : 'Preview PDF'}
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => void downloadPdf()}
                  disabled={busy || !draft.latest_export}
                >
                  <Download size={14} aria-hidden />
                  Download PDF
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
          {error ? <p className={styles.error}>{error}</p> : null}
          {notice ? <p className={styles.notice}>{notice}</p> : null}
        </div>

        <div className={styles.previewPane}>
          <h2 className={styles.sectionTitle}>PDF preview</h2>
          {previewUrl ? (
            <iframe className={styles.previewFrame} title="Tech pack PDF preview" src={previewUrl} />
          ) : (
            <div className={styles.previewEmpty}>
              Complete the stages, generate technical content, then Preview PDF.
              <br />
              Every export starts as DRAFT / UNVERIFIED.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export type { WorkflowStage }
