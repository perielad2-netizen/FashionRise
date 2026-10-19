import type { ToolKind } from '@/lib/strokes'
import { BRUSH_SIZES } from '@/lib/strokes'
import styles from './FloatingBrushPanel.module.css'

type Props = {
  tool: ToolKind
  brushSize: number
  opacity: number
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  /** When true, panel is hidden (narrow screens use brush sheet instead). */
  hiddenOnNarrow?: boolean
  variant?: 'float' | 'sheet'
}

export function FloatingBrushPanel({
  tool,
  brushSize,
  opacity,
  onBrushSize,
  onOpacity,
  hiddenOnNarrow = true,
  variant = 'float',
}: Props) {
  const title = tool === 'erase' ? 'Eraser' : 'Pencil'
  return (
    <div
      className={`${variant === 'sheet' ? styles.sheet : styles.panel} ${hiddenOnNarrow && variant === 'float' ? styles.hideNarrow : ''}`}
      aria-label="Brush settings"
    >
      <p className={styles.title}>{title}</p>
      <div className={styles.preview} aria-hidden>
        <div
          className={styles.stroke}
          style={{
            height: Math.max(1, Math.min(12, brushSize)),
            opacity: tool === 'erase' ? 1 : opacity,
            background: tool === 'erase' ? '#9ca3af' : '#111827',
          }}
        />
      </div>
      <div className={styles.row}>
        <span>Size</span>
        <strong>{brushSize.toFixed(brushSize < 10 ? 2 : 0).replace(/\.00$/, '')} px</strong>
      </div>
      <input
        className={styles.slider}
        type="range"
        min={BRUSH_SIZES.thin}
        max={BRUSH_SIZES.bold}
        step={0.25}
        value={brushSize}
        aria-label="Brush size"
        onChange={(e) => onBrushSize(Number(e.target.value))}
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
