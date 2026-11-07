import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AiSpendConfirmDialog } from '@/shell/components/AiSpendConfirmDialog'

describe('AiSpendConfirmDialog', () => {
  it('approves when the wallet can cover the cost', () => {
    const onApproved = vi.fn()
    const onOpenShop = vi.fn()
    render(
      <AiSpendConfirmDialog
        open
        feature="magic"
        cost={10}
        balance={20}
        unlimited={false}
        onCancel={vi.fn()}
        onApproved={onApproved}
        onOpenShop={onOpenShop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Approve −10/i }))
    expect(onApproved).toHaveBeenCalledTimes(1)
    expect(onOpenShop).not.toHaveBeenCalled()
  })

  it('shows insufficient Stars and Get Stars when Approve cannot cover cost', () => {
    const onApproved = vi.fn()
    const onOpenShop = vi.fn()
    const onCancel = vi.fn()
    render(
      <AiSpendConfirmDialog
        open
        feature="pdf"
        cost={50}
        balance={5}
        unlimited={false}
        onCancel={onCancel}
        onApproved={onApproved}
        onOpenShop={onOpenShop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Approve$/i }))
    expect(onApproved).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: /Not enough Stars/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Get Stars/i }))
    expect(onOpenShop).toHaveBeenCalledTimes(1)
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
