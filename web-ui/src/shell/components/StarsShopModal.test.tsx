import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StarsShopModal } from './StarsShopModal'

const listStarsIapProducts = vi.fn()
const fetchAppleIapStatus = vi.fn()
const recoverPendingStarsPurchases = vi.fn()
const refreshUser = vi.fn()

vi.mock('@/services/native/iap', () => ({
  fetchAppleIapStatus: (...args: unknown[]) => fetchAppleIapStatus(...args),
  isNativeAndroidShell: () => false,
  isNativeIosStarsShop: () => true,
  listStarsIapProducts: (...args: unknown[]) => listStarsIapProducts(...args),
  purchaseStarsPack: vi.fn(),
  recoverPendingStarsPurchases: (...args: unknown[]) => recoverPendingStarsPurchases(...args),
}))

vi.mock('@/services/starsShopApi', () => ({
  checkoutStarCart: vi.fn(),
  clearStarCart: vi.fn(),
  fetchStarCart: vi.fn(),
  fetchStarPackages: vi.fn(),
  formatUsdCents: (cents: number) => `$${(cents / 100).toFixed(2)}`,
  setStarCartItem: vi.fn(),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: {
      email: 'perielad2@gmail.com',
      ai_stars: 40,
      ai_stars_unlimited: false,
    },
    refreshUser,
  }),
}))

describe('StarsShopModal native iOS polish', () => {
  beforeEach(() => {
    listStarsIapProducts.mockReset()
    fetchAppleIapStatus.mockReset()
    recoverPendingStarsPurchases.mockReset()
    refreshUser.mockReset()
    recoverPendingStarsPurchases.mockResolvedValue({ recovered: 0, attempted: 0, state: 'idle' })
    fetchAppleIapStatus.mockResolvedValue({
      platform: 'ios',
      purchasing_enabled: true,
      credit_enabled: true,
      verification_configured: true,
      products: [],
    })
    listStarsIapProducts.mockResolvedValue([
      {
        productId: 'stars_50',
        title: 'Starter',
        description: '50 Stars',
        priceString: '$5.99',
        stars: 50,
      },
      {
        productId: 'stars_150',
        title: 'Creator',
        description: '150 Stars',
        priceString: '$16.99',
        stars: 150,
      },
      {
        productId: 'stars_500',
        title: 'Studio',
        description: '500 Stars',
        priceString: '$49.99',
        stars: 500,
      },
    ])
  })

  it('shows friendly copy, finite balance, ordered packages, and localized prices', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)

    await waitFor(() => {
      expect(screen.getByText(/Stars power your AI fashion creations/i)).toBeInTheDocument()
    })
    expect(
      screen.getByText(/Magic: 10 Stars · Model: 10 Stars · Fabric: 5 Stars · PDF: 50 Stars/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/Your balance:/i)).toBeInTheDocument()
    expect(screen.getByText('40')).toBeInTheDocument()
    expect(screen.queryByText(/unlimited/i)).not.toBeInTheDocument()
    expect(screen.queryByText('∞')).not.toBeInTheDocument()

    const names = screen.getAllByText(/^(Starter|Creator|Studio)$/).map((el) => el.textContent)
    expect(names).toEqual(['Starter', 'Creator', 'Studio'])
    expect(screen.getAllByText(/50 Stars/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/150 Stars/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/500 Stars/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/\$5\.99/)).toBeInTheDocument()
    expect(screen.getByText(/\$16\.99/)).toBeInTheDocument()
    expect(screen.getByText(/\$49\.99/)).toBeInTheDocument()
    expect(screen.queryByText(/FashionRise - 500 Stars/i)).not.toBeInTheDocument()
  })
})
