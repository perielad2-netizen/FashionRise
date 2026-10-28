import {
  Eraser,
  PaintBucket,
  Pencil,
  Pipette,
  Redo2,
  Undo2,
} from 'lucide-react'
import type { ToolKind } from '@/lib/strokes'
import styles from './FloatingToolRail.module.css'

type Props = {
  tool: ToolKind
  canUndo: boolean
  canRedo: boolean
  onTool: (tool: ToolKind) => void
  onUndo: () => void
  onRedo: () => void
  orientation?: 'vertical' | 'horizontal'
  /** Highlight when the next Fill will use a bounded Close-small-gaps seal. */
  closeSmallGapsArmed?: boolean
  onCloseSmallGaps?: () => void
  showCloseSmallGaps?: boolean
}

export function FloatingToolRail({
  tool,
  canUndo,
  canRedo,
  onTool,
  onUndo,
  onRedo,
  orientation = 'vertical',
  closeSmallGapsArmed = false,
  onCloseSmallGaps,
  showCloseSmallGaps = false,
}: Props) {
  return (
    <div
      className={orientation === 'horizontal' ? `${styles.rail} ${styles.railHorizontal}` : styles.rail}
      role="toolbar"
      aria-label="Drawing tools"
    >
      <button
        type="button"
        className={tool === 'draw' ? styles.btnActive : styles.btn}
        aria-label="Pencil"
        aria-pressed={tool === 'draw'}
        title="Pencil"
        onClick={() => onTool('draw')}
      >
        <Pencil size={18} strokeWidth={1.75} />
      </button>
      <button
        type="button"
        className={tool === 'erase' ? styles.btnActive : styles.btn}
        aria-label="Eraser"
        aria-pressed={tool === 'erase'}
        title="Eraser"
        onClick={() => onTool('erase')}
      >
        <Eraser size={18} strokeWidth={1.75} />
      </button>
      <button
        type="button"
        className={tool === 'fill' ? styles.btnActive : styles.btn}
        aria-label="Fill"
        aria-pressed={tool === 'fill'}
        title="Fill a closed outline"
        onClick={() => onTool('fill')}
      >
        <PaintBucket size={18} strokeWidth={1.75} />
      </button>
      {showCloseSmallGaps && onCloseSmallGaps ? (
        <button
          type="button"
          className={closeSmallGapsArmed ? styles.btnActive : styles.btn}
          aria-label="Close small gaps"
          aria-pressed={closeSmallGapsArmed}
          title="Close small gaps — seals nearby stroke joins for the next Fill only"
          data-testid="close-small-gaps"
          onClick={() => onCloseSmallGaps()}
        >
          <span className={styles.gapCloseLabel}>Gaps</span>
        </button>
      ) : null}
      <button
        type="button"
        className={tool === 'eyedropper' ? styles.btnActive : styles.btn}
        aria-label="Eyedropper"
        aria-pressed={tool === 'eyedropper'}
        title="Sample a color from your sketch"
        onClick={() => onTool('eyedropper')}
      >
        <Pipette size={18} strokeWidth={1.75} />
      </button>
      <div className={styles.sep} aria-hidden />
      <button
        type="button"
        className={styles.btn}
        aria-label="Undo"
        title="Undo"
        disabled={!canUndo}
        onClick={onUndo}
      >
        <Undo2 size={18} strokeWidth={1.75} />
      </button>
      <button
        type="button"
        className={styles.btn}
        aria-label="Redo"
        title="Redo"
        disabled={!canRedo}
        onClick={onRedo}
      >
        <Redo2 size={18} strokeWidth={1.75} />
      </button>
    </div>
  )
}
