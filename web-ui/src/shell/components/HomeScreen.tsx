import { ChevronRight, FolderHeart, Images, Shirt, Sparkles, Star, UserRound } from 'lucide-react'
import { isFittingRoomUiEnabled } from '@/config/fittingRoomUi'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import type { NavDestination } from '@/shell/components/GlobalNavigation'
import { HomeBeforeAfterGallery } from '@/shell/components/HomeBeforeAfterGallery'
import type { AuthorizedHomeExample } from '@/shell/homeAuthorizedExamples'
import styles from './HomeScreen.module.css'

type Props = {
  username: string
  onNavigate: (destination: NavDestination) => void
  /** Test-only override for V2-0031 authorized examples. */
  homeExamples?: readonly AuthorizedHomeExample[]
}

const DESTINATIONS: Array<{
  id: NavDestination
  label: string
  hint: string
  icon: typeof Sparkles
  requiresMyCroquis?: boolean
  requiresFittingRoom?: boolean
}> = [
  {
    id: 'designs',
    label: 'My Designs',
    hint: 'Saved sketches and working drafts.',
    icon: FolderHeart,
  },
  {
    id: 'looks',
    label: 'My Looks',
    hint: 'Magic looks, try-ons, and tech packs.',
    icon: Images,
  },
  {
    id: 'croquis',
    label: 'My Models',
    hint: 'Personal croquis for try-on and sketching.',
    icon: UserRound,
    requiresMyCroquis: true,
  },
  {
    id: 'fitting-room',
    label: 'Fitting Room',
    hint: 'AI try-on with your photo and a clothing image.',
    icon: Shirt,
    requiresFittingRoom: true,
  },
]

export function HomeScreen({ username, onNavigate, homeExamples }: Props) {
  const croquisEnabled = isMyCroquisUiEnabled()
  const fittingRoomEnabled = isFittingRoomUiEnabled()
  const firstName = username.trim().split(/\s+/)[0] || 'Creator'
  const destinations = DESTINATIONS.filter((item) => {
    if (item.requiresMyCroquis) return croquisEnabled
    if (item.requiresFittingRoom) return fittingRoomEnabled
    return true
  })

  return (
    <section className={styles.screen} aria-labelledby="home-headline">
      <HomeBeforeAfterGallery examples={homeExamples} />

      <header className={styles.hero}>
        <div className={styles.copy}>
          <p className={styles.greeting}>Welcome back, {firstName}</p>
          <p className={styles.brandMark}>
            Fashion<span>Rise</span>
          </p>
          <h1 id="home-headline" className={styles.tagline}>
            Sketch it. See it come to life.
          </h1>
          <p className={styles.lead}>
            Turn your fashion ideas into stunning AI creations — or jump back into saved designs,
            looks, and models.
          </p>
          <div className={styles.heroCtas}>
            <button
              type="button"
              className={styles.featuredCta}
              onClick={() => onNavigate('fashionrise')}
              data-testid="home-open-fashionrise"
            >
              <Star size={18} aria-hidden />
              FashionRise
            </button>
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
        </div>
      </header>

      <div className={styles.studioBlock}>
        <p className={styles.sectionLabel}>Your studio</p>
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
                <ChevronRight className={styles.destinationChevron} size={18} aria-hidden />
              </button>
            )
          })}
        </nav>
      </div>
    </section>
  )
}
