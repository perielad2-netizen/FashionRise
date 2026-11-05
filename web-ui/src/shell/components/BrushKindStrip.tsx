import type { BrushKind } from '@/lib/professionalBrushes'
import styles from './BrushKindStrip.module.css'

const OPTIONS: Array<{ id: BrushKind; label: string }> = [
  { id: 'tapered', label: 'Ink' },
  { id: 'charcoal', label: 'Charcoal' },
  { id: 'airbrush', label: 'Airbrush' },
]

type Props = {
  brushKind: BrushKind
  disabled?: boolean
  onBrushKind: (kind: BrushKind) => void
  /** Compact chips for toolbars; default is the immersive/mobile strip. */
  compact?: boolean
}

/** Always-visible Ink / Charcoal / Airbrush switcher. */
export function BrushKindStrip({
  brushKind,
  disabled = false,
  onBrushKind,
  compact = false,
}: Props) {
  return (
    <div
      className={compact ? styles.compact : styles.strip}
      role="radiogroup"
      aria-label="Brush type"
      data-testid="brush-kind-strip"
    >
      {OPTIONS.map((opt) => {
        const selected = brushKind === opt.id
        return (
          <button
            key={opt.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            className={selected ? styles.active : styles.btn}
            onClick={() => onBrushKind(opt.id)}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export function brushKindShortLabel(kind: BrushKind): string {
  if (kind === 'charcoal') return 'Charcoal'
  if (kind === 'airbrush') return 'Airbrush'
  return 'Ink'
}
