import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ImmersiveToolbar } from '@/shell/components/ImmersiveToolbar'

const baseProps = {
  tool: 'draw' as const,
  canUndo: true,
  canRedo: false,
  brushSize: 1.75,
  zoomPercent: 125,
  nativeFullscreen: false,
  onTool: vi.fn(),
  onUndo: vi.fn(),
  onRedo: vi.fn(),
  onZoomIn: vi.fn(),
  onZoomOut: vi.fn(),
  onFitPage: vi.fn(),
  onFitWidth: vi.fn(),
  onHundred: vi.fn(),
  onCenter: vi.fn(),
  onOpenMaterials: vi.fn(),
  onOpenBrush: vi.fn(),
  onOpenModels: vi.fn(),
  onSave: vi.fn(),
  onExit: vi.fn(),
}

describe('ImmersiveToolbar', () => {
  it('exposes accessible tool controls and exit', () => {
    const onTool = vi.fn()
    const onExit = vi.fn()
    const onFitWidth = vi.fn()
    render(
      <ImmersiveToolbar
        {...baseProps}
        onTool={onTool}
        onFitWidth={onFitWidth}
        onExit={onExit}
      />,
    )

    expect(screen.getByRole('toolbar', { name: 'Immersive drawing toolbar' })).toBeTruthy()
    expect(screen.getByText('125%')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Export PNG/i })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hand pan' }))
    expect(onTool).toHaveBeenCalledWith('pan')
    fireEvent.click(screen.getByRole('button', { name: 'Fit width' }))
    expect(onFitWidth).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Exit immersive drawing' }))
    expect(onExit).toHaveBeenCalled()
  })

  it('minimizes to pencil, eraser, fill, undo, redo only', () => {
    const onTool = vi.fn()
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    render(
      <ImmersiveToolbar
        {...baseProps}
        canRedo
        onTool={onTool}
        onUndo={onUndo}
        onRedo={onRedo}
      />,
    )

    fireEvent.click(screen.getByTestId('immersive-toolbar-minimize'))
    const bar = screen.getByTestId('immersive-toolbar')
    expect(bar.getAttribute('data-minimized')).toBe('true')

    expect(screen.getByRole('button', { name: 'Pencil' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Eraser' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Fill' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Undo' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Redo' })).toBeTruthy()
    expect(screen.getByTestId('immersive-toolbar-maximize')).toBeTruthy()

    expect(screen.queryByRole('button', { name: 'Hand pan' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Eyedropper' })).toBeNull()
    expect(screen.queryByTestId('immersive-exit')).toBeNull()
    expect(screen.queryByText('125%')).toBeNull()
    expect(screen.queryByText('Materials')).toBeNull()
    expect(screen.queryByText('Models')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Fill' }))
    expect(onTool).toHaveBeenCalledWith('fill')
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(onUndo).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Redo' }))
    expect(onRedo).toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('immersive-toolbar-maximize'))
    expect(screen.getByTestId('immersive-toolbar').getAttribute('data-minimized')).toBe('false')
    expect(screen.getByTestId('immersive-exit')).toBeTruthy()
    expect(screen.getByText('125%')).toBeTruthy()
  })
})
