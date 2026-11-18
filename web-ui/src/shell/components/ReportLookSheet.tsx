import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, ChevronLeft, ChevronRight, Flag, Send, X } from 'lucide-react'
import { onAndroidEditableFocus } from '@/lib/androidKeyboardInput'
import { ApiError } from '@/services/api/client'
import {
  reportGalleryItem,
  type ContentReportReason,
  type GalleryItem,
} from '@/services/galleryApi'
import { isNativeShell, nativePlatform } from '@/services/native/platform'
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

type Step = 'reasons' | 'details' | 'thanks'

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
  const detailsRef = useRef<HTMLTextAreaElement | null>(null)
  const [step, setStep] = useState<Step>('reasons')
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
      if (event.key !== 'Escape') return
      // Never dismiss while typing details — Esc should not wipe the report draft.
      if (step === 'details') return
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose, step])

  useEffect(() => {
    if (!open || step !== 'details') return
    // Autofocus once on the details step so the caret is ready without a
    // second tap that could race a scrim dismiss on some mobile browsers.
    const id = window.setTimeout(() => {
      const el = detailsRef.current
      if (!el) return
      try {
        el.focus({ preventScroll: true })
      } catch {
        el.focus()
      }
    }, 40)
    return () => window.clearTimeout(id)
  }, [open, step])

  if (!open) return null

  const designer = item.username?.trim() || 'this designer'
  const reasonMeta = reason ? REASONS.find((row) => row.id === reason) : null
  const detailsTrimmed = details.trim()
  const otherNeedsDetails = reason === 'other' && !detailsTrimmed
  const canSend = Boolean(reason) && !busy && !otherNeedsDetails

  function pickReason(selected: ContentReportReason) {
    setReason(selected)
    setError(null)
    setStep('details')
  }

  async function sendReport() {
    if (!reason || !canSend) return
    setBusy(true)
    setError(null)
    try {
      await reportGalleryItem(item.id, {
        reason,
        details: detailsTrimmed || undefined,
      })
      setStep('thanks')
      onReported(item.id)
    } catch (err) {
      // Duplicate report: still hide from this viewer — the first report already
      // registered the look, and refreshes must not bring it back into their feed.
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        /already reported/i.test(err.message)
      ) {
        setStep('thanks')
        onReported(item.id)
        return
      }
      const message =
        err instanceof ApiError
          ? err.message
          : 'Couldn’t send your report. Try again.'
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  const titleText =
    step === 'thanks' ? 'Thanks for reporting' : step === 'details' ? 'Add details' : 'Report look'

  return createPortal(
    <div
      className={`fr-keyboard-overlay ${styles.chatScrim}`}
      role="presentation"
      data-testid="report-look-scrim"
      // Safety sheet: never close from a scrim tap. Focus/keyboard reflow on
      // mobile web was turning the details-field tap into a backdrop click and
      // dumping users back to the feed. Close only via X / Done / explicit Back.
      onMouseDown={(event) => {
        // Swallow backdrop presses so they cannot synthesize a click on feed UI.
        if (event.target === event.currentTarget) event.preventDefault()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          event.preventDefault()
          event.stopPropagation()
        }
      }}
    >
      <div
        className={styles.chatDialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="report-look-sheet"
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.chatHead}>
          <div className={styles.chatHeadText}>
            <p className={styles.chatEyebrow}>Safety</p>
            <h3 id={titleId} className={styles.chatTitle}>
              {titleText}
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
          ) : null}

          {step === 'reasons' ? (
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
                      onClick={() => pickReason(row.id)}
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
            </>
          ) : null}

          {step === 'details' && reasonMeta ? (
            <>
              <p className={styles.reportIntro}>
                Confirm before sending. You can add context for the moderation team.
              </p>
              <div className={styles.reportSelectedReason} data-testid="report-selected-reason">
                <span className={styles.reportReasonLabel}>{reasonMeta.label}</span>
                <span className={styles.reportReasonHint}>{reasonMeta.hint}</span>
              </div>
              <label className={styles.reportDetailsLabel} htmlFor={detailsId}>
                {reason === 'other' ? 'Details (required)' : 'Details (optional)'}
              </label>
              <textarea
                ref={detailsRef}
                id={detailsId}
                className={styles.reportDetails}
                value={details}
                maxLength={2000}
                rows={4}
                placeholder={
                  reason === 'other'
                    ? 'Tell us what happened…'
                    : 'Add context if it helps (optional)'
                }
                disabled={busy}
                data-testid="report-details"
                onChange={(event) => setDetails(event.target.value)}
                onFocus={(event) => {
                  // scrollIntoView only on Android native — on mobile web it
                  // reflows the fixed sheet under the finger and used to close it.
                  if (isNativeShell() && nativePlatform() === 'android') {
                    onAndroidEditableFocus(event.currentTarget)
                  }
                }}
              />
              {otherNeedsDetails ? (
                <p className={styles.commentsStatus} role="status">
                  Add a short note so we know what to review.
                </p>
              ) : null}
              {busy ? (
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
          ) : null}
        </div>

        {step === 'thanks' ? (
          <div className={styles.reportFooter}>
            <button type="button" className={styles.reportDoneBtn} onClick={onClose}>
              Done
            </button>
          </div>
        ) : null}

        {step === 'details' ? (
          <div className={styles.reportFooterActions}>
            <button
              type="button"
              className={styles.reportBackBtn}
              disabled={busy}
              data-testid="report-back"
              onClick={() => {
                setError(null)
                setStep('reasons')
              }}
            >
              <ChevronLeft size={16} aria-hidden />
              Back
            </button>
            <button
              type="button"
              className={styles.reportSendBtn}
              disabled={!canSend}
              data-testid="report-send"
              onClick={() => void sendReport()}
            >
              <Send size={16} aria-hidden />
              Send report
            </button>
          </div>
        ) : null}

        {step === 'reasons' ? (
          <div className={styles.reportFooterHint}>
            <Flag size={14} aria-hidden />
            <span>Reports go to FashionRise moderation — not the designer.</span>
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  )
}
