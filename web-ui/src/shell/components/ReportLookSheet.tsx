import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, ChevronRight, Flag, X } from 'lucide-react'
import { ApiError } from '@/services/api/client'
import {
  reportGalleryItem,
  type ContentReportReason,
  type GalleryItem,
} from '@/services/galleryApi'
import styles from './RunwayScreen.module.css'

const REASONS: { id: ContentReportReason; label: string; hint: string }[] = [
  {
    id: 'sexual_content',
    label: 'Nudity or sexual content',
    hint: 'Inappropriate or explicit imagery',
  },
  {
    id: 'harassment',
    label: 'Harassment or abuse',
    hint: 'Threats, cursing, or bullying',
  },
  {
    id: 'hate',
    label: 'Hate or discrimination',
    hint: 'Attacks based on identity or group',
  },
  {
    id: 'spam',
    label: 'Spam or misleading',
    hint: 'Scams, ads, or fake engagement',
  },
  {
    id: 'impersonation',
    label: 'Impersonation',
    hint: 'Pretending to be someone else',
  },
  {
    id: 'other',
    label: 'Something else',
    hint: 'Doesn’t fit the options above',
  },
]

type Props = {
  item: GalleryItem
  open: boolean
  onClose: () => void
  /** Hide the look from this viewer’s feed after a successful report. */
  onReported: (galleryItemId: string) => void
}

export function ReportLookSheet({ item, open, onClose, onReported }: Props) {
  const titleId = useId()
  const detailsId = useId()
  const [step, setStep] = useState<'reasons' | 'thanks'>('reasons')
  const [reason, setReason] = useState<ContentReportReason | null>(null)
  const [details, setDetails] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setStep('reasons')
    setReason(null)
    setDetails('')
    setBusy(false)
    setError(null)
  }, [open, item.id])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const designer = item.username?.trim() || 'this designer'

  async function submit(selected: ContentReportReason) {
    setReason(selected)
    setBusy(true)
    setError(null)
    try {
      await reportGalleryItem(item.id, {
        reason: selected,
        details: details.trim() || undefined,
      })
      setStep('thanks')
      onReported(item.id)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Couldn’t send your report. Try again.'
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div
      className={styles.chatScrim}
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className={styles.chatDialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="report-look-sheet"
      >
        <header className={styles.chatHead}>
          <div className={styles.chatHeadText}>
            <p className={styles.chatEyebrow}>Safety</p>
            <h3 id={titleId} className={styles.chatTitle}>
              {step === 'thanks' ? 'Thanks for reporting' : 'Report look'}
            </h3>
          </div>
          <button
            type="button"
            className={styles.chatClose}
            aria-label="Close report"
            onClick={onClose}
          >
            <X size={18} aria-hidden />
          </button>
        </header>

        <div className={styles.chatBody}>
          {step === 'thanks' ? (
            <div className={styles.reportThanks}>
              <CheckCircle2 size={40} className={styles.reportThanksIcon} aria-hidden />
              <p className={styles.reportThanksLead}>
                We received your report about @{designer}.
              </p>
              <p className={styles.reportThanksBody}>
                Our team reviews reports to keep FashionRise safe. This look is hidden from
                your feed. We won’t tell the designer who reported them.
              </p>
            </div>
          ) : (
            <>
              <p className={styles.reportIntro}>
                Why are you reporting this look
                {item.title ? ` (“${item.title}”)` : ''}?
              </p>
              <ul className={styles.reportReasonList} aria-label="Report reasons">
                {REASONS.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={styles.reportReasonBtn}
                      disabled={busy}
                      data-testid={`report-reason-${row.id}`}
                      onClick={() => void submit(row.id)}
                    >
                      <span className={styles.reportReasonText}>
                        <span className={styles.reportReasonLabel}>{row.label}</span>
                        <span className={styles.reportReasonHint}>{row.hint}</span>
                      </span>
                      <ChevronRight size={18} aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
              <label className={styles.reportDetailsLabel} htmlFor={detailsId}>
                Optional details
              </label>
              <textarea
                id={detailsId}
                className={styles.reportDetails}
                value={details}
                maxLength={2000}
                rows={3}
                placeholder="Add context if it helps (optional)"
                disabled={busy}
                onChange={(event) => setDetails(event.target.value)}
              />
              {reason && busy ? (
                <p className={styles.commentsStatus} role="status">
                  Sending report…
                </p>
              ) : null}
              {error ? (
                <p className={styles.cardError} role="alert">
                  {error}
                </p>
              ) : null}
            </>
          )}
        </div>

        {step === 'thanks' ? (
          <div className={styles.reportFooter}>
            <button type="button" className={styles.reportDoneBtn} onClick={onClose}>
              Done
            </button>
          </div>
        ) : (
          <div className={styles.reportFooterHint}>
            <Flag size={14} aria-hidden />
            <span>Reports go to FashionRise moderation — not the designer.</span>
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
