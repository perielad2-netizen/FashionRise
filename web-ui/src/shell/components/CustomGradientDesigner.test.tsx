import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { CustomGradientDesigner } from '@/shell/components/CustomGradientDesigner'

describe('CustomGradientDesigner', () => {
  it('applies custom colors and angle without mutating cancel state', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <CustomGradientDesigner open initial={null} onApply={onApply} onCancel={onCancel} />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Create gradient' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')

    fireEvent.click(within(dialog).getByRole('button', { name: /Color 1/i }))
    const colorDialog = screen.getByRole('dialog', { name: 'Choose color' })
    fireEvent.change(within(colorDialog).getByLabelText('Hex color'), {
      target: { value: '#FF0044' },
    })
    fireEvent.blur(within(colorDialog).getByLabelText('Hex color'))
    fireEvent.click(within(colorDialog).getByRole('button', { name: 'Apply' }))

    fireEvent.click(within(dialog).getByRole('button', { name: /Color 2/i }))
    const colorDialog2 = screen.getByRole('dialog', { name: 'Choose color' })
    fireEvent.change(within(colorDialog2).getByLabelText('Hex color'), {
      target: { value: '#00AABB' },
    })
    fireEvent.blur(within(colorDialog2).getByLabelText('Hex color'))
    fireEvent.click(within(colorDialog2).getByRole('button', { name: 'Apply' }))

    fireEvent.click(within(dialog).getByRole('button', { name: 'Diagonal' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Use gradient' }))

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'gradient',
        gradientId: 'custom',
        colors: ['#FF0044', '#00AABB'],
        angle: 135,
      }),
    )
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('Escape cancels the designer when no nested picker is open', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <CustomGradientDesigner open initial={null} onApply={onApply} onCancel={onCancel} />,
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onApply).not.toHaveBeenCalled()
  })

  it('first Escape closes only the nested color picker; second Escape closes designer', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <CustomGradientDesigner open initial={null} onApply={onApply} onCancel={onCancel} />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create gradient' })
    fireEvent.click(within(dialog).getByRole('button', { name: /Color 1/i }))
    expect(screen.getByRole('dialog', { name: 'Choose color' })).toBeTruthy()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Choose color' })).toBeNull()
    expect(screen.getByRole('dialog', { name: 'Create gradient' })).toBeTruthy()
    expect(onCancel).not.toHaveBeenCalled()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onApply).not.toHaveBeenCalled()
  })

  it('moves keyboard focus into the dialog on open and restores the trigger on close', () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'Create gradient'
    document.body.appendChild(trigger)
    trigger.focus()

    const onCancel = vi.fn()
    const { rerender } = render(
      <CustomGradientDesigner open initial={null} onApply={() => undefined} onCancel={onCancel} />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create gradient' })
    expect(dialog.contains(document.activeElement)).toBe(true)

    rerender(
      <CustomGradientDesigner
        open={false}
        initial={null}
        onApply={() => undefined}
        onCancel={onCancel}
      />,
    )
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it('keeps Tab focus cycling inside the designer while open', () => {
    render(
      <CustomGradientDesigner
        open
        initial={null}
        onApply={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create gradient' })
    const first = within(dialog).getByRole('button', { name: 'Close' })
    const last = within(dialog).getByRole('button', { name: 'Use gradient' })
    first.focus()
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
    last.focus()
    fireEvent.keyDown(window, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
  })

  it('Cancel does not apply; Apply preserves drafted angle/colors', () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <CustomGradientDesigner
        open
        initial={{
          kind: 'gradient',
          gradientId: 'custom',
          colors: ['#111111', '#EEEEEE'],
          angle: 45,
        }}
        onApply={onApply}
        onCancel={onCancel}
      />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Create gradient' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Horizontal' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalled()
    expect(onApply).not.toHaveBeenCalled()

    onCancel.mockClear()
    render(
      <CustomGradientDesigner
        open
        initial={{
          kind: 'gradient',
          gradientId: 'custom',
          colors: ['#111111', '#EEEEEE'],
          angle: 45,
        }}
        onApply={onApply}
        onCancel={onCancel}
      />,
    )
    const dialog2 = screen.getAllByRole('dialog', { name: 'Create gradient' }).at(-1)!
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Vertical' }))
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Use gradient' }))
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        gradientId: 'custom',
        colors: ['#111111', '#EEEEEE'],
        angle: 90,
      }),
    )
  })
})
