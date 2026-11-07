import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SettingsInspector } from '@/shell/components/SettingsInspector'

describe('SettingsInspector', () => {
  it('toggles Dim reference and has no brush controls', () => {
    const onToggleDim = vi.fn()
    render(<SettingsInspector dimmed={false} onToggleDim={onToggleDim} />)

    expect(screen.queryByText('Brush settings')).toBeNull()
    expect(screen.queryByRole('slider', { name: 'Brush size' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Dim reference off/i }))
    expect(onToggleDim).toHaveBeenCalled()
  })
})
