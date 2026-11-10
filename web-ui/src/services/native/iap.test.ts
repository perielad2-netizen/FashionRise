import { beforeEach, describe, expect, it, vi } from 'vitest'

const purchaseProduct = vi.fn()
const getProducts = vi.fn()
const getPurchases = vi.fn()
const acknowledgePurchase = vi.fn()
const restorePurchases = vi.fn()

vi.mock('@capgo/native-purchases', () => ({
  PURCHASE_TYPE: { INAPP: 'inapp', SUBS: 'subs' },
  NativePurchases: {
    purchaseProduct: (...args: unknown[]) => purchaseProduct(...args),
    getProducts: (...args: unknown[]) => getProducts(...args),
    getPurchases: (...args: unknown[]) => getPurchases(...args),
    acknowledgePurchase: (...args: unknown[]) => acknowledgePurchase(...args),
    restorePurchases: (...args: unknown[]) => restorePurchases(...args),
  },
}))

vi.mock('./platform', () => ({
  isNativeShell: () => true,
  nativePlatform: () => 'ios',
}))

const apiRequest = vi.fn()
vi.mock('@/services/api/client', () => ({
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status = 400) {
      super(message)
      this.status = status
    }
  },
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}))

describe('native iap Phase B', () => {
  beforeEach(async () => {
    vi.resetModules()
    purchaseProduct.mockReset()
    getProducts.mockReset()
    getPurchases.mockReset()
    acknowledgePurchase.mockReset()
    apiRequest.mockReset()
    const mod = await import('./iap')
    mod.__resetIapGuardsForTests()
  })

  it('lists localized StoreKit products without hardcoded prices', async () => {
    getProducts.mockResolvedValue({
      products: [
        {
          identifier: 'stars_50',
          title: 'Starter',
          description: '50 Stars',
          priceString: '₪22.90',
        },
      ],
    })
    const { listStarsIapProducts } = await import('./iap')
    const products = await listStarsIapProducts()
    expect(products).toEqual([
      {
        productId: 'stars_50',
        title: 'Starter',
        description: '50 Stars',
        priceString: '₪22.90',
        stars: 50,
      },
    ])
  })

  it('purchases with appAccountToken and confirms JWS before finish', async () => {
    apiRequest.mockImplementation((path: string) => {
      if (path === '/shop/iap/apple/status') {
        return Promise.resolve({
          purchasing_enabled: true,
          credit_enabled: true,
          verification_configured: true,
          products: [],
        })
      }
      if (path === '/shop/iap/app-account-token') {
        return Promise.resolve({ app_account_token: '11111111-1111-4111-8111-111111111111' })
      }
      if (path === '/shop/iap/confirm') {
        return Promise.resolve({ stars_credited: 50, already_processed: false, ai_stars: 60 })
      }
      return Promise.reject(new Error(`unexpected ${path}`))
    })
    purchaseProduct.mockResolvedValue({
      transactionId: 'txn-1',
      productIdentifier: 'stars_50',
      jwsRepresentation: 'aaa.bbb.ccc',
      purchaseToken: 'txn-1',
    })
    acknowledgePurchase.mockResolvedValue({})

    const { purchaseStarsPack } = await import('./iap')
    const out = await purchaseStarsPack('stars_50')
    expect(out.state).toBe('success')
    expect(purchaseProduct).toHaveBeenCalledWith(
      expect.objectContaining({
        productIdentifier: 'stars_50',
        appAccountToken: '11111111-1111-4111-8111-111111111111',
        autoAcknowledgePurchases: false,
      }),
    )
    expect(apiRequest).toHaveBeenCalledWith(
      '/shop/iap/confirm',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({
          jws: 'aaa.bbb.ccc',
          platform: 'ios',
        }),
      }),
    )
    expect(acknowledgePurchase).toHaveBeenCalled()
  })

  it('treats user cancel as cancelled, not error credit', async () => {
    apiRequest.mockResolvedValue({
      purchasing_enabled: true,
      credit_enabled: true,
      verification_configured: true,
      products: [],
    })
    // status + token
    apiRequest
      .mockResolvedValueOnce({
        purchasing_enabled: true,
        credit_enabled: true,
        verification_configured: true,
        products: [],
      })
      .mockResolvedValueOnce({ app_account_token: '11111111-1111-4111-8111-111111111111' })
    purchaseProduct.mockRejectedValue(new Error('User cancelled the purchase'))

    const { purchaseStarsPack } = await import('./iap')
    const out = await purchaseStarsPack('stars_50')
    expect(out.state).toBe('cancelled')
    expect(acknowledgePurchase).not.toHaveBeenCalled()
  })

  it('blocks parallel purchases', async () => {
    let releaseToken: () => void = () => undefined
    const tokenGate = new Promise<void>((resolve) => {
      releaseToken = resolve
    })
    apiRequest.mockImplementation((path: string) => {
      if (path === '/shop/iap/apple/status') {
        return Promise.resolve({
          purchasing_enabled: true,
          credit_enabled: true,
          verification_configured: true,
          products: [],
        })
      }
      if (path === '/shop/iap/app-account-token') {
        return tokenGate.then(() => ({
          app_account_token: '11111111-1111-4111-8111-111111111111',
        }))
      }
      if (path === '/shop/iap/confirm') {
        return Promise.resolve({ stars_credited: 50 })
      }
      return Promise.resolve({})
    })
    purchaseProduct.mockResolvedValue({
      transactionId: 'txn-1',
      productIdentifier: 'stars_50',
      jwsRepresentation: 'a.b.c',
      purchaseToken: 'txn-1',
    })
    acknowledgePurchase.mockResolvedValue({})

    const { purchaseStarsPack } = await import('./iap')
    const first = purchaseStarsPack('stars_50')
    // First call holds purchaseInFlight while awaiting token
    await Promise.resolve()
    const second = await purchaseStarsPack('stars_150')
    expect(second.state).toBe('purchasing')
    releaseToken()
    const done = await first
    expect(done.state).toBe('success')
  })

  it('skips recovery when credit gate is off', async () => {
    apiRequest.mockResolvedValue({
      purchasing_enabled: false,
      credit_enabled: false,
      verification_configured: true,
      products: [],
    })
    const { recoverPendingStarsPurchases } = await import('./iap')
    const out = await recoverPendingStarsPurchases()
    expect(out.state).toBe('gate_off')
    expect(getPurchases).not.toHaveBeenCalled()
  })

  it('recovers unfinished purchases for matching appAccountToken only', async () => {
    apiRequest.mockImplementation((path: string) => {
      if (path === '/shop/iap/apple/status') {
        return Promise.resolve({
          purchasing_enabled: true,
          credit_enabled: true,
          verification_configured: true,
          products: [],
        })
      }
      if (path === '/shop/iap/app-account-token') {
        return Promise.resolve({ app_account_token: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' })
      }
      if (path === '/shop/iap/confirm') {
        return Promise.resolve({ stars_credited: 50, already_processed: false })
      }
      if (path === '/shop/iap/restore') {
        return Promise.resolve({ restored: 0 })
      }
      return Promise.resolve({})
    })
    getPurchases.mockResolvedValue({
      purchases: [
        {
          productIdentifier: 'stars_50',
          transactionId: 't1',
          jwsRepresentation: 'a.b.c',
          purchaseToken: 't1',
          appAccountToken: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        },
        {
          productIdentifier: 'stars_50',
          transactionId: 't2',
          jwsRepresentation: 'd.e.f',
          purchaseToken: 't2',
          appAccountToken: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        },
      ],
    })
    acknowledgePurchase.mockResolvedValue({})

    const { recoverPendingStarsPurchases } = await import('./iap')
    const out = await recoverPendingStarsPurchases()
    expect(out.attempted).toBe(1)
    expect(out.recovered).toBe(1)
    expect(apiRequest).toHaveBeenCalledWith(
      '/shop/iap/confirm',
      expect.objectContaining({
        body: expect.objectContaining({ transaction_id: 't1' }),
      }),
    )
  })

  it('returns gate_off when purchasing disabled', async () => {
    apiRequest.mockResolvedValue({
      purchasing_enabled: false,
      credit_enabled: true,
      verification_configured: true,
      products: [],
    })
    const { purchaseStarsPack } = await import('./iap')
    const out = await purchaseStarsPack('stars_50')
    expect(out.state).toBe('gate_off')
    expect(purchaseProduct).not.toHaveBeenCalled()
  })
})
