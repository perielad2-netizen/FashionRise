/**
 * Nested ConfirmDialog must not dismiss a parent overlay on checkbox / body taps
 * (My Looks → Publish to Runway consent).
 */
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { ConfirmDialog } from './ConfirmDialog'

function NestedPublishFixture({ onParentClose }: { onParentClose: () => void }) {
  const [agreed, setAgreed] = useState(false)
  return (
    <div data-testid="parent-overlay" onClick={onParentClose}>
      <div onClick={(e) => e.stopPropagation()}>Look details</div>
      <ConfirmDialog
        title="Publish to Runway"
        scrollable
        onEscape={() => undefined}
        actions={[
          { label: 'Cancel', onClick: () => undefined, variant: 'ghost' },
          { label: 'Publish', onClick: () => undefined, disabled: !agreed },
        ]}
      >
        <p>Publishing makes this look visible.</p>
        <label>
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            data-testid="runway-share-consent"
          />
          <span>I have the rights to share this design.</span>
        </label>
      </ConfirmDialog>
    </div>
  )
}

describe('ConfirmDialog nested under dismissible overlay', () => {
  it('keeps the parent overlay open when the consent checkbox is toggled', () => {
    const onParentClose = vi.fn()
    render(<NestedPublishFixture onParentClose={onParentClose} />)

    const checkbox = screen.getByTestId('runway-share-consent')
    fireEvent.click(checkbox)

    expect(checkbox).toBeChecked()
    expect(onParentClose).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Publish' })).toBeEnabled()
    expect(screen.getByTestId('parent-overlay')).toBeInTheDocument()
  })

  it('stops pointerdown on the scrim from closing the parent overlay', () => {
    const onParentClose = vi.fn()
    render(<NestedPublishFixture onParentClose={onParentClose} />)

    fireEvent.pointerDown(screen.getByTestId('confirm-dialog-scrim'))
    fireEvent.click(screen.getByTestId('confirm-dialog-scrim'))

    expect(onParentClose).not.toHaveBeenCalled()
  })
})
