import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PAPER_HEIGHT, PAPER_WIDTH } from '@/lib/paperBounds'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import { SettingsInspector } from './SettingsInspector'

describe('SettingsInspector canvas properties (V2-0021)', () => {
  it('labels size and background as fixed using real canvas constants', () => {
    render(<SettingsInspector dimmed={false} onToggleDim={vi.fn()} />)

    const section = screen.getByTestId('canvas-properties')
    expect(section).toBeInTheDocument()
    expect(screen.getByTestId('canvas-size-fixed')).toHaveTextContent(/Fixed/i)
    expect(screen.getByTestId('canvas-background-fixed')).toHaveTextContent(/Fixed/i)

    expect(screen.getByTestId('canvas-size-value')).toHaveTextContent(
      `Model ${DESIGN_WIDTH} × ${DESIGN_HEIGHT}`,
    )
    expect(screen.getByTestId('canvas-size-value')).toHaveTextContent(
      `extended paper ${PAPER_WIDTH} × ${PAPER_HEIGHT}`,
    )
    expect(screen.getByTestId('canvas-size-hint')).toHaveTextContent(/Resizing is not available/i)
    expect(screen.getByTestId('canvas-background-value')).toHaveTextContent(/Cream paper/i)
    expect(screen.getByTestId('canvas-background-hint')).toHaveTextContent(/cannot be changed/i)

    // No fake editors that imply unsupported resize / background pickers.
    expect(section.querySelector('select')).toBeNull()
    expect(section.querySelector('input[type="color"]')).toBeNull()
    expect(section.querySelector('input[type="number"]')).toBeNull()
  })

  it('keeps Dim reference interactive and clearly editable', () => {
    const onToggleDim = vi.fn()
    render(<SettingsInspector dimmed={false} onToggleDim={onToggleDim} />)

    expect(screen.getByTestId('canvas-dim-hint')).toHaveTextContent(/editable/i)
    const toggle = screen.getByTestId('canvas-dim-reference')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(toggle)
    expect(onToggleDim).toHaveBeenCalledTimes(1)
  })
})
