import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import styles from './GenerateAiPdfOverlay.module.css'

const ROTATING_MESSAGES = [
  'Analyzing your design…',
  'Creating technical illustrations…',
  'Preparing your PDF…',
]

type Props = {
  open: boolean
  message: string
  phase?: string | null
  thumbnailUrl?: string | null
  ready?: boolean
  reconnecting?: boolean
  onDownloadPdf?: () => void
  onBackToLooks?: () => void
  busyActions?: boolean
}

function friendlyMessage(phase: string | null | undefined, fallback: string): string {
  switch (phase) {
    case 'analyzing':
      return 'Analyzing your design…'
    case 'flat_front':
    case 'flat_back':
    case 'flat_back_proposed':
    case 'detail_callouts':
    case 'pattern_sheet':
      return 'Creating technical illustrations…'
    case 'assembling':
      return 'Preparing your PDF…'
    case 'preparing':
      return 'Analyzing your design…'
    case 'ready':
      return fallback || 'Your AI Technical Pack is ready'
    default:
      return fallback
  }
}

export function GenerateAiPdfOverlay({
  open,
  message,
  phase,
  thumbnailUrl,
  ready = false,
  reconnecting = false,
  onDownloadPdf,
  onBackToLooks,
  busyActions = false,
}: Props) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    if (!open || ready) return
    const id = window.setInterval(() => setTick((n) => n + 1), 4200)
    return () => window.clearInterval(id)
  }, [open, ready])

  const statusText = useMemo(() => {
    if (reconnecting) return 'Reconnecting to your generation…'
    if (ready) return message || 'Your AI Technical Pack is ready'
    const fromPhase = friendlyMessage(phase, message)
    if (fromPhase && fromPhase !== 'Preparing your design') return fromPhase
    return ROTATING_MESSAGES[tick % ROTATING_MESSAGES.length]
  }, [reconnecting, ready, message, phase, tick])

  if (!open || typeof document === 'undefined') return null

  const content = (
    <div className={styles.scrim} role="dialog" aria-modal="true" aria-labelledby="gen-ai-title">
      <div className={styles.card}>
        <p className={styles.kicker}>FashionRise</p>
        <h2 id="gen-ai-title" className={styles.title}>
          {ready ? 'Your AI Technical Pack Is Ready!' : 'Creating Your AI Technical Pack'}
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
          {statusText}
        </p>
        {ready ? (
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.primary}
              data-testid="download-ai-pdf"
              disabled={busyActions}
              onClick={onDownloadPdf}
            >
              Download PDF
            </button>
            {onBackToLooks ? (
              <button type="button" className={styles.ghost} onClick={onBackToLooks}>
                Back to My Looks
              </button>
            ) : null}
          </div>
        ) : (
          <p className={styles.footnote}>
            Generation continues on FashionRise servers. Reloading resumes this same run — it does
            not start a duplicate charge.
          </p>
        )}
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
