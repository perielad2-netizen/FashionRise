import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import type { FillOp, FillStyle } from '@/lib/fills'
import type { Stroke, ToolKind } from '@/lib/strokes'
import styles from './DrawingWorkspace.module.css'

type Props = {
  strokes: Stroke[]
  fills: FillOp[]
  tool: ToolKind
  brushColor: string
  brushSize: number
  brushOpacity: number
  fillStyle: FillStyle
  referenceUrl: string | null
  referenceOpacity: number
  onStrokeComplete: (stroke: Stroke) => void
  onFillComplete: (fill: FillOp) => void
  onFillError: (message: string) => void
  onEyedropperSample: (color: string) => void
  onBrushSize?: (px: number) => void
}

export function DrawingWorkspace({
  strokes,
  fills,
  tool,
  brushColor,
  brushSize,
  brushOpacity,
  fillStyle,
  referenceUrl,
  referenceOpacity,
  onStrokeComplete,
  onFillComplete,
  onFillError,
  onEyedropperSample,
  onBrushSize,
}: Props) {
  return (
    <div className={styles.wrap} data-studio-paper="true">
      <div className={styles.canvasFrame} data-testid="paper-frame">
        <DrawingCanvas
          strokes={strokes}
          fills={fills}
          activeTool={tool}
          brushColor={brushColor}
          brushSize={brushSize}
          brushOpacity={brushOpacity}
          fillStyle={fillStyle}
          referenceUrl={referenceUrl}
          referenceOpacity={referenceOpacity}
          onStrokeComplete={onStrokeComplete}
          onFillComplete={onFillComplete}
          onFillError={onFillError}
          onEyedropperSample={onEyedropperSample}
          onBrushSize={onBrushSize}
          framed={false}
        />
      </div>
    </div>
  )
}
