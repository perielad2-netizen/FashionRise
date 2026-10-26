import type { MeasuredValue } from '@/services/techpacksApi'
import { FieldHelp } from '@/shell/components/techpack/FieldHelp'
import { getFieldHelp } from '@/shell/components/techpack/fieldHelpContent'
import styles from './MeasuredField.module.css'

type Props = {
  label: string
  value: MeasuredValue
  onChange: (next: MeasuredValue) => void
  helpKey?: string
  /** Larger touch targets for the mobile measurement sheet. */
  compact?: boolean
}

export function MeasuredField({ label, value, onChange, helpKey, compact = false }: Props) {
  const help = helpKey ? getFieldHelp(helpKey) : null
  return (
    <div className={compact ? `${styles.measureRow} ${styles.measureRowCompact}` : styles.measureRow}>
      <div className={styles.field}>
        <div className={styles.fieldLabelRow}>
          <label>{label}</label>
          {help ? (
            <FieldHelp
              title={help.title}
              explanation={help.explanation}
              examples={help.examples}
              diagram={help.diagram}
            />
          ) : null}
        </div>
        <input
          type="text"
          inputMode="decimal"
          enterKeyHint="next"
          autoComplete="off"
          value={value.value ?? ''}
          placeholder="Leave empty if unknown"
          aria-label={label}
          onChange={(e) => {
            const raw = e.target.value.trim()
            onChange({
              ...value,
              value: raw === '' ? null : Number.isFinite(Number(raw)) ? Number(raw) : raw,
              source: raw === '' ? 'empty' : value.source === 'empty' ? 'designer' : value.source,
            })
          }}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor={`unit-${label}`}>Unit</label>
        <input
          id={`unit-${label}`}
          type="text"
          value={value.unit ?? ''}
          aria-label={`${label} unit`}
          onChange={(e) => onChange({ ...value, unit: e.target.value })}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor={`source-${label}`}>Source</label>
        <select
          id={`source-${label}`}
          value={value.source}
          aria-label={`${label} source`}
          onChange={(e) =>
            onChange({ ...value, source: e.target.value as MeasuredValue['source'] })
          }
        >
          <option value="empty">Empty</option>
          <option value="designer">Designer</option>
          <option value="estimate">Estimate</option>
          <option value="look">Look</option>
          <option value="calculated">Calculated</option>
          <option value="unknown">Unknown</option>
          <option value="ai">AI (unverified)</option>
        </select>
      </div>
    </div>
  )
}
