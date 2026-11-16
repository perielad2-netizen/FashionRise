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

  it('exposes mobile-safe size hint copy (V2-0027)', () => {
    render(<BrushSizeControl tool="draw" brushSize={3} opacity={1} onBrushSize={vi.fn()} />)
    expect(screen.getByTestId('brush-size-hint')).toHaveTextContent(/Drag the slider|Scroll wheel/)
  })

  it('renders a kind-aware tip preview (V2-0023)', () => {
    render(
      <BrushSizeControl
        tool="draw"
        brushSize={8}
        opacity={0.8}
        brushKind="airbrush"
        brushColor="#c2185b"
        onBrushSize={vi.fn()}
      />,
    )
    expect(screen.getByTestId('brush-tip-preview').className).toMatch(/tipAirbrush/)
  })

  it('paints the stroke strip with the brush color (readable size preview)', () => {
    render(
      <BrushSizeControl
        tool="draw"
        brushSize={12.5}
        opacity={0.75}
        tone="light"
        brushColor="#c9a227"
        onBrushSize={vi.fn()}
      />,
    )
    const stroke = screen.getByTestId('brush-stroke-preview')
    expect(stroke).toHaveStyle({ background: '#c9a227' })
    expect(stroke.style.height).toBe('12.5px')
  })

  it('adds a contrast edge for near-white brush colors on the light sheet', () => {
    render(
      <BrushSizeControl
        tool="draw"
        brushSize={26}
        opacity={1}
        tone="light"
        brushColor="#f8fafc"
        onBrushSize={vi.fn()}
      />,
    )
    expect(screen.getByTestId('brush-tip-preview').className).toMatch(/tipContrast/)
    expect(screen.getByTestId('brush-stroke-preview').className).toMatch(/strokeContrast/)
  })
})
