import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SettingsInspector } from '@/shell/components/SettingsInspector'

describe('SettingsInspector', () => {
  it('toggles Dim reference', () => {
    const onToggleDim = vi.fn()
    render(
      <SettingsInspector
        sizeId="medium"
        brushSize={3.5}
        opacity={1}
        dimmed={false}
        toolLabel="Pencil"
        studioNotice={null}
        magicNotice={null}
        comingSoon={null}
        onSize={vi.fn()}
        onBrushSize={vi.fn()}
        onOpacity={vi.fn()}
        onToggleDim={onToggleDim}
        onMagic={vi.fn()}
        onDismissStudioNotice={vi.fn()}
        onDismissMagic={vi.fn()}
        onDismissComingSoon={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Dim reference off/i }))
    expect(onToggleDim).toHaveBeenCalled()
  })
})
