import { useState } from 'react'
import { Share2, X } from 'lucide-react'
import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { TryOnExperimentVerdict } from '@/services/ai/magicApi'
import { ShareSheet } from '@/shell/components/ShareSheet'
import styles from './MagicLookPanel.module.css'

export type MagicPhase = 'idle' | 'capturing' | 'submitting' | 'polling' | 'ready' | 'failed'

export type MagicSidePhase = 'idle' | 'polling' | 'ready' | 'failed'

export type MagicSidePanelState = {
  phase: MagicSidePhase
  result: MagicLookResult | null
  lookObjectUrl: string | null
  sketchObjectUrl: string | null
  error: string | null
  canRetry: boolean
}

export type MagicDualPanelState = {
  operationId: string
  viewSide: 'front' | 'back'
  onViewSide: (side: 'front' | 'back') => void
  front: MagicSidePanelState
  back: MagicSidePanelState
  onRetrySide: (side: 'front' | 'back') => void
  onDownloadSide: (side: 'front' | 'back') => void
}

export type MagicResultMode = 'fashion' | 'try_on'

type Props = {
  open: boolean
  phase: MagicPhase
  result: MagicLookResult | null
  lookObjectUrl: string | null
  sketchObjectUrl: string | null
  /** Original model photo for Try On Person before/after compare. */
  originalPhotoUrl?: string | null
  error: string | null
  /** Optional one-click pipeline status (e.g. FASHN realism → fidelity → try-on). */
  statusHint?: string | null
  canRecover: boolean
  /** Fashion Magic (illustration) vs Try On Person (photorealistic). */
  resultMode?: MagicResultMode
  dual?: MagicDualPanelState | null
  /** #176 — owner FASHN comparison verdict (Accepted / Rejected / Unreviewed). */
  onExperimentVerdict?: (verdict: TryOnExperimentVerdict) => void
  experimentVerdictBusy?: boolean
  onClose: () => void
  onCancel: () => void
  onDownload: () => void
  onRecover: () => void
  onBackToSketch: () => void
  onViewInMyLooks?: () => void
}

function sideStatusLabel(side: MagicSidePanelState): string {
  if (side.phase === 'polling') return 'Working…'
  if (side.phase === 'ready') {
    if (side.result?.status === 'completed_unverified') return 'Review needed'
    return side.result?.status === 'completed' ? 'Ready' : String(side.result?.status ?? 'Ready')
  }
  if (side.phase === 'failed') return 'Failed'
  return 'Pending'
}

export type TryOnCompareMode = 'result' | 'original' | 'garment' | 'side_by_side'

