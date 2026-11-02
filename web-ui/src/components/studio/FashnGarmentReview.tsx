import { useMemo, useState } from 'react'
import type { FashnGarmentPrepareResult, FashnRealisticPiece } from '@/services/ai/magicApi'
import { confirmDialogStyles as styles } from './ConfirmDialog'

export type AcceptedRealismOption = {
  jobId: string
  label: string
  pieceCount: number
  categories: string[]
}

export type FashnExperimentControls = {
  ownerAllowed: boolean
  provider: 'fashn' | 'fashn_max'
  onProviderChange: (provider: 'fashn' | 'fashn_max') => void
  mode: 'balanced' | 'quality'
  onModeChange: (mode: 'balanced' | 'quality') => void
  resolution: '1k' | '2k'
  onResolutionChange: (resolution: '1k' | '2k') => void
  prompt: string
  onPromptChange: (prompt: string) => void
  promptOpen: boolean
  onTogglePrompt: () => void
  softBudgetCredits: number | null
  creditsBalanced: number | null
  creditsQuality: number | null
  estimateBalancedCents: number | null
  estimateQualityCents: number | null
  /** #176 v1.6 owner knobs */
  v16Category: 'one-pieces' | 'auto'
  onV16CategoryChange: (category: 'one-pieces' | 'auto') => void
  v16SegmentationFree: boolean
  onV16SegmentationFreeChange: (value: boolean) => void
  v16Mode: 'balanced' | 'quality'
  onV16ModeChange: (mode: 'balanced' | 'quality') => void
  v16Seed: number
  onV16SeedChange: (seed: number) => void
  acceptedOptions: AcceptedRealismOption[]
  selectedAcceptedJobId: string | null
  onSelectAcceptedJobId: (jobId: string | null) => void
  onLoadAcceptedJob: (jobId: string) => void
  acceptedLoadBusy: boolean
}

type Props = {
  prep: FashnGarmentPrepareResult
  realisticPieces: FashnRealisticPiece[] | null
  realismBusy: boolean
  realismError: string | null
  detailsOpen: boolean
  onToggleDetails: () => void
  experiment?: FashnExperimentControls | null
}

function pieceLabel(category: string, index: number, total: number): string {
  const c = category.toLowerCase()
  if (c === 'tops') return 'Top'
  if (c === 'bottoms') return 'Bottom'
  if (total === 1) return 'Garment'
  return `Piece ${index + 1}`
}

