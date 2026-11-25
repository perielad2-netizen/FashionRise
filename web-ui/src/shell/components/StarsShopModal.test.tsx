import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { APP_STORE_LISTING_URL } from '@/config/mobileStoreLinks'

const listStarsIapProducts = vi.fn()
const fetchAppleIapStatus = vi.fn()
const recoverPendingStarsPurchases = vi.fn()
const purchaseStarsPack = vi.fn()
const fetchStarPackages = vi.fn()
const checkoutStarCart = vi.fn()
const setStarCartItem = vi.fn()
const clearStarCart = vi.fn()
const fetchStarCart = vi.fn()
const refreshUser = vi.fn()

/** Mock Capacitor runtime — real `platform.ts` / `isNativeIosStarsShop` / `isNativeAndroidShell` run. */
const capacitorRuntime = vi.hoisted(() => ({
  isNative: false,
  platform: 'web' as string,
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: () => capacitorRuntime.isNative,
    getPlatform: () => capacitorRuntime.platform,
  },
}))

vi.mock('@/services/native/iap', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/native/iap')>()
  return {
    ...actual,
    fetchAppleIapStatus: (...args: unknown[]) => fetchAppleIapStatus(...args),
    listStarsIapProducts: (...args: unknown[]) => listStarsIapProducts(...args),
    purchaseStarsPack: (...args: unknown[]) => purchaseStarsPack(...args),
    recoverPendingStarsPurchases: (...args: unknown[]) => recoverPendingStarsPurchases(...args),
  }
})

vi.mock('@/services/starsShopApi', () => ({
  checkoutStarCart: (...args: unknown[]) => checkoutStarCart(...args),
  clearStarCart: (...args: unknown[]) => clearStarCart(...args),
  fetchStarCart: (...args: unknown[]) => fetchStarCart(...args),
  fetchStarPackages: (...args: unknown[]) => fetchStarPackages(...args),
  fetchStarsWallet: vi.fn(async () => ({
    ai_stars: 40,
    ai_stars_unlimited: false,
    ai_stars_magic_cost: 10,
    ai_stars_costs: { magic: 10, croquis: 10, pdf: 50, fabric: 5 },
  })),
  formatUsdCents: (cents: number) => `$${(cents / 100).toFixed(2)}`,
  setStarCartItem: (...args: unknown[]) => setStarCartItem(...args),
}))

const authUser = vi.hoisted(() => ({
  email: 'perielad2@gmail.com',
  ai_stars: 40,
  ai_stars_unlimited: false,
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: authUser,
    refreshUser,
  }),
}))

import { StarsShopModal } from './StarsShopModal'

function setCapacitor(kind: 'web' | 'ios' | 'android' | 'native-unknown') {
  if (kind === 'web') {
    capacitorRuntime.isNative = false
    capacitorRuntime.platform = 'web'
    return
  }
  capacitorRuntime.isNative = true
  if (kind === 'ios') capacitorRuntime.platform = 'ios'
  else if (kind === 'android') capacitorRuntime.platform = 'android'
  else capacitorRuntime.platform = 'electron' // unrecognized native platform string
}

