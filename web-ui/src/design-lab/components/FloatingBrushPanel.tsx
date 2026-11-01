import styles from './FloatingBrushPanel.module.css'

export function FloatingBrushPanel() {
  return (
    <div className={styles.panel} aria-label="Brush settings prototype">
      <p className={styles.title}>Pencil</p>
      <div className={styles.preview} aria-hidden>
        <div className={styles.stroke} />
      </div>
      <div className={styles.row}>
        <span>Size</span>
        <strong>2 px</strong>
      </div>
      <input className={styles.slider} type="range" min={1} max={24} defaultValue={2} readOnly tabIndex={-1} />
      <div className={styles.row}>
        <span>Opacity</span>
        <strong>100%</strong>
      </div>
      <input className={styles.slider} type="range" min={0} max={100} defaultValue={100} readOnly tabIndex={-1} />
    </div>
  )
}
