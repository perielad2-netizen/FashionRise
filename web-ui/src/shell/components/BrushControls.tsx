import type { ToolKind } from '@/lib/strokes'
import { BrushSizeControl } from '@/shell/components/BrushSizeControl'
import styles from './BrushControls.module.css'

type Props = {
  tool: ToolKind
  brushSize: number
  opacity: number
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
}

/** Brush size and opacity for the dock sheet when the Settings column is hidden. */
export function BrushControls({ tool, brushSize, opacity, onBrushSize, onOpacity }: Props) {
  const title = tool === 'erase' ? 'Eraser' : 'Pencil'
  return (
    <div className={styles.sheet} aria-label="Brush settings">
      <p className={styles.title}>{title}</p>
      <BrushSizeControl
        tool={tool}
        brushSize={brushSize}
        opacity={opacity}
        onBrushSize={onBrushSize}
        tone="light"
      />
      <div className={styles.row}>
        <span>Opacity</span>
        <strong>{Math.round(opacity * 100)}%</strong>
      </div>
      <input
        className={styles.slider}
        type="range"
        min={5}
        max={100}
        step={1}
        value={Math.round(opacity * 100)}
        aria-label="Brush opacity"
        disabled={tool === 'erase'}
        onChange={(e) => onOpacity(Number(e.target.value) / 100)}
      />
    </div>
  )
}
