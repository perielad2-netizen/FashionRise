import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import type { FillOp, FillStyle } from '@/lib/fills'
import type { Stroke, ToolKind } from '@/lib/strokes'
import type { StudioPaperSide } from '@/lib/studioSideArtwork'
import type { ViewportState } from '@/lib/viewportTransform'
import { FlipPaperControl } from '@/shell/components/FlipPaperControl'
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
  immersive?: boolean
  panTool?: boolean
  viewport?: ViewportState
  onViewportChange?: (next: ViewportState) => void
  /** WEB-V4J: paper-corner Front/Back flip (same model, paired croquis). */
  frontBackEnabled?: boolean
  activeSide?: StudioPaperSide
  rearAvailable?: boolean
  rearUnavailableReason?: string
  onSideChange?: (side: StudioPaperSide) => void
  onUnavailableFlip?: (reason: string) => void
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
  immersive = false,
  panTool = false,
  viewport,
  onViewportChange,
  frontBackEnabled = false,
  activeSide = 'front',
  rearAvailable = false,
  rearUnavailableReason,
  onSideChange,
  onUnavailableFlip,
}: Props) {
  return (
    <div
      className={`${styles.wrap}${immersive ? ` ${styles.wrapImmersive}` : ''}`}
      data-studio-paper="true"
      data-immersive={immersive ? 'true' : 'false'}
    >
      <div
        className={`${styles.canvasFrame}${immersive ? ` ${styles.canvasFrameImmersive}` : ''}`}
        data-testid="paper-frame"
      >
        {frontBackEnabled && onSideChange ? (
          <FlipPaperControl
            compact={immersive}
            activeSide={activeSide}
            rearAvailable={rearAvailable}
            unavailableReason={rearUnavailableReason}
            onSideChange={onSideChange}
            onUnavailableFlip={onUnavailableFlip}
          />
        ) : null}
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
          immersive={immersive}
          panTool={panTool}
          viewport={viewport}
          onViewportChange={onViewportChange}
        />
      </div>
    </div>
  )
}
