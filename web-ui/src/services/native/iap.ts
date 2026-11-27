/**
 * Stars In-App Purchase adapter (Apple StoreKit / Google Play Billing).
 *
 * iOS (Capacitor + @capgo/native-purchases 7.19.3):
 * - Load localized products from StoreKit
 * - Purchase with server-issued appAccountToken
 * - Confirm with StoreKit 2 jwsRepresentation (server verifies + credits)
 * - Prefer autoAcknowledgePurchases:false and acknowledge after backend accept
 *
 * Capgo limitation (verified in plugin sources):
 * - `Transaction.updates` listener **auto-finishes** verified transactions before
 *   emitting `transactionUpdated`. Consumables may therefore leave the unfinished
 *   queue even when purchaseProduct used autoAcknowledgePurchases:false.
 * - Recovery still uses `getPurchases()` → StoreKit `Transaction.all` (includes
 *   history with jwsRepresentation) filtered by appAccountToken, plus a
 *   session-scoped pending transaction-id hint (never stores raw JWS).
 * - If Apple history omits a finished consumable and our pending hint is gone,
 *   support reconciliation via ASN + App Store Server API is required (gated).
 *
 * Android (Capacitor + Billing Library via Capgo):
 * - Load localized Play products
 * - Purchase with obfuscatedAccountId (= server appAccountToken UUID)
 * - Confirm with purchaseToken (server verifies via Play Developer API)
 * - consumePurchase after durable backend credit (never trust client Stars)
 * - Gates: IAP_GOOGLE_* / license-tester emails (default OFF)
 *
 * Web: this module is a no-op; StarsShopModal keeps the web cart UX.
 */
import { NativePurchases, PURCHASE_TYPE, type Transaction } from '@capgo/native-purchases'
import { ApiError, apiRequest } from '@/services/api/client'
import { isNativeShell, nativePlatform } from './platform'

const PENDING_TXN_KEY = 'fr.iap.pendingTxn.v1'

export type StarsIapProduct = {
  productId: string
  title: string
  description: string
  /** StoreKit `Product.displayPrice` — never invent/FX-convert this string. */
  priceString: string
  /** StoreKit currency code (ISO 4217) from Capgo — for QA/storefront checks only. */
  currencyCode?: string
  stars: number
}

export type IapConfirmResult = {
  stars_credited: number
  already_processed?: boolean
  blocked?: boolean
  ai_stars?: number
  product_id?: string
  transaction_id?: string
  reason?: string
}

export type AppleIapStatus = {
  platform: string
  purchasing_enabled: boolean
  credit_enabled: boolean
  verification_configured: boolean
  /** True when the signed-in account is on IAP_APPLE_SANDBOX_TESTER_EMAILS. */
  sandbox_tester?: boolean
  /** Unlimited wallets must not start new Store purchases. */
  unlimited_wallet?: boolean
  products: Array<{ product_id: string; stars: number }>
}

export type GoogleIapStatus = {
  platform: string
  purchasing_enabled: boolean
  credit_enabled: boolean
  verification_configured: boolean
  /** True when the signed-in account is on IAP_GOOGLE_LICENSE_TESTER_EMAILS. */
  license_tester?: boolean
  /** Unlimited wallets must not start new Play purchases. */
  unlimited_wallet?: boolean
  package_name?: string
  products: Array<{ product_id: string; stars: number }>
}

export type PurchaseFlowState =
  | 'idle'
  | 'loading_products'
  | 'available'
  | 'unavailable'
  | 'purchasing'
  | 'confirming'
  | 'success'
  | 'cancelled'
  | 'verification_failed'
  | 'network_failure'
  | 'recovery_required'
  | 'already_processed'
  | 'gate_off'

/**
 * Product IDs — must match App Store Connect + Play Console exactly.
 * Launch console prices (USD): Starter $5.99 · Creator $16.99 · Studio $49.99
 * Never display hardcoded prices as the App Store price — use StoreKit localization.
 */
