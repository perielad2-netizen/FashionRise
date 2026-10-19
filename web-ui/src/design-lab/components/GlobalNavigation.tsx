import { BookOpen, Compass, Home, Images, Sparkles } from 'lucide-react'
import { DESIGN_LAB_BRAND_MARK } from '@/design-lab/designLabAssets'
import styles from './GlobalNavigation.module.css'

const ITEMS = [
  { id: 'home', label: 'Home', icon: Home, active: false },
  { id: 'create', label: 'Create', icon: Sparkles, active: true },
  { id: 'book', label: 'Design Book', icon: BookOpen, active: false },
  { id: 'discover', label: 'Discover', icon: Compass, active: false },
  { id: 'looks', label: 'My Looks', icon: Images, active: false },
] as const

export function GlobalNavigation() {
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
              tabIndex={-1}
              aria-current={item.active ? 'page' : undefined}
              aria-disabled
            >
              <Icon size={18} strokeWidth={1.75} />
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>
      <div className={styles.brandPanel} aria-hidden>
        <img
          src="/assets/ui/design-lab/models/croquis-female-05.png"
          alt=""
          className={styles.brandPhoto}
          draggable={false}
        />
        <p className={styles.brandCopy}>Fashion is your superpower</p>
        <img src={DESIGN_LAB_BRAND_MARK} alt="" className={styles.brandMark} draggable={false} />
      </div>
    </nav>
  )
}
