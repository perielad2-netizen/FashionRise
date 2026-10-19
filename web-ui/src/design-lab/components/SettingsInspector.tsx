import { Sparkles } from 'lucide-react'
import styles from './SettingsInspector.module.css'

export function SettingsInspector() {
  return (
    <aside className={styles.panel} aria-label="Settings inspector prototype">
      <div className={styles.tabs}>
        <button type="button" className={styles.tabActive} tabIndex={-1} aria-disabled>
          Settings
        </button>
        <button type="button" className={styles.tab} tabIndex={-1} aria-disabled>
          Help
        </button>
      </div>

      <section className={styles.section}>
        <h3>Canvas</h3>
        <label className={styles.field}>
          Size
          <div className={styles.select}>
            <span>1024 × 1536</span>
            <span>▾</span>
          </div>
        </label>
        <div className={styles.row}>
          <span>Background</span>
          <span
            className={styles.inputLike}
            style={{ width: 36, minHeight: 28, padding: 0, background: '#f8f3ee' }}
          />
        </div>
        <div className={styles.row}>
          <span>Grid</span>
          <button type="button" className={styles.toggle} tabIndex={-1} aria-disabled aria-label="Grid off" />
        </div>
      </section>

      <section className={styles.section}>
        <h3>Brush settings</h3>
        <div className={styles.row}>
          <span>Size</span>
          <strong>2 px</strong>
        </div>
        <input className={styles.slider} type="range" min={1} max={40} defaultValue={2} readOnly tabIndex={-1} />
        <div className={styles.row}>
          <span>Opacity</span>
          <strong>100%</strong>
        </div>
        <input className={styles.slider} type="range" min={0} max={100} defaultValue={100} readOnly tabIndex={-1} />
        <div className={styles.row}>
          <span>Pressure sensitivity</span>
          <button
            type="button"
            className={styles.toggleOn}
            tabIndex={-1}
            aria-disabled
            aria-label="Pressure on"
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
            <span className={styles.kbd}>F</span>
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

      <p className={styles.note}>
        Generate with AI is a visual prototype control. No paid AI request is made from this lab.
      </p>
      <button type="button" className={styles.generate} tabIndex={-1} aria-disabled>
        <Sparkles size={16} />
        Generate with AI
      </button>
    </aside>
  )
}
