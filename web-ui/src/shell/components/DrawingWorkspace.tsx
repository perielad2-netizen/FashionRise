import { Maximize2, ScanSearch, Search } from 'lucide-react'
import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import { FloatingBrushPanel } from '@/shell/components/FloatingBrushPanel'
import type { Stroke, ToolKind } from '@/lib/strokes'
import styles from './DrawingWorkspace.module.css'

type Props = {
  strokes: Stroke[]
  tool: ToolKind
  brushColor: string
  brushSize: number
  brushOpacity: number
  referenceUrl: string | null
  referenceOpacity: number
  onStrokeComplete: (stroke: Stroke) => void
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  showFloatingBrush: boolean
}

export function DrawingWorkspace({
  strokes,
  tool,
  brushColor,
  brushSize,
  brushOpacity,
  referenceUrl,
  referenceOpacity,
  onStrokeComplete,
  onBrushSize,
  onOpacity,
  showFloatingBrush,
}: Props) {
  return (
    <div className={showFloatingBrush ? styles.wrapWithBrush : styles.wrap}>
      <div className={styles.canvasFrame}>
        <DrawingCanvas
          strokes={strokes}
          activeTool={tool}
          brushColor={brushColor}
          brushSize={brushSize}
          brushOpacity={brushOpacity}
          referenceUrl={referenceUrl}
          referenceOpacity={referenceOpacity}
          onStrokeComplete={onStrokeComplete}
          framed={false}
        />
        <div className={styles.zoom} aria-label="Zoom controls">
          <button type="button" className={styles.zoomBtn} disabled aria-label="Zoom unavailable">
            <Search size={14} />
          </button>
          <span>100%</span>
          <button type="button" className={styles.zoomBtn} disabled aria-label="Fit unavailable">
            <ScanSearch size={14} />
          </button>
          <button type="button" className={styles.zoomBtn} disabled aria-label="Fullscreen unavailable">
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
      {showFloatingBrush ? (
        <FloatingBrushPanel
          tool={tool}
          brushSize={brushSize}
          opacity={brushOpacity}
          onBrushSize={onBrushSize}
          onOpacity={onOpacity}
          hiddenOnNarrow
        />
      ) : null}
    </div>
  )
}
