import { useState, type ReactNode } from 'react'
import { ChevronDown, LogOut, Settings, UserRound } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import styles from './GlobalHeader.module.css'

type Props = {
  leading?: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
}

export function GlobalHeader({ leading, username, onLogout, onComingSoon }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        {leading}
        <img src={UI_ASSETS.brand.mark} alt="" className={styles.mark} draggable={false} />
        <p className={styles.wordmark}>FashionRise</p>
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
          aria-label="Settings"
          onClick={() => onComingSoon?.('Settings')}
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  )
}