describe('StarsShopModal native iOS polish', () => {
  beforeEach(() => {
    setCapacitor('ios')
    listStarsIapProducts.mockReset()
    fetchAppleIapStatus.mockReset()
    recoverPendingStarsPurchases.mockReset()
    purchaseStarsPack.mockReset()
    refreshUser.mockReset()
    fetchStarPackages.mockReset()
    checkoutStarCart.mockReset()
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
    authUser.ai_stars = 40
    authUser.ai_stars_unlimited = false
  })

  it('portals the shop to document.body so header stacking cannot clip the title', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)
    const backdrop = await waitFor(() => screen.getByTestId('stars-shop-backdrop'))
    expect(backdrop.parentElement).toBe(document.body)
    expect(screen.getByTestId('stars-shop-modal')).toBeInTheDocument()
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
    expect(screen.queryByTestId('stars-web-store-panel')).not.toBeInTheDocument()
    expect(screen.getByTestId('stars-shop-modal')).toHaveAttribute('data-platform', 'ios')
  })

  it('shows Buying… only on the selected package while purchase is in flight', async () => {
    let resolvePurchase: (value: {
      result: null
      state: 'success'
      message?: string
    }) => void = () => undefined
    purchaseStarsPack.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePurchase = resolve
        }),
    )

    render(<StarsShopModal open onClose={() => undefined} />)
    const buyButtons = await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: /^Buy$/i })
      expect(buttons).toHaveLength(3)
      return buttons
    })

    fireEvent.click(buyButtons[0]!)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Buying/i })).toBeInTheDocument()
    })
    expect(screen.getAllByRole('button', { name: /^Buy$/i })).toHaveLength(2)
    expect(purchaseStarsPack).toHaveBeenCalledWith('stars_50')

    resolvePurchase({ result: null, state: 'success' })
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /^Buy$/i })).toHaveLength(3)
    })
  })

  it('respects disabled Apple purchasing gates (Buy disabled, no purchase call)', async () => {
    fetchAppleIapStatus.mockResolvedValue({
      platform: 'ios',
      purchasing_enabled: false,
      credit_enabled: false,
      verification_configured: true,
      products: [],
    })
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(
        screen.getByText(/Apple Stars purchasing is prepared but not enabled yet/i),
      ).toBeInTheDocument()
    })
    const buyButtons = screen.getAllByRole('button', { name: /^Buy$/i })
    expect(buyButtons.every((b) => (b as HTMLButtonElement).disabled)).toBe(true)
    fireEvent.click(buyButtons[0]!)
    expect(purchaseStarsPack).not.toHaveBeenCalled()
  })
})

describe('StarsShopModal browser / PWA web-only purchase restriction', () => {
  beforeEach(() => {
    setCapacitor('web')
    refreshUser.mockReset()
    fetchStarPackages.mockReset()
    checkoutStarCart.mockReset()
    setStarCartItem.mockReset()
    clearStarCart.mockReset()
    fetchStarCart.mockReset()
    purchaseStarsPack.mockReset()
    listStarsIapProducts.mockReset()
    fetchAppleIapStatus.mockReset()
    recoverPendingStarsPurchases.mockReset()
    authUser.ai_stars = 40
    authUser.ai_stars_unlimited = false
  })

  it('desktop browser shows Get more Stars with balance and costs', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-web-store-panel')).toBeInTheDocument()
    })
    expect(screen.getByTestId('stars-shop-modal')).toHaveAttribute('data-platform', 'web')
    expect(screen.getByRole('heading', { name: /Get more Stars/i })).toBeInTheDocument()
    expect(
      screen.getByText(/Stars can only be purchased through the FashionRise mobile app/i),
    ).toBeInTheDocument()
    expect(screen.getByText('40')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Buy$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Checkout$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Add$/i })).not.toBeInTheDocument()
    expect(fetchStarPackages).not.toHaveBeenCalled()
    expect(checkoutStarCart).not.toHaveBeenCalled()
    expect(purchaseStarsPack).not.toHaveBeenCalled()
    expect(listStarsIapProducts).not.toHaveBeenCalled()
  })

  it('mobile Safari / Chrome / installed PWA use the same Capacitor web path', async () => {
    // UA/PWA display-mode are intentionally irrelevant — Capacitor reports web.
    setCapacitor('web')
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-web-store-panel')).toBeInTheDocument()
    })
    expect(fetchAppleIapStatus).not.toHaveBeenCalled()
    expect(listStarsIapProducts).not.toHaveBeenCalled()
    expect(recoverPendingStarsPurchases).not.toHaveBeenCalled()
    expect(refreshUser).toHaveBeenCalled()
  })

  it('preserves unlimited Stars display on web', async () => {
    authUser.ai_stars_unlimited = true
    authUser.ai_stars = 0
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-web-store-panel')).toBeInTheDocument()
    })
    expect(screen.getByText('∞')).toBeInTheDocument()
    expect(screen.getByText(/\(unlimited\)/i)).toBeInTheDocument()
  })

  it('links App Store with accessible name and marks Google Play Coming soon', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-store-app_store')).toBeInTheDocument()
    })
    const appleLink = screen.getByRole('link', {
      name: /Open FashionRise on the Apple App Store/i,
    })
    expect(appleLink).toHaveAttribute('href', APP_STORE_LISTING_URL)
    expect(appleLink).toHaveAttribute('target', '_blank')
    expect(screen.getByTestId('stars-store-google_play')).toHaveAttribute(
      'data-availability',
      'coming_soon',
    )
    expect(screen.getByTestId('stars-store-badge-google_play')).toHaveTextContent(/Coming soon/i)
    expect(screen.queryByTestId('stars-store-link-google_play')).not.toBeInTheDocument()
  })
})

