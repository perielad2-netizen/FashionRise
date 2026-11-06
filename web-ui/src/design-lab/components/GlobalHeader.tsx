import type { ReactNode } from 'react'
import { ChevronDown, Settings, UserRound } from 'lucide-react'
import { DESIGN_LAB_BRAND_MARK } from '@/design-lab/designLabAssets'
import styles from './GlobalHeader.module.css'

type Props = {
  leading?: ReactNode
}

export function GlobalHeader({ leading }: Props) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        {leading}
        <img src={DESIGN_LAB_BRAND_MARK} alt="" className={styles.mark} draggable={false} />
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
        <button type="button" className={styles.studioBtn} tabIndex={-1} aria-disabled>
          <span>My Studio</span>
          <ChevronDown size={14} />
        </button>
        <button
          type="button"
          className={styles.settingsBtn}
          tabIndex={-1}
          aria-label="Settings"
          aria-disabled
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  )
}
