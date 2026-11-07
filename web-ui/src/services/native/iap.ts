/**
 * Stars In-App Purchase adapter (Apple StoreKit / Google Play Billing).
 * No custom card UI — stores own checkout. We only unlock Stars after a verified purchase.
 */
import { NativePurchases, PURCHASE_TYPE } from '@capgo/native-purchases'
import { apiRequest } from '@/services/api/client'
import { isNativeShell, nativePlatform } from './platform'

export type StarsIapProduct = {
  productId: string
  title: string
  description: string
  priceString: string
  stars: number
}

/** Product IDs — must match App Store Connect + Play Console exactly. */
export const STARS_IAP_PRODUCTS: Array<{ productId: string; stars: number }> = [
  { productId: 'stars_50', stars: 50 },
  { productId: 'stars_120', stars: 120 },
  { productId: 'stars_300', stars: 300 },
]

export function iapAvailable(): boolean {
  return isNativeShell()
}

export async function listStarsIapProducts(): Promise<StarsIapProduct[]> {
  if (!iapAvailable()) return []
  const ids = STARS_IAP_PRODUCTS.map((p) => p.productId)
  const { products } = await NativePurchases.getProducts({
    productIdentifiers: ids,
    productType: PURCHASE_TYPE.INAPP,
  })
  return products.map((p) => {
    const meta = STARS_IAP_PRODUCTS.find((x) => x.productId === p.identifier)
    return {
      productId: p.identifier,
      title: p.title || p.identifier,
      description: p.description || '',
      priceString: p.priceString || '',
      stars: meta?.stars ?? 0,
    }
  })
}

export async function purchaseStarsPack(productId: string): Promise<{ stars_credited: number }> {
  if (!iapAvailable()) {
    throw new Error('In-app purchases are only available in the App Store / Play Store app')
  }
  const meta = STARS_IAP_PRODUCTS.find((p) => p.productId === productId)
  if (!meta) throw new Error('Unknown Stars pack')

  const transaction = await NativePurchases.purchaseProduct({
    productIdentifier: productId,
    productType: PURCHASE_TYPE.INAPP,
  })

  // Server verifies with Apple/Google and credits the Stars wallet.
  return apiRequest<{ stars_credited: number }>('/shop/iap/confirm', {
    method: 'POST',
    body: {
      platform: nativePlatform(),
      product_id: productId,
      transaction_id: transaction.transactionId,
      purchase_token: transaction.purchaseToken ?? null,
      receipt: transaction.receipt ?? null,
      jws: transaction.jwsRepresentation ?? null,
    },
  })
}

export async function restoreStarsPurchases(): Promise<{ restored: number }> {
  if (!iapAvailable()) return { restored: 0 }
  await NativePurchases.restorePurchases()
  return apiRequest<{ restored: number }>('/shop/iap/restore', { method: 'POST', body: {} })
}
