import type { ReactNode } from 'react'
import { UI_ASSETS } from '@/assets/uiAssets'
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
        icon={<Glyph src={UI_ASSETS.tool.draw} />}
      />
      <ToolButton
        label="Erase"
        active={tool === 'erase'}
        onClick={() => onTool('erase')}
        icon={<Glyph src={UI_ASSETS.tool.erase} />}
      />
      <div className={styles.sep} aria-hidden />
      <ToolButton
        label="Undo"
        active={false}
        onClick={onUndo}
        disabled={!canUndo}
        icon={<Glyph src={UI_ASSETS.tool.undo} />}
      />
      <ToolButton
        label="Redo"
        active={false}
        onClick={onRedo}
        disabled={!canRedo}
        icon={<Glyph src={UI_ASSETS.tool.redo} />}
      />
      <ToolButton
        label="Clear"
        active={false}
        onClick={onClear}
        icon={<Glyph src={UI_ASSETS.tool.clear} />}
      />
    </div>
  )
}

function Glyph({ src }: { src: string }) {
  return <img src={src} alt="" className={styles.glyph} draggable={false} />
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
