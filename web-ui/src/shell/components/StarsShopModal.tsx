import { useCallback, useEffect, useRef, useState } from 'react'
import { ShoppingBag, Star, X } from 'lucide-react'
import { ApiError } from '@/services/api/client'
import {
  fetchAppleIapStatus,
  isNativeAndroidShell,
  isNativeIosStarsShop,
  listStarsIapProducts,
  purchaseStarsPack,
  recoverPendingStarsPurchases,
  type AppleIapStatus,
  type PurchaseFlowState,
  type StarsIapProduct,
} from '@/services/native/iap'
import {
  checkoutStarCart,
  clearStarCart,
  fetchStarCart,
  fetchStarPackages,
  formatUsdCents,
  setStarCartItem,
  type StarCart,
  type StarPackage,
} from '@/services/starsShopApi'
import { useAiStarsWallet } from '@/hooks/useAiStarsWallet'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './StarsShopModal.module.css'

type Props = {
  open: boolean
  onClose: () => void
}

function stateMessage(state: PurchaseFlowState, fallback?: string): string | null {
  switch (state) {
    case 'cancelled':
      return null
    case 'success':
      return 'Stars added to your balance.'
    case 'already_processed':
      return fallback || 'This purchase was already processed.'
    case 'gate_off':
      return fallback || 'Apple Stars purchasing is not enabled yet.'
    case 'unavailable':
      return fallback || 'Stars packages are unavailable in the App Store right now.'
    case 'recovery_required':
      return (
        fallback ||
        'Purchase may have completed. We will retry confirmation — check your balance shortly.'
      )
    case 'network_failure':
      return fallback || 'Network error. If you were charged, reopen the shop to recover Stars.'
    case 'verification_failed':
      return fallback || 'Could not verify this purchase. Contact support if Stars are missing.'
    default:
      return fallback || null
  }
}