export function MagicLookPanel({
  open,
  phase,
  result,
  lookObjectUrl,
  sketchObjectUrl,
  originalPhotoUrl = null,
  error,
  statusHint = null,
  canRecover,
  resultMode = 'fashion',
  dual,
  onExperimentVerdict,
  experimentVerdictBusy = false,
  onClose,
  onCancel,
  onDownload,
  onRecover,
  onBackToSketch,
  onViewInMyLooks,
}: Props) {
  const [compareSketch, setCompareSketch] = useState(false)
  const [tryOnCompare, setTryOnCompare] = useState<TryOnCompareMode>('result')
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)

  if (!open) return null

  const tryOn = resultMode === 'try_on' && !dual
  const dualActive = Boolean(dual)
  const activeSide = dual?.viewSide ?? 'front'
  const activeSideState = dual ? (activeSide === 'front' ? dual.front : dual.back) : null
  const activeLookUrl = dualActive ? activeSideState?.lookObjectUrl : lookObjectUrl
  const activeSketchUrl = dualActive ? activeSideState?.sketchObjectUrl : sketchObjectUrl
  const activeResult = dualActive ? activeSideState?.result : result

  const busy = phase === 'capturing' || phase === 'submitting' || phase === 'polling'
  const comparing = !tryOn && phase === 'ready' && compareSketch
  const showLook =
    phase === 'ready' &&
    activeLookUrl &&
    (tryOn ? tryOnCompare === 'result' : !comparing)
  const showSketchCompare = comparing && Boolean(activeSketchUrl)
  const showTryOnOriginal = tryOn && tryOnCompare === 'original' && Boolean(originalPhotoUrl)
  const showTryOnGarment = tryOn && tryOnCompare === 'garment' && Boolean(activeSketchUrl)
  const showTryOnSideBySide =
    tryOn &&
    tryOnCompare === 'side_by_side' &&
    Boolean(activeLookUrl) &&
    Boolean(originalPhotoUrl)
  const hasDetails = Boolean(activeResult?.summary || activeResult?.bullets?.length)
  const structureRejected = Boolean(activeResult?.structureRejected)
  const fidelityBanner =
    structureRejected &&
    (activeResult?.structureReviewMessage ||
      activeResult?.summary ||
      'This try-on does not match your sketch well enough to treat as a faithful result.')
  // #176 — experiment comparison results stay private (never auto My Looks).
  const experimentBlocksLooks = Boolean(activeResult?.experimentMeta?.experiment)
  const canViewInLooks =
    phase === 'ready' &&
    Boolean(onViewInMyLooks) &&
    !structureRejected &&
    !experimentBlocksLooks &&
    (dualActive
      ? Boolean(dual?.front.lookObjectUrl || dual?.back.lookObjectUrl)
      : Boolean(lookObjectUrl))
  const compareLabel = comparing ? 'Show look' : 'Compare sketch'
  const cycleTryOnCompare = () => {
    const order: TryOnCompareMode[] = originalPhotoUrl
      ? ['result', 'side_by_side', 'original', 'garment']
      : ['result', 'garment']
    const available = order.filter((mode) => {
      if (mode === 'garment') return Boolean(activeSketchUrl)
      if (mode === 'original' || mode === 'side_by_side') return Boolean(originalPhotoUrl)
      return true
    })
    const idx = available.indexOf(tryOnCompare)
    const next = available[(idx + 1) % available.length] ?? 'result'
    setTryOnCompare(next)
  }
  const tryOnCompareLabel =
    tryOnCompare === 'result'
      ? originalPhotoUrl
        ? 'Compare original'
        : 'Compare garment'
      : tryOnCompare === 'side_by_side'
        ? 'Show original only'
        : tryOnCompare === 'original'
          ? activeSketchUrl
            ? 'Compare garment'
            : 'Show try-on'
          : 'Show try-on'

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label={tryOn ? 'Try On Person' : 'Your Look'}
    >
      <div className={styles.panel}>
        <div className={styles.header}>
          <div className={styles.titleBlock}>
            <h2>
              {phase === 'ready'
                ? tryOn
                  ? 'Try On Person'
                  : 'Your Look'
                : tryOn
                  ? 'Try On Person'
                  : 'Magic'}
            </h2>
            <p>
              {busy
                ? dualActive
                  ? 'Polishing Front and Back…'
                  : tryOn
                    ? 'Creating a photorealistic preview on your original photo…'
                    : 'Turning your sketch into a finished fashion illustration…'
                : phase === 'ready'
                  ? dualActive
                    ? 'Both sides stay in Studio. These looks are private results for you.'
                    : tryOn
                      ? structureRejected
                        ? 'Private review only — this preview is not accepted as a faithful try-on or My Look.'
                        : 'Concept preview only — not a fit guarantee. Your photo and sketch stay private and unchanged.'
                      : 'Your original sketch stays in Studio. This look is a private result for you.'
                  : tryOn
                    ? 'FashionRise Try On Person'
                    : 'FashionRise Magic'}
            </p>
          </div>
          <button type="button" className={styles.close} aria-label="Close Magic" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className={styles.panelBody}>
        {dualActive && dual ? (
          <div className={styles.dualTabs} role="tablist" aria-label="Magic results by side">
            {(['front', 'back'] as const).map((side) => {
              const state = side === 'front' ? dual.front : dual.back
              const selected = dual.viewSide === side
              return (
                <button
                  key={side}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  className={selected ? styles.dualTabActive : styles.dualTab}
                  onClick={() => dual.onViewSide(side)}
                >
                  <span className={styles.dualTabLabel}>{side === 'front' ? 'Front' : 'Back'}</span>
                  <span className={styles.dualTabStatus} data-status={state.phase}>
                    {sideStatusLabel(state)}
                  </span>
                </button>
              )
            })}
          </div>
        ) : null}

        {fidelityBanner && phase === 'ready' ? (
          <div className={styles.fidelityBanner} role="status">
            <strong>Not a faithful try-on</strong>
            <p>{fidelityBanner}</p>
          </div>
        ) : null}

        <div className={styles.stage}>
          {busy ? (
            <div className={styles.statusBox}>
              <div className={styles.spinner} aria-hidden />
              <strong>
                {tryOn
                  ? // #178 — normal try-on never exposes provider/stage/cost text.
                    statusHint &&
                    !/fashn|openai|credit|¢|max\b|v1\.6|provider|realistic garment/i.test(
                      statusHint,
                    )
                    ? statusHint
                    : 'Generating your try-on preview...'
                  : statusHint
                    ? statusHint
                    : phase === 'capturing'
                      ? 'Capturing sketch…'
                      : phase === 'submitting'
                        ? 'Starting Magic…'
                        : dualActive
                          ? 'Creating your looks…'
                          : 'Creating your look…'}
              </strong>
              <span>You can leave this open — we recover the same job if the network blips.</span>
            </div>
          ) : null}

          {dualActive && dual && phase === 'ready' ? (
            <div className={styles.dualStageGrid}>
              {(['front', 'back'] as const).map((side) => {
                const state = side === 'front' ? dual.front : dual.back
                const url = state.lookObjectUrl
                return (
                  <div
                    key={side}
                    className={`${styles.dualPane} ${dual.viewSide === side ? styles.dualPaneActive : ''}`}
                  >
                    <div className={styles.dualPaneHead}>
                      <strong>{side === 'front' ? 'Front' : 'Back'}</strong>
                      <span>{sideStatusLabel(state)}</span>
                    </div>
                    {state.phase === 'failed' ? (
                      <div className={styles.dualPaneError}>
                        <span>{state.error || 'This side did not finish.'}</span>
                        {state.canRetry ? (
                          <button type="button" onClick={() => dual.onRetrySide(side)}>
                            Retry {side}
                          </button>
                        ) : null}
                      </div>
                    ) : url ? (
                      <img
                        className={styles.dualImage}
                        src={url}
                        alt={`Magic fashion look (${side})`}
                      />
                    ) : (
                      <div className={styles.dualPanePending}>
                        {state.phase === 'polling' ? 'Still working…' : 'No preview yet.'}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : null}

          {!dualActive && showLook && activeLookUrl ? (
            <img
              className={styles.image}
              src={activeLookUrl}
              alt={
                structureRejected
                  ? 'Try On Person preview — structural mismatch flagged'
                  : tryOn
                    ? 'Try On Person preview'
                    : 'Magic fashion look'
              }
            />
          ) : null}

          {showTryOnSideBySide && activeLookUrl && originalPhotoUrl ? (
            <div className={styles.compareGrid} aria-label="Original versus try-on">
              <figure className={styles.comparePane}>
                <figcaption>Original photo</figcaption>
                <img src={originalPhotoUrl} alt="Original model photo" />
              </figure>
              <figure className={styles.comparePane}>
                <figcaption>Try-on preview</figcaption>
                <img src={activeLookUrl} alt="Try On Person preview" />
              </figure>
            </div>
          ) : null}

          {showTryOnOriginal && originalPhotoUrl ? (
            <img
              className={styles.image}
              src={originalPhotoUrl}
              alt="Original model photo"
            />
          ) : null}

          {showTryOnGarment && activeSketchUrl ? (
            <img
              className={styles.sketchPreview}
              src={activeSketchUrl}
              alt="Garment artwork"
            />
          ) : null}

          {showSketchCompare && activeSketchUrl ? (
            <img
              className={styles.sketchPreview}
              src={activeSketchUrl}
              alt="Original sketch"
            />
          ) : null}

          {phase === 'failed' ? (
            <div className={styles.statusBox}>
              <strong>{tryOn ? 'Try On Person did not finish' : 'Magic did not finish'}</strong>
              <p className={styles.errorText}>{error || 'Something went wrong.'}</p>
            </div>
          ) : null}

          {phase === 'ready' && !dualActive && !activeLookUrl ? (
            <div className={styles.statusBox}>
              <strong>Look ready</strong>
              <span>{activeResult?.summary || 'Completed without an image preview.'}</span>
            </div>
          ) : null}
        </div>

        {error && phase !== 'failed' ? <p className={styles.error}>{error}</p> : null}

        {hasDetails && phase === 'ready' ? (
          <div className={styles.details}>
            <button
              type="button"
              className={styles.detailsToggle}
              aria-expanded={detailsOpen}
              onClick={() => setDetailsOpen((v) => !v)}
            >
              {detailsOpen ? 'Hide look notes' : 'Show look notes'}
            </button>
            {detailsOpen ? (
              <>
                {activeResult?.summary ? <p className={styles.summary}>{activeResult.summary}</p> : null}
                {activeResult?.bullets?.length ? (
                  <ul className={styles.bullets}>
                    {activeResult.bullets.slice(0, 6).map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}

        {tryOn &&
        phase === 'ready' &&
        activeResult?.experimentMeta?.experiment === true ? (
          <div className={styles.details} data-testid="try-on-experiment-meta">
            <p className={styles.summary}>
              Experiment · {activeResult.experimentMeta.provider || 'fashn'} · prompt{' '}
              {activeResult.experimentMeta.promptVersion || '—'}
              {activeResult.experimentMeta.costCents != null
                ? ` · ${activeResult.experimentMeta.costCents}¢`
                : ''}
              {activeResult.experimentMeta.predictionIds?.length
                ? ` · pred ${activeResult.experimentMeta.predictionIds[0].slice(0, 8)}`
                : ''}
            </p>
            {activeResult.experimentMeta.approvedGarmentShas?.length ? (
              <p className={styles.summary}>
                Approved garment SHA {activeResult.experimentMeta.approvedGarmentShas[0].slice(0, 12)}
                {activeResult.experimentMeta.croquisId
                  ? ` · croquis ${activeResult.experimentMeta.croquisId.slice(0, 8)}@v${
                      activeResult.experimentMeta.croquisVersion ?? '?'
                    }`
                  : ''}
              </p>
            ) : null}
            {activeResult.experimentMeta.v16Settings ? (
              <p className={styles.summary}>
                v1.6 settings {JSON.stringify(activeResult.experimentMeta.v16Settings)}
              </p>
            ) : null}
            {activeResult.experimentMeta.fashnMaxExperiment ? (
              <p className={styles.summary}>
                Max settings{' '}
                {JSON.stringify({
                  mode: activeResult.experimentMeta.fashnMaxExperiment.generation_mode,
                  resolution: activeResult.experimentMeta.fashnMaxExperiment.resolution,
                  seed: activeResult.experimentMeta.fashnMaxExperiment.seed,
                })}
              </p>
            ) : null}
            {onExperimentVerdict ? (
              <div className={styles.actions} data-testid="try-on-experiment-verdict">
                <span className={styles.summary}>
                  Verdict: {activeResult.experimentMeta.verdict || 'unreviewed'}
                </span>
                {(['accepted', 'rejected', 'unreviewed'] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    disabled={experimentVerdictBusy || activeResult.experimentMeta?.verdict === v}
                    onClick={() => onExperimentVerdict(v)}
                  >
                    {v === 'accepted' ? 'Accepted' : v === 'rejected' ? 'Rejected' : 'Unreviewed'}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        </div>

        <div className={styles.actions}>
          {busy ? (
            <button
              type="button"
              onClick={onCancel}
              title="Stops local waiting only. Jobs already started keep running — use Recover result later."
            >
              Stop waiting
            </button>
          ) : null}
          {phase === 'ready' && dualActive && dual ? (
            <>
              <button
                type="button"
                onClick={() => setCompareSketch((v) => !v)}
                disabled={!activeSketchUrl}
              >
                {comparing ? 'Show look' : 'Compare sketch'}
              </button>
              <button
                type="button"
                className={styles.primary}
                onClick={() => dual.onDownloadSide(activeSide)}
                disabled={!activeLookUrl}
              >
                Download {activeSide}
              </button>
              <button
                type="button"
                onClick={() => setShareOpen(true)}
                disabled={!activeLookUrl}
                data-testid="magic-share-look"
                title="Share with promo text for FashionRise"
              >
                <Share2 size={14} aria-hidden style={{ marginInlineEnd: 6, verticalAlign: '-2px' }} />
                Share
              </button>
              {canViewInLooks ? (
                <button type="button" onClick={onViewInMyLooks}>
                  View in My Looks
                </button>
              ) : null}
              {dual.front.canRetry ? (
                <button type="button" onClick={() => dual.onRetrySide('front')}>
                  Retry front
                </button>
              ) : null}
              {dual.back.canRetry ? (
                <button type="button" onClick={() => dual.onRetrySide('back')}>
                  Retry back
                </button>
              ) : null}
            </>
          ) : null}
          {phase === 'ready' && !dualActive && lookObjectUrl ? (
            <>
              {tryOn ? (
                <button
                  type="button"
                  onClick={cycleTryOnCompare}
                  disabled={!originalPhotoUrl && !sketchObjectUrl}
                >
                  {tryOnCompareLabel}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setCompareSketch((v) => !v)}
                  disabled={!sketchObjectUrl}
                >
                  {compareLabel}
                </button>
              )}
              <button type="button" className={styles.primary} onClick={onDownload}>
                {tryOn ? 'Download preview' : 'Download look'}
              </button>
              <button
                type="button"
                onClick={() => setShareOpen(true)}
                data-testid="magic-share-look"
                title="Share with promo text for FashionRise"
              >
                <Share2 size={14} aria-hidden style={{ marginInlineEnd: 6, verticalAlign: '-2px' }} />
                Share
              </button>
              {canViewInLooks ? (
                <button type="button" onClick={onViewInMyLooks}>
                  {tryOn ? 'Save in My Looks' : 'View in My Looks'}
                </button>
              ) : null}
            </>
          ) : null}
          {phase === 'failed' && canRecover ? (
            <button type="button" className={styles.primary} onClick={onRecover}>
              Recover result
            </button>
          ) : null}
          <button type="button" onClick={onBackToSketch}>
            Back to sketch
          </button>
        </div>
      </div>
      <ShareSheet
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        payload={{
          kind: 'look',
          title: tryOn ? 'Try-on look' : 'Magic look',
          imageUrl: activeLookUrl,
          imageFileName: tryOn ? 'fashionrise-tryon.png' : 'fashionrise-look.png',
        }}
      />
    </div>
  )
}
