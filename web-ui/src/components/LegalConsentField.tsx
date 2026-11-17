/**
 * One short mandatory checkbox + expandable "Read full terms" / "Hide full terms".
 * Expand toggle must not toggle the checkbox. Unchecked by default (caller state).
 */
import { useId, useState, type ReactNode } from 'react'
import styles from './LegalConsentField.module.css'

export type LegalConsentFieldProps = {
  checked: boolean
  onCheckedChange: (next: boolean) => void
  disabled?: boolean
  shortLabel: string
  intro: string
  points: readonly string[]
  /** Extra content inside the expanded panel (e.g. approved notices, Privacy link). */
  expandedExtra?: ReactNode
  checkboxTestId?: string
  termsTestId?: string
  className?: string
}

export function LegalConsentField({
  checked,
  onCheckedChange,
  disabled = false,
  shortLabel,
  intro,
  points,
  expandedExtra,
  checkboxTestId,
  termsTestId,
  className,
}: LegalConsentFieldProps) {
  const reactId = useId()
  const checkboxId = `${reactId}-consent`
  const termsId = `${reactId}-terms`
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={[styles.root, className].filter(Boolean).join(' ')}>
      <label className={styles.check} htmlFor={checkboxId}>
        <input
          id={checkboxId}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onCheckedChange(e.target.checked)}
          data-testid={checkboxTestId}
        />
        <span>{shortLabel}</span>
      </label>

      <button
        type="button"
        className={styles.termsToggle}
        aria-expanded={expanded}
        aria-controls={termsId}
        onClick={() => setExpanded((v) => !v)}
        data-testid={termsTestId ? `${termsTestId}-toggle` : undefined}
      >
        {expanded ? 'Hide full terms' : 'Read full terms'}
      </button>

      {expanded ? (
        <div
          id={termsId}
          className={styles.termsPanel}
          role="region"
          aria-label="Full terms"
          data-testid={termsTestId}
        >
          <p className={styles.intro}>{intro}</p>
          <ol className={styles.points}>
            {points.map((point) => (
              <li key={point.slice(0, 48)}>{point}</li>
            ))}
          </ol>
          {expandedExtra}
        </div>
      ) : null}
    </div>
  )
}
