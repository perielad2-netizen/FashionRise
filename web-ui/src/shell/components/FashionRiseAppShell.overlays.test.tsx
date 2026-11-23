import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import shellCss from '@/shell/components/FashionRiseAppShell.module.css?raw'

vi.mock('@/shell/components/WeeklyAwardClaimDialog', () => ({
  WeeklyAwardClaimDialog: () => null,
}))
import magicCss from '@/shell/components/MagicLookPanel.module.css?raw'
import myLooksCss from '@/shell/components/MyLooksScreen.module.css?raw'

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

vi.mock('@/services/profilesApi', () => ({
  getMyProfile: vi.fn(async () => ({
    id: 'p1',
    user_id: 'u1',
    display_name: 'Maya',
    bio: null,
    avatar_url: null,
    cover_url: null,
    style_tags: [],
    published_count: 0,
    followers_count: 0,
    likes_received_count: 0,
    rating_average: null,
    rating_count: 0,
    reputation_score: 0,
    reputation_tier: 'new',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  })),
  profileAvatarSrc: () => null,
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

  it('keeps the mobile nav drawer above Magic + My Looks overlays', () => {
    expect(magicCss).toMatch(/\.overlay\s*\{[\s\S]*?z-index:\s*40/)
    expect(myLooksCss).toMatch(/\.overlay\s*\{[\s\S]*?z-index:\s*80/)
    expect(shellCss).toMatch(/\.navSlot\.navOpen\s*\{[\s\S]*?z-index:\s*110/)
    expect(shellCss).toMatch(/\.scrim\s*\{[\s\S]*?z-index:\s*100/)
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