/** Canonical display order: Starter (50) → Creator (150) → Studio (500). */
export const STARS_IAP_PRODUCTS: Array<{ productId: string; stars: number; name: string }> = [
  { productId: 'stars_50', stars: 50, name: 'Starter' },
  { productId: 'stars_150', stars: 150, name: 'Creator' },
  { productId: 'stars_500', stars: 500, name: 'Studio' },
]

const STARS_IAP_ORDER = new Map(
  STARS_IAP_PRODUCTS.map((product, index) => [product.productId, index] as const),
)

/** Sort mapped StoreKit products into Starter → Creator → Studio; drop unknowns. */
export function sortStarsIapProducts(products: StarsIapProduct[]): StarsIapProduct[] {
  return [...products]
    .filter((product) => STARS_IAP_ORDER.has(product.productId) && product.stars > 0)
    .sort(
      (a, b) => (STARS_IAP_ORDER.get(a.productId) ?? 99) - (STARS_IAP_ORDER.get(b.productId) ?? 99),
    )
}

/** In-flight purchase guard (module scope — survives remounts within the same JS context). */
let purchaseInFlight = false
let recoveryInFlight = false
let lastRecoveryAt = 0
const RECOVERY_COOLDOWN_MS = 15_000

export function iapAvailable(): boolean {
  return isNativeShell()
}

export function isNativeIosStarsShop(): boolean {
  return isNativeShell() && nativePlatform() === 'ios'
}

export function isNativeAndroidShell(): boolean {
  return isNativeShell() && nativePlatform() === 'android'
}

export async function fetchAppleIapStatus(): Promise<AppleIapStatus> {
  // Prefer auth so designated sandbox testers receive purchasing/credit=true
  // while public gates remain OFF for anonymous / non-tester callers.
  return apiRequest<AppleIapStatus>('/shop/iap/apple/status')
}

export async function fetchGoogleIapStatus(): Promise<GoogleIapStatus> {
  return apiRequest<GoogleIapStatus>('/shop/iap/google/status')
}

export async function fetchAppAccountToken(): Promise<string> {
  const res = await apiRequest<{ app_account_token: string }>('/shop/iap/app-account-token')
  const token = (res.app_account_token || '').trim()
  if (!token) throw new Error('Missing app account token')
  return token
}

export async function listStarsIapProducts(): Promise<StarsIapProduct[]> {
  if (!iapAvailable()) return []
  const ids = STARS_IAP_PRODUCTS.map((p) => p.productId)
  const { products } = await NativePurchases.getProducts({
    productIdentifiers: ids,
    productType: PURCHASE_TYPE.INAPP,
  })
  const mapped: StarsIapProduct[] = []
  for (const p of products) {
    const meta = STARS_IAP_PRODUCTS.find((x) => x.productId === p.identifier)
    if (!meta) continue
    mapped.push({
      productId: meta.productId,
      // Friendly FashionRise package name — not ASC marketing title.
      title: meta.name,
      description: p.description || `${meta.stars} Stars`,
      // Always Apple's localized StoreKit price string (never hardcode USD/ILS).
      priceString: p.priceString || '',
      currencyCode: (p.currencyCode || '').trim() || undefined,
      stars: meta.stars,
    })
  }
  // Explicit canonical order regardless of StoreKit response order.
  return sortStarsIapProducts(mapped)
}

function classifyPurchaseError(err: unknown): PurchaseFlowState {
  const msg = err instanceof Error ? err.message : String(err || '')
  const lower = msg.toLowerCase()
  if (
    lower.includes('cancel') ||
    lower.includes('user cancelled') ||
    lower.includes('user canceled') ||
    lower.includes('paymentsheeterror.canceled')
  ) {
    return 'cancelled'
  }
  if (lower.includes('network') || lower.includes('timeout') || lower.includes('failed to fetch')) {
    return 'network_failure'
  }
  if (err instanceof ApiError) {
    if (err.status === 503) return 'gate_off'
    if (err.status === 403 || err.status === 422) return 'verification_failed'
    if (err.status >= 500) return 'network_failure'
  }
  return 'verification_failed'
}