describe('StarsShopModal native Android preservation', () => {
  beforeEach(() => {
    setCapacitor('android')
    refreshUser.mockReset()
    fetchStarPackages.mockReset()
    purchaseStarsPack.mockReset()
    listStarsIapProducts.mockReset()
    checkoutStarCart.mockReset()
    fetchStarPackages.mockResolvedValue([
      {
        sku: 'stars_50',
        name: 'Starter',
        stars: 50,
        price_usd_cents: 599,
        description: '50 Stars',
        available: true,
      },
    ])
    authUser.ai_stars = 12
    authUser.ai_stars_unlimited = false
  })

  it('does not show the web-only panel and keeps catalog preview without Play Billing', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-android-packages')).toBeInTheDocument()
    })
    expect(screen.getByTestId('stars-shop-modal')).toHaveAttribute('data-platform', 'android')
    expect(screen.queryByTestId('stars-web-store-panel')).not.toBeInTheDocument()
    expect(screen.getByText(/Google Play Stars purchasing is not available yet/i)).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Starter')).toBeInTheDocument()
    const add = screen.getByRole('button', { name: /^Add$/i })
    expect(add).toBeDisabled()
    fireEvent.click(add)
    expect(purchaseStarsPack).not.toHaveBeenCalled()
    expect(listStarsIapProducts).not.toHaveBeenCalled()
    expect(checkoutStarCart).not.toHaveBeenCalled()
  })
})

describe('StarsShopModal unrecognized native runtime', () => {
  beforeEach(() => {
    setCapacitor('native-unknown')
    refreshUser.mockReset()
    fetchStarPackages.mockReset()
    purchaseStarsPack.mockReset()
    listStarsIapProducts.mockReset()
    fetchAppleIapStatus.mockReset()
    checkoutStarCart.mockReset()
    authUser.ai_stars = 7
    authUser.ai_stars_unlimited = false
  })

  it('does not show Get more Stars or initiate any purchase APIs', async () => {
    render(<StarsShopModal open onClose={() => undefined} />)
    await waitFor(() => {
      expect(screen.getByTestId('stars-native-unknown-hint')).toBeInTheDocument()
    })
    expect(screen.getByTestId('stars-shop-modal')).toHaveAttribute('data-platform', 'native-unknown')
    expect(screen.queryByTestId('stars-web-store-panel')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Buy$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Checkout$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /App Store/i })).not.toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(fetchStarPackages).not.toHaveBeenCalled()
    expect(listStarsIapProducts).not.toHaveBeenCalled()
    expect(fetchAppleIapStatus).not.toHaveBeenCalled()
    expect(purchaseStarsPack).not.toHaveBeenCalled()
    expect(checkoutStarCart).not.toHaveBeenCalled()
  })
})
