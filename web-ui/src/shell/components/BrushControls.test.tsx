import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { BrushEngineState } from '@/lib/professionalBrushes'
import { BrushControls } from './BrushControls'

const engine: BrushEngineState = {
  brushKind: 'tapered',
  logicalLayer: 'ink',
  blendMode: 'source-over',
  flow: 0.7,
  softness: 0.2,
  textureIntensity: 0,
  garmentMask: false,
}

describe('BrushControls V2-0026 explainers', () => {
  it('shows touch-safe opacity and layer hints without hover', () => {
    render(
      <BrushControls
        tool="draw"
        brushSize={2}
        opacity={0.85}
        brushEngine={engine}
        onBrushSize={vi.fn()}
        onOpacity={vi.fn()}
        onBrushEnginePatch={vi.fn()}
      />,
    )

    expect(screen.getByTestId('brush-opacity-hint')).toHaveTextContent(/see-through/i)
    expect(screen.getByTestId('brush-layer-hint')).toHaveTextContent(/separate stacks/i)
  })

  it('exposes advanced setting explainers that match real controls', () => {
    render(
      <BrushControls
        tool="draw"
        brushSize={2}
        opacity={0.85}
        brushEngine={engine}
        onBrushSize={vi.fn()}
        onOpacity={vi.fn()}
        onBrushEnginePatch={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTestId('brush-advanced-toggle'))
    expect(screen.getByTestId('brush-advanced-body')).toBeInTheDocument()
    expect(screen.getByTestId('brush-advanced-intro')).toHaveTextContent(/do not rewrite/i)
    expect(screen.getByTestId('brush-flow-hint')).toHaveTextContent(/each stamp/i)
    expect(screen.getByTestId('brush-softness-hint')).toHaveTextContent(
      /Charcoal and Airbrush only/i,
    )
    expect(screen.getByTestId('brush-texture-hint')).toHaveTextContent(/Charcoal only/i)
    expect(screen.getByTestId('brush-blend-hint')).toHaveTextContent(/mix with paint/i)
  })
})
