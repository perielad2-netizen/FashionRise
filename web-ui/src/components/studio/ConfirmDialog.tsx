import { useEffect, useId, useRef, type ReactNode, type SyntheticEvent } from 'react'
import styles from './ConfirmDialog.module.css'

type Action = {
  label: string
  onClick: () => void
  variant?: 'primary' | 'danger' | 'ghost'
  disabled?: boolean
}

type Props = {
  title: string
  children: ReactNode
  actions: Action[]
  /** When provided, Escape triggers it. Omit for decisions that must be made explicitly. */
  onEscape?: () => void
  busy?: boolean
  /**
   * Viewport-bounded dialog with scrollable body and sticky action footer.
   * Required for tall FASHN garment review on mobile (#161).
   */
  scrollable?: boolean
}

export function ConfirmDialog({
  title,
  children,
  actions,
  onEscape,
  busy = false,
  scrollable = false,
}: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const actionsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const node = dialogRef.current
    const primary = node?.querySelector<HTMLButtonElement>(
      'button[data-variant="primary"]:not(:disabled)',
    )
    // Focus primary without forcing a scroll that hides content on short viewports —
    // scroll the sticky footer into view instead when scrollable.
    ;(primary ?? node)?.focus({ preventScroll: true })
    if (typeof actionsRef.current?.scrollIntoView === 'function') {
      actionsRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    }
    return () => {
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [scrollable])

  // Keep actions above Android/Samsung/Chrome bottom toolbars via visualViewport.
  useEffect(() => {
    const root = dialogRef.current?.parentElement
    if (!root) return
    const vv = window.visualViewport
    const sync = () => {
      const layoutH = window.innerHeight || 0
      const visibleH = vv?.height ?? layoutH
      const offsetTop = vv?.offsetTop ?? 0
      // Chrome/Samsung UI that overlaps the layout viewport.
      const chromeBottom = Math.max(0, Math.round(layoutH - visibleH - offsetTop))
      root.style.setProperty('--fr-browser-chrome-bottom', `${chromeBottom}px`)
    }
    sync()
    vv?.addEventListener('resize', sync)
    vv?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
    return () => {
      vv?.removeEventListener('resize', sync)
      vv?.removeEventListener('scroll', sync)
      window.removeEventListener('resize', sync)
      root.style.removeProperty('--fr-browser-chrome-bottom')
    }
  }, [])

  useEffect(() => {
    if (!onEscape) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onEscape()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onEscape])

  // Nested under another dismissible overlay (e.g. My Looks detail), clicks must not
  // bubble — otherwise checkbox / Cancel / Publish taps close the parent sheet.
  const stopOverlayDismiss = (event: SyntheticEvent) => {
    event.stopPropagation()
  }

  return (
    <div
      className={styles.scrim}
      role="presentation"
      data-testid="confirm-dialog-scrim"
      onPointerDown={stopOverlayDismiss}
      onMouseDown={stopOverlayDismiss}
      onClick={stopOverlayDismiss}
      onTouchStart={stopOverlayDismiss}
    >
      <div
        ref={dialogRef}
        className={scrollable ? `${styles.dialog} ${styles.dialogScrollable}` : styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={busy || undefined}
        tabIndex={-1}
        data-scrollable={scrollable || undefined}
        onPointerDown={stopOverlayDismiss}
        onClick={stopOverlayDismiss}
      >
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <div className={styles.body}>{children}</div>
        <div ref={actionsRef} className={styles.actions} data-testid="confirm-dialog-actions">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              data-variant={action.variant ?? 'primary'}
              className={
                action.variant === 'danger'
                  ? styles.danger
                  : action.variant === 'ghost'
                    ? styles.ghost
                    : styles.primary
              }
              disabled={busy || action.disabled}
              onClick={action.onClick}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export { styles as confirmDialogStyles }
