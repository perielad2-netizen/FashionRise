import { Sparkles } from 'lucide-react'
import { BRUSH_SIZES, type BrushSizeId } from '@/lib/strokes'
import styles from './SettingsInspector.module.css'

type Props = {
  sizeId: BrushSizeId
  brushSize: number
  opacity: number
  dimmed: boolean
  toolLabel: string
  onSize: (id: BrushSizeId) => void
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  onToggleDim: () => void
  onMagic: () => void
}

export function SettingsInspector({
  sizeId,
  brushSize,
  opacity,
  dimmed,
  toolLabel,
  onSize,
  onBrushSize,
  onOpacity,
  onToggleDim,
  onMagic,
}: Props) {
  return (
    <aside className={styles.panel} aria-label="Settings inspector">
      <div className={styles.tabs}>
        <button type="button" className={styles.tabActive}>
          Settings
        </button>
        <button type="button" className={styles.tab} disabled title="Coming later">
          Help
        </button>
      </div>

      <section className={styles.section}>
        <h3>Canvas</h3>
        <div className={styles.row}>
          <span>Size</span>
          <strong>768 × 1024</strong>
        </div>
        <div className={styles.row}>
          <span>Background</span>
          <strong>Cream paper</strong>
        </div>
        <div className={styles.row}>
          <span>Dim reference</span>
          <button
            type="button"
            className={dimmed ? styles.toggleOn : styles.toggle}
            aria-pressed={dimmed}
            aria-label={dimmed ? 'Dim reference on' : 'Dim reference off'}
            onClick={onToggleDim}
          />
        </div>
      </section>

      <section className={styles.section}>
        <h3>Brush settings</h3>
        <div className={styles.row}>
          <span>Tool</span>
          <strong>{toolLabel}</strong>
        </div>
        <div className={styles.row}>
          <span>Size</span>
          <strong>{brushSize} px</strong>
        </div>
        <div className={styles.sizes}>
          {(Object.keys(BRUSH_SIZES) as BrushSizeId[]).map((id) => (
            <button
              key={id}
              type="button"
              className={sizeId === id ? styles.sizeActive : styles.size}
              onClick={() => onSize(id)}
            >
              {id}
            </button>
          ))}
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
          onChange={(e) => onOpacity(Number(e.target.value) / 100)}
        />
        <div className={styles.row}>
          <span>Pressure sensitivity</span>
          <button
            type="button"
            className={styles.toggle}
            disabled
            aria-disabled
            title="Uses device pressure when available; not configurable"
            aria-label="Pressure sensitivity unavailable"
          />
        </div>
      </section>

      <section className={styles.section}>
        <h3>Shortcuts</h3>
        <div className={styles.shortcuts}>
          <div className={styles.shortcut}>
            <span>Pencil</span>
            <span className={styles.kbd}>B</span>
          </div>
          <div className={styles.shortcut}>
            <span>Eraser</span>
            <span className={styles.kbd}>E</span>
          </div>
          <div className={styles.shortcut}>
            <span>Fill</span>
            <span className={styles.kbd}>G</span>
          </div>
          <div className={styles.shortcut}>
            <span>Eyedropper</span>
            <span className={styles.kbd}>I</span>
          </div>
          <div className={styles.shortcut}>
            <span>Undo</span>
            <span className={styles.kbd}>Ctrl + Z</span>
          </div>
          <div className={styles.shortcut}>
            <span>Redo</span>
            <span className={styles.kbd}>Ctrl + Shift + Z</span>
          </div>
        </div>
      </section>

      <div className={styles.footer}>
        <button
          type="button"
          className={styles.generateSoon}
          onClick={onMagic}
          title="AI generation is not available in this beta"
        >
          <Sparkles size={15} aria-hidden />
          <span className={styles.generateLabel}>Generate with AI</span>
          <span className={styles.soon}>Soon</span>
        </button>
      </div>
    </aside>
  )
}
