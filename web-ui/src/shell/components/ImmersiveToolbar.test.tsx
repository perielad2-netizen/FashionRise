import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ImmersiveToolbar } from '@/shell/components/ImmersiveToolbar'

describe('ImmersiveToolbar', () => {
  it('exposes accessible tool controls and exit', () => {
    const onTool = vi.fn()
    const onExit = vi.fn()
    const onFitWidth = vi.fn()
    render(
      <ImmersiveToolbar
        tool="draw"
        canUndo
        canRedo={false}
        brushSize={1.75}
        zoomPercent={125}
        nativeFullscreen={false}
        onTool={onTool}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        onFitPage={vi.fn()}
        onFitWidth={onFitWidth}
        onHundred={vi.fn()}
        onCenter={vi.fn()}
        onOpenMaterials={vi.fn()}
        onOpenBrush={vi.fn()}
        onOpenModels={vi.fn()}
        onSave={vi.fn()}
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
})
