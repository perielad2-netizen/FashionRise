import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'

vi.mock('@/services/auth/authApi', () => ({
  deleteAccount: vi.fn(),
}))

vi.mock('@/services/starsShopApi', () => ({
  fetchStarsWallet: vi.fn(async () => ({
    ai_stars: 25,
    ai_stars_unlimited: false,
    ai_stars_magic_cost: 10,
    ai_stars_costs: { magic: 10, croquis: 10, pdf: 50, fabric: 5 },
  })),
  fetchStarPackages: vi.fn(async () => []),
  fetchStarCart: vi.fn(async () => ({
    id: 'c1',
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
    user: { id: 'u1', username: 'maya', ai_stars: 25, ai_stars_unlimited: false },
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

describe('FashionRiseAppShell overlay coordination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('closes account menu when navigation opens, and Escape closes overlays', () => {
    render(
      <FashionRiseAppShell username="maya" onLogout={vi.fn()}>
        <div>studio</div>
      </FashionRiseAppShell>,
    )

    fireEvent.click(screen.getByTestId('global-account-menu'))
    expect(screen.getByTestId('global-account-menu-panel')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('shell-nav-toggle'))
    expect(screen.queryByTestId('global-account-menu-panel')).toBeNull()
    expect(screen.getByTestId('shell-nav-scrim')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('global-account-menu'))
    expect(screen.getByTestId('global-account-menu-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('shell-nav-scrim')).toBeNull()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByTestId('global-account-menu-panel')).toBeNull()
  })

  it('shows Stars badge and My Stars & Billing entry', async () => {
    render(
      <FashionRiseAppShell username="maya" onLogout={vi.fn()}>
        <div>studio</div>
      </FashionRiseAppShell>,
    )

    expect(screen.getByTestId('global-stars-badge')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('global-account-menu'))
    fireEvent.click(screen.getByTestId('menu-stars-billing'))
    expect(await screen.findByTestId('stars-billing-panel')).toBeInTheDocument()
    expect(screen.getByTestId('stars-billing-balance')).toHaveTextContent(/25 Stars/i)
    expect(screen.getByText(/not listed here yet/i)).toBeInTheDocument()
  })
})
