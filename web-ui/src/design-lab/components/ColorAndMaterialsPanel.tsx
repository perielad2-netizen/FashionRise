import { Eye, Lock, Pipette, Plus, Trash2 } from 'lucide-react'
import styles from './ColorAndMaterialsPanel.module.css'

const SWATCHES = ['#d63384', '#1c1c1e', '#1e3a8a', '#9f1239', '#6b7280', '#f8f3ee']
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
  { id: 'hat', label: 'Hat', active: false },
  { id: 'sketch', label: 'Sketch', active: true },
  { id: 'notes', label: 'Design Notes', active: false },
  { id: 'bg', label: 'Background', active: false },
]

export function ColorAndMaterialsPanel() {
  return (
    <div className={styles.stack} aria-label="Colors and materials prototype">
      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Colors</h3>
        </div>
        <div className={styles.picker} aria-hidden>
          <span className={styles.pickerDot} />
        </div>
        <div className={styles.hue} aria-hidden />
        <div className={styles.swatches}>
          {SWATCHES.map((c, i) => (
            <span
              key={c}
              className={i === 0 ? styles.swatchActive : styles.swatch}
              style={{ background: c }}
            />
          ))}
        </div>
        <div className={styles.hexRow}>
          <input className={styles.hex} value="#D63384" readOnly tabIndex={-1} aria-label="Hex" />
          <button type="button" className={styles.iconBtn} tabIndex={-1} aria-disabled aria-label="Eyedropper">
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
            <div key={bg} className={styles.fabric} style={{ background: bg }} />
          ))}
        </div>
        <p className={styles.note}>Visual prototype — fabrics are not implemented in production Studio.</p>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Gradients</h3>
        </div>
        <div className={styles.gradients}>
          {GRADIENTS.map((bg) => (
            <div key={bg} className={styles.gradient} style={{ background: bg }} />
          ))}
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.head}>
          <h3>Layers</h3>
          <button type="button" className={styles.iconBtn} tabIndex={-1} aria-disabled>
            <Plus size={14} />
          </button>
        </div>
        <div className={styles.layers}>
          {LAYERS.map((layer) => (
            <div key={layer.id} className={layer.active ? styles.layerActive : styles.layer}>
              <span>{layer.label}</span>
              <button type="button" className={styles.iconBtn} tabIndex={-1} aria-disabled>
                <Eye size={14} />
              </button>
              <button type="button" className={styles.iconBtn} tabIndex={-1} aria-disabled>
                <Lock size={14} />
              </button>
              <button type="button" className={styles.iconBtn} tabIndex={-1} aria-disabled>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <p className={styles.note}>Layer stack is visual only in this design lab.</p>
      </section>
    </div>
  )
}
