import { useEffect, useState } from 'react'
import { Eye, Lock, Pipette, Plus, Trash2 } from 'lucide-react'
import { INK_SWATCHES } from '@/lib/strokes'
import styles from './ColorAndMaterialsPanel.module.css'

const FABRICS = [
  'linear-gradient(145deg,#f9a8d4,#be185d)',
  'linear-gradient(145deg,#f5e6d3,#c4a484)',
  'linear-gradient(145deg,#93c5fd,#1d4ed8)',
  'linear-gradient(145deg,#d1d5db,#4b5563)',
]
const GRADIENTS = [
  'linear-gradient(135deg,#d63384,#7c3aed)',
  'linear-gradient(135deg,#f8f4f0,#d4af9b)',
  'linear-gradient(135deg,#0ea5e9,#d63384)',
  'linear-gradient(135deg,#111827,#9f1239)',
]
const LAYERS = [
  { id: 'hat', label: 'Hat' },
  { id: 'sketch', label: 'Sketch', active: true },
  { id: 'notes', label: 'Design Notes' },
  { id: 'bg', label: 'Background' },
]

type Props = {
  color: string
  onColor: (color: string) => void
  onColorHex: (hex: string) => boolean
}

export function ColorAndMaterialsPanel({ color, onColor, onColorHex }: Props) {
  const [hexDraft, setHexDraft] = useState(color)

  useEffect(() => {
    setHexDraft(color)
  }, [color])

  const commitHex = () => {
    const ok = onColorHex(hexDraft.startsWith('#') ? hexDraft : `#${hexDraft}`)
    if (!ok) setHexDraft(color)
  }

  return (
    <div className={styles.stack} aria-label="Colors and materials">
      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Colors</h3>
        </div>
        <div
          className={styles.picker}
          aria-hidden
          style={{
            background: `linear-gradient(180deg, transparent, #000), linear-gradient(90deg, #fff, ${color})`,
          }}
        >
          <span className={styles.pickerDot} />
        </div>
        <div className={styles.hue} aria-hidden />
        <div className={styles.swatches}>
          {INK_SWATCHES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={color.toLowerCase() === s.color.toLowerCase() ? styles.swatchActive : styles.swatch}
              style={{ background: s.color }}
              aria-label={s.label}
              title={s.label}
              onClick={() => {
                onColor(s.color)
                setHexDraft(s.color)
              }}
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
          <button type="button" className={styles.iconBtn} disabled aria-label="Eyedropper unavailable">
            <Pipette size={14} />
          </button>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Fabrics &amp; Textures</h3>
        </div>
        <div className={styles.fabrics}>
          {FABRICS.map((bg) => (
            <button
              key={bg}
              type="button"
              className={styles.fabric}
              style={{ background: bg }}
              disabled
              aria-disabled
              title="Unavailable"
              aria-label="Fabric unavailable"
            />
          ))}
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Gradients</h3>
        </div>
        <div className={styles.gradients}>
          {GRADIENTS.map((bg) => (
            <button
              key={bg}
              type="button"
              className={styles.gradient}
              style={{ background: bg }}
              disabled
              aria-disabled
              title="Unavailable"
              aria-label="Gradient unavailable"
            />
          ))}
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Layers</h3>
          <button type="button" className={styles.iconBtn} disabled aria-label="Add layer unavailable">
            <Plus size={14} />
          </button>
        </div>
        <div className={styles.layers}>
          {LAYERS.map((layer) => (
            <div key={layer.id} className={layer.active ? styles.layerActive : styles.layer}>
              <span>{layer.label}</span>
              <button type="button" className={styles.iconBtn} disabled aria-label="Visibility unavailable">
                <Eye size={14} />
              </button>
              <button type="button" className={styles.iconBtn} disabled aria-label="Lock unavailable">
                <Lock size={14} />
              </button>
              <button type="button" className={styles.iconBtn} disabled aria-label="Delete unavailable">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
