import { FolderHeart, Home, Images, Sparkles, Star, UserRound } from 'lucide-react'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import styles from './GlobalNavigation.module.css'

export type NavDestination = 'home' | 'create' | 'designs' | 'looks' | 'croquis' | 'fashion-stars'

const BASE_ITEMS = [
  { id: 'home', label: 'Home', icon: Home, destination: 'home' as NavDestination | null },
  { id: 'create', label: 'Create', icon: Sparkles, destination: 'create' as NavDestination | null },
  {
    id: 'designs',
    label: 'My Designs',
    icon: FolderHeart,
    destination: 'designs' as NavDestination | null,
  },
  {
    id: 'croquis',
    label: 'My Models',
    icon: UserRound,
    destination: 'croquis' as NavDestination | null,
    requiresMyCroquis: true,
  },
  {
    id: 'fashion-stars',
    label: 'Fashion Stars',
    icon: Star,
    destination: 'fashion-stars' as NavDestination | null,
  },
  { id: 'looks', label: 'My Looks', icon: Images, destination: 'looks' as NavDestination | null },
]

type Props = {
  current?: NavDestination
  onNavigate?: (destination: NavDestination) => void
  onComingSoon?: (label: string) => void
}

export function GlobalNavigation({ current = 'create', onNavigate, onComingSoon }: Props) {
  const croquisEnabled = isMyCroquisUiEnabled()
  const items = BASE_ITEMS.filter((item) => !('requiresMyCroquis' in item && item.requiresMyCroquis) || croquisEnabled)
  return (
    <nav className={styles.nav} aria-label="FashionRise">
      <div className={styles.items}>
        {items.map((item) => {
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
