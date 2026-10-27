import { BookOpen, Compass, FolderHeart, Home, Images, Sparkles } from 'lucide-react'
import styles from './GlobalNavigation.module.css'

export type NavDestination = 'create' | 'designs' | 'looks'

const ITEMS = [
  { id: 'home', label: 'Home', icon: Home, destination: null },
  { id: 'create', label: 'Create', icon: Sparkles, destination: 'create' },
  { id: 'designs', label: 'My Designs', icon: FolderHeart, destination: 'designs' },
  { id: 'book', label: 'Design Book', icon: BookOpen, destination: null },
  { id: 'discover', label: 'Discover', icon: Compass, destination: null },
  { id: 'looks', label: 'My Looks', icon: Images, destination: 'looks' },
] as const

type Props = {
  current?: NavDestination
  onNavigate?: (destination: NavDestination) => void
  onComingSoon?: (label: string) => void
}

export function GlobalNavigation({ current = 'create', onNavigate, onComingSoon }: Props) {
  return (
    <nav className={styles.nav} aria-label="FashionRise">
      <div className={styles.items}>
        {ITEMS.map((item) => {
          const Icon = item.icon
          const available = item.destination !== null
          const active = available && item.destination === current
          return (
            <button
              key={item.id}
              type="button"
              className={active ? styles.itemActive : styles.item}
              aria-current={active ? 'page' : undefined}
              aria-disabled={!available}
              disabled={!available}
              title={available ? item.label : `${item.label} — coming later`}
              onClick={() => {
                if (item.destination === null) onComingSoon?.(item.label)
                else onNavigate?.(item.destination)
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
