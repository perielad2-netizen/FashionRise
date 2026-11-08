import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SettingsInspector } from '@/shell/components/SettingsInspector'
import { CONTACT_EMAIL } from '@/lib/contact'

describe('SettingsInspector', () => {
  it('toggles dim reference from Settings', () => {
    const onToggleDim = vi.fn()
    render(<SettingsInspector dimmed={false} onToggleDim={onToggleDim} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dim reference off' }))
    expect(onToggleDim).toHaveBeenCalledTimes(1)
  })

  it('opens a useful Help tab with contact email', () => {
    render(<SettingsInspector dimmed={false} onToggleDim={() => undefined} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Help' }))
    expect(screen.getByTestId('settings-help')).toBeTruthy()
    expect(screen.getByText(/Studio basics/i)).toBeTruthy()
    expect(screen.getByRole('link', { name: CONTACT_EMAIL })).toHaveAttribute(
      'href',
      `mailto:${CONTACT_EMAIL}`,
    )
    expect(screen.queryByText('Dim reference')).toBeNull()
  })
})
