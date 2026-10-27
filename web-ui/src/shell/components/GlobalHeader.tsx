import { useState, type ReactNode } from 'react'
import { ChevronDown, LogOut, Settings, UserRound, X } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import styles from './GlobalHeader.module.css'

const APP_VERSION =
  (import.meta.env.VITE_BUILD_SHA as string | undefined)?.slice(0, 8) ||
  (import.meta.env.VITE_APP_VERSION as string | undefined) ||
  'unknown'

type Props = {
  leading?: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
}

export function GlobalHeader({ leading, username, onLogout }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)

  return (
    <header className={styles.header}>
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
        <span className={styles.avatar} aria-hidden>
          <UserRound size={16} />
        </span>
        <div className={styles.menuWrap}>
          <button
            type="button"
            className={styles.studioBtn}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span>My Studio</span>
            <ChevronDown size={14} />
          </button>
          {menuOpen ? (
            <div className={styles.menu} role="menu">
              <p className={styles.menuUser}>{username}</p>
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
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className={styles.settingsBtn}
          aria-label="Settings and About"
          title="Settings / About"
          onClick={() => setAboutOpen(true)}
        >
          <Settings size={16} />
        </button>
      </div>
      {aboutOpen ? (
        <div
          className={styles.aboutScrim}
          role="presentation"
          onClick={() => setAboutOpen(false)}
        >
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
                onClick={() => setAboutOpen(false)}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>Private family-beta studio.</p>
            <dl className={styles.aboutMeta}>
              <div>
                <dt>Build</dt>
                <dd data-testid="global-app-version">{APP_VERSION}</dd>
              </div>
              <div>
                <dt>API</dt>
                <dd>/api/v1 (same origin)</dd>
              </div>
            </dl>
          </div>
        </div>
      ) : null}
    </header>
  )
}
