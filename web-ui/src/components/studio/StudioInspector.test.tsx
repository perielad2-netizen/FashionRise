import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StudioInspector } from '@/components/studio/StudioInspector'

describe('StudioInspector', () => {
  it('toggles Dim reference', () => {
    const onToggleDim = vi.fn()
    render(
      <StudioInspector
        sizeId="medium"
        color="#1C1C1E"
        dimmed={false}
        magicNotice={null}
        onSize={vi.fn()}
        onColor={vi.fn()}
        onToggleDim={onToggleDim}
        onMagic={vi.fn()}
        onDismissMagic={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Dim reference/i }))
    expect(onToggleDim).toHaveBeenCalled()
  })
})