async function confirmTransaction(transaction: Transaction, productId: string): Promise<IapConfirmResult> {
  return apiRequest<IapConfirmResult>('/shop/iap/confirm', {
    method: 'POST',
    body: {
      platform: nativePlatform(),
      product_id: productId || transaction.productIdentifier || '',
      transaction_id: transaction.transactionId,
      purchase_token: transaction.purchaseToken ?? null,
      receipt: transaction.receipt ?? null,
      jws: transaction.jwsRepresentation ?? null,
    },
  })
}

async function finishTransaction(transaction: Transaction): Promise<void> {
  // Capgo: acknowledgePurchase finishes StoreKit 2 transactions when
  // autoAcknowledgePurchases was false. Capgo Transaction.updates may already
  // have finished it — treat "not found / already finished" as success.
  // Android consumables: consumePurchase after durable backend credit.
  const token = String(transaction.purchaseToken || transaction.transactionId || '')
  if (!token) return
  try {
    if (nativePlatform() === 'android') {
      await NativePurchases.consumePurchase({ purchaseToken: token })
      return
    }
    await NativePurchases.acknowledgePurchase({ purchaseToken: token })
  } catch {
    /* already finished / consumed — confirm already durable */
  }
}

type PendingTxnHint = {
  transactionId: string
  productId: string
  appAccountToken: string
  at: number
}

