import { useEffect, useState, type ReactNode } from 'react'
import { Menu, X } from 'lucide-react'
import { GlobalHeader } from '@/shell/components/GlobalHeader'
import { GlobalNavigation, type NavDestination } from '@/shell/components/GlobalNavigation'
import styles from './FashionRiseAppShell.module.css'

type Props = {
  children: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
  currentNav?: NavDestination
  onNavigate?: (destination: NavDestination) => void
}

export function FashionRiseAppShell({
  children,
  username,
  onLogout,
  onComingSoon,
  currentNav,
  onNavigate,
}: Props) {
  const [navOpen, setNavOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)

  function setNav(next: boolean) {
    if (next) setAccountMenuOpen(false)
    setNavOpen(next)
  }

  function setAccountMenu(next: boolean) {
    if (next) setNavOpen(false)
    setAccountMenuOpen(next)
  }

  useEffect(() => {
    if (!navOpen && !accountMenuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setNavOpen(false)
      setAccountMenuOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [navOpen, accountMenuOpen])

  return (
    <div className={styles.shell} data-testid="fashionrise-app-shell">
      <GlobalHeader
        username={username}
        onLogout={onLogout}
        onComingSoon={onComingSoon}
        accountMenuOpen={accountMenuOpen}
        onAccountMenuOpenChange={setAccountMenu}
        leading={
          <button
            type="button"
            className={styles.menuBtn}
            data-testid="shell-nav-toggle"
            onClick={() => setNav(!navOpen)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={navOpen}
          >
            {navOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        }
      />
      <div className={styles.body}>
        <div className={`${styles.navSlot} ${navOpen ? styles.navOpen : ''}`}>
          <GlobalNavigation
            current={currentNav}
            onComingSoon={onComingSoon}
            onNavigate={(destination) => {
              setNav(false)
              setAccountMenu(false)
              onNavigate?.(destination)
            }}
          />
        </div>
        {navOpen ? (
          <button
            type="button"
            className={styles.scrim}
            aria-label="Close navigation"
            data-testid="shell-nav-scrim"
            onClick={() => setNav(false)}
          />
        ) : null}
        <div className={styles.main}>{children}</div>
      </div>
    </div>
  )
}
