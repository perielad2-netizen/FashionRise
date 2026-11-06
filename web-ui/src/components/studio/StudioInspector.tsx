import { UI_ASSETS } from '@/assets/uiAssets'
import { BRUSH_SIZES, INK_SWATCHES, type BrushSizeId } from '@/lib/strokes'
import styles from './StudioInspector.module.css'

type Props = {
  sizeId: BrushSizeId
  color: string
  dimmed: boolean
  studioNotice: string | null
  magicNotice: string | null
  onSize: (id: BrushSizeId) => void
  onColor: (color: string) => void
  onToggleDim: () => void
  onMagic: () => void
  onDismissStudioNotice: () => void
  onDismissMagic: () => void
}

export function StudioInspector({
  sizeId,
  color,
  dimmed,
  studioNotice,
  magicNotice,
  onSize,
  onColor,
  onToggleDim,
  onMagic,
  onDismissStudioNotice,
  onDismissMagic,
}: Props) {
  return (
    <aside className={styles.panel} aria-label="Studio controls">
      <div className={styles.titleRow}>
        <h2>Studio</h2>
        <span>Brush &amp; color</span>
      </div>

      <section className={styles.section}>
        <h3>Brush</h3>
        <div className={styles.sizes}>
          {(Object.keys(BRUSH_SIZES) as BrushSizeId[]).map((id) => (
            <button
              key={id}
              type="button"
              className={sizeId === id ? styles.sizeActive : styles.size}
              onClick={() => onSize(id)}
            >
              <span className={styles.dot} style={{ width: BRUSH_SIZES[id] + 6, height: BRUSH_SIZES[id] + 6 }} />
              <em>{labelFor(id)}</em>
            </button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h3>Color</h3>
        <div className={styles.swatches}>
          {INK_SWATCHES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={color === s.color ? styles.swatchActive : styles.swatch}
              style={{ background: s.color }}
              aria-label={s.label}
              title={s.label}
              onClick={() => onColor(s.color)}
            />
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h3>Reference</h3>
        <button
          type="button"
          className={dimmed ? styles.dimActive : styles.dim}
          onClick={onToggleDim}
        >
          <img
            src={UI_ASSETS.inspector.reference}
            alt=""
            width={20}
            height={20}
            draggable={false}
          />
          Dim reference
        </button>
      </section>

      <div className={styles.footer}>
        {studioNotice ? (
          <div className={styles.notice} role="alert">
            <p>{studioNotice}</p>
            <button type="button" onClick={onDismissStudioNotice}>
              Got it
            </button>
          </div>
        ) : null}
        {magicNotice ? (
          <div className={styles.notice} role="status">
            <p>{magicNotice}</p>
            <button type="button" onClick={onDismissMagic}>
              Got it
            </button>
          </div>
        ) : null}
        <button type="button" className={styles.magic} onClick={onMagic}>
          <img src={UI_ASSETS.inspector.magic} alt="" width={22} height={22} draggable={false} />
          Magic
        </button>
      </div>
    </aside>
  )
}

function labelFor(id: BrushSizeId): string {
  switch (id) {
    case 'thin':
      return 'Thin'
    case 'medium':
      return 'Med'
    case 'thick':
      return 'Thick'
    case 'bold':
      return 'Bold'
  }
}
