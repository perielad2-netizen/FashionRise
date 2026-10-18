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
        icon={<Glyph name="fr_icon_draw" />}
      />
      <ToolButton
        label="Erase"
        active={tool === 'erase'}
        onClick={() => onTool('erase')}
        icon={<Glyph name="fr_icon_erase" />}
      />
      <div className={styles.sep} aria-hidden />
      <ToolButton
        label="Undo"
        active={false}
        onClick={onUndo}
        disabled={!canUndo}
        icon={<Glyph name="fr_icon_undo" />}
      />
      <ToolButton
        label="Redo"
        active={false}
        onClick={onRedo}
        disabled={!canRedo}
        icon={<Glyph name="fr_icon_redo" />}
      />
      <ToolButton
        label="Clear"
        active={false}
        onClick={onClear}
        icon={<Glyph name="fr_icon_clear" />}
      />
    </div>
  )
}

function Glyph({ name }: { name: string }) {
  return <img src={`/assets/ui/icons/${name}.png`} alt="" className={styles.glyph} draggable={false} />
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
