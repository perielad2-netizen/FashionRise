import { LogOut } from 'lucide-react'
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
          src="/branding/fashion_rise_logo.png"
          alt=""
          className={styles.logo}
          width={48}
          height={48}
        />
        <div className={styles.brandText}>
          <div className={styles.wordmark}>
            <span className={styles.fr}>FR</span>
            <span className={styles.name}>
              Fashion<span>Rise</span>
            </span>
          </div>
          <p className={styles.context}>New Design · Creator Studio</p>
        </div>
      </div>

      <p className={styles.motto} aria-hidden>
        Dream · Sketch · Create
      </p>

      <div className={styles.actions}>
        <span className={styles.saved}>{savedLabel}</span>
        <button type="button" className={styles.magic} onClick={onMagic}>
          <img src="/assets/ui/icons/fr_icon_magic.png" alt="" className={styles.magicIcon} draggable={false} />
          Magic
        </button>
        <div className={styles.user}>
          <span className={styles.avatar} aria-hidden>
            <img src="/assets/ui/icons/fr_icon_profile.png" alt="" className={styles.avatarIcon} draggable={false} />
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
