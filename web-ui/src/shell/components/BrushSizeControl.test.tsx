import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BrushSizeControl } from '@/shell/components/BrushSizeControl'

describe('BrushSizeControl', () => {
  it('syncs slider and numeric input to exact pixel sizes', () => {
    const onBrushSize = vi.fn()
    render(
      <BrushSizeControl tool="draw" brushSize={1.75} opacity={1} onBrushSize={onBrushSize} />,
    )
    const slider = screen.getByLabelText('Brush size')
    fireEvent.change(slider, { target: { value: '6.5' } })
    expect(onBrushSize).toHaveBeenCalledWith(6.5)

    const input = screen.getByLabelText('Brush size in pixels')
    fireEvent.change(input, { target: { value: '12.75' } })
    fireEvent.blur(input)
    expect(onBrushSize).toHaveBeenCalledWith(12.75)
  })

  it('nudges size with mouse wheel over the control', () => {
    const onBrushSize = vi.fn()
    render(
      <BrushSizeControl tool="erase" brushSize={2.5} opacity={1} onBrushSize={onBrushSize} />,
    )
    const root = screen.getByLabelText('Brush size control')
    fireEvent.wheel(root, { deltaY: -100 })
    expect(onBrushSize).toHaveBeenCalledWith(2.75)
    fireEvent.wheel(root, { deltaY: 100 })
    expect(onBrushSize).toHaveBeenCalledWith(2.25)
  })
})
