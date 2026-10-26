import { useState } from 'react'
import { X } from 'lucide-react'
import type { MagicLookResult } from '@/services/ai/aiJobTypes'
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

type Props = {
  open: boolean
  phase: MagicPhase
  result: MagicLookResult | null
  lookObjectUrl: string | null
  sketchObjectUrl: string | null
  error: string | null
  canRecover: boolean
  dual?: MagicDualPanelState | null
  onClose: () => void
  onCancel: () => void
  onDownload: () => void
  onRecover: () => void
  onBackToSketch: () => void
  onViewInMyLooks?: () => void
}

function sideStatusLabel(side: MagicSidePanelState): string {
  if (side.phase === 'polling') return 'Working…'
  if (side.phase === 'ready') return side.result?.status === 'completed' ? 'Ready' : String(side.result?.status ?? 'Ready')
  if (side.phase === 'failed') return 'Failed'
  return 'Pending'
}

export function MagicLookPanel({
  open,
  phase,
  result,
  lookObjectUrl,
  sketchObjectUrl,
  error,
  canRecover,
  dual,
  onClose,
  onCancel,
  onDownload,
  onRecover,
  onBackToSketch,
  onViewInMyLooks,
}: Props) {
  const [compareSketch, setCompareSketch] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)

  if (!open) return null

  const dualActive = Boolean(dual)
  const activeSide = dual?.viewSide ?? 'front'
  const activeSideState = dual ? (activeSide === 'front' ? dual.front : dual.back) : null
  const activeLookUrl = dualActive ? activeSideState?.lookObjectUrl : lookObjectUrl
  const activeSketchUrl = dualActive ? activeSideState?.sketchObjectUrl : sketchObjectUrl
  const activeResult = dualActive ? activeSideState?.result : result

  const busy = phase === 'capturing' || phase === 'submitting' || phase === 'polling'
  const comparing = phase === 'ready' && compareSketch
  const showLook = phase === 'ready' && activeLookUrl && !comparing
  const showSketchCompare = comparing && Boolean(activeSketchUrl)
  const hasDetails = Boolean(activeResult?.summary || activeResult?.bullets?.length)
  const canViewInLooks =
    phase === 'ready' &&
    Boolean(onViewInMyLooks) &&
    (dualActive
      ? Boolean(dual?.front.lookObjectUrl || dual?.back.lookObjectUrl)
      : Boolean(lookObjectUrl))

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Your Look">
      <div className={styles.panel}>
        <div className={styles.header}>
          <div className={styles.titleBlock}>
            <h2>{phase === 'ready' ? 'Your Look' : 'Magic'}</h2>
            <p>
              {busy
                ? dualActive
                  ? 'Polishing Front and Back…'
                  : 'Turning your sketch into a finished fashion illustration…'
                : phase === 'ready'
                  ? dualActive
                    ? 'Both sides stay in Studio. These looks are private results for you.'
                    : 'Your original sketch stays in Studio. This look is a private result for you.'
                  : 'FashionRise Magic'}
            </p>
          </div>
          <button type="button" className={styles.close} aria-label="Close Magic" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

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

        <div className={styles.stage}>
          {busy ? (
            <div className={styles.statusBox}>
              <div className={styles.spinner} aria-hidden />
              <strong>
                {phase === 'capturing'
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
            <img className={styles.image} src={activeLookUrl} alt="Magic fashion look" />
          ) : null}

          {showSketchCompare && activeSketchUrl ? (
            <img className={styles.sketchPreview} src={activeSketchUrl} alt="Original sketch" />
          ) : null}

          {phase === 'failed' ? (
            <div className={styles.statusBox}>
              <strong>Magic did not finish</strong>
              <span>{error || 'Something went wrong.'}</span>
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

        <div className={styles.actions}>
          {busy ? (
            <button type="button" onClick={onCancel}>
              Cancel wait
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
              <button
                type="button"
                onClick={() => setCompareSketch((v) => !v)}
                disabled={!sketchObjectUrl}
              >
                {comparing ? 'Show look' : 'Compare sketch'}
              </button>
              <button type="button" className={styles.primary} onClick={onDownload}>
                Download look
              </button>
              {canViewInLooks ? (
                <button type="button" onClick={onViewInMyLooks}>
                  View in My Looks
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
    </div>
  )
}
