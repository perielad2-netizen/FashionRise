import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DrawingWorkspace } from '@/shell/components/DrawingWorkspace'
import { solidStyle } from '@/lib/fills'

vi.mock('@/components/studio/DrawingCanvas', () => ({
  DrawingCanvas: () => <div data-testid="drawing-canvas" />,
}))

const baseProps = {
  strokes: [],
  fills: [],
  tool: 'draw' as const,
  brushColor: '#1C1C1E',
  brushSize: 1.75,
  brushOpacity: 1,
  fillStyle: solidStyle('#1C1C1E'),
  referenceUrl: null,
  referenceOpacity: 0.35,
  onStrokeComplete: () => undefined,
  onFillComplete: () => undefined,
  onFillError: () => undefined,
  onEyedropperSample: () => undefined,
}

describe('DrawingWorkspace paper corner controls', () => {
  it('anchors Full Screen and Flip inside the paper frame (not stage chrome)', () => {
    render(
      <DrawingWorkspace
        {...baseProps}
        frontBackEnabled
        activeSide="front"
        rearAvailable
        onSideChange={() => undefined}
        onEnterFullscreen={() => undefined}
      />,
    )
    const paper = screen.getByTestId('paper-frame')
    expect(within(paper).getByTestId('paper-fullscreen-button')).toBeTruthy()
    expect(within(paper).getByTestId('flip-paper-control')).toBeTruthy()
    expect(within(paper).getByRole('button', { name: 'Enter full screen drawing' })).toBeTruthy()
    expect(within(paper).getByRole('button', { name: 'Flip to Back' })).toBeTruthy()
  })

  it('hides paper Full Screen in immersive mode (toolbar owns exit/fullscreen)', () => {
    render(
      <DrawingWorkspace
        {...baseProps}
        immersive
        frontBackEnabled
        activeSide="front"
        rearAvailable
        onSideChange={() => undefined}
        onEnterFullscreen={() => undefined}
      />,
    )
    expect(screen.queryByTestId('paper-fullscreen-button')).toBeNull()
    expect(screen.getByTestId('flip-paper-control')).toBeTruthy()
  })

  it('invokes enter-fullscreen and Front/Back flip handlers', async () => {
    const user = userEvent.setup()
    const onEnterFullscreen = vi.fn()
    const onSideChange = vi.fn()
    render(
      <DrawingWorkspace
        {...baseProps}
        frontBackEnabled
        activeSide="front"
        rearAvailable
        onSideChange={onSideChange}
        onEnterFullscreen={onEnterFullscreen}
      />,
    )
    await user.click(screen.getByTestId('paper-fullscreen-button'))
    expect(onEnterFullscreen).toHaveBeenCalledTimes(1)
    await user.click(screen.getByTestId('flip-paper-button'))
    expect(onSideChange).toHaveBeenCalledWith('back')
  })
})
