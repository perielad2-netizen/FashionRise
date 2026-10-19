import { useState, type ReactNode } from 'react'
import { Menu, X } from 'lucide-react'
import { GlobalHeader } from '@/design-lab/components/GlobalHeader'
import { GlobalNavigation } from '@/design-lab/components/GlobalNavigation'
import styles from './FashionRiseAppShell.module.css'

type Props = {
  children: ReactNode
}

export function FashionRiseAppShell({ children }: Props) {
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className={styles.shell}>
      <GlobalHeader
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
          <GlobalNavigation />
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
