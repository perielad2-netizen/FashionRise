import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import {
  ChevronDown,
  LogOut,
  Mail,
  Settings,
  Star,
  Trash2,
  UserRound,
  X,
} from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { CONTACT_EMAIL, openContactMail } from '@/lib/contact'
import { useAiStarsWallet } from '@/hooks/useAiStarsWallet'
import { deleteAccount } from '@/services/auth/authApi'
import {
  isNativeAndroidShell,
  isNativeIosStarsShop,
} from '@/services/native/iap'
import { StarsShopModal } from '@/shell/components/StarsShopModal'
import styles from './GlobalHeader.module.css'

type Props = {
  leading?: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
  /** Controlled account menu — shell coordinates with nav drawer. */
  accountMenuOpen?: boolean
  onAccountMenuOpenChange?: (open: boolean) => void
}

type Panel = 'settings' | 'about' | 'contact' | 'delete' | 'stars' | null

function opsFor(balance: number | null, unlimited: boolean, cost: number): string {
  if (unlimited) return 'Unlimited'
  if (cost <= 0) return '—'
  const b = Math.max(0, Number(balance ?? 0))
  return String(Math.floor(b / cost))
}

export function GlobalHeader({
  leading,
  username,
  onLogout,
  accountMenuOpen: accountMenuOpenProp,
  onAccountMenuOpenChange,
}: Props) {
  const [menuOpenInternal, setMenuOpenInternal] = useState(false)
  const menuOpen = accountMenuOpenProp ?? menuOpenInternal
  const setMenuOpen = (next: boolean) => {
    onAccountMenuOpenChange?.(next)
    if (accountMenuOpenProp === undefined) setMenuOpenInternal(next)
  }

  const [panel, setPanel] = useState<Panel>(null)
  const [shopOpen, setShopOpen] = useState(false)
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [replyEmail, setReplyEmail] = useState('')
  const [sentHint, setSentHint] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const subjectId = useId()
  const messageId = useId()
  const replyId = useId()
  const deleteConfirmId = useId()
  const menuWrapRef = useRef<HTMLDivElement>(null)
  const { balance, unlimited, costs, reload } = useAiStarsWallet()

  const nativeIos = isNativeIosStarsShop()
  const nativeAndroid = isNativeAndroidShell()

  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (e: MouseEvent) => {
      if (!menuWrapRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuOpen])

  function openContact() {
    setMenuOpen(false)
    setSentHint(null)
    setPanel('contact')
  }

  function openStarsBilling() {
    setMenuOpen(false)
    void reload()
    setPanel('stars')
  }

  function openDeleteAccount() {
    setMenuOpen(false)
    setDeleteConfirm('')
    setDeleteError(null)
    setDeleteBusy(false)
    setPanel('delete')
  }

  function closePanel() {
    if (deleteBusy) return
    setPanel(null)
    setSentHint(null)
    setDeleteError(null)
  }

  function openShopFromHeader() {
    setMenuOpen(false)
    setPanel(null)
    setShopOpen(true)
  }

  function onSubmitContact(event: FormEvent) {
    event.preventDefault()
    const trimmedMessage = message.trim()
    if (!trimmedMessage) return
    openContactMail({
      subject,
      message: trimmedMessage,
      replyEmail,
      username,
    })
    setSentHint(`Opening your email app to message ${CONTACT_EMAIL}.`)
  }

  async function onConfirmDelete(event: FormEvent) {
    event.preventDefault()
    if (deleteConfirm.trim() !== 'DELETE' || deleteBusy) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await deleteAccount()
      setPanel(null)
      onLogout()
    } catch (err) {
      const msg =
        typeof err === 'object' && err && 'message' in err
          ? String((err as { message?: string }).message || '')
          : ''
      setDeleteError(msg || 'Could not delete account. Try again or email support.')
      setDeleteBusy(false)
    }
  }

  const starsLabel = unlimited
    ? '∞'
    : Number(balance ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })
  const purchaseNote = nativeIos
    ? 'Buy Stars with Apple In‑App Purchase when purchasing is enabled for this build.'
    : nativeAndroid
      ? 'Google Play Billing for Stars is not available yet. Your current balance still works for AI features.'
      : 'Web checkout for Stars is not open yet. On iPhone, buy Stars in the FashionRise iOS app when enabled.'

  return (
    <header className={`${styles.header} ${menuOpen ? styles.headerMenuOpen : ''}`}>
      <div className={styles.brand}>
        {leading}
        <img src={UI_ASSETS.brand.mark} alt="" className={styles.mark} draggable={false} />
        <p className={styles.wordmark}>
          Fashion<span>Rise</span>
        </p>
      </div>
      <p className={styles.tagline} aria-hidden>
        Dream <span className={styles.plus}>+</span> Sketch{' '}
        <span className={styles.plus}>+</span> Create
      </p>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.starsBadge}
          data-testid="global-stars-badge"
          onClick={openShopFromHeader}
          title={
            unlimited
              ? 'Unlimited Stars — open Stars Shop'
              : `${starsLabel} Stars — Magical looks, models, fabric & PDF. Tap to buy or view.`
          }
          aria-label={
            unlimited ? 'Unlimited Stars, open Stars Shop' : `${starsLabel} Stars, open Stars Shop`
          }
        >
          <Star size={14} aria-hidden />
          <span>{starsLabel}</span>
        </button>
        <span className={styles.avatar} aria-hidden>
          <UserRound size={16} />
        </span>
        <div className={styles.menuWrap} ref={menuWrapRef}>
          <button
            type="button"
            className={styles.studioBtn}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            data-testid="global-account-menu"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <span>My Studio</span>
            <ChevronDown size={14} />
          </button>
          {menuOpen ? (
            <div className={styles.menu} role="menu" data-testid="global-account-menu-panel">
              <p className={styles.menuUser}>{username}</p>
              <button
                type="button"
                role="menuitem"
                className={styles.menuItem}
                data-testid="menu-stars-billing"
                onClick={openStarsBilling}
              >
                <Star size={14} />
                My Stars &amp; Billing
              </button>
              <button
                type="button"
                role="menuitem"
                className={styles.menuItem}
                onClick={openContact}
              >
                <Mail size={14} />
                Contact us
              </button>
              <button
                type="button"
                role="menuitem"
                className={styles.menuItem}
                onClick={() => {
                  setMenuOpen(false)
                  onLogout()
                }}
              >
                <LogOut size={14} />
                Sign out
              </button>
              <button
                type="button"
                role="menuitem"
                className={`${styles.menuItem} ${styles.menuItemDanger}`}
                onClick={openDeleteAccount}
              >
                <Trash2 size={14} />
                Delete account
              </button>
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className={styles.settingsBtn}
          aria-label="Settings"
          title="Settings"
          data-testid="global-settings"
          onClick={() => {
            setMenuOpen(false)
            setSentHint(null)
            setPanel('settings')
          }}
        >
          <Settings size={16} />
        </button>
      </div>

      {panel === 'settings' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={styles.aboutCard}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-settings-title"
            data-testid="global-settings-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-settings-title">Settings</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close settings"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              App information and account helpers. Studio canvas preferences live in Studio → More →
              Settings.
            </p>
            <div className={styles.settingsList}>
              <button
                type="button"
                className={styles.settingsItem}
                onClick={() => setPanel('about')}
              >
                About FashionRise
              </button>
              <a className={styles.settingsItem} href="/privacy">
                Privacy Policy
              </a>
              <button type="button" className={styles.settingsItem} onClick={openContact}>
                Contact us
              </button>
              <button
                type="button"
                className={styles.settingsItem}
                onClick={() => {
                  void reload()
                  setPanel('stars')
                }}
              >
                My Stars &amp; Billing
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {panel === 'stars' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={`${styles.aboutCard} ${styles.contactCard}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-stars-title"
            data-testid="stars-billing-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-stars-title">My Stars &amp; Billing</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close Stars & Billing"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              Balance:{' '}
              <strong data-testid="stars-billing-balance">
                {unlimited ? 'Unlimited' : `${balance ?? 0} Stars`}
              </strong>
            </p>
            <p className={styles.aboutBody}>Current AI feature costs (from your account):</p>
            <ul className={styles.starsCostList}>
              <li>
                Magic look — {costs.magic} Stars
                {!unlimited ? ` · ~${opsFor(balance, unlimited, costs.magic)} with your balance` : ''}
              </li>
              <li>
                Create Model — {costs.croquis} Stars
                {!unlimited
                  ? ` · ~${opsFor(balance, unlimited, costs.croquis)} with your balance`
                  : ''}
              </li>
              <li>
                AI fabric — {costs.fabric} Stars
                {!unlimited
                  ? ` · ~${opsFor(balance, unlimited, costs.fabric)} with your balance`
                  : ''}
              </li>
              <li>
                Tech pack PDF — {costs.pdf} Stars
                {!unlimited ? ` · ~${opsFor(balance, unlimited, costs.pdf)} with your balance` : ''}
              </li>
            </ul>
            <p className={styles.aboutBody}>{purchaseNote}</p>
            <p className={styles.aboutBody}>
              In-app purchase history is not listed here yet. Store receipts stay with Apple or
              Google; FashionRise only keeps what is needed to credit Stars safely.
            </p>
            <div className={styles.contactActions}>
              <button type="button" className={styles.contactGhost} onClick={closePanel}>
                Close
              </button>
              <button
                type="button"
                className={styles.contactPrimary}
                data-testid="stars-billing-open-shop"
                onClick={() => {
                  setPanel(null)
                  setShopOpen(true)
                }}
              >
                <Star size={14} aria-hidden />
                Open Stars Shop
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {panel === 'about' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={styles.aboutCard}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-about-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-about-title">About FashionRise</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close about"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              Dream, sketch, and create looks in your personal FashionRise studio.
            </p>
            <p className={styles.aboutBody}>
              Questions or feedback? Email{' '}
              <a className={styles.contactLink} href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              .
            </p>
            <p className={styles.aboutBody}>
              <a className={styles.contactLink} href="/privacy">
                Privacy Policy
              </a>
            </p>
            <button type="button" className={styles.contactPrimary} onClick={openContact}>
              <Mail size={14} aria-hidden />
              Contact us
            </button>
          </div>
        </div>
      ) : null}

      {panel === 'contact' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={`${styles.aboutCard} ${styles.contactCard}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-contact-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-contact-title">Contact us</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close contact"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              Send a note to{' '}
              <a className={styles.contactLink} href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              . Your mail app opens with the message ready to send.
            </p>
            <form className={styles.contactForm} onSubmit={onSubmitContact}>
              <label className={styles.contactLabel} htmlFor={subjectId}>
                Subject
              </label>
              <input
                id={subjectId}
                className={styles.contactInput}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={120}
                placeholder="How can we help?"
                autoComplete="off"
              />
              <label className={styles.contactLabel} htmlFor={messageId}>
                Message
              </label>
              <textarea
                id={messageId}
                className={styles.contactTextarea}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={4000}
                rows={5}
                required
                placeholder="Tell us what’s going on…"
              />
              <label className={styles.contactLabel} htmlFor={replyId}>
                Your email (optional)
              </label>
              <input
                id={replyId}
                className={styles.contactInput}
                type="email"
                value={replyEmail}
                onChange={(e) => setReplyEmail(e.target.value)}
                maxLength={200}
                placeholder="so we can reply"
                autoComplete="email"
              />
              {sentHint ? (
                <p className={styles.contactHint} role="status">
                  {sentHint}
                </p>
              ) : null}
              <div className={styles.contactActions}>
                <button type="button" className={styles.contactGhost} onClick={closePanel}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.contactPrimary}
                  disabled={!message.trim()}
                >
                  <Mail size={14} aria-hidden />
                  Send message
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {panel === 'delete' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={`${styles.aboutCard} ${styles.contactCard}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-delete-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-delete-title">Delete account</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close delete account"
                onClick={closePanel}
                disabled={deleteBusy}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              This permanently deletes your FashionRise account, designs, looks, and related data.
              Stars balance tied to this account is removed. Store receipts remain with Apple or
              Google. This cannot be undone.
            </p>
            <form className={styles.contactForm} onSubmit={onConfirmDelete}>
              <label className={styles.contactLabel} htmlFor={deleteConfirmId}>
                Type DELETE to confirm
              </label>
              <input
                id={deleteConfirmId}
                className={styles.contactInput}
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                autoComplete="off"
                disabled={deleteBusy}
                placeholder="DELETE"
              />
              {deleteError ? (
                <p className={styles.deleteError} role="alert">
                  {deleteError}
                </p>
              ) : null}
              <div className={styles.contactActions}>
                <button
                  type="button"
                  className={styles.contactGhost}
                  onClick={closePanel}
                  disabled={deleteBusy}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.deletePrimary}
                  disabled={deleteBusy || deleteConfirm.trim() !== 'DELETE'}
                >
                  <Trash2 size={14} aria-hidden />
                  {deleteBusy ? 'Deleting…' : 'Delete account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      <StarsShopModal
        open={shopOpen}
        onClose={() => {
          setShopOpen(false)
          void reload()
        }}
      />
    </header>
  )
}
