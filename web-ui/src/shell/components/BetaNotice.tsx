import styles from './BetaNotice.module.css'

type Props = {
  message: string
  onDismiss: () => void
}

/** One workspace-level beta notice. Stays visible when Settings is docked away. */
export function BetaNotice({ message, onDismiss }: Props) {
  return (
    <div className={styles.notice} role="status" aria-live="polite" aria-label={message}>
      <p>{message}</p>
      <button type="button" onClick={onDismiss}>
        Got it
      </button>
    </div>
  )
}
