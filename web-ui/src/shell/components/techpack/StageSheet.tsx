import { useEffect, useId, useRef, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import styles from './StageSheet.module.css'

type Props = {
  open: boolean
  stepIndex: number
  title: string
  subtitle?: string
  busy?: boolean
  children: ReactNode
  onClose: () => void
  onSave?: () => void | Promise<void>
  onContinue?: () => void | Promise<void>
  continueLabel?: string
  showContinue?: boolean
}

/**
 * Full-screen mobile editor for Create Real Design stages 1 / 2 / 4.
 * Step 3 keeps the specialized MeasurementsSheet.
 */
export function StageSheet({
  open,
  stepIndex,
  title,
  subtitle,
  busy = false,
  children,
  onClose,
  onSave,
  onContinue,
  continueLabel = 'Continue',
  showContinue = true,
}: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const closeBtn = dialogRef.current?.querySelector<HTMLButtonElement>('[data-close]')
    ;(closeBtn ?? dialogRef.current)?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (scrollRef.current) {
      if (typeof scrollRef.current.scrollTo === 'function') {
        scrollRef.current.scrollTo({ top: 0 })
      } else {
        scrollRef.current.scrollTop = 0
      }
    }
    return () => {
      document.body.style.overflow = prevOverflow
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [open, stepIndex])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className={styles.scrim} role="presentation">
      <div
        ref={dialogRef}
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className={styles.header}>
          <div className={styles.headerText}>
            <p className={styles.kicker}>Step {stepIndex} of 4</p>
            <h2 id={titleId} className={styles.title}>
              {title}
            </h2>
            {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            data-close
            aria-label="Close step form"
            onClick={onClose}
            disabled={busy}
          >
            <X size={20} aria-hidden />
          </button>
        </header>

        <div ref={scrollRef} className={styles.body}>
          {children}
        </div>

        <footer className={styles.footer}>
          <button type="button" className={styles.ghostBtn} onClick={onClose} disabled={busy}>
            <ChevronLeft size={16} aria-hidden />
            Close
          </button>
          {onSave ? (
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={busy}
              onClick={() => void onSave()}
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
          ) : null}
          {showContinue && onContinue ? (
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={busy}
              onClick={() => void onContinue()}
            >
              {busy ? 'Working…' : continueLabel}
              <ChevronRight size={16} aria-hidden />
            </button>
          ) : null}
        </footer>
      </div>
    </div>
  )
}
