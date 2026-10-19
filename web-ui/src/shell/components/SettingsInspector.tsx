import { Sparkles } from 'lucide-react'
import { BRUSH_SIZES, type BrushSizeId } from '@/lib/strokes'
import styles from './SettingsInspector.module.css'

type Props = {
  sizeId: BrushSizeId
  brushSize: number
  opacity: number
  dimmed: boolean
  toolLabel: string
  magicNotice: string | null
  studioNotice: string | null
  comingSoon: string | null
  onSize: (id: BrushSizeId) => void
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  onToggleDim: () => void
  onMagic: () => void
  onDismissMagic: () => void
  onDismissStudioNotice: () => void
  onDismissComingSoon: () => void
}

export function SettingsInspector({
  sizeId,
  brushSize,
  opacity,
  dimmed,
  toolLabel,
  magicNotice,
  studioNotice,
  comingSoon,
  onSize,
  onBrushSize,
  onOpacity,
  onToggleDim,
  onMagic,
  onDismissMagic,
  onDismissStudioNotice,
  onDismissComingSoon,
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
        <label className={styles.field}>
          Size
          <div className={styles.select} aria-disabled title="Fixed drawing space 768×1024">
            <span>768 × 1024</span>
            <span>▾</span>
          </div>
        </label>
        <div className={styles.row}>
          <span>Background</span>
          <span
            className={styles.inputLike}
            style={{ width: 36, minHeight: 28, padding: 0, background: '#f8f3ee' }}
            title="Cream paper"
          />
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
            <span>Undo</span>
            <span className={styles.kbd}>Ctrl + Z</span>
          </div>
          <div className={styles.shortcut}>
            <span>Redo</span>
            <span className={styles.kbd}>Ctrl + Shift + Z</span>
          </div>
        </div>
      </section>

      {studioNotice ? (
        <div className={styles.toast} role="alert">
          <p>{studioNotice}</p>
          <button type="button" onClick={onDismissStudioNotice}>
            Got it
          </button>
        </div>
      ) : null}
      {magicNotice ? (
        <div className={styles.toast} role="status">
          <p>{magicNotice}</p>
          <button type="button" onClick={onDismissMagic}>
            Got it
          </button>
        </div>
      ) : null}
      {comingSoon ? (
        <div className={styles.toast} role="status">
          <p>{comingSoon}</p>
          <button type="button" onClick={onDismissComingSoon}>
            Got it
          </button>
        </div>
      ) : null}

      <button type="button" className={styles.generate} onClick={onMagic}>
        <Sparkles size={16} />
        Generate with AI
      </button>
    </aside>
  )
}
