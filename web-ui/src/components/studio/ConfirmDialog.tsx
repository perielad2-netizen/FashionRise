import type { ReactNode } from 'react'
import styles from './ConfirmDialog.module.css'

type Action = {
  label: string
  onClick: () => void
  variant?: 'primary' | 'danger' | 'ghost'
}

type Props = {
  title: string
  children: ReactNode
  actions: Action[]
}

export function ConfirmDialog({ title, children, actions }: Props) {
  return (
    <div className={styles.scrim} role="presentation">
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="studio-confirm-title">
        <h2 id="studio-confirm-title" className={styles.title}>
          {title}
        </h2>
        <div className={styles.body}>{children}</div>
        <div className={styles.actions}>
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              className={
                action.variant === 'danger'
                  ? styles.danger
                  : action.variant === 'ghost'
                    ? styles.ghost
                    : styles.primary
              }
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
