import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, ShoppingBag, Smartphone, Star, X } from 'lucide-react'
import { MOBILE_STORE_LINKS } from '@/config/mobileStoreLinks'
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
import { isNativeShell } from '@/services/native/platform'
import { fetchStarPackages, formatUsdCents, type StarPackage } from '@/services/starsShopApi'
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
  // Capacitor-only detection (`@/services/native/platform`). Safari / Chrome / PWA stay web.
  const nativeIos = isNativeIosStarsShop()
  const nativeAndroid = isNativeAndroidShell()
  const isWebRuntime = !isNativeShell()
  const costLine = `Magic: ${costs.magic} Stars · Model: ${costs.croquis} Stars · Fabric: ${costs.fabric} Stars · PDF: ${costs.pdf} Stars`

  const [packages, setPackages] = useState<StarPackage[]>([])
  const [iapProducts, setIapProducts] = useState<StarsIapProduct[]>([])
  const [iapStatus, setIapStatus] = useState<AppleIapStatus | null>(null)
  const [busy, setBusy] = useState(false)
  /** Only the tapped package shows “Buying…” — other packs stay labeled Buy (disabled). */
  const [buyingProductId, setBuyingProductId] = useState<string | null>(null)
  const [flowState, setFlowState] = useState<PurchaseFlowState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const purchaseLock = useRef(false)

  const reloadAndroidCatalog = useCallback(async () => {
    setError(null)
    const pkgs = await fetchStarPackages()
    setPackages(pkgs)
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
        } else if (nativeAndroid) {
          // Native Android keeps current catalog preview; Play Billing is a future task.
          await reloadAndroidCatalog()
        } else {
          // Browser / mobile browser / installed PWA — balance only; no purchase APIs.
          setPackages([])
          setIapProducts([])
          setIapStatus(null)
          setError(null)
          void refreshUser()
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
  }, [open, nativeIos, nativeAndroid, reloadNativeIos, reloadAndroidCatalog, refreshUser])

  if (!open) return null

  async function onNativeBuy(productId: string) {
    // Hard boundary: StoreKit purchase only on Capacitor iOS.
    if (!nativeIos || isWebRuntime || nativeAndroid) return
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

  // Portal to body so GlobalHeader stacking/background cannot clip the shop title
  // when opened from the yellow Stars badge inside the header.
  return createPortal(
    <div
      className={styles.backdrop}
      role="presentation"
      data-testid="stars-shop-backdrop"
      onClick={onClose}
    >
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-label="Stars shop"
        data-testid="stars-shop-modal"
        data-platform={nativeIos ? 'ios' : nativeAndroid ? 'android' : 'web'}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.handle} aria-hidden />
        <header className={styles.header}>
          <div className={styles.brandBlock}>
            <p className={styles.eyebrow}>FashionRise</p>
            <div className={styles.titleRow}>
              <ShoppingBag size={18} aria-hidden />
              <h2>Stars shop</h2>
            </div>
          </div>
          <button type="button" className={styles.close} aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </header>

        <div className={styles.balanceHero}>
          <div className={styles.balanceGlow} aria-hidden />
          <p className={styles.balanceLabel}>
            <Star size={14} aria-hidden /> Your balance:
          </p>
          <p className={styles.balanceValue}>
            <strong>{balance}</strong>
          </p>
          <p className={styles.balanceSub}>
            {unlimited ? '(unlimited)' : 'Ready for Magic, Model, Fabric & PDF'}
          </p>
        </div>

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
                    <div className={styles.packTop}>
                      <div>
                        <div className={styles.packStars}>{pkg.stars}</div>
                        <div className={styles.pkgName}>{pkg.title}</div>
                        <div className={styles.pkgMeta}>
                          {pkg.stars} Stars
                          {pkg.priceString ? <> · {pkg.priceString}</> : null}
                        </div>
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
        ) : nativeAndroid ? (
          <>
            <p className={styles.hint}>
              Stars power your AI fashion creations. Choose a package below to get started. Google
              Play Stars purchasing is not available yet.
            </p>
            <p className={styles.costs}>{costLine}</p>

            <section className={styles.section} data-testid="stars-android-packages">
              <h3>Packages</h3>
              <ul className={styles.list}>
                {packages.map((pkg) => (
                  <li key={pkg.sku} className={styles.card}>
                    <div className={styles.packTop}>
                      <div>
                        <div className={styles.packStars}>{pkg.stars}</div>
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
                    </div>
                    <button
                      type="button"
                      className={styles.addBtn}
                      disabled
                      aria-disabled="true"
                      title="Google Play Stars purchasing is not available yet"
                    >
                      Add
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </>
        ) : (
          <>
            <p className={styles.hint}>
              Stars power your AI fashion creations. Your balance works the same on web and in the
              mobile apps.
            </p>
            <p className={styles.costs}>{costLine}</p>

            <section
              className={styles.section}
              data-testid="stars-web-store-panel"
              aria-labelledby="fr-get-more-stars"
            >
              <div className={styles.webStorePanel}>
                <div className={styles.webStoreIcon} aria-hidden>
                  <Smartphone size={22} />
                </div>
                <h3 id="fr-get-more-stars" className={styles.webStoreHeading}>
                  Get more Stars
                </h3>
                <p className={styles.webStoreLead}>
                  Stars can only be purchased through the FashionRise mobile app.
                </p>
                <p className={styles.webStoreSync}>
                  Sign in with the same FashionRise account to use your Stars across devices.
                </p>
                <ul className={styles.storeOptions}>
                  {MOBILE_STORE_LINKS.map((store) => {
                    const available = store.availability === 'available' && Boolean(store.href)
                    return (
                      <li
                        key={store.id}
                        className={`${styles.storeCard} ${
                          available ? styles.storeCardAvailable : styles.storeCardSoon
                        }`}
                        data-testid={`stars-store-${store.id}`}
                        data-availability={store.availability}
                      >
                        <div className={styles.storeCardBody}>
                          <div className={styles.storeCardTitle}>{store.title}</div>
                          <div className={styles.storeCardSub}>{store.subtitle}</div>
                        </div>
                        {available && store.href ? (
                          <a
                            className={styles.storeLink}
                            href={store.href}
                            target="_blank"
                            rel="noopener noreferrer"
                            data-testid={`stars-store-link-${store.id}`}
                          >
                            Open
                            <ExternalLink size={14} aria-hidden />
                          </a>
                        ) : (
                          <span
                            className={styles.storeBadge}
                            data-testid={`stars-store-badge-${store.id}`}
                          >
                            Coming soon
                          </span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </div>
            </section>
          </>
        )}

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {notice ? <p className={styles.notice}>{notice}</p> : null}
      </div>
    </div>,
    document.body,
  )
}
