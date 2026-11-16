import type { BrushKind } from '@/lib/professionalBrushes'
import {
  AirbrushKindIcon,
  CharcoalKindIcon,
  InkKindIcon,
} from '@/shell/components/StudioToolIcons'
import styles from './BrushKindStrip.module.css'

const OPTIONS: Array<{
  id: BrushKind
  label: string
  Icon: (props: { size?: number }) => JSX.Element
}> = [
  { id: 'tapered', label: 'Ink', Icon: InkKindIcon },
  { id: 'charcoal', label: 'Charcoal', Icon: CharcoalKindIcon },
  { id: 'airbrush', label: 'Airbrush', Icon: AirbrushKindIcon },
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
        const Icon = opt.Icon
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
            <Icon size={compact ? 13 : 14} />
            <span>{opt.label}</span>
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
