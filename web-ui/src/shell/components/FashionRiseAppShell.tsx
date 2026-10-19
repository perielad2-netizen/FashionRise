import { useState, type ReactNode } from 'react'
import { Menu, X } from 'lucide-react'
import { GlobalHeader } from '@/shell/components/GlobalHeader'
import { GlobalNavigation } from '@/shell/components/GlobalNavigation'
import styles from './FashionRiseAppShell.module.css'

type Props = {
  children: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
}

export function FashionRiseAppShell({ children, username, onLogout, onComingSoon }: Props) {
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className={styles.shell}>
      <GlobalHeader
        username={username}
        onLogout={onLogout}
        onComingSoon={onComingSoon}
        leading={
          <button
            type="button"
            className={styles.menuBtn}
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
          >
            {navOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        }
      />
      <div className={styles.body}>
        <div className={`${styles.navSlot} ${navOpen ? styles.navOpen : ''}`}>
          <GlobalNavigation onComingSoon={onComingSoon} />
        </div>
        {navOpen ? (
          <button
            type="button"
            className={styles.scrim}
            aria-label="Close navigation"
            onClick={() => setNavOpen(false)}
          />
        ) : null}
        <div className={styles.main}>{children}</div>
      </div>
    </div>
  )
}
