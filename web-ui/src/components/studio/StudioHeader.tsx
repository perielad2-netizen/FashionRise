import { LogOut } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import styles from './StudioHeader.module.css'

type Props = {
  username: string
  savedLabel: string
  onMagic: () => void
  onLogout: () => void
}

export function StudioHeader({ username, savedLabel, onMagic, onLogout }: Props) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <img
          src={UI_ASSETS.brand.logo}
          alt="FashionRise"
          className={styles.logo}
          width={56}
          height={56}
          draggable={false}
        />
        <div className={styles.brandText}>
          <p className={styles.name}>
            Fashion<span>Rise</span>
          </p>
          <p className={styles.context}>Creator Studio</p>
        </div>
      </div>

      <p className={styles.motto} aria-hidden>
        Dream · Sketch · Create
      </p>

      <div className={styles.actions}>
        <span className={styles.saved}>{savedLabel}</span>
        <button type="button" className={styles.magic} onClick={onMagic}>
          <img
            src={UI_ASSETS.header.magic}
            alt=""
            className={styles.magicIcon}
            draggable={false}
          />
          Magic
        </button>
        <div className={styles.user}>
          <span className={styles.avatar} aria-hidden>
            <img
              src={UI_ASSETS.header.profile}
              alt=""
              className={styles.avatarIcon}
              draggable={false}
            />
          </span>
          <span className={styles.userName}>{username}</span>
          <button type="button" className={styles.logout} onClick={onLogout} aria-label="Sign out">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  )
}
