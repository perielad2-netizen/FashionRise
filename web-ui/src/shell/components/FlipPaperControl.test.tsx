import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FlipPaperControl } from '@/shell/components/FlipPaperControl'
import { rearUnavailableReasonForModel } from '@/shell/rearUnavailableReason'

describe('FlipPaperControl', () => {
  it('shows FRONT label and Flip to Back tooltip on the front side', () => {
    render(
      <FlipPaperControl activeSide="front" rearAvailable onSideChange={() => undefined} />,
    )
    expect(screen.getByText('FRONT')).toBeInTheDocument()
    expect(screen.getByTestId('flip-paper-button')).toHaveAttribute('title', 'Flip to Back')
    expect(screen.getByTestId('flip-paper-button')).toHaveAttribute('aria-label', 'Flip to Back')
  })

  it('toggles to Back when flipped and available', async () => {
    const user = userEvent.setup()
    const onSideChange = vi.fn()
    render(
      <FlipPaperControl activeSide="front" rearAvailable onSideChange={onSideChange} />,
    )
    await user.click(screen.getByTestId('flip-paper-button'))
    expect(onSideChange).toHaveBeenCalledWith('back')
  })

  it('does not switch side when Back is unavailable; explains via notice callback', async () => {
    const user = userEvent.setup()
    const onSideChange = vi.fn()
    const onUnavailableFlip = vi.fn()
    const reason = rearUnavailableReasonForModel('female-atelier')
    render(
      <FlipPaperControl
        activeSide="front"
        rearAvailable={false}
        unavailableReason={reason}
        onSideChange={onSideChange}
        onUnavailableFlip={onUnavailableFlip}
      />,
    )
    await user.click(screen.getByTestId('flip-paper-button'))
    expect(onSideChange).not.toHaveBeenCalled()
    expect(onUnavailableFlip).toHaveBeenCalledWith(reason)
    expect(screen.getByTestId('flip-paper-button').getAttribute('title')).toContain('Atelier')
  })
})

describe('rearUnavailableReasonForModel', () => {
  it('names atelier specifically and keeps other unpublished models generic', () => {
    expect(rearUnavailableReasonForModel('female-atelier')).toMatch(/Atelier/)
    expect(rearUnavailableReasonForModel('custom')).toMatch(/library models/)
  })
})
