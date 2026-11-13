import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  deleteAccount: vi.fn(async () => undefined),
}))

vi.mock('@/services/auth/authApi', () => ({
  deleteAccount: () => api.deleteAccount(),
}))

vi.mock('@/services/starsShopApi', () => ({
  fetchStarsWallet: vi.fn(async () => ({
    ai_stars: 10,
    ai_stars_unlimited: false,
    ai_stars_magic_cost: 10,
    ai_stars_costs: { magic: 10, croquis: 10, pdf: 50, fabric: 5 },
  })),
  fetchStarPackages: vi.fn(async () => []),
  fetchStarCart: vi.fn(async () => ({
    id: 'c',
    status: 'open',
    items: [],
    stars_total: 0,
    price_usd_cents_total: 0,
    checkout_enabled: false,
    checkout_note: null,
  })),
  formatUsdCents: (c: number) => `$${(c / 100).toFixed(2)}`,
  setStarCartItem: vi.fn(),
  clearStarCart: vi.fn(),
  checkoutStarCart: vi.fn(),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'peri', ai_stars: 10 },
    refreshUser: vi.fn(),
  }),
}))

vi.mock('@/services/native/iap', () => ({
  isNativeIosStarsShop: () => false,
  isNativeAndroidShell: () => false,
  fetchAppleIapStatus: vi.fn(),
  listStarsIapProducts: vi.fn(),
  purchaseStarsPack: vi.fn(),
  recoverPendingStarsPurchases: vi.fn(),
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
