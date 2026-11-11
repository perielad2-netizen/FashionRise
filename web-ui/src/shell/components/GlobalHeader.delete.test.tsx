import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  deleteAccount: vi.fn(async () => undefined),
}))

vi.mock('@/services/auth/authApi', () => ({
  deleteAccount: () => api.deleteAccount(),
}))

import { GlobalHeader } from '@/shell/components/GlobalHeader'

describe('GlobalHeader delete account', () => {
  beforeEach(() => {
    api.deleteAccount.mockReset()
    api.deleteAccount.mockResolvedValue(undefined)
  })

  it('requires DELETE confirmation then deletes and signs out', async () => {
    const onLogout = vi.fn()
    render(<GlobalHeader username="peri" onLogout={onLogout} />)

    fireEvent.click(screen.getByRole('button', { name: /My Studio/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /Delete account/i }))

    const confirm = screen.getByLabelText(/Type DELETE to confirm/i)
    const submit = screen.getByRole('button', { name: /^Delete account$/i })
    expect(submit).toBeDisabled()

    fireEvent.change(confirm, { target: { value: 'DELETE' } })
    expect(submit).not.toBeDisabled()
    fireEvent.click(submit)

    await waitFor(() => expect(api.deleteAccount).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(onLogout).toHaveBeenCalledTimes(1))
  })
})
