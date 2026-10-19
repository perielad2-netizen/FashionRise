import {
  Brush,
  Eraser,
  Layers,
  MousePointer2,
  PenLine,
  Pencil,
  Pipette,
  Redo2,
  Ruler,
  Square,
  Type,
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
}

const FUTURE = [
  { id: 'pen', icon: PenLine, label: 'Pen' },
  { id: 'brush', icon: Brush, label: 'Brush' },
  { id: 'eyedropper', icon: Pipette, label: 'Eyedropper' },
  { id: 'select', icon: MousePointer2, label: 'Select' },
  { id: 'shape', icon: Square, label: 'Shape' },
  { id: 'type', icon: Type, label: 'Type' },
  { id: 'ruler', icon: Ruler, label: 'Ruler' },
  { id: 'layers', icon: Layers, label: 'Layers' },
] as const

export function FloatingToolRail({
  tool,
  canUndo,
  canRedo,
  onTool,
  onUndo,
  onRedo,
  orientation = 'vertical',
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
      <div className={styles.sep} aria-hidden />
      {FUTURE.map((item) => {
        const Icon = item.icon
        return (
          <button
            key={item.id}
            type="button"
            className={styles.btn}
            aria-label={`${item.label} (coming later)`}
            title={`${item.label} — coming later`}
            disabled
            aria-disabled
          >
            <Icon size={18} strokeWidth={1.75} />
          </button>
        )
      })}
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
