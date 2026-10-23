import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  customGradientStyle,
  gradientPreviewCss,
  normalizeGradientAngle,
  type GradientFillStyle,
} from '@/lib/fills'
import { ProfessionalColorPicker } from '@/shell/components/ProfessionalColorPicker'
import styles from './CustomGradientDesigner.module.css'

type Props = {
  open: boolean
  initial?: GradientFillStyle | null
  onApply: (style: GradientFillStyle) => void
  onCancel: () => void
}

type Endpoint = 'c0' | 'c1'

const QUICK_ANGLES: { label: string; angle: number }[] = [
  { label: 'Horizontal', angle: 0 },
  { label: 'Vertical', angle: 90 },
  { label: 'Diagonal', angle: 135 },
]

/**
 * Contained custom two-color gradient designer.
 * Endpoint color picks reuse ProfessionalColorPicker and never mutate pencil ink.
 */
export function CustomGradientDesigner({ open, initial, onApply, onCancel }: Props) {
  const titleId = useId()
  const angleId = useId()
  const [c0, setC0] = useState('#D63384')
  const [c1, setC1] = useState('#7C3AED')
  const [angle, setAngle] = useState(135)
  const [angleDraft, setAngleDraft] = useState('135')
  const [picking, setPicking] = useState<Endpoint | null>(null)

  useEffect(() => {
    if (!open) return
    const next0 = initial?.colors[0] ?? '#D63384'
    const next1 = initial?.colors[1] ?? '#7C3AED'
    const nextAngle = normalizeGradientAngle(initial?.angle ?? 135)
    setC0(next0)
    setC1(next1)
    setAngle(nextAngle)
    setAngleDraft(String(nextAngle))
    setPicking(null)
  }, [open, initial])

  if (!open) return null

  const preview = gradientPreviewCss([c0, c1], angle)

  const commitAngle = (raw: number) => {
    const next = normalizeGradientAngle(raw)
    setAngle(next)
    setAngleDraft(String(next))
  }

  const apply = () => {
    const style = customGradientStyle([c0, c1], angle)
    if (!style) return
    onApply(style)
  }

  return createPortal(
    <div className={styles.scrim} role="presentation">
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className={styles.head}>
          <h2 id={titleId}>Create gradient</h2>
          <button type="button" className={styles.ghost} onClick={onCancel} aria-label="Close">
            Cancel
          </button>
        </header>

        <div
          className={styles.preview}
          style={{ background: preview }}
          aria-label={`Gradient preview at ${angle} degrees`}
        />

        <div className={styles.colors}>
          <button
            type="button"
            className={styles.swatchBtn}
            style={{ background: c0 }}
            aria-label={`Color 1 ${c0}`}
            onClick={() => setPicking('c0')}
          >
            <span>Color 1</span>
            <strong>{c0}</strong>
          </button>
          <button
            type="button"
            className={styles.swap}
            aria-label="Swap colors"
            onClick={() => {
              setC0(c1)
              setC1(c0)
            }}
          >
            Swap
          </button>
          <button
            type="button"
            className={styles.swatchBtn}
            style={{ background: c1 }}
            aria-label={`Color 2 ${c1}`}
            onClick={() => setPicking('c1')}
          >
            <span>Color 2</span>
            <strong>{c1}</strong>
          </button>
        </div>

        <label className={styles.angleRow} htmlFor={angleId}>
          <span>Direction</span>
          <div className={styles.angleNumeric}>
            <input
              id={angleId}
              inputMode="decimal"
              value={angleDraft}
              aria-label="Gradient angle in degrees"
              onChange={(e) => setAngleDraft(e.target.value)}
              onBlur={() => {
                const n = Number.parseFloat(angleDraft)
                if (!Number.isFinite(n)) {
                  setAngleDraft(String(angle))
                  return
                }
                commitAngle(n)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
              }}
            />
            <span aria-hidden>°</span>
          </div>
        </label>
        <input
          className={styles.slider}
          type="range"
          min={0}
          max={360}
          step={1}
          value={angle}
          aria-label="Gradient angle"
          onChange={(e) => commitAngle(Number(e.target.value))}
        />
        <div className={styles.quick}>
          {QUICK_ANGLES.map((q) => (
            <button
              key={q.label}
              type="button"
              className={angle === q.angle ? styles.quickActive : styles.quickBtn}
              aria-pressed={angle === q.angle}
              onClick={() => commitAngle(q.angle)}
            >
              {q.label}
            </button>
          ))}
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.ghost} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className={styles.primary} onClick={apply}>
            Use gradient
          </button>
        </div>
      </div>

      <ProfessionalColorPicker
        open={picking !== null}
        initialColor={picking === 'c1' ? c1 : c0}
        onApply={(hex) => {
          if (picking === 'c1') setC1(hex)
          else setC0(hex)
          setPicking(null)
        }}
        onCancel={() => setPicking(null)}
      />
    </div>,
    document.body,
  )
}
