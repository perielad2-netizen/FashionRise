import { useEffect, useRef, useState } from 'react'
import { Share2, X } from 'lucide-react'
import { requestShare, type SharePayload } from '@/lib/sharePromo'
import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { TryOnExperimentVerdict } from '@/services/ai/magicApi'
import { ShareSheet } from '@/shell/components/ShareSheet'
import styles from './MagicLookPanel.module.css'

type DownloadMethod = 'web' | 'gallery' | 'share'

function downloadSuccessCopy(method: DownloadMethod): string {
  if (method === 'gallery') return 'Saved to your gallery ✓'
  if (method === 'share') return 'Opened the system share sheet — save from there to finish.'
  return 'Download started.'
}

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
  onDownloadSide: (side: 'front' | 'back') => void | Promise<DownloadMethod>
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
  onDownload: () => void | Promise<DownloadMethod>
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
  onCancel: _onCancel,
  onDownload,
  onRecover,
  onBackToSketch,
  onViewInMyLooks,
}: Props) {
  void _onCancel
  const [compareSketch, setCompareSketch] = useState(false)
  const [tryOnCompare, setTryOnCompare] = useState<TryOnCompareMode>('result')
  const [shareOpen, setShareOpen] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const downloadInFlight = useRef(false)
  const [downloadNotice, setDownloadNotice] = useState<string | null>(null)
  const [downloadNoticeTone, setDownloadNoticeTone] = useState<'ok' | 'info' | 'error'>('ok')
  const downloadNoticeTimer = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (downloadNoticeTimer.current != null) window.clearTimeout(downloadNoticeTimer.current)
    }
  }, [])

  useEffect(() => {
    if (!open) {
      setDownloadBusy(false)
      downloadInFlight.current = false
      setDownloadNotice(null)
      if (downloadNoticeTimer.current != null) {
        window.clearTimeout(downloadNoticeTimer.current)
        downloadNoticeTimer.current = null
      }
    }
  }, [open])

  function showDownloadNotice(message: string, tone: 'ok' | 'info' | 'error') {
    if (downloadNoticeTimer.current != null) window.clearTimeout(downloadNoticeTimer.current)
    setDownloadNoticeTone(tone)
    setDownloadNotice(message)
    if (tone !== 'error') {
      downloadNoticeTimer.current = window.setTimeout(() => {
        setDownloadNotice(null)
        downloadNoticeTimer.current = null
      }, 4500)
    }
  }

  async function runDownload(action: () => void | Promise<DownloadMethod>) {
    if (downloadBusy || downloadInFlight.current) return
    downloadInFlight.current = true
    setDownloadBusy(true)
    setDownloadNotice(null)
    try {
      const method = await Promise.resolve(action())
      if (method === 'share') showDownloadNotice(downloadSuccessCopy('share'), 'info')
      else if (method === 'gallery' || method === 'web') {
        showDownloadNotice(downloadSuccessCopy(method), 'ok')
      } else {
        // Sync void handlers (tests / legacy) — still confirm the tap completed.
        showDownloadNotice('Saved ✓', 'ok')
      }
    } catch (err) {
      const cancelled =
        (err instanceof Error && err.name === 'SaveCancelledError') ||
        (err instanceof Error && /cancel|dismiss/i.test(err.message))
      if (cancelled) {
        showDownloadNotice('Download cancelled', 'info')
      } else {
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Could not download the look image.'
        showDownloadNotice(message, 'error')
      }
    } finally {
      setDownloadBusy(false)
      downloadInFlight.current = false
    }
  }

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
  const lookSharePayload: SharePayload = {
    kind: 'look',
    title: tryOn ? 'Try-on look' : dualActive ? `Magic look (${activeSide})` : 'Magic look',
    imageUrl: activeLookUrl,
    imageFileName: tryOn
      ? `fashionrise-tryon-${Date.now()}.png`
      : dualActive
        ? `fashionrise-look-${activeSide}-${Date.now()}.png`
        : `fashionrise-look-${Date.now()}.png`,
  }
  const onShareLook = () => {
    void (async () => {
      const result = await requestShare(lookSharePayload)
      if (result === 'needs-fallback') setShareOpen(true)
    })()
  }
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
            <p className={styles.eyebrow}>
              {tryOn ? 'Try On Person' : 'FashionRise Magic'}
            </p>
            <h2>
              {phase === 'ready'
                ? tryOn
                  ? 'Your preview'
                  : 'Your Look'
                : busy
                  ? tryOn
                    ? 'Creating preview'
                    : 'Creating your look'
                  : tryOn
                    ? 'Try On Person'
                    : 'Magic'}
            </h2>
            <p>
              {busy
                ? dualActive
                  ? 'Polishing Front and Back together — stay on this screen or come back anytime.'
                  : tryOn
                    ? 'Building a photorealistic preview on your original photo…'
                    : 'Turning your sketch into a finished fashion illustration…'
                : phase === 'ready'
                  ? dualActive
                    ? 'Private Studio results — switch Front / Back, then download or share.'
                    : tryOn
                      ? structureRejected
                        ? 'Private review only — this preview is not accepted as a faithful try-on or My Look.'
                        : 'Concept preview only — not a fit guarantee. Your photo and sketch stay private.'
                      : 'Private Studio result — your sketch stays unchanged.'
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
            <div className={styles.statusBox} data-testid="magic-generating">
              <div className={styles.generatingVisual} aria-hidden>
                <span className={styles.pulseRing} />
                <span className={styles.pulseRingDelayed} />
                <div className={styles.spinner} />
              </div>
              <strong>
                {tryOn
                  ? // #178 — normal try-on never exposes provider/stage/cost text.
                    statusHint &&
                    !/fashn|openai|credit|¢|max\b|v1\.6|provider|realistic garment/i.test(
                      statusHint,
                    )
                    ? statusHint
                    : 'Generating your try-on preview…'
                  : statusHint
                    ? statusHint
                    : phase === 'capturing'
                      ? 'Capturing sketch…'
                      : phase === 'submitting'
                        ? 'Starting Magic…'
                        : dualActive
                          ? 'Creating Front & Back…'
                          : 'Creating your look…'}
              </strong>
              <span className={styles.statusPill} data-testid="magic-status-pill">
                {phase === 'capturing'
                  ? 'Capturing'
                  : phase === 'submitting'
                    ? 'Queued'
                    : dualActive
                      ? 'Rendering both sides'
                      : 'Rendering'}
              </span>
              <span>Hang tight — you can leave this open. We recover the same job if the network blips.</span>
            </div>
          ) : null}

          {dualActive && dual && phase === 'ready' ? (
            <>
              {/* Mobile: one full-bleed active side (tabs switch). Desktop: dual compare grid. */}
              <div className={styles.dualHero} data-testid="magic-dual-hero">
                {activeSideState?.phase === 'failed' ? (
                  <div className={styles.dualPaneError}>
                    <span>{activeSideState.error || 'This side did not finish.'}</span>
                    {activeSideState.canRetry ? (
                      <button type="button" onClick={() => dual.onRetrySide(activeSide)}>
                        Retry {activeSide}
                      </button>
                    ) : null}
                  </div>
                ) : comparing && activeSketchUrl ? (
                  <img
                    className={styles.sketchPreview}
                    src={activeSketchUrl}
                    alt={`Original sketch (${activeSide})`}
                  />
                ) : activeLookUrl ? (
                  <img
                    className={styles.image}
                    src={activeLookUrl}
                    alt={`Magic fashion look (${activeSide})`}
                  />
                ) : (
                  <div className={styles.dualPanePending}>
                    {activeSideState?.phase === 'polling' ? 'Still working…' : 'No preview yet.'}
                  </div>
                )}
              </div>
              <div className={styles.dualStageGrid} data-testid="magic-dual-compare">
                {(['front', 'back'] as const).map((side) => {
                  const state = side === 'front' ? dual.front : dual.back
                  const url = state.lookObjectUrl
                  return (
                    <button
                      key={side}
                      type="button"
                      className={`${styles.dualPane} ${dual.viewSide === side ? styles.dualPaneActive : ''}`}
                      onClick={() => dual.onViewSide(side)}
                      aria-label={`Show ${side} look`}
                    >
                      <div className={styles.dualPaneHead}>
                        <strong>{side === 'front' ? 'Front' : 'Back'}</strong>
                        <span>{sideStatusLabel(state)}</span>
                      </div>
                      {state.phase === 'failed' ? (
                        <div className={styles.dualPaneError}>
                          <span>{state.error || 'This side did not finish.'}</span>
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
                    </button>
                  )
                })}
              </div>
            </>
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

        {tryOn &&
        phase === 'ready' &&
        activeResult?.experimentMeta?.experiment === true &&
        onExperimentVerdict ? (
          <div className={styles.details} data-testid="try-on-experiment-meta">
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
          </div>
        ) : null}
        </div>

        <div className={styles.actions}>
          {downloadBusy || downloadNotice ? (
            <p
              className={
                downloadNoticeTone === 'error'
                  ? styles.downloadToastError
                  : downloadNoticeTone === 'info'
                    ? styles.downloadToastInfo
                    : styles.downloadToastOk
              }
              role="status"
              aria-live="polite"
              data-testid="magic-download-notice"
            >
              {downloadBusy ? 'Saving image…' : downloadNotice}
            </p>
          ) : null}
          {phase === 'ready' && dualActive && dual ? (
            <>
              <button
                type="button"
                onClick={() => setCompareSketch((v) => !v)}
                disabled={!activeSketchUrl || downloadBusy}
              >
                {comparing ? 'Show look' : 'Compare sketch'}
              </button>
              <button
                type="button"
                className={styles.primary}
                onClick={() => {
                  void runDownload(() => dual.onDownloadSide(activeSide))
                }}
                disabled={!activeLookUrl || downloadBusy}
                data-testid="magic-download-side"
              >
                {downloadBusy ? 'Saving…' : `Download ${activeSide}`}
              </button>
              <button
                type="button"
                onClick={onShareLook}
                disabled={!activeLookUrl || downloadBusy}
                data-testid="magic-share-look"
                title="Share look — pick WhatsApp, Instagram, Facebook, or another app"
              >
                <Share2 size={14} aria-hidden style={{ marginInlineEnd: 6, verticalAlign: '-2px' }} />
                Share
              </button>
              {canViewInLooks ? (
                <button type="button" onClick={onViewInMyLooks} disabled={downloadBusy}>
                  View in My Looks
                </button>
              ) : null}
              {dual.front.canRetry ? (
                <button type="button" onClick={() => dual.onRetrySide('front')} disabled={downloadBusy}>
                  Retry front
                </button>
              ) : null}
              {dual.back.canRetry ? (
                <button type="button" onClick={() => dual.onRetrySide('back')} disabled={downloadBusy}>
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
                  disabled={(!originalPhotoUrl && !sketchObjectUrl) || downloadBusy}
                >
                  {tryOnCompareLabel}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setCompareSketch((v) => !v)}
                  disabled={!sketchObjectUrl || downloadBusy}
                >
                  {compareLabel}
                </button>
              )}
              <button
                type="button"
                className={styles.primary}
                onClick={() => {
                  void runDownload(onDownload)
                }}
                disabled={downloadBusy}
                data-testid="magic-download"
              >
                {downloadBusy
                  ? 'Saving…'
                  : tryOn
                    ? 'Download preview'
                    : 'Download look'}
              </button>
              <button
                type="button"
                onClick={onShareLook}
                disabled={downloadBusy}
                data-testid="magic-share-look"
                title="Share look — pick WhatsApp, Instagram, Facebook, or another app"
              >
                <Share2 size={14} aria-hidden style={{ marginInlineEnd: 6, verticalAlign: '-2px' }} />
                Share
              </button>
              {canViewInLooks ? (
                <button type="button" onClick={onViewInMyLooks} disabled={downloadBusy}>
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
          {/* Busy/start: no Stop waiting / Back to sketch — Close (X) dismisses; recover later if needed. */}
          {!busy ? (
            <button type="button" onClick={onBackToSketch}>
              Back to sketch
            </button>
          ) : null}
        </div>
      </div>
      <ShareSheet
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        payload={lookSharePayload}
      />
    </div>
  )
}
