import { useState, type ReactNode } from 'react'
import {
  BookmarkPlus,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Hand,
  Maximize2,
  Minimize2,
  Palette,
  Redo2,
  Scan,
  Trash2,
  Undo2,
  Users,
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
import {
  EraserToolIcon,
  EyedropperToolIcon,
  FillToolIcon,
  PenToolIcon,
} from '@/shell/components/StudioToolIcons'
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
  /** Clear ink/fills — trash icon on the tools row (no More menu duplicate). */
  onClear: () => void
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
  onClear,
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
        {/* Row 1: drawing tools including Clear canvas */}
        <div className={`${styles.row} ${styles.rowPrimary}`}>
          <div className={styles.cluster} role="group" aria-label="Drawing tools">
            <ToolBtn active={tool === 'draw'} label="Pencil" onClick={() => onTool('draw')}>
              <PenToolIcon size={20} glow={tool === 'draw'} />
            </ToolBtn>
            <ToolBtn active={tool === 'erase'} label="Eraser" onClick={() => onTool('erase')}>
              <EraserToolIcon size={20} glow={tool === 'erase'} />
            </ToolBtn>
            <ToolBtn active={tool === 'fill'} label="Fill" onClick={() => onTool('fill')}>
              <FillToolIcon size={20} glow={tool === 'fill'} />
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
            <ToolBtn active={false} label="Clear canvas" onClick={onClear}>
              <Trash2 size={18} strokeWidth={1.75} />
            </ToolBtn>
          </div>
        </div>
        {/* Row 2: maximize + exit only */}
        <div className={`${styles.row} ${styles.rowMinimizedChrome}`}>
          <div className={`${styles.cluster} ${styles.exitCluster}`} role="group" aria-label="Expand toolbar">
            <button
              type="button"
              className={styles.expandBtn}
              onClick={() => setMinimized(false)}
              aria-label="Maximize sketch toolbar"
              aria-expanded={false}
              data-testid="immersive-toolbar-maximize"
              title="Maximize toolbar"
            >
              <ChevronUp size={18} strokeWidth={2} aria-hidden />
              <span className={styles.btnText}>Max</span>
            </button>
            <button
              type="button"
              className={styles.exitBtn}
              onClick={onExit}
              aria-label={nativeFullscreen ? 'Exit full screen drawing' : 'Exit immersive drawing'}
              data-testid="immersive-exit"
            >
              {nativeFullscreen ? <Minimize2 size={16} aria-hidden /> : <Maximize2 size={16} aria-hidden />}
              <span>Exit</span>
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
          <BrushKindStrip compact brushKind={brushKind} onBrushKind={onBrushKind} />
        </div>
      ) : null}
      <div className={`${styles.row} ${styles.rowPrimary}`}>
        <div className={styles.cluster} role="group" aria-label="Drawing tools">
          <ToolBtn active={tool === 'draw'} label="Pencil" onClick={() => onTool('draw')}>
            <PenToolIcon size={20} glow={tool === 'draw'} />
          </ToolBtn>
          <ToolBtn active={tool === 'erase'} label="Eraser" onClick={() => onTool('erase')}>
            <EraserToolIcon size={20} glow={tool === 'erase'} />
          </ToolBtn>
          <ToolBtn active={tool === 'fill'} label="Fill" onClick={() => onTool('fill')}>
            <FillToolIcon size={20} glow={tool === 'fill'} />
          </ToolBtn>
          <ToolBtn active={tool === 'eyedropper'} label="Eyedropper" onClick={() => onTool('eyedropper')}>
            <EyedropperToolIcon size={20} glow={tool === 'eyedropper'} />
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
          <ToolBtn active={false} label="Clear canvas" onClick={onClear}>
            <Trash2 size={18} strokeWidth={1.75} />
          </ToolBtn>
        </div>
      </div>

      {/* Single nowrap band: zoom · fit · Min/Exit (must not wrap under each other). */}
      <div className={`${styles.row} ${styles.rowView}`} data-testid="immersive-view-dock">
        <div className={styles.viewStrip} role="group" aria-label="View and exit">
          <div className={styles.zoomTrack} role="group" aria-label="Zoom">
            <ToolBtn active={false} label="Zoom out" onClick={onZoomOut}>
              <ZoomOut size={16} strokeWidth={1.75} />
            </ToolBtn>
            <span className={styles.zoomReadout} aria-live="polite">
              {zoomPercent}%
            </span>
            <ToolBtn active={false} label="Zoom in" onClick={onZoomIn}>
              <ZoomIn size={16} strokeWidth={1.75} />
            </ToolBtn>
          </div>
          <span className={styles.viewDivider} aria-hidden />
          <button type="button" className={styles.chip} onClick={onFitPage} aria-label="Fit page">
            <Scan size={14} strokeWidth={2} aria-hidden />
            <span className={styles.chipLabel}>Page</span>
          </button>
          <button type="button" className={styles.chip} onClick={onFitWidth} aria-label="Fit width">
            <Maximize2 size={14} strokeWidth={2} aria-hidden />
            <span className={styles.chipLabel}>Width</span>
          </button>
          <button type="button" className={styles.chip} onClick={onHundred} aria-label="100%">
            <span className={styles.chipMono}>100%</span>
          </button>
          <button type="button" className={styles.chip} onClick={onCenter} aria-label="Center">
            <Crosshair size={14} strokeWidth={2} aria-hidden />
            <span className={styles.chipLabel}>Center</span>
          </button>
          <span className={styles.viewDivider} aria-hidden />
          <button
            type="button"
            className={styles.minimizeBtn}
            onClick={() => setMinimized(true)}
            aria-label="Minimize sketch toolbar"
            aria-expanded={true}
            data-testid="immersive-toolbar-minimize"
            title="Minimize toolbar — keep pencil, eraser, fill, hand, undo, redo, clear"
          >
            <ChevronDown size={18} strokeWidth={2.25} aria-hidden />
          </button>
          <button
            type="button"
            className={styles.exitBtn}
            onClick={onExit}
            aria-label={nativeFullscreen ? 'Exit full screen drawing' : 'Exit immersive drawing'}
            data-testid="immersive-exit"
          >
            {nativeFullscreen ? <Minimize2 size={15} aria-hidden /> : <Maximize2 size={15} aria-hidden />}
            <span>Exit</span>
          </button>
        </div>
      </div>

      {/* Action dock — Canva / Posh style icon+label tiles. */}
      <div className={`${styles.row} ${styles.rowActions}`} data-testid="immersive-action-dock">
        <div className={styles.actionTrack} role="group" aria-label="Studio actions">
          <button
            type="button"
            className={styles.actionChip}
            onClick={onOpenBrush}
            aria-label="Brush settings"
          >
            <span className={styles.actionIcon} aria-hidden>
              <PenToolIcon size={16} />
            </span>
            <span className={styles.actionLabel}>{brushLabel}</span>
          </button>
          <button type="button" className={styles.actionChip} onClick={onOpenMaterials}>
            <span className={styles.actionIcon} aria-hidden>
              <Palette size={16} strokeWidth={2} />
            </span>
            <span className={styles.actionLabel}>Materials</span>
          </button>
          <button type="button" className={styles.actionChip} onClick={onOpenModels}>
            <span className={styles.actionIcon} aria-hidden>
              <Users size={16} strokeWidth={2} />
            </span>
            <span className={styles.actionLabel}>Models</span>
          </button>
          <button
            type="button"
            className={`${styles.actionChip} ${styles.actionChipPrimary}`}
            onClick={onSave}
          >
            <span className={styles.actionIcon} aria-hidden>
              <BookmarkPlus size={16} strokeWidth={2} />
            </span>
            <span className={styles.actionLabel}>{saveLabel}</span>
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
