import { useState, type ReactNode } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Eraser,
  Hand,
  Maximize2,
  Minimize2,
  PaintBucket,
  Pencil,
  Pipette,
  Redo2,
  Undo2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import type { BrushKind } from '@/lib/professionalBrushes'
import type { ToolKind } from '@/lib/strokes'
import { formatBrushSizePx } from '@/lib/strokes'
import {
  BrushKindStrip,
  brushKindShortLabel,
} from '@/shell/components/BrushKindStrip'
import styles from './ImmersiveToolbar.module.css'

export type ImmersiveTool = ToolKind | 'pan'

type Props = {
  tool: ImmersiveTool
  canUndo: boolean
  canRedo: boolean
  brushSize: number
  brushKind?: BrushKind
  zoomPercent: number
  nativeFullscreen: boolean
  onTool: (tool: ImmersiveTool) => void
  onUndo: () => void
  onRedo: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onFitPage: () => void
  onFitWidth: () => void
  onHundred: () => void
  onCenter: () => void
  onOpenMaterials: () => void
  onOpenBrush: () => void
  onOpenModels: () => void
  onBrushKind?: (kind: BrushKind) => void
  onSave: () => void
  onExit: () => void
  saveLabel?: string
  /** Optional controlled minimize state (defaults to internal state). */
  minimized?: boolean
  onMinimizedChange?: (minimized: boolean) => void
}

