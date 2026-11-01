import { useEffect, useId, useRef, useState, type WheelEvent as ReactWheelEvent } from 'react'
import {
  BRUSH_SIZE_MAX_PX,
  BRUSH_SIZE_MIN_PX,
  BRUSH_SIZE_STEP_PX,
  formatBrushSizePx,
  snapBrushSizePx,
  type ToolKind,
} from '@/lib/strokes'
import styles from './BrushSizeControl.module.css'

type Props = {
  tool: ToolKind
  brushSize: number
  opacity: number
  onBrushSize: (px: number) => void
  /** Visual theme: dark studio inspector vs light tablet brush sheet. */
  tone?: 'dark' | 'light'
  /** Show a circular tip preview (default) in addition to the stroke strip. */
  showTip?: boolean
}

/**
 * Continuous pixel brush control shared by desktop Settings and tablet Brush panel.
 * Wheel over the control adjusts size; does not capture page scroll outside the control.
 */
export function BrushSizeControl({
  tool,
  brushSize,
  opacity,
  onBrushSize,
  tone = 'dark',
  showTip = true,
}: Props) {
  const inputId = useId()
  const [draft, setDraft] = useState(formatBrushSizePx(brushSize))
  const focusedRef = useRef(false)

  useEffect(() => {
    if (!focusedRef.current) setDraft(formatBrushSizePx(brushSize))
  }, [brushSize])

  const commitDraft = () => {
    const parsed = Number.parseFloat(draft.replace(/px/gi, '').trim())
    if (!Number.isFinite(parsed)) {
      setDraft(formatBrushSizePx(brushSize))
      return
    }
    const next = snapBrushSizePx(parsed)
    onBrushSize(next)
    setDraft(formatBrushSizePx(next))
  }

  const onWheel = (e: ReactWheelEvent) => {
    // Only when pointer is over this control — prevent page scroll hijack.
    e.preventDefault()
    e.stopPropagation()
    const dir = e.deltaY < 0 ? 1 : e.deltaY > 0 ? -1 : 0
    if (!dir) return
    onBrushSize(snapBrushSizePx(brushSize + dir * BRUSH_SIZE_STEP_PX))
  }

  const tipPx = Math.max(2, Math.min(48, brushSize))
  const strokeH = Math.max(1, Math.min(28, brushSize))
  const erase = tool === 'erase'

  return (
    <div
      className={tone === 'light' ? styles.rootLight : styles.root}
      onWheel={onWheel}
      aria-label="Brush size control"
    >
      <div className={styles.previewRow} aria-hidden>
        {showTip ? (
          <div className={styles.tipWell}>
            <span
              className={erase ? styles.tipErase : styles.tip}
              style={{
                width: tipPx,
                height: tipPx,
                opacity: erase ? 1 : opacity,
              }}
            />
          </div>
        ) : null}
        <div className={styles.strokeWell}>
          <div
            className={erase ? styles.strokeErase : styles.stroke}
            style={{
              height: strokeH,
              opacity: erase ? 1 : opacity,
            }}
          />
        </div>
      </div>

      <div className={styles.row}>
        <label htmlFor={inputId}>Size</label>
        <div className={styles.numeric}>
          <input
            id={inputId}
            className={styles.numberInput}
            inputMode="decimal"
            aria-label="Brush size in pixels"
            value={draft}
            onFocus={() => {
              focusedRef.current = true
            }}
            onBlur={() => {
              focusedRef.current = false
              commitDraft()
            }}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.currentTarget.blur()
              }
            }}
          />
          <span className={styles.suffix} aria-hidden>
            px
          </span>
        </div>
      </div>

      <input
        className={styles.slider}
        type="range"
        min={BRUSH_SIZE_MIN_PX}
        max={BRUSH_SIZE_MAX_PX}
        step={BRUSH_SIZE_STEP_PX}
        value={snapBrushSizePx(brushSize)}
        aria-label="Brush size"
        aria-valuemin={BRUSH_SIZE_MIN_PX}
        aria-valuemax={BRUSH_SIZE_MAX_PX}
        aria-valuenow={snapBrushSizePx(brushSize)}
        aria-valuetext={`${formatBrushSizePx(brushSize)} pixels`}
        onChange={(e) => onBrushSize(Number(e.target.value))}
      />
      <p className={styles.hint}>Scroll wheel over this control to nudge size</p>
    </div>
  )
}