export function FashnGarmentReview({
  prep,
  realisticPieces,
  realismBusy,
  realismError,
  detailsOpen,
  onToggleDetails,
  experiment = null,
}: Props) {
  const [lightbox, setLightbox] = useState<{ src: string; label: string } | null>(null)

  const sketchPieces = prep.pieces
  const hasRealistic = Boolean(realisticPieces && realisticPieces.length > 0)
  // #176 — show owner experiment panel as soon as allowlisted (Max was invisible before realism).
  const showExperiment = Boolean(experiment?.ownerAllowed)
  const maxCredits =
    experiment?.mode === 'quality'
      ? (experiment.creditsQuality ?? 3)
      : (experiment?.creditsBalanced ?? 2)
  const maxEstimate =
    experiment?.mode === 'quality'
      ? (experiment.estimateQualityCents ?? maxCredits * 8)
      : (experiment?.estimateBalancedCents ?? maxCredits * 8)
  const fidelityFailures = useMemo(
    () => (realisticPieces ?? []).filter((p) => p.fidelity && p.fidelity.ok === false),
    [realisticPieces],
  )
  const softWarnings = useMemo(
    () =>
      (realisticPieces ?? []).filter(
        (p) =>
          p.fidelity &&
          p.fidelity.ok !== false &&
          typeof p.fidelity.message === 'string' &&
          p.fidelity.message.trim().length > 0 &&
          p.fidelity.code &&
          p.fidelity.code !== 'FIDELITY_OK',
      ),
    [realisticPieces],
  )

  const costSummary = useMemo(() => {
    const realism = prep.realism_estimate_cents ?? 0
    const fashn = prep.estimate_cents
    const combined = prep.combined_estimate_cents ?? realism + fashn
    return { realism, fashn, combined }
  }, [prep])

  return (
    <>
      <div className={styles.costRow} data-testid="fashn-cost-summary">
        <div>
          <strong>1. Realistic garment (OpenAI)</strong> — about {costSummary.realism}¢
          {prep.realism_calls && prep.realism_calls > 1 ? ` · ${prep.realism_calls} images` : ''}
          {hasRealistic ? ' · already generated for this review' : ''}
        </div>
        <div>
          <strong>2. FASHN try-on</strong> — about{' '}
          {showExperiment && experiment?.provider === 'fashn_max'
            ? `${maxEstimate}¢ · ~${maxCredits * prep.fashn_calls} Max credit${
                maxCredits * prep.fashn_calls === 1 ? '' : 's'
              }`
            : `${costSummary.fashn}¢ · ${prep.fashn_calls} credit${
                prep.fashn_calls === 1 ? '' : 's'
              }`}{' '}
          · charged only after Accept & Try On
        </div>
        <div>
          Combined estimate about{' '}
          <strong>
            {showExperiment && experiment?.provider === 'fashn_max'
              ? costSummary.realism + maxEstimate * prep.fashn_calls
              : costSummary.combined}
            ¢
          </strong>{' '}
          if you run both stages. Reusing an accepted garment skips OpenAI. Cancel never starts
          FASHN.
        </div>
      </div>

      {showExperiment && experiment ? (
        <div
          data-testid="fashn-max-experiment"
          style={{
            margin: '12px 0',
            padding: '12px',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 8,
          }}
        >
          <p className={styles.hint} style={{ marginBottom: 8 }}>
            <strong>Owner experiment</strong> — compare FASHN v1.6 vs Try-On Max on the same
            accepted garment. Soft budget ~{experiment.softBudgetCredits ?? 90} Max credits.
            Results stay private (not My Looks).
          </p>

          {experiment.acceptedOptions.length > 0 ? (
            <fieldset style={{ border: 0, padding: 0, margin: '0 0 10px' }} data-testid="fashn-reuse-accepted">
              <legend className={styles.hint}>Reuse accepted garment (no OpenAI regen)</legend>
              <select
                aria-label="Accepted realistic garment"
                value={experiment.selectedAcceptedJobId ?? ''}
                onChange={(e) =>
                  experiment.onSelectAcceptedJobId(e.target.value ? e.target.value : null)
                }
                style={{ width: '100%', marginBottom: 6 }}
              >
                <option value="">Current review / new generate</option>
                {experiment.acceptedOptions.map((opt) => (
                  <option key={opt.jobId} value={opt.jobId}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className={styles.detailsToggle}
                disabled={!experiment.selectedAcceptedJobId || experiment.acceptedLoadBusy}
                onClick={() => {
                  if (experiment.selectedAcceptedJobId) {
                    experiment.onLoadAcceptedJob(experiment.selectedAcceptedJobId)
                  }
                }}
              >
                {experiment.acceptedLoadBusy ? 'Loading accepted garment…' : 'Load selected garment'}
              </button>
            </fieldset>
          ) : null}

          <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
            <legend className={styles.hint}>Provider</legend>
            <label style={{ display: 'block', marginBottom: 4 }}>
              <input
                type="radio"
                name="fashn-exp-provider"
                checked={experiment.provider === 'fashn'}
                onChange={() => experiment.onProviderChange('fashn')}
              />{' '}
              FASHN v1.6
            </label>
            <label style={{ display: 'block' }}>
              <input
                type="radio"
                name="fashn-exp-provider"
                checked={experiment.provider === 'fashn_max'}
                onChange={() => experiment.onProviderChange('fashn_max')}
              />{' '}
              FASHN Try-On Max
            </label>
          </fieldset>

          {experiment.provider === 'fashn' ? (
            <div data-testid="fashn-v16-controls">
              <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
                <legend className={styles.hint}>v1.6 category</legend>
                <label style={{ display: 'inline-block', marginRight: 12 }}>
                  <input
                    type="radio"
                    name="fashn-v16-cat"
                    checked={experiment.v16Category === 'one-pieces'}
                    onChange={() => experiment.onV16CategoryChange('one-pieces')}
                  />{' '}
                  one-pieces
                </label>
                <label style={{ display: 'inline-block' }}>
                  <input
                    type="radio"
                    name="fashn-v16-cat"
                    checked={experiment.v16Category === 'auto'}
                    onChange={() => experiment.onV16CategoryChange('auto')}
                  />{' '}
                  auto
                </label>
              </fieldset>
              <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
                <legend className={styles.hint}>segmentation_free</legend>
                <label style={{ display: 'inline-block', marginRight: 12 }}>
                  <input
                    type="radio"
                    name="fashn-v16-seg"
                    checked={experiment.v16SegmentationFree === true}
                    onChange={() => experiment.onV16SegmentationFreeChange(true)}
                  />{' '}
                  true (default)
                </label>
                <label style={{ display: 'inline-block' }}>
                  <input
                    type="radio"
                    name="fashn-v16-seg"
                    checked={experiment.v16SegmentationFree === false}
                    onChange={() => experiment.onV16SegmentationFreeChange(false)}
                  />{' '}
                  false
                </label>
              </fieldset>
              <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
                <legend className={styles.hint}>v1.6 mode</legend>
                <label style={{ display: 'inline-block', marginRight: 12 }}>
                  <input
                    type="radio"
                    name="fashn-v16-mode"
                    checked={experiment.v16Mode === 'balanced'}
                    onChange={() => experiment.onV16ModeChange('balanced')}
                  />{' '}
                  balanced (default)
                </label>
                <label style={{ display: 'inline-block' }}>
                  <input
                    type="radio"
                    name="fashn-v16-mode"
                    checked={experiment.v16Mode === 'quality'}
                    onChange={() => experiment.onV16ModeChange('quality')}
                  />{' '}
                  quality
                </label>
              </fieldset>
              <label className={styles.hint} style={{ display: 'block', marginBottom: 8 }}>
                Seed (default 42)
                <input
                  type="number"
                  min={0}
                  max={4294967295}
                  value={experiment.v16Seed}
                  onChange={(e) => {
                    const n = Number(e.target.value)
                    experiment.onV16SeedChange(
                      Number.isFinite(n) ? Math.max(0, Math.min(4294967295, Math.trunc(n))) : 42,
                    )
                  }}
                  style={{ display: 'block', width: '100%', marginTop: 4 }}
                  aria-label="FASHN v1.6 seed"
                />
              </label>
              <p className={styles.hint}>Outputs: 1 (fixed for this experiment).</p>
            </div>
          ) : null}

          {experiment.provider === 'fashn_max' ? (
            <>
              <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
                <legend className={styles.hint}>Max mode</legend>
                <label style={{ display: 'inline-block', marginRight: 12 }}>
                  <input
                    type="radio"
                    name="fashn-max-mode"
                    checked={experiment.mode === 'balanced'}
                    onChange={() => experiment.onModeChange('balanced')}
                  />{' '}
                  Balanced (default · {experiment.creditsBalanced ?? 2} cr @ 1k)
                </label>
                <label style={{ display: 'inline-block' }}>
                  <input
                    type="radio"
                    name="fashn-max-mode"
                    checked={experiment.mode === 'quality'}
                    onChange={() => experiment.onModeChange('quality')}
                  />{' '}
                  Quality ({experiment.creditsQuality ?? 3} cr @ 1k)
                </label>
              </fieldset>
              <fieldset style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
                <legend className={styles.hint}>Resolution</legend>
                <label style={{ display: 'inline-block', marginRight: 12 }}>
                  <input
                    type="radio"
                    name="fashn-max-res"
                    checked={experiment.resolution === '1k'}
                    onChange={() => experiment.onResolutionChange('1k')}
                  />{' '}
                  1k (default)
                </label>
                <label style={{ display: 'inline-block' }}>
                  <input
                    type="radio"
                    name="fashn-max-res"
                    checked={experiment.resolution === '2k'}
                    onChange={() => experiment.onResolutionChange('2k')}
                  />{' '}
                  2k
                </label>
              </fieldset>
              <button
                type="button"
                className={styles.detailsToggle}
                onClick={experiment.onTogglePrompt}
              >
                {experiment.promptOpen ? 'Hide Max prompt' : 'Show Max prompt'}
              </button>
              {experiment.promptOpen ? (
                <textarea
                  data-testid="fashn-max-prompt"
                  value={experiment.prompt}
                  onChange={(e) => experiment.onPromptChange(e.target.value.slice(0, 1000))}
                  rows={5}
                  style={{ width: '100%', marginTop: 8, fontFamily: 'inherit' }}
                  aria-label="Try-On Max prompt"
                />
              ) : null}
            </>
          ) : null}

          {!hasRealistic ? (
            <p className={styles.hint} style={{ marginTop: 8 }}>
              Generate or load an accepted realistic garment before Accept & Try On.
            </p>
          ) : null}
        </div>
      ) : null}

      {!prep.quality_ok ? (
        <p className={styles.error} role="alert">
          {prep.quality_notes ||
            'Prepared plates do not look like a filled garment. Adjust your sketch fills, then retry.'}
        </p>
      ) : null}

      <p className={styles.hint} style={{ marginBottom: 8 }}>
        Layout: <strong>{prep.layout === 'two_piece' ? 'two-piece' : 'one-piece'}</strong>.{' '}
        {hasRealistic
          ? 'Compare your sketch with the realistic product image, then Accept before FASHN.'
          : 'Review the sketch plates, then generate a realistic product garment.'}
      </p>

      <button type="button" className={styles.detailsToggle} onClick={onToggleDetails}>
        {detailsOpen ? 'Hide provider details' : 'Show provider details'}
      </button>
      {detailsOpen ? (
        <p className={styles.hint} style={{ marginBottom: 10 }}>
          {prep.notice_text}
        </p>
      ) : null}

      {realismError ? (
        <p className={styles.error} role="alert" data-testid="fashn-realism-error">
          {realismError}
        </p>
      ) : null}
      {fidelityFailures.length > 0 ? (
        <p className={styles.error} role="alert" data-testid="fashn-fidelity-hard-fail">
          {fidelityFailures[0].fidelity?.message ||
            'Fidelity checks failed. Accept is disabled — regenerate or edit the sketch.'}
        </p>
      ) : null}
      {softWarnings.length > 0 && fidelityFailures.length === 0 ? (
        <p className={styles.hint} role="status" data-testid="fashn-fidelity-warning">
          Fidelity note: {softWarnings[0].fidelity?.message}
        </p>
      ) : null}
      {realismBusy ? (
        <p className={styles.hint} data-testid="fashn-realism-busy">
          Generating realistic garment…
        </p>
      ) : null}

      <section aria-label="Your design">
        <p className={styles.pieceLabel}>Step 1 — Your design</p>
        <div
          className={styles.pieceGrid}
          data-testid="fashn-sketch-pieces"
          data-layout={prep.layout}
        >
          {sketchPieces.map((piece, index) => {
            const label = pieceLabel(piece.category, index, sketchPieces.length)
            return (
              <div key={`sketch-${piece.category}-${index}`} className={styles.pieceCard}>
                <p className={styles.pieceLabel}>{label}</p>
                <button
                  type="button"
                  className={styles.pieceActions}
                  style={{ padding: 0, border: 0, background: 'none', display: 'block', width: '100%' }}
                  onClick={() => setLightbox({ src: piece.image_base64, label: `${label} sketch` })}
                  aria-label={`Enlarge ${label} sketch`}
                >
                  <img
                    className={styles.pieceThumb}
                    src={piece.image_base64}
                    alt={`${label} sketch plate`}
                  />
                </button>
              </div>
            )
          })}
        </div>
      </section>

      {hasRealistic ? (
        <section aria-label="Realistic garment" style={{ marginTop: 12 }}>
          <p className={styles.pieceLabel}>Step 2 — Realistic garment</p>
          <div
            className={styles.pieceGrid}
            data-testid="fashn-realistic-pieces"
            data-layout={prep.layout}
          >
            {(realisticPieces ?? []).map((piece, index) => {
              const label = pieceLabel(piece.category, index, realisticPieces!.length)
              const failed = piece.fidelity && piece.fidelity.ok === false
              return (
                <div key={`real-${piece.category}-${index}`} className={styles.pieceCard}>
                  <p className={styles.pieceLabel}>
                    {label}
                    {failed ? ' · fidelity failed' : ''}
                  </p>
                  <button
                    type="button"
                    style={{ padding: 0, border: 0, background: 'none', display: 'block', width: '100%' }}
                    onClick={() =>
                      setLightbox({ src: piece.image_base64, label: `${label} realistic` })
                    }
                    aria-label={`Enlarge ${label} realistic garment`}
                  >
                    <img
                      className={styles.pieceThumb}
                      src={piece.image_base64}
                      alt={`${label} realistic product`}
                    />
                  </button>
                </div>
              )
            })}
          </div>
        </section>
      ) : null}

      {!prep.live_http ? (
        <p className={styles.error}>FASHN is not live-armed yet. Confirm stay disabled.</p>
      ) : null}
      {prep.openai_live_http === false ? (
        <p className={styles.error}>
          OpenAI live HTTP is off — realistic garment generation cannot run on this server yet.
        </p>
      ) : null}

      {lightbox ? (
        <div
          className={styles.lightbox}
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.label}
          data-testid="fashn-piece-lightbox"
          onClick={() => setLightbox(null)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setLightbox(null)
          }}
        >
          <button
            type="button"
            className={styles.lightboxClose}
            onClick={() => setLightbox(null)}
          >
            Close
          </button>
          <img
            className={styles.lightboxImg}
            src={lightbox.src}
            alt={lightbox.label}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}
    </>
  )
}
