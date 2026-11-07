import { Expand } from 'lucide-react'
import { DrawingCanvas } from '@/components/studio/DrawingCanvas'
import type { FillOp, FillStyle } from '@/lib/fills'
import type { BrushEngineState } from '@/lib/professionalBrushes'
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
  brushEngine?: BrushEngineState
  fillStyle: FillStyle
  referenceUrl: string | null
  referenceOpacity: number
  onStrokeComplete: (stroke: Stroke) => void
  onFillComplete: (fill: FillOp) => void
  onFillError: (
    message: string,
    detail?: {
      reason: string
      gapHint?: { x: number; y: number }
      suggestCloseGaps?: boolean
    },
  ) => void
  fillCloseSmallGaps?: boolean
  onFillCloseSmallGapsConsumed?: () => void
  fillGapHint?: { x: number; y: number } | null
  onEyedropperSample: (color: string) => void
  onBrushSize?: (px: number) => void
  immersive?: boolean
  panTool?: boolean
  viewport?: ViewportState
  onViewportChange?: (next: ViewportState) => void
  /** Enter immersive/full-screen drawing from the paper corner (hidden while immersive). */
  onEnterFullscreen?: () => void
  /** WEB-V4J: paper-corner Front/Back flip (same model, paired croquis). */
  frontBackEnabled?: boolean
  activeSide?: StudioPaperSide
  rearAvailable?: boolean
  rearUnavailableReason?: string
  onSideChange?: (side: StudioPaperSide) => void
  onUnavailableFlip?: (reason: string) => void
  /**
   * When a workspace banner/notice is open on phone, lift Front/Fullscreen out of
   * the cream paper so they do not crowd the croquis head.
   */
  noticeOpen?: boolean
}

export function DrawingWorkspace({
  strokes,
  fills,
  tool,
  brushColor,
  brushSize,
  brushOpacity,
  brushEngine,
  fillStyle,
  referenceUrl,
  referenceOpacity,
  onStrokeComplete,
  onFillComplete,
  onFillError,
  fillCloseSmallGaps = false,
  onFillCloseSmallGapsConsumed,
  fillGapHint = null,
  onEyedropperSample,
  onBrushSize,
  immersive = false,
  panTool = false,
  viewport,
  onViewportChange,
  onEnterFullscreen,
  frontBackEnabled = false,
  activeSide = 'front',
  rearAvailable = false,
  rearUnavailableReason,
  onSideChange,
  onUnavailableFlip,
  noticeOpen = false,
}: Props) {
  const showFlip = Boolean(frontBackEnabled && rearAvailable && onSideChange)
  const showFullscreen = Boolean(!immersive && onEnterFullscreen)
  const showBarChrome = Boolean(!immersive && (showFlip || showFullscreen))

  const flipControl = showFlip ? (
    <FlipPaperControl
      compact={immersive}
      embedded={!immersive}
      activeSide={activeSide}
      rearAvailable={rearAvailable}
      unavailableReason={rearUnavailableReason}
      onSideChange={onSideChange!}
      onUnavailableFlip={onUnavailableFlip}
    />
  ) : null

  const fullscreenBtn = showFullscreen ? (
    <button
      type="button"
      className={styles.fullscreenCorner}
      aria-label="Enter full screen drawing"
      title="Full screen drawing — nearly the whole device, with zoom and pan"
      data-testid="paper-fullscreen-button"
      onClick={() => onEnterFullscreen?.()}
    >
      <Expand size={16} strokeWidth={1.85} aria-hidden="true" />
      <span className={styles.fullscreenLabel}>Full screen</span>
    </button>
  ) : null

  return (
    <div
      className={`${styles.wrap}${immersive ? ` ${styles.wrapImmersive}` : ''}${
        noticeOpen ? ` ${styles.wrapNotice}` : ''
      }`}
      data-studio-paper="true"
      data-immersive={immersive ? 'true' : 'false'}
      data-notice-open={noticeOpen ? 'true' : 'false'}
    >
      {showBarChrome ? (
        <div className={styles.paperChrome} data-testid="paper-chrome-bar">
          {fullscreenBtn}
          <span className={styles.paperChromeSpacer} aria-hidden="true" />
          {flipControl}
        </div>
      ) : null}
      <div
        className={`${styles.canvasFrame}${immersive ? ` ${styles.canvasFrameImmersive}` : ''}`}
        data-testid="paper-frame"
      >
        {immersive && showFlip ? (
          <div className={styles.paperChromeOverlay}>{flipControl}</div>
        ) : null}
        <DrawingCanvas
          strokes={strokes}
          fills={fills}
          activeTool={tool}
          brushColor={brushColor}
          brushSize={brushSize}
          brushOpacity={brushOpacity}
          brushEngine={brushEngine}
          fillStyle={fillStyle}
          referenceUrl={referenceUrl}
          referenceOpacity={referenceOpacity}
          onStrokeComplete={onStrokeComplete}
          onFillComplete={onFillComplete}
          onFillError={onFillError}
          fillCloseSmallGaps={fillCloseSmallGaps}
          onFillCloseSmallGapsConsumed={onFillCloseSmallGapsConsumed}
          fillGapHint={fillGapHint}
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
