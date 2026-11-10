import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { FloatingToolRail } from '@/shell/components/FloatingToolRail'

describe('FloatingToolRail', () => {
  it('offers pencil, eraser, fill and eyedropper without placeholder tools', () => {
    const onTool = vi.fn()
    render(
      <FloatingToolRail
        tool="draw"
        canUndo
        canRedo
        onTool={onTool}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Fill' }))
    expect(onTool).toHaveBeenCalledWith('fill')
    fireEvent.click(screen.getByRole('button', { name: 'Eyedropper' }))
    expect(onTool).toHaveBeenCalledWith('eyedropper')
    expect(screen.queryByText(/coming/i)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Clear canvas' })).toBeNull()
  })

  it('exposes Clear canvas when onClear is provided', () => {
    const onClear = vi.fn()
    render(
      <FloatingToolRail
        tool="draw"
        canUndo
        canRedo
        onTool={vi.fn()}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        onClear={onClear}
        canClear
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Clear canvas' }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })
})
