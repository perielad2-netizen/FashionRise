import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StageSheet } from './StageSheet'

describe('StageSheet', () => {
  afterEach(() => {
    cleanup()
    document.body.style.overflow = ''
  })

  it('renders nothing when closed', () => {
    render(
      <StageSheet open={false} stepIndex={1} title="Understand" onClose={() => undefined}>
        <p>Hidden body</p>
      </StageSheet>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens a full-screen dialog with save and continue actions', () => {
    const onClose = vi.fn()
    const onSave = vi.fn()
    const onContinue = vi.fn()
    render(
      <StageSheet
        open
        stepIndex={2}
        title="Customize Each Piece"
        busy={false}
        onClose={onClose}
        onSave={onSave}
        onContinue={onContinue}
      >
        <label htmlFor="shell">Shell fabric</label>
        <input id="shell" />
      </StageSheet>,
    )
    expect(screen.getByRole('dialog', { name: /Customize Each Piece/i })).toBeInTheDocument()
    expect(screen.getByText(/Step 2 of 4/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }))
    expect(onSave).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }))
    expect(onContinue).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Close step form/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