function readPendingHints(): PendingTxnHint[] {
  try {
    const raw = sessionStorage.getItem(PENDING_TXN_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as PendingTxnHint[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writePendingHints(hints: PendingTxnHint[]): void {
  try {
    sessionStorage.setItem(PENDING_TXN_KEY, JSON.stringify(hints.slice(-8)))
  } catch {
    /* private mode / unavailable */
  }
}

function rememberPendingTxn(hint: PendingTxnHint): void {
  const rest = readPendingHints().filter((h) => h.transactionId !== hint.transactionId)
  rest.push(hint)
  writePendingHints(rest)
}

function clearPendingTxn(transactionId: string): void {
  writePendingHints(readPendingHints().filter((h) => h.transactionId !== transactionId))
}

/**
 * Full native purchase → confirm → finish/consume flow (iOS StoreKit / Android Play).
 * Does not start when another purchase is in flight.
 */
export async function purchaseStarsPack(productId: string): Promise<{
  result: IapConfirmResult | null
  state: PurchaseFlowState
  message?: string
}> {
  const onIos = isNativeIosStarsShop()
  const onAndroid = isNativeAndroidShell()
  if (!onIos && !onAndroid) {
    return {
      result: null,
      state: 'unavailable',
      message: 'In-app purchases are only available in the iOS or Android store app',
    }
  }
  if (purchaseInFlight) {
    return { result: null, state: 'purchasing', message: 'A purchase is already in progress' }
  }

  const meta = STARS_IAP_PRODUCTS.find((p) => p.productId === productId)
  if (!meta) {
    return { result: null, state: 'unavailable', message: 'Unknown Stars pack' }
  }

  purchaseInFlight = true
  let transaction: Transaction | null = null
  try {
    let purchasingEnabled = false
    try {
      if (onIos) {
        const status = await fetchAppleIapStatus()
        purchasingEnabled = Boolean(status.purchasing_enabled)
      } else {
        const status = await fetchGoogleIapStatus()
        purchasingEnabled = Boolean(status.purchasing_enabled)
      }
    } catch {
      purchasingEnabled = false
    }
    if (!purchasingEnabled) {
      return {
        result: null,
        state: 'gate_off',
        message: onIos
          ? 'Apple Stars purchasing is not enabled yet.'
          : 'Google Play Stars purchasing is not enabled yet.',
      }
    }

    const appAccountToken = await fetchAppAccountToken()

    transaction = await NativePurchases.purchaseProduct({
      productIdentifier: productId,
      productType: PURCHASE_TYPE.INAPP,
      appAccountToken,
      // Android consumables must be consumed after server credit.
      isConsumable: onAndroid,
      // Prefer manual finish; Capgo Transaction.updates may still auto-finish on iOS.
      autoAcknowledgePurchases: false,
    })

    if (transaction.transactionId) {
      rememberPendingTxn({
        transactionId: String(transaction.transactionId),
        productId,
        appAccountToken,
        at: Date.now(),
      })
    }

    if (onIos && !transaction.jwsRepresentation) {
      return {
        result: null,
        state: 'recovery_required',
        message:
          'Purchase completed in the App Store but signed transaction evidence is missing. Recovery will retry when you reopen the shop.',
      }
    }
    if (onAndroid && !transaction.purchaseToken) {
      return {
        result: null,
        state: 'recovery_required',
        message:
          'Purchase completed in Google Play but purchase token is missing. Recovery will retry when you reopen the shop.',
      }
    }

    try {
      const result = await confirmTransaction(transaction, productId)
      if ((result as IapConfirmResult & { pending?: boolean }).pending) {
        return {
          result,
          state: 'recovery_required',
          message: 'Payment is still pending. Stars will credit after Google Play completes the charge.',
        }
      }
      // Finish/consume after durable acceptance (credit, already processed, or blocked refund).
      await finishTransaction(transaction)
      if (transaction.transactionId) clearPendingTxn(String(transaction.transactionId))
      if (result.blocked) {
        return {
          result,
          state: 'already_processed',
          message: 'This purchase was refunded or revoked and was not credited.',
        }
      }
      if (result.already_processed) {
        return { result, state: 'already_processed' }
      }
      return { result, state: 'success' }
    } catch (confirmErr) {
      const state = classifyPurchaseError(confirmErr)
      if (state === 'network_failure' || state === 'gate_off') {
        return {
          result: null,
          state: state === 'gate_off' ? 'gate_off' : 'recovery_required',
          message:
            state === 'gate_off'
              ? 'Purchase recorded by the store; Stars credit is not enabled yet. Contact support if Stars are missing after enablement.'
              : 'Purchase succeeded in the store but confirmation failed. We will retry when the app resumes.',
        }
      }
      return {
        result: null,
        state,
        message: confirmErr instanceof Error ? confirmErr.message : 'Verification failed',
      }
    }
  } catch (err) {
    const state = classifyPurchaseError(err)
    return {
      result: null,
      state,
      message:
        state === 'cancelled'
          ? undefined
          : err instanceof Error
            ? err.message
            : 'Purchase failed',
    }
  } finally {
    purchaseInFlight = false
  }
}

/**
 * Bounded unfinished-transaction recovery for the signed-in account.
 * Uses Capgo getPurchases filtered by appAccountToken — does not replay
 * historical consumables as fresh credits (server idempotency + token bind).
 */
export async function recoverPendingStarsPurchases(): Promise<{
  recovered: number
  attempted: number
  state: PurchaseFlowState
  message?: string
}> {
  const onIos = isNativeIosStarsShop()
  const onAndroid = isNativeAndroidShell()
  if (!onIos && !onAndroid) {
    return { recovered: 0, attempted: 0, state: 'unavailable' }
  }
  if (purchaseInFlight || recoveryInFlight) {
    return { recovered: 0, attempted: 0, state: 'purchasing' }
  }
  const now = Date.now()
  if (now - lastRecoveryAt < RECOVERY_COOLDOWN_MS) {
    return { recovered: 0, attempted: 0, state: 'idle' }
  }

  recoveryInFlight = true
  lastRecoveryAt = now
  try {
    let creditEnabled = false
    try {
      if (onIos) {
        creditEnabled = Boolean((await fetchAppleIapStatus()).credit_enabled)
      } else {
        creditEnabled = Boolean((await fetchGoogleIapStatus()).credit_enabled)
      }
    } catch {
      return { recovered: 0, attempted: 0, state: 'network_failure' }
    }
    if (!creditEnabled) {
      return { recovered: 0, attempted: 0, state: 'gate_off' }
    }

    const appAccountToken = await fetchAppAccountToken()
    // Drop pending hints that belong to a different signed-in account.
    writePendingHints(
      readPendingHints().filter(
        (h) => h.appAccountToken.toLowerCase() === appAccountToken.toLowerCase(),
      ),
    )
    const pendingIds = new Set(readPendingHints().map((h) => h.transactionId))

    const { purchases } = await NativePurchases.getPurchases({
      productType: PURCHASE_TYPE.INAPP,
      appAccountToken,
    })

    let recovered = 0
    let attempted = 0
    let pendingStillMissing = 0
    const seen = new Set<string>()

    for (const purchase of purchases || []) {
      const productId = purchase.productIdentifier || ''
      if (!STARS_IAP_PRODUCTS.some((p) => p.productId === productId)) continue
      if (!purchase.jwsRepresentation) continue
      const txnToken = (purchase.appAccountToken || '').trim()
      if (txnToken && txnToken.toLowerCase() !== appAccountToken.toLowerCase()) continue

      const txnId = String(purchase.transactionId || '')
      seen.add(txnId)
      attempted += 1
      try {
        const result = await confirmTransaction(purchase, productId)
        await finishTransaction(purchase)
        if (txnId) clearPendingTxn(txnId)
        if (!result.blocked && (result.stars_credited > 0 || result.already_processed)) {
          recovered += 1
        }
      } catch {
        /* leave for a later bounded retry / support */
      }
    }

    for (const id of pendingIds) {
      if (!seen.has(id)) pendingStillMissing += 1
    }

    try {
      await apiRequest<{ restored: number }>('/shop/iap/restore', { method: 'POST', body: {} })
    } catch {
      /* ignore */
    }

    const supportNote =
      pendingStillMissing > 0 && recovered === 0
        ? ' A recent App Store purchase may need support reconciliation if Stars do not appear.'
        : ''

    return {
      recovered,
      attempted,
      state: recovered > 0 ? 'success' : pendingStillMissing > 0 ? 'recovery_required' : 'idle',
      message:
        recovered > 0
          ? `Recovered ${recovered} Stars purchase${recovered === 1 ? '' : 's'}.`
          : supportNote.trim() || undefined,
    }
  } catch (err) {
    return {
      recovered: 0,
      attempted: 0,
      state: classifyPurchaseError(err),
      message: err instanceof Error ? err.message : undefined,
    }
  } finally {
    recoveryInFlight = false
  }
}

let updatesListenerStarted = false

/**
 * Listen for Capgo transactionUpdated (fired after Capgo auto-finish).
 * Confirms with backend when credit gate is on and token matches.
 */
export async function startIapTransactionUpdateRecovery(): Promise<void> {
  if (!isNativeIosStarsShop() || updatesListenerStarted) return
  updatesListenerStarted = true
  try {
    await NativePurchases.addListener('transactionUpdated', (transaction) => {
      void (async () => {
        try {
          const status = await fetchAppleIapStatus()
          if (!status.credit_enabled) return
          const productId = transaction.productIdentifier || ''
          if (!STARS_IAP_PRODUCTS.some((p) => p.productId === productId)) return
          if (!transaction.jwsRepresentation) return
          const appAccountToken = await fetchAppAccountToken()
          const txnToken = (transaction.appAccountToken || '').trim()
          if (txnToken && txnToken.toLowerCase() !== appAccountToken.toLowerCase()) {
            return
          }
          if (transaction.transactionId) {
            rememberPendingTxn({
              transactionId: String(transaction.transactionId),
              productId,
              appAccountToken,
              at: Date.now(),
            })
          }
          await confirmTransaction(transaction, productId)
          if (transaction.transactionId) clearPendingTxn(String(transaction.transactionId))
        } catch {
          /* recovery loop / shop open will retry */
        }
      })()
    })
  } catch {
    updatesListenerStarted = false
  }
}

/** @deprecated Prefer purchaseStarsPack return state; kept for call-site compat. */
export async function restoreStarsPurchases(): Promise<{ restored: number }> {
  const out = await recoverPendingStarsPurchases()
  return { restored: out.recovered }
}

/** Test helper — reset module guards. */
export function __resetIapGuardsForTests(): void {
  purchaseInFlight = false
  recoveryInFlight = false
  lastRecoveryAt = 0
}
