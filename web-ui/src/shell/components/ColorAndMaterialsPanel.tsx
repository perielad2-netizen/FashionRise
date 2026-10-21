import { useEffect, useState } from 'react'
import { Pipette } from 'lucide-react'
import {
  FABRIC_PRESETS,
  FASHION_PALETTE,
  GRADIENT_PRESETS,
  type FillStyle,
} from '@/lib/fills'
import { INK_SWATCHES } from '@/lib/strokes'
import styles from './ColorAndMaterialsPanel.module.css'

type Props = {
  color: string
  onColor: (color: string) => void
  onColorHex: (hex: string) => boolean
  fillStyle: FillStyle
  onFillStyle: (style: FillStyle) => void
  eyedropperActive: boolean
  onToggleEyedropper: () => void
}

export function ColorAndMaterialsPanel({
  color,
  onColor,
  onColorHex,
  fillStyle,
  onFillStyle,
  eyedropperActive,
  onToggleEyedropper,
}: Props) {
  const [hexDraft, setHexDraft] = useState(color)

  useEffect(() => {
    setHexDraft(color)
  }, [color])

  const commitHex = () => {
    const ok = onColorHex(hexDraft.startsWith('#') ? hexDraft : `#${hexDraft}`)
    if (!ok) setHexDraft(color)
  }

  const selectSolid = (next: string) => {
    onColor(next)
    setHexDraft(next)
  }

  return (
    <div className={styles.stack} aria-label="Colors and materials">
      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Colors</h3>
        </div>
        <div className={styles.currentInk}>
          <span className={styles.currentSwatch} style={{ background: color }} />
          <span>Current color</span>
        </div>
        <div className={styles.swatches}>
          {INK_SWATCHES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={color.toLowerCase() === s.color.toLowerCase() ? styles.swatchActive : styles.swatch}
              style={{ background: s.color }}
              aria-label={s.label}
              title={s.label}
              onClick={() => selectSolid(s.color)}
            />
          ))}
        </div>
        <p className={styles.note}>Fashion palette</p>
        <div className={styles.swatches}>
          {FASHION_PALETTE.map((s) => (
            <button
              key={s.id}
              type="button"
              className={color.toLowerCase() === s.color.toLowerCase() ? styles.swatchActive : styles.swatch}
              style={{ background: s.color }}
              aria-label={s.label}
              title={s.label}
              onClick={() => selectSolid(s.color)}
            />
          ))}
        </div>
        <div className={styles.hexRow}>
          <input
            className={styles.hex}
            value={hexDraft}
            aria-label="Hex color"
            onChange={(e) => setHexDraft(e.target.value)}
            onBlur={commitHex}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitHex()
            }}
          />
          <input
            type="color"
            className={styles.nativePicker}
            value={/^#[0-9a-fA-F]{6}$/.test(color) ? color : '#1C1C1E'}
            aria-label="Color picker"
            title="Pick a color"
            onChange={(e) => selectSolid(e.target.value.toUpperCase())}
          />
          <button
            type="button"
            className={eyedropperActive ? styles.iconBtnActive : styles.iconBtn}
            aria-label={eyedropperActive ? 'Eyedropper on' : 'Eyedropper'}
            aria-pressed={eyedropperActive}
            title="Sample a color from your sketch"
            onClick={onToggleEyedropper}
          >
            <Pipette size={14} />
          </button>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Fabrics</h3>
        </div>
        <p className={styles.note}>Select a fabric, then use Fill on a closed dress region.</p>
        <div className={styles.fabrics}>
          {FABRIC_PRESETS.map((fabric) => {
            const active = fillStyle.kind === 'fabric' && fillStyle.fabricId === fabric.id
            return (
              <button
                key={fabric.id}
                type="button"
                className={active ? styles.fabricActive : styles.fabric}
                style={{ background: fabric.preview }}
                aria-label={fabric.label}
                aria-pressed={active}
                title={fabric.label}
                onClick={() => onFillStyle({ kind: 'fabric', fabricId: fabric.id })}
              />
            )
          })}
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Gradients</h3>
        </div>
        <p className={styles.note}>Select a gradient, then Fill a closed region.</p>
        <div className={styles.gradients}>
          {GRADIENT_PRESETS.map((g) => {
            const active = fillStyle.kind === 'gradient' && fillStyle.gradientId === g.id
            return (
              <button
                key={g.id}
                type="button"
                className={active ? styles.gradientActive : styles.gradient}
                style={{ background: g.preview }}
                aria-label={g.label}
                aria-pressed={active}
                title={g.label}
                onClick={() =>
                  onFillStyle({
                    kind: 'gradient',
                    gradientId: g.id,
                    colors: [...g.colors] as [string, string],
                    angle: g.angle,
                  })
                }
              />
            )
          })}
        </div>
      </section>
    </div>
  )
}
