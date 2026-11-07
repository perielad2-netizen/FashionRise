import { useCallback, useEffect, useState } from 'react'
import { ShoppingBag, Star, X } from 'lucide-react'
import { ApiError } from '@/services/api/client'
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
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './StarsShopModal.module.css'

type Props = {
  open: boolean
  onClose: () => void
}

export function StarsShopModal({ open, onClose }: Props) {
  const { user, refreshUser } = useAuth()
  const [packages, setPackages] = useState<StarPackage[]>([])
  const [cart, setCart] = useState<StarCart | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setError(null)
    const [pkgs, nextCart] = await Promise.all([fetchStarPackages(), fetchStarCart()])
    setPackages(pkgs)
    setCart(nextCart)
    void refreshUser()
  }, [refreshUser])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    ;(async () => {
      try {
        await reload()
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Could not load Stars shop.')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, reload])

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
      await reload()
    } catch (err) {
      // Expected until payments ship.
      setNotice(err instanceof ApiError ? err.message : 'Checkout is not available yet.')
    } finally {
      setBusy(false)
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
        <p className={styles.hint}>
          Magic 10 · Model 10 · Fabric 5 · Professional PDF 50. Packages are listed now;
          checkout opens later.
        </p>

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
                  disabled={busy}
                  onClick={() => void onAdd(pkg.sku)}
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        </section>

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
            <button type="button" className={styles.secondary} disabled={busy || !cart?.items.length} onClick={() => void onClear()}>
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
