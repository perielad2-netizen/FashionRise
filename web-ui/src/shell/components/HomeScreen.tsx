import { FolderHeart, Images, Sparkles, Star, UserRound } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import type { NavDestination } from '@/shell/components/GlobalNavigation'
import styles from './HomeScreen.module.css'

type Props = {
  username: string
  onNavigate: (destination: NavDestination) => void
}

const DESTINATIONS: Array<{
  id: NavDestination
  label: string
  hint: string
  icon: typeof Sparkles
  requiresMyCroquis?: boolean
}> = [
  {
    id: 'create',
    label: 'Create',
    hint: 'Open the sketch studio and start a new design',
    icon: Sparkles,
  },
  {
    id: 'designs',
    label: 'My Designs',
    hint: 'Saved sketches and working drafts',
    icon: FolderHeart,
  },
  {
    id: 'looks',
    label: 'My Looks',
    hint: 'Magic looks, try-ons, and tech packs',
    icon: Images,
  },
  {
    id: 'runway',
    label: 'Runway',
    hint: 'FashionRise Runway — share, like, and score looks',
    icon: Star,
  },
  {
    id: 'croquis',
    label: 'My Models',
    hint: 'Personal croquis for try-on and sketching',
    icon: UserRound,
    requiresMyCroquis: true,
  },
]

export function HomeScreen({ username, onNavigate }: Props) {
  const croquisEnabled = isMyCroquisUiEnabled()
  const firstName = username.trim().split(/\s+/)[0] || 'Creator'
  const destinations = DESTINATIONS.filter(
    (item) => !item.requiresMyCroquis || croquisEnabled,
  )

  return (
    <section className={styles.screen} aria-labelledby="home-brand">
      <header className={styles.hero}>
        <div className={styles.logoPlate}>
          <img
            src={UI_ASSETS.brand.login}
            alt=""
            className={styles.logo}
            draggable={false}
          />
        </div>
        <div className={styles.copy}>
          <p className={styles.greeting}>Welcome back, {firstName}</p>
          <h1 id="home-brand" className={styles.brand}>
            Fashion<span>Rise</span>
          </h1>
          <p className={styles.tagline}>Sketch a garment. Turn it into a Magic look.</p>
          <p className={styles.lead}>
            Draw on a fashion figure in the studio, then generate an AI Magic look from your
            sketch — or jump back into saved designs, looks, and models.
          </p>
          <button
            type="button"
            className={styles.primaryCta}
            onClick={() => onNavigate('create')}
            data-testid="home-start-creating"
          >
            <Sparkles size={18} aria-hidden />
            Start creating
          </button>
        </div>
      </header>

      <nav className={styles.destinations} aria-label="Studio destinations">
        {destinations.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              className={styles.destination}
              onClick={() => onNavigate(item.id)}
            >
              <span className={styles.destinationIcon} aria-hidden>
                <Icon size={18} strokeWidth={1.75} />
              </span>
              <span className={styles.destinationText}>
                <span className={styles.destinationLabel}>{item.label}</span>
                <span className={styles.destinationHint}>{item.hint}</span>
              </span>
            </button>
          )
        })}
      </nav>
    </section>
  )
}
