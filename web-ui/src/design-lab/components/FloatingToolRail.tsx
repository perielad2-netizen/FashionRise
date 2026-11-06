import {
  Brush,
  Eraser,
  Layers,
  MousePointer2,
  PenLine,
  Pencil,
  Pipette,
  Ruler,
  Square,
  Type,
  Undo2,
} from 'lucide-react'
import styles from './FloatingToolRail.module.css'

const TOOLS = [
  { id: 'pencil', icon: Pencil, active: true, label: 'Pencil' },
  { id: 'eraser', icon: Eraser, active: false, label: 'Eraser' },
  { id: 'pen', icon: PenLine, active: false, label: 'Pen' },
  { id: 'brush', icon: Brush, active: false, label: 'Brush' },
  { id: 'eyedropper', icon: Pipette, active: false, label: 'Eyedropper' },
  { id: 'select', icon: MousePointer2, active: false, label: 'Select' },
  { id: 'shape', icon: Square, active: false, label: 'Shape' },
  { id: 'type', icon: Type, active: false, label: 'Type' },
  { id: 'ruler', icon: Ruler, active: false, label: 'Ruler' },
  { id: 'layers', icon: Layers, active: false, label: 'Layers' },
] as const

export function FloatingToolRail() {
  return (
    <div className={styles.rail} role="toolbar" aria-label="Prototype drawing tools">
      {TOOLS.map((tool, index) => {
        const Icon = tool.icon
        return (
          <span key={tool.id} style={{ display: 'contents' }}>
            {index === 5 ? <div className={styles.sep} aria-hidden /> : null}
            <button
              type="button"
              className={tool.active ? styles.btnActive : styles.btn}
              tabIndex={-1}
              aria-label={`${tool.label} (prototype)`}
              aria-pressed={tool.active}
              aria-disabled
              title={`${tool.label} — visual prototype`}
            >
              <Icon size={18} strokeWidth={1.75} />
            </button>
          </span>
        )
      })}
      <div className={styles.sep} aria-hidden />
      <button type="button" className={styles.btn} tabIndex={-1} aria-label="Undo (prototype)" aria-disabled>
        <Undo2 size={18} strokeWidth={1.75} />
      </button>
    </div>
  )
}
