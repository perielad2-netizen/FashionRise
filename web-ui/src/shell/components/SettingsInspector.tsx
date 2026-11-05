import type { BrushEngineState, BrushKind } from '@/lib/professionalBrushes'
import type { ToolKind } from '@/lib/strokes'
import { BrushControls } from '@/shell/components/BrushControls'
import styles from './SettingsInspector.module.css'

type Props = {
  tool: ToolKind
  brushSize: number
  opacity: number
  brushEngine?: BrushEngineState
  dimmed: boolean
  toolLabel: string
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  onBrushKind?: (kind: BrushKind) => void
  onBrushEnginePatch?: (patch: Partial<BrushEngineState>) => void
  onToggleDim: () => void
}

export function SettingsInspector({
  tool,
  brushSize,
  opacity,
  brushEngine,
  dimmed,
  toolLabel,
  onBrushSize,
  onOpacity,
  onBrushKind,
  onBrushEnginePatch,
  onToggleDim,
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
        <div className={styles.row}>
          <span>Size</span>
          <strong>768 × 1024</strong> croquis · extended paper 1280 × 1536
        </div>
        <div className={styles.row}>
          <span>Background</span>
          <strong>Cream paper</strong>
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
        <BrushControls
          tool={tool === 'erase' ? 'erase' : 'draw'}
          brushSize={brushSize}
          opacity={opacity}
          brushEngine={brushEngine}
          variant="flat"
          onBrushSize={onBrushSize}
          onOpacity={onOpacity}
          onBrushKind={onBrushKind}
          onBrushEnginePatch={onBrushEnginePatch}
        />
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
            <span className={styles.kbd}>G</span>
          </div>
          <div className={styles.shortcut}>
            <span>Eyedropper</span>
            <span className={styles.kbd}>I</span>
          </div>
          <div className={styles.shortcut}>
            <span>Brush size</span>
            <span className={styles.kbd}>Alt + wheel</span>
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
    </aside>
  )
}
