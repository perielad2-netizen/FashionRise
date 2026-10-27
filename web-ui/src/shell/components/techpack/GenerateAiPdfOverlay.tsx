import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import styles from './GenerateAiPdfOverlay.module.css'

const PHASE_ORDER = [
  'preparing',
  'analyzing',
  'flat_front',
  'flat_back',
  'flat_back_proposed',
  'detail_callouts',
  'pattern_sheet',
  'assembling',
  'ready',
] as const

type Props = {
  open: boolean
  message: string
  phase?: string | null
  thumbnailUrl?: string | null
  ready?: boolean
  reconnecting?: boolean
  onViewIllustrations?: () => void
  onPreviewPdf?: () => void
  onDownloadPdf?: () => void
  busyActions?: boolean
}

export function GenerateAiPdfOverlay({
  open,
  message,
  phase,
  thumbnailUrl,
  ready = false,
  reconnecting = false,
  onViewIllustrations,
  onPreviewPdf,
  onDownloadPdf,
  busyActions = false,
}: Props) {
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open || typeof document === 'undefined') return null
  const idx = Math.max(0, PHASE_ORDER.indexOf((phase as (typeof PHASE_ORDER)[number]) || 'preparing'))

  const content = (
    <div className={styles.scrim} role="dialog" aria-modal="true" aria-labelledby="gen-ai-title">
      <div className={styles.card}>
        <p className={styles.kicker}>AI Technical Design</p>
        <h2 id="gen-ai-title" className={styles.title}>
          {ready ? 'Your AI Technical Design is Ready' : 'Creating your AI Technical Pack'}
        </h2>
        <div className={styles.visual}>
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="" className={styles.thumb} />
          ) : (
            <div className={styles.thumbPlaceholder} aria-hidden />
          )}
          {!ready ? <div className={styles.spinner} aria-hidden /> : null}
        </div>
        <p className={styles.status} role="status" aria-live="polite">
          {reconnecting ? 'Reconnecting to your generation…' : message}
        </p>
        {!ready ? (
          <ol className={styles.phases}>
            {[
              ['preparing', 'Preparing your design'],
              ['analyzing', 'Analyzing the garment'],
              ['flat_front', 'Creating technical illustrations'],
              ['pattern_sheet', 'Preparing pattern-development drawings'],
              ['assembling', 'Assembling your PDF'],
            ].map(([id, label]) => {
              const active =
                id === phase ||
                (id === 'flat_front' &&
                  ['flat_back', 'flat_back_proposed', 'detail_callouts'].includes(phase || ''))
              const done = idx > PHASE_ORDER.indexOf(id as (typeof PHASE_ORDER)[number])
              return (
                <li
                  key={id}
                  className={
                    done ? styles.phaseDone : active ? styles.phaseActive : styles.phasePending
                  }
                >
                  <span aria-hidden>{done ? '✓' : active ? '●' : '○'}</span>
                  {label}
                </li>
              )
            })}
          </ol>
        ) : (
          <div className={styles.actions}>
            <button type="button" className={styles.primary} onClick={onViewIllustrations}>
              View illustrations
            </button>
            <button
              type="button"
              className={styles.ghost}
              disabled={busyActions}
              onClick={onPreviewPdf}
            >
              Preview PDF
            </button>
            <button
              type="button"
              className={styles.ghost}
              disabled={busyActions}
              onClick={onDownloadPdf}
            >
              Download PDF
            </button>
          </div>
        )}
        <p className={styles.footnote}>
          {ready
            ? 'Preview and Download never start a new paid AI run.'
            : 'Generation continues on FashionRise servers. Reloading resumes this same run — it does not start a duplicate paid charge.'}
        </p>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
