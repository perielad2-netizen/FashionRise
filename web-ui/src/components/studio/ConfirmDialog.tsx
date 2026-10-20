import { useEffect, useId, useRef, type ReactNode } from 'react'
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
}

export function ConfirmDialog({ title, children, actions, onEscape, busy = false }: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const node = dialogRef.current
    const primary = node?.querySelector<HTMLButtonElement>('button[data-variant="primary"]:not(:disabled)')
    ;(primary ?? node)?.focus()
    return () => {
      if (previous && document.contains(previous)) previous.focus()
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

  return (
    <div className={styles.scrim} role="presentation">
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={busy || undefined}
        tabIndex={-1}
      >
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <div className={styles.body}>{children}</div>
        <div className={styles.actions}>
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
