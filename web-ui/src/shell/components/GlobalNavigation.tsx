import { BookOpen, Compass, Home, Images, Sparkles } from 'lucide-react'
import styles from './GlobalNavigation.module.css'

const ITEMS = [
  { id: 'home', label: 'Home', icon: Home, active: false, available: false },
  { id: 'create', label: 'Create', icon: Sparkles, active: true, available: true },
  { id: 'book', label: 'Design Book', icon: BookOpen, active: false, available: false },
  { id: 'discover', label: 'Discover', icon: Compass, active: false, available: false },
  { id: 'looks', label: 'My Looks', icon: Images, active: false, available: false },
] as const

type Props = {
  onComingSoon?: (label: string) => void
}

export function GlobalNavigation({ onComingSoon }: Props) {
  return (
    <nav className={styles.nav} aria-label="FashionRise">
      <div className={styles.items}>
        {ITEMS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              className={item.active ? styles.itemActive : styles.item}
              aria-current={item.active ? 'page' : undefined}
              aria-disabled={!item.available}
              disabled={!item.available}
              title={item.available ? item.label : `${item.label} — coming later`}
              onClick={() => {
                if (!item.available) onComingSoon?.(item.label)
              }}
            >
              <Icon size={18} strokeWidth={1.75} />
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
