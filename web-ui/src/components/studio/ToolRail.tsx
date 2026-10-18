import { Pencil, Eraser, Undo2, Redo2, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ToolKind } from '@/lib/strokes'
import styles from './ToolRail.module.css'

type Props = {
  tool: ToolKind
  canUndo: boolean
  canRedo: boolean
  onTool: (tool: ToolKind) => void
  onUndo: () => void
  onRedo: () => void
  onClear: () => void
  orientation?: 'vertical' | 'horizontal'
}

export function ToolRail({
  tool,
  canUndo,
  canRedo,
  onTool,
  onUndo,
  onRedo,
  onClear,
  orientation = 'vertical',
}: Props) {
  return (
    <div
      className={orientation === 'horizontal' ? styles.railHorizontal : styles.rail}
      role="toolbar"
      aria-label="Drawing tools"
    >
      <ToolButton
        label="Draw"
        active={tool === 'draw'}
        onClick={() => onTool('draw')}
        icon={<Pencil size={18} strokeWidth={1.75} />}
      />
      <ToolButton
        label="Erase"
        active={tool === 'erase'}
        onClick={() => onTool('erase')}
        icon={<Eraser size={18} strokeWidth={1.75} />}
      />
      <div className={styles.sep} aria-hidden />
      <ToolButton
        label="Undo"
        active={false}
        onClick={onUndo}
        disabled={!canUndo}
        icon={<Undo2 size={18} strokeWidth={1.75} />}
      />
      <ToolButton
        label="Redo"
        active={false}
        onClick={onRedo}
        disabled={!canRedo}
        icon={<Redo2 size={18} strokeWidth={1.75} />}
      />
      <ToolButton
        label="Clear"
        active={false}
        onClick={onClear}
        icon={<Trash2 size={18} strokeWidth={1.75} />}
      />
    </div>
  )
}

function ToolButton({
  label,
  active,
  onClick,
  icon,
  disabled,
}: {
  label: string
  active: boolean
  onClick: () => void
  icon: ReactNode
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      className={active ? styles.btnActive : styles.btn}
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      disabled={disabled}
    >
      {icon}
    </button>
  )
}
