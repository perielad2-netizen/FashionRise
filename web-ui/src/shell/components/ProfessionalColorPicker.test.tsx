import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ProfessionalColorPicker } from '@/shell/components/ProfessionalColorPicker'

describe('ProfessionalColorPicker', () => {
  it('applies the draft color and cancels without applying', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()

    const { rerender } = render(
      <ProfessionalColorPicker open initialColor="#112233" onApply={onApply} onCancel={onCancel} />,
    )

    expect(screen.getByRole('dialog', { name: 'Choose color' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Hex color'), { target: { value: '#FF0088' } })
    fireEvent.blur(screen.getByLabelText('Hex color'))
    expect(screen.getByLabelText('Red')).toHaveProperty('value', '255')
    expect(screen.getByLabelText('Green')).toHaveProperty('value', '0')
    expect(screen.getByLabelText('Blue')).toHaveProperty('value', '136')

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApply).toHaveBeenCalledWith('#FF0088')

    rerender(
      <ProfessionalColorPicker open initialColor="#112233" onApply={onApply} onCancel={onCancel} />,
    )
    fireEvent.change(screen.getByLabelText('Hex color'), { target: { value: '#00FF00' } })
    fireEvent.blur(screen.getByLabelText('Hex color'))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('closes on Escape without applying', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <ProfessionalColorPicker open initialColor="#ABCDEF" onApply={onApply} onCancel={onCancel} />,
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalled()
    expect(onApply).not.toHaveBeenCalled()
  })

  it('synchronizes RGB edits into HEX', () => {
    render(
      <ProfessionalColorPicker
        open
        initialColor="#000000"
        onApply={() => undefined}
        onCancel={() => undefined}
      />,
    )
    fireEvent.change(screen.getByLabelText('Red'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Green'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Blue'), { target: { value: '30' } })
    expect((screen.getByLabelText('Hex color') as HTMLInputElement).value).toBe('#0A141E')
  })
})
