import { useEffect, useId, useRef, useState, type WheelEvent as ReactWheelEvent } from 'react'
import {
  BRUSH_SIZE_MAX_PX,
  BRUSH_SIZE_MIN_PX,
  BRUSH_SIZE_STEP_PX,
  formatBrushSizePx,
  snapBrushSizePx,
  type ToolKind,
} from '@/lib/strokes'
import type { BrushKind } from '@/lib/professionalBrushes'
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
  /** V2-0023: kind-aware tip preview. */
  brushKind?: BrushKind
  brushColor?: string
}

/** Parse #RRGGBB for contrast helpers (invalid → null). */
function parseBrushHex(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(hex.trim())
  if (!m) return null
  const n = Number.parseInt(m[1]!, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

/** Relative luminance 0–1 (sRGB). */
function brushLuminance(hex: string): number {
  const c = parseBrushHex(hex)
  if (!c) return 0.5
  const lin = (v: number) => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
}

function airbrushBackground(hex: string): string {
  const c = parseBrushHex(hex)
  if (!c) {
    return 'radial-gradient(circle, rgba(248,250,252,0.95) 0%, rgba(248,250,252,0.2) 55%, transparent 72%)'
  }
  const { r, g, b } = c
  return `radial-gradient(circle, rgba(${r},${g},${b},0.95) 0%, rgba(${r},${g},${b},0.22) 55%, transparent 72%)`
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
  brushKind = 'tapered',
  brushColor = '#f8fafc',
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
  // Keep a readable minimum thickness so tiny sizes still show a clear stripe.
  const strokeH = Math.max(3, Math.min(28, brushSize))
  const erase = tool === 'erase'
  const previewColor = erase ? undefined : brushColor
  const lightBrush = !erase && brushLuminance(brushColor) >= 0.72
  const tipClass = erase
    ? styles.tipErase
    : brushKind === 'airbrush'
      ? styles.tipAirbrush
      : brushKind === 'charcoal'
        ? styles.tipCharcoal
        : styles.tip

  return (
    <div
      className={tone === 'light' ? styles.rootLight : styles.root}
      onWheel={onWheel}
      aria-label="Brush size control"
    >
      <div className={styles.previewRow} aria-hidden>
        {showTip ? (
          <div className={styles.tipWell} data-testid="brush-tip-well">
            <span
              className={`${tipClass}${lightBrush ? ` ${styles.tipContrast}` : ''}`}
              style={{
                width: tipPx,
                height: tipPx,
                opacity: erase ? 1 : Math.max(0.45, opacity),
                background: erase
                  ? undefined
                  : brushKind === 'airbrush'
                    ? airbrushBackground(brushColor)
                    : brushColor,
              }}
              data-testid="brush-tip-preview"
            />
          </div>
        ) : null}
        <div className={styles.strokeWell} data-testid="brush-stroke-well">
          <div
            className={`${erase ? styles.strokeErase : styles.stroke}${
              lightBrush ? ` ${styles.strokeContrast}` : ''
            }`}
            style={{
              height: strokeH,
              opacity: erase ? 1 : Math.max(0.55, opacity),
              ...(previewColor ? { background: previewColor } : {}),
            }}
            data-testid="brush-stroke-preview"
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
      <p className={styles.hint} data-testid="brush-size-hint">
        {/* V2-0027: wheel copy only where a fine pointer exists. */}
        <span className={styles.hintFine}>Scroll wheel over this control to nudge size</span>
        <span className={styles.hintCoarse}>Drag the slider or type an exact size</span>
      </p>
    </div>
  )
}
