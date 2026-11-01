import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MeasuredValue } from '@/services/techpacksApi'
import { MeasuredField } from './MeasuredField'

function mv(partial: Partial<MeasuredValue> = {}): MeasuredValue {
  return {
    value: null,
    unit: 'cm',
    source: 'empty',
    review_status: 'open',
    ...partial,
  }
}

afterEach(() => {
  cleanup()
})

describe('MeasuredField decimal buffer', () => {
  it('preserves trailing decimal separator while typing (desktop)', () => {
    const onChange = vi.fn()
    let current = mv({ value: null, source: 'empty' })
    onChange.mockImplementation((next: MeasuredValue) => {
      current = next
    })

    const { rerender } = render(
      <MeasuredField label="Height" value={current} onChange={onChange} />,
    )
    const input = screen.getByLabelText(/^Height$/i)
    expect(input).toHaveAttribute('inputMode', 'decimal')

    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '2' } })
    rerender(<MeasuredField label="Height" value={current} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '25' } })
    rerender(<MeasuredField label="Height" value={current} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '25.' } })

    expect(screen.getByLabelText(/^Height$/i)).toHaveValue('25.')
    // Incomplete trailing separator must not collapse via Number("25.") === 25 in the input.
    expect(screen.getByLabelText(/^Height$/i)).not.toHaveValue('25')

    fireEvent.change(screen.getByLabelText(/^Height$/i), { target: { value: '25.5' } })
    rerender(<MeasuredField label="Height" value={current} onChange={onChange} />)
    expect(current).toMatchObject({ value: 25.5, source: 'designer' })
    expect(screen.getByLabelText(/^Height$/i)).toHaveValue('25.5')
  })

  it('preserves buffer on compact/Android-style inputs and keeps inputMode decimal', () => {
    const onChange = vi.fn()
    let current = mv({ value: 40, source: 'ai', review_status: 'open' })
    onChange.mockImplementation((next: MeasuredValue) => {
      current = next
    })

    const { rerender } = render(
      <MeasuredField compact label="Waist" value={current} onChange={onChange} />,
    )
    const input = screen.getByLabelText(/^Waist$/i)
    expect(input).toHaveAttribute('inputMode', 'decimal')

    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '40.' } })
    expect(screen.getByLabelText(/^Waist$/i)).toHaveValue('40.')
    // Parent stays on prior complete value until a complete draft commits.
    expect(current.value).toBe(40)
    expect(current.source).toBe('ai')

    fireEvent.change(screen.getByLabelText(/^Waist$/i), { target: { value: '40.5' } })
    rerender(<MeasuredField compact label="Waist" value={current} onChange={onChange} />)
    expect(current).toMatchObject({ value: 40.5, source: 'designer', review_status: 'open' })
  })

  it('accepts locale comma decimals on commit', () => {
    const onChange = vi.fn()
    let current = mv()
    onChange.mockImplementation((next: MeasuredValue) => {
      current = next
    })
    const { rerender } = render(
      <MeasuredField label="Bust" value={current} onChange={onChange} />,
    )
    const input = screen.getByLabelText(/^Bust$/i)
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '88,5' } })
    rerender(<MeasuredField label="Bust" value={current} onChange={onChange} />)
    expect(current).toMatchObject({ value: 88.5, source: 'designer' })
  })

  it('clears to null + empty source and does not invent 0 for invalid blur', () => {
    const onChange = vi.fn()
    let current = mv({ value: 12, source: 'calculated', review_status: 'open' })
    onChange.mockImplementation((next: MeasuredValue) => {
      current = next
    })
    const { rerender } = render(
      <MeasuredField label="Hip" value={current} onChange={onChange} />,
    )
    const input = screen.getByLabelText(/^Hip$/i)
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '' } })
    rerender(<MeasuredField label="Hip" value={current} onChange={onChange} />)
    expect(current).toMatchObject({ value: null, source: 'empty', review_status: 'open' })

    fireEvent.focus(screen.getByLabelText(/^Hip$/i))
    fireEvent.change(screen.getByLabelText(/^Hip$/i), { target: { value: '.' } })
    fireEvent.blur(screen.getByLabelText(/^Hip$/i))
    // Invalid intermediate must not become 0; revert to last committed empty.
    expect(current.value).toBeNull()
    expect(current.source).toBe('empty')
    expect(screen.getByLabelText(/^Hip$/i)).toHaveValue('')
  })

  it('sets designer when editing calculated values without changing review_status', () => {
    const onChange = vi.fn()
    let current = mv({ value: 100, source: 'calculated', review_status: 'open' })
    onChange.mockImplementation((next: MeasuredValue) => {
      current = next
    })
    render(<MeasuredField label="Garment length" value={current} onChange={onChange} />)
    const input = screen.getByLabelText(/^Garment length$/i)
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '112' } })
    expect(current).toMatchObject({
      value: 112,
      source: 'designer',
      review_status: 'open',
    })
  })

  it('focus + blur without edits leaves AI provenance untouched', () => {
    const onChange = vi.fn()
    const current = mv({ value: 70, source: 'ai', review_status: 'open' })
    render(<MeasuredField label="Inseam" value={current} onChange={onChange} />)
    const input = screen.getByLabelText(/^Inseam$/i)
    fireEvent.focus(input)
    fireEvent.blur(input)
    expect(onChange).not.toHaveBeenCalled()
  })
})