export function ImmersiveToolbar({
  tool,
  canUndo,
  canRedo,
  brushSize,
  brushKind = 'tapered',
  zoomPercent,
  nativeFullscreen,
  onTool,
  onUndo,
  onRedo,
  onZoomIn,
  onZoomOut,
  onFitPage,
  onFitWidth,
  onHundred,
  onCenter,
  onOpenMaterials,
  onOpenBrush,
  onOpenModels,
  onBrushKind,
  onSave,
  onExit,
  saveLabel = 'Save',
  minimized: minimizedProp,
  onMinimizedChange,
}: Props) {
  const [minimizedInternal, setMinimizedInternal] = useState(false)
  const minimized = minimizedProp ?? minimizedInternal
  const setMinimized = (next: boolean) => {
    onMinimizedChange?.(next)
    if (minimizedProp === undefined) setMinimizedInternal(next)
  }

  const brushLabel = `${brushKindShortLabel(brushKind)} · ${formatBrushSizePx(brushSize)} px`

  if (minimized) {
    return (
      <div
        className={`${styles.bar} ${styles.barMinimized}`}
        role="toolbar"
        aria-label="Immersive drawing toolbar"
        data-testid="immersive-toolbar"
        data-minimized="true"
      >
        <div className={`${styles.row} ${styles.rowPrimary}`}>
          <div className={styles.cluster} role="group" aria-label="Drawing tools">
            <ToolBtn active={tool === 'draw'} label="Pencil" onClick={() => onTool('draw')}>
              <Pencil size={18} strokeWidth={1.75} />
            </ToolBtn>
            <ToolBtn active={tool === 'erase'} label="Eraser" onClick={() => onTool('erase')}>
              <Eraser size={18} strokeWidth={1.75} />
            </ToolBtn>
            <ToolBtn active={tool === 'fill'} label="Fill" onClick={() => onTool('fill')}>
              <PaintBucket size={18} strokeWidth={1.75} />
            </ToolBtn>
            <ToolBtn active={false} label="Undo" disabled={!canUndo} onClick={onUndo}>
              <Undo2 size={18} strokeWidth={1.75} />
            </ToolBtn>
            <ToolBtn active={false} label="Redo" disabled={!canRedo} onClick={onRedo}>
              <Redo2 size={18} strokeWidth={1.75} />
            </ToolBtn>
          </div>
          <div className={`${styles.cluster} ${styles.exitCluster}`} role="group" aria-label="Expand toolbar">
            <button
              type="button"
              className={styles.expandBtn}
              onClick={() => setMinimized(false)}
              aria-label="Maximize sketch toolbar"
              aria-expanded={false}
              data-testid="immersive-toolbar-maximize"
              title="Maximize"
            >
              <ChevronUp size={18} strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={styles.bar}
      role="toolbar"
      aria-label="Immersive drawing toolbar"
      data-testid="immersive-toolbar"
      data-minimized="false"
    >
      {onBrushKind && tool === 'draw' ? (
        <div className={`${styles.row} ${styles.rowKinds}`}>
          <BrushKindStrip
            compact
            brushKind={brushKind}
            onBrushKind={onBrushKind}
          />
        </div>
      ) : null}
      <div className={`${styles.row} ${styles.rowPrimary}`}>
        <div className={styles.cluster} role="group" aria-label="Drawing tools">
          <ToolBtn active={tool === 'draw'} label="Pencil" onClick={() => onTool('draw')}>
            <Pencil size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={tool === 'erase'} label="Eraser" onClick={() => onTool('erase')}>
            <Eraser size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={tool === 'fill'} label="Fill" onClick={() => onTool('fill')}>
            <PaintBucket size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={tool === 'eyedropper'} label="Eyedropper" onClick={() => onTool('eyedropper')}>
            <Pipette size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={tool === 'pan'} label="Hand pan" onClick={() => onTool('pan')}>
            <Hand size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={false} label="Undo" disabled={!canUndo} onClick={onUndo}>
            <Undo2 size={18} strokeWidth={1.75} />
          </ToolBtn>
          <ToolBtn active={false} label="Redo" disabled={!canRedo} onClick={onRedo}>
            <Redo2 size={18} strokeWidth={1.75} />
          </ToolBtn>
        </div>

        <div className={`${styles.cluster} ${styles.exitCluster}`} role="group" aria-label="Toolbar layout">
          <button
            type="button"
            className={styles.minimizeBtn}
            onClick={() => setMinimized(true)}
            aria-label="Minimize sketch toolbar"
            aria-expanded={true}
            data-testid="immersive-toolbar-minimize"
            title="Minimize"
          >
            <ChevronDown size={16} strokeWidth={2} />
            <span>Minimize</span>
          </button>
          <button
            type="button"
            className={styles.exitBtn}
            onClick={onExit}
            aria-label={nativeFullscreen ? 'Exit full screen drawing' : 'Exit immersive drawing'}
            data-testid="immersive-exit"
          >
            {nativeFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            <span>Exit</span>
          </button>
        </div>
      </div>

      <div className={`${styles.row} ${styles.rowSecondary}`}>
        <div className={styles.cluster} role="group" aria-label="Zoom">
          <ToolBtn active={false} label="Zoom out" onClick={onZoomOut}>
            <ZoomOut size={18} strokeWidth={1.75} />
          </ToolBtn>
          <span className={styles.zoomReadout} aria-live="polite">
            {zoomPercent}%
          </span>
          <ToolBtn active={false} label="Zoom in" onClick={onZoomIn}>
            <ZoomIn size={18} strokeWidth={1.75} />
          </ToolBtn>
          <button type="button" className={styles.textBtn} onClick={onFitPage}>
            Fit page
          </button>
          <button type="button" className={styles.textBtn} onClick={onFitWidth}>
            Fit width
          </button>
          <button type="button" className={styles.textBtn} onClick={onHundred}>
            100%
          </button>
          <button type="button" className={styles.textBtn} onClick={onCenter}>
            Center
          </button>
        </div>

        <div className={styles.cluster} role="group" aria-label="Studio actions">
          <button type="button" className={styles.textBtn} onClick={onOpenBrush} aria-label="Brush settings">
            {brushLabel}
          </button>
          <button type="button" className={styles.textBtn} onClick={onOpenMaterials}>
            Materials
          </button>
          <button type="button" className={styles.textBtn} onClick={onOpenModels}>
            Models
          </button>
          <button type="button" className={styles.textBtn} onClick={onSave}>
            {saveLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

function ToolBtn({
  active,
  label,
  disabled,
  onClick,
  children,
}: {
  active: boolean
  label: string
  disabled?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={active ? styles.btnActive : styles.btn}
      aria-label={label}
      aria-pressed={active}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
