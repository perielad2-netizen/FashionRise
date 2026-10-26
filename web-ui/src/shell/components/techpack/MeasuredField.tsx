import { useId, useState } from 'react'
import type { MeasuredValue } from '@/services/techpacksApi'
import { FieldHelp } from '@/shell/components/techpack/FieldHelp'
import { getFieldHelp } from '@/shell/components/techpack/fieldHelpContent'
import styles from './MeasuredField.module.css'

type Props = {
  label: string
  value: MeasuredValue
  onChange: (next: MeasuredValue) => void
  helpKey?: string
  /** Larger touch targets + value-first layout for the mobile measurement sheet. */
  compact?: boolean
}

export function MeasuredField({ label, value, onChange, helpKey, compact = false }: Props) {
  const help = helpKey ? getFieldHelp(helpKey) : null
  const uid = useId()
  const [metaOpen, setMetaOpen] = useState(false)
  const unit = value.unit || 'cm'

  const onValue = (rawInput: string) => {
    const raw = rawInput.trim()
    onChange({
      ...value,
      value: raw === '' ? null : Number.isFinite(Number(raw)) ? Number(raw) : raw,
      source: raw === '' ? 'empty' : value.source === 'empty' ? 'designer' : value.source,
      unit: value.unit || 'cm',
    })
  }

  if (compact) {
    return (
      <div className={`${styles.measureRow} ${styles.measureRowCompact} ${styles.measureRowValueFirst}`}>
        <div className={styles.valueFirstRow}>
          <div className={styles.fieldLabelRow}>
            <label htmlFor={`${uid}-val`}>{label}</label>
            {help ? (
              <FieldHelp
                title={help.title}
                explanation={help.explanation}
                examples={help.examples}
                diagram={help.diagram}
              />
            ) : null}
          </div>
          <div className={styles.valueUnitGroup}>
            <input
              id={`${uid}-val`}
              type="text"
              inputMode="decimal"
              enterKeyHint="next"
              autoComplete="off"
              value={value.value ?? ''}
              placeholder="—"
              aria-label={label}
              onChange={(e) => onValue(e.target.value)}
              onFocus={(e) => {
                // Keep focused field visible above Android keyboard when possible.
                const target = e.target
                window.setTimeout(() => {
                  if (typeof target.scrollIntoView === 'function') {
                    target.scrollIntoView({ block: 'center', behavior: 'smooth' })
                  }
                }, 50)
              }}
            />
            <span className={styles.unitBadge} aria-hidden>
              {unit}
            </span>
          </div>
        </div>
        <button
          type="button"
          className={styles.metaToggle}
          aria-expanded={metaOpen}
          onClick={() => setMetaOpen((v) => !v)}
        >
          {metaOpen ? 'Hide unit / source' : 'Unit / source'}
        </button>
        {metaOpen ? (
          <div className={styles.metaPanel}>
            <div className={styles.field}>
              <label htmlFor={`${uid}-unit`}>Unit</label>
              <input
                id={`${uid}-unit`}
                type="text"
                value={value.unit ?? ''}
                aria-label={`${label} unit`}
                onChange={(e) => onChange({ ...value, unit: e.target.value })}
              />
            </div>
            <div className={styles.field}>
              <label htmlFor={`${uid}-source`}>Source</label>
              <select
                id={`${uid}-source`}
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
        ) : null}
      </div>
    )
  }

  return (
    <div className={styles.measureRow}>
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
          onChange={(e) => onValue(e.target.value)}
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