export function StarsShopModal({ open, onClose }: Props) {
  const { user, refreshUser } = useAuth()
  const { costs } = useAiStarsWallet()
  const nativeIos = isNativeIosStarsShop()
  const nativeAndroid = isNativeAndroidShell()
  const costLine = `Magic: ${costs.magic} Stars · Model: ${costs.croquis} Stars · Fabric: ${costs.fabric} Stars · PDF: ${costs.pdf} Stars`

  const [packages, setPackages] = useState<StarPackage[]>([])
  const [cart, setCart] = useState<StarCart | null>(null)
  const [iapProducts, setIapProducts] = useState<StarsIapProduct[]>([])
  const [iapStatus, setIapStatus] = useState<AppleIapStatus | null>(null)
  const [busy, setBusy] = useState(false)
  /** Only the tapped package shows “Buying…” — other packs stay labeled Buy (disabled). */
  const [buyingProductId, setBuyingProductId] = useState<string | null>(null)
  const [flowState, setFlowState] = useState<PurchaseFlowState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const purchaseLock = useRef(false)

  const reloadWeb = useCallback(async () => {
    setError(null)
    const [pkgs, nextCart] = await Promise.all([fetchStarPackages(), fetchStarCart()])
    setPackages(pkgs)
    setCart(nextCart)
    void refreshUser()
  }, [refreshUser])

  const reloadNativeIos = useCallback(async () => {
    setError(null)
    setFlowState('loading_products')
    try {
      const [status, products] = await Promise.all([
        fetchAppleIapStatus().catch(() => null),
        listStarsIapProducts().catch(() => [] as StarsIapProduct[]),
      ])
      setIapStatus(status)
      setIapProducts(products)
      if (!products.length) {
        setFlowState('unavailable')
      } else if (status && !status.purchasing_enabled) {
        setFlowState('gate_off')
      } else {
        setFlowState('available')
      }
      void refreshUser()
    } catch (err) {
      setFlowState('unavailable')
      setError(err instanceof Error ? err.message : 'Could not load App Store products.')
    }
  }, [refreshUser])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    ;(async () => {
      try {
        if (nativeIos) {
          await reloadNativeIos()
          // Bounded recovery when opening shop (credit gate may still be off).
          const recovery = await recoverPendingStarsPurchases()
          if (!cancelled && recovery.recovered > 0) {
            setNotice(recovery.message || 'Recovered a pending Stars purchase.')
            void refreshUser()
          }
        } else {
          await reloadWeb()
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Could not load Stars shop.')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, nativeIos, reloadNativeIos, reloadWeb, refreshUser])

  if (!open) return null

  async function onAdd(sku: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const current = cart?.items.find((i) => i.package_sku === sku)?.quantity ?? 0
      const next = await setStarCartItem(sku, current + 1)
      setCart(next)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update cart.')
    } finally {
      setBusy(false)
    }
  }

  async function onClear() {
    setBusy(true)
    setError(null)
    try {
      setCart(await clearStarCart())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not clear cart.')
    } finally {
      setBusy(false)
    }
  }

  async function onCheckout() {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await checkoutStarCart()
      setNotice('Checkout complete.')
      await reloadWeb()
    } catch (err) {
      // Expected until payments ship.
      setNotice(err instanceof ApiError ? err.message : 'Checkout is not available yet.')
    } finally {
      setBusy(false)
    }
  }

  async function onNativeBuy(productId: string) {
    if (purchaseLock.current || busy) return
    purchaseLock.current = true
    setBusy(true)
    setBuyingProductId(productId)
    setError(null)
    setNotice(null)
    setFlowState('purchasing')
    try {
      const { result, state, message } = await purchaseStarsPack(productId)
      setFlowState(state === 'purchasing' ? 'confirming' : state)
      if (state === 'cancelled') {
        setFlowState('available')
        setNotice('Purchase cancelled.')
        return
      }
      const text = stateMessage(state, message)
      if (state === 'success' || state === 'already_processed') {
        setNotice(text)
        void refreshUser()
        setFlowState('available')
      } else if (text) {
        if (state === 'gate_off' || state === 'unavailable') {
          setNotice(text)
        } else {
          setError(text)
        }
        setFlowState(state === 'recovery_required' ? 'recovery_required' : 'available')
      }
      if (result?.ai_stars != null) {
        void refreshUser()
      }
    } finally {
      setBusy(false)
      setBuyingProductId(null)
      purchaseLock.current = false
    }
  }

  const unlimited = Boolean(user?.ai_stars_unlimited)
  const balance = unlimited ? '∞' : String(user?.ai_stars ?? 0)

  return (
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-label="Stars shop"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <div className={styles.titleRow}>
            <ShoppingBag size={18} aria-hidden />
            <h2>Stars shop</h2>
          </div>
          <button type="button" className={styles.close} aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </header>

        <p className={styles.balance}>
          <Star size={14} aria-hidden /> Your balance: <strong>{balance}</strong>
          {unlimited ? ' (unlimited)' : null}
        </p>

        {nativeIos ? (
          <>
            <p className={styles.hint}>
              Stars power your AI fashion creations. Choose a package below to get started.
            </p>
            <p className={styles.costs}>{costLine}</p>
            {flowState === 'loading_products' ? (
              <p className={styles.empty}>Loading App Store products…</p>
            ) : null}
            {flowState === 'unavailable' ? (
              <p className={styles.notice} role="status">
                Stars packages are not available from the App Store right now.
              </p>
            ) : null}
            {flowState === 'gate_off' || (iapStatus && !iapStatus.purchasing_enabled) ? (
              <p className={styles.comingSoon} role="status">
                Apple Stars purchasing is prepared but not enabled yet. Your balance still works for
                existing Stars.
              </p>
            ) : null}
            <section className={styles.section}>
              <h3>Packages</h3>
              <ul className={styles.list}>
                {iapProducts.map((pkg) => (
                  <li key={pkg.productId} className={styles.card}>
                    <div>
                      <div className={styles.pkgName}>{pkg.title}</div>
                      <div className={styles.pkgMeta}>
                        {pkg.stars} Stars
                        {pkg.priceString ? <> · {pkg.priceString}</> : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={styles.addBtn}
                      disabled={
                        busy ||
                        flowState === 'purchasing' ||
                        flowState === 'confirming' ||
                        !iapStatus?.purchasing_enabled
                      }
                      onClick={() => void onNativeBuy(pkg.productId)}
                    >
                      {buyingProductId === pkg.productId &&
                      (flowState === 'purchasing' || flowState === 'confirming')
                        ? 'Buying…'
                        : 'Buy'}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
            {flowState === 'recovery_required' ? (
              <p className={styles.notice} role="status">
                Confirmation pending. Close and reopen the shop, or restart the app, to recover
                Stars if they do not appear.
              </p>
            ) : null}
          </>
        ) : (
          <>
            <p className={styles.hint}>
              Stars power your AI fashion creations. Choose a package below to get started.
              {nativeAndroid
                ? ' Google Play Stars purchasing is not available yet.'
                : ' Packages are listed now; web checkout opens later. On iOS, buy Stars in the App Store app.'}
            </p>
            <p className={styles.costs}>{costLine}</p>

            <section className={styles.section}>
              <h3>Packages</h3>
              <ul className={styles.list}>
                {packages.map((pkg) => (
                  <li key={pkg.sku} className={styles.card}>
                    <div>
                      <div className={styles.pkgName}>{pkg.name}</div>
                      <div className={styles.pkgMeta}>
                        {pkg.stars} Stars · {formatUsdCents(pkg.price_usd_cents)}
                        {pkg.list_price_usd_cents != null &&
                        pkg.list_price_usd_cents > pkg.price_usd_cents ? (
                          <>
                            {' '}
                            <s>{formatUsdCents(pkg.list_price_usd_cents)}</s>
                          </>
                        ) : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={styles.addBtn}
                      disabled={busy || nativeAndroid}
                      onClick={() => void onAdd(pkg.sku)}
                    >
                      Add
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            {!nativeAndroid ? (
              <section className={styles.section}>
                <h3>Cart</h3>
                {!cart?.items.length ? (
                  <p className={styles.empty}>Cart is empty.</p>
                ) : (
                  <ul className={styles.list}>
                    {cart.items.map((item) => (
                      <li key={item.package_sku} className={styles.cartLine}>
                        <span>
                          {item.name} × {item.quantity}
                        </span>
                        <span>
                          {item.stars_line} Stars · {formatUsdCents(item.price_usd_cents_line)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {cart ? (
                  <div className={styles.totals}>
                    <span>Total: {cart.stars_total} Stars</span>
                    <span>{formatUsdCents(cart.price_usd_cents_total)}</span>
                  </div>
                ) : null}
                <div className={styles.actions}>
                  <button
                    type="button"
                    className={styles.secondary}
                    disabled={busy || !cart?.items.length}
                    onClick={() => void onClear()}
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    className={styles.primary}
                    disabled={busy || !cart?.items.length}
                    onClick={() => void onCheckout()}
                    title={cart?.checkout_note || 'Checkout'}
                  >
                    Checkout
                  </button>
                </div>
                {cart?.checkout_note ? <p className={styles.comingSoon}>{cart.checkout_note}</p> : null}
              </section>
            ) : null}
          </>
        )}

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {notice ? <p className={styles.notice}>{notice}</p> : null}
      </div>
    </div>
  )
}
