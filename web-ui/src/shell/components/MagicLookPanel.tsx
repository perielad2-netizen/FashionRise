import { useState } from 'react'
import { X } from 'lucide-react'
import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import styles from './MagicLookPanel.module.css'

export type MagicPhase = 'idle' | 'capturing' | 'submitting' | 'polling' | 'ready' | 'failed'

type Props = {
  open: boolean
  phase: MagicPhase
  result: MagicLookResult | null
  lookObjectUrl: string | null
  sketchObjectUrl: string | null
  error: string | null
  canRecover: boolean
  onClose: () => void
  onCancel: () => void
  onDownload: () => void
  onRecover: () => void
  onBackToSketch: () => void
}

export function MagicLookPanel({
  open,
  phase,
  result,
  lookObjectUrl,
  sketchObjectUrl,
  error,
  canRecover,
  onClose,
  onCancel,
  onDownload,
  onRecover,
  onBackToSketch,
}: Props) {
  const [compareSketch, setCompareSketch] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)

  if (!open) return null

  const busy = phase === 'capturing' || phase === 'submitting' || phase === 'polling'
  const comparing = phase === 'ready' && compareSketch
  const showLook = phase === 'ready' && lookObjectUrl && !comparing
  const showSketchCompare = comparing && Boolean(sketchObjectUrl)
  const hasDetails = Boolean(result?.summary || result?.bullets?.length)

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Your Look">
      <div className={styles.panel}>
        <div className={styles.header}>
          <div className={styles.titleBlock}>
            <h2>{phase === 'ready' ? 'Your Look' : 'Magic'}</h2>
            <p>
              {busy
                ? 'Turning your sketch into a finished fashion illustration…'
                : phase === 'ready'
                  ? 'Your original sketch stays in Studio. This look is a private result for you.'
                  : 'FashionRise Magic'}
            </p>
          </div>
          <button type="button" className={styles.close} aria-label="Close Magic" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className={styles.stage}>
          {busy ? (
            <div className={styles.statusBox}>
              <div className={styles.spinner} aria-hidden />
              <strong>
                {phase === 'capturing'
                  ? 'Capturing sketch…'
                  : phase === 'submitting'
                    ? 'Starting Magic…'
                    : 'Creating your look…'}
              </strong>
              <span>You can leave this open — we recover the same job if the network blips.</span>
            </div>
          ) : null}

          {showLook && lookObjectUrl ? (
            <img className={styles.image} src={lookObjectUrl} alt="Magic fashion look" />
          ) : null}

          {showSketchCompare && sketchObjectUrl ? (
            <img className={styles.sketchPreview} src={sketchObjectUrl} alt="Original sketch" />
          ) : null}

          {phase === 'failed' ? (
            <div className={styles.statusBox}>
              <strong>Magic did not finish</strong>
              <span>{error || 'Something went wrong.'}</span>
            </div>
          ) : null}

          {phase === 'ready' && !lookObjectUrl ? (
            <div className={styles.statusBox}>
              <strong>Look ready</strong>
              <span>{result?.summary || 'Completed without an image preview.'}</span>
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
                {result?.summary ? <p className={styles.summary}>{result.summary}</p> : null}
                {result?.bullets?.length ? (
                  <ul className={styles.bullets}>
                    {result.bullets.slice(0, 6).map((b) => (
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
          {phase === 'ready' && lookObjectUrl ? (
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
