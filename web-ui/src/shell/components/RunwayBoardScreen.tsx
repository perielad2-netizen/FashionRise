import { useCallback, useEffect, useState } from 'react'
import {
  Crown,
  Globe2,
  HeartHandshake,
  MessageCircle,
  Palette,
  Sparkles,
  Star,
  ThumbsUp,
  Trophy,
  Users,
  UserPlus,
  type LucideIcon,
} from 'lucide-react'
import { listGallery, type GalleryItem } from '@/services/galleryApi'
import { ApiError } from '@/services/api/client'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import {
  fetchCategoryBoard,
  fetchCompetitionStatus,
  type CategoryBoard,
  type CategoryBoardEntry,
} from '@/services/competitionsApi'
import { profileAvatarSrc } from '@/services/profilesApi'
import styles from './RunwayBoardScreen.module.css'

type ScopeId = 'worldwide' | 'friends' | 'following'
type TopLimit = 10 | 20 | 50
type Mode = 'rankings' | 'category'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: GalleryItem[] }

type CategoryLoad =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; board: CategoryBoard }

const TOP_LIMITS: TopLimit[] = [10, 20, 50]

const WEEKLY_CATEGORIES: ReadonlyArray<{
  id: string
  label: string
  stars: number
  blurb: string
  Icon: LucideIcon
}> = [
  {
    id: 'top_design',
    label: 'Top Design',
    stars: 50,
    blurb: 'Most engaged look this week',
    Icon: Sparkles,
  },
  {
    id: 'top_designer',
    label: 'Top Designer',
    stars: 50,
    blurb: 'Strongest engagement this week',
    Icon: Palette,
  },
  {
    id: 'community_champion',
    label: 'Community Champion',
    stars: 50,
    blurb: 'Publish + give back',
    Icon: HeartHandshake,
  },
  { id: 'top_supporter', label: 'Top Supporter', stars: 20, blurb: 'Likes across designers', Icon: ThumbsUp },
  {
    id: 'top_commenter',
    label: 'Top Commenter',
    stars: 20,
    blurb: 'Meaningful comments',
    Icon: MessageCircle,
  },
  { id: 'top_rater', label: 'Top Rater', stars: 20, blurb: 'Thoughtful ratings', Icon: Star },
]

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 10_000) return `${Math.round(n / 1000)}K`
  if (n >= 1_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`
  return String(n)
}

function initialFrom(name: string): string {
  const ch = name.trim().charAt(0)
  return ch ? ch.toUpperCase() : '·'
}

function podiumClass(rank: number): string {
  if (rank === 1) return styles.metalGold
  if (rank === 2) return styles.metalSilver
  if (rank === 3) return styles.metalBronze
  return ''
}

/**
 * Runway — rankings + weekly competition category boards (profile lists).
 * Separate from FashionRise immersive feed.
 * Visual polish inspired by Mobbin leaderboard / awards patterns (branch only).
 */
export function RunwayBoardScreen() {
  const [mode, setMode] = useState<Mode>('rankings')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [scope, setScope] = useState<ScopeId>('worldwide')
  const [topLimit, setTopLimit] = useState<TopLimit>(10)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [categoryLoad, setCategoryLoad] = useState<CategoryLoad>({ status: 'idle' })
  const [daysLeft, setDaysLeft] = useState<number | null>(null)

  const loadRankings = useCallback(
    async (signal?: AbortSignal) => {
      setState({ status: 'loading' })
      try {
        const sort = scope === 'worldwide' ? 'top10' : scope === 'friends' ? 'circle' : 'following'
        const limit = scope === 'worldwide' ? topLimit : Math.max(topLimit, 20)
        const items = await listGallery({ sort, limit, signal })
        setState({ status: 'ready', items })
      } catch (err) {
        if (signal?.aborted) return
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Could not load Runway'
        setState({ status: 'error', message })
      }
    },
    [scope, topLimit],
  )

  const loadCategory = useCallback(async (categoryId: string, signal?: AbortSignal) => {
    setCategoryLoad({ status: 'loading' })
    try {
      const board = await fetchCategoryBoard(categoryId, 20)
      if (signal?.aborted) return
      setCategoryLoad({ status: 'ready', board })
    } catch (err) {
      if (signal?.aborted) return
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Could not load category board'
      setCategoryLoad({ status: 'error', message })
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void (async () => {
      try {
        const status = await fetchCompetitionStatus()
        if (ac.signal.aborted) return
        const raw = status.days_remaining
        setDaysLeft(typeof raw === 'number' && Number.isFinite(raw) ? Math.max(0, Math.ceil(raw)) : null)
      } catch {
        if (!ac.signal.aborted) setDaysLeft(null)
      }
    })()
    return () => ac.abort()
  }, [])

  useEffect(() => {
    if (mode !== 'rankings') return
    const ac = new AbortController()
    void loadRankings(ac.signal)
    return () => ac.abort()
  }, [loadRankings, mode])

  useEffect(() => {
    if (mode !== 'category' || !activeCategory) return
    const ac = new AbortController()
    void loadCategory(activeCategory, ac.signal)
    return () => ac.abort()
  }, [activeCategory, loadCategory, mode])

  const selectedMeta = WEEKLY_CATEGORIES.find((c) => c.id === activeCategory) ?? null

  const boardTitle =
    mode === 'category' && selectedMeta
      ? selectedMeta.label
      : scope === 'worldwide'
        ? `Worldwide Top ${topLimit}`
        : scope === 'friends'
          ? 'Friends circle'
          : 'Following'

  const boardHint =
    mode === 'category' && selectedMeta
      ? `${selectedMeta.blurb} · ${selectedMeta.stars}★ weekly prize`
      : scope === 'worldwide'
        ? 'Most liked public looks worldwide — pick Top 10, 20, or 50.'
        : scope === 'friends'
          ? 'Published looks from your friends circle.'
          : 'Looks from designers you follow.'

  function selectCategory(id: string) {
    setActiveCategory(id)
    setMode('category')
  }

  function selectRankingsScope(next: ScopeId) {
    setMode('rankings')
    setActiveCategory(null)
    setCategoryLoad({ status: 'idle' })
    setScope(next)
  }

  return (
    <section className={styles.screen} aria-labelledby="runway-board-title">
      <header className={styles.header}>
        <div className={styles.headerTop}>
          {daysLeft != null ? (
            <p className={styles.weekChip} data-testid="runway-week-chip">
              <Trophy size={14} aria-hidden />
              {daysLeft === 0
                ? 'Ends today'
                : daysLeft === 1
                  ? '1 day left this week'
                  : `${daysLeft} days left this week`}
            </p>
          ) : null}
        </div>
        <h1 id="runway-board-title" className={styles.title}>
          Runway
        </h1>
        <p className={styles.lead}>Weekly awards and Top rankings.</p>
      </header>

      <section className={styles.weekly} aria-labelledby="runway-weekly-title">
        <div className={styles.weeklyHead}>
          <h2 id="runway-weekly-title" className={styles.weeklyTitle}>
            Weekly awards
          </h2>
          <p className={styles.weeklyHint}>One prize per designer. Tap a category for the live board.</p>
        </div>
        <div className={styles.awardRail} role="tablist" aria-label="Award categories">
          {WEEKLY_CATEGORIES.map((cat) => {
            const active = mode === 'category' && activeCategory === cat.id
            const Icon = cat.Icon
            return (
              <button
                key={cat.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={active ? styles.awardChipActive : styles.awardChip}
                data-testid={`runway-cat-${cat.id}`}
                onClick={() => selectCategory(cat.id)}
              >
                <span className={styles.awardMark} aria-hidden>
                  <Icon size={18} strokeWidth={2.1} />
                </span>
                <span className={styles.awardCopy}>
                  <span className={styles.weeklyCatLabel}>{cat.label}</span>
                  <span className={styles.weeklyStars}>{cat.stars}★</span>
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <div className={styles.segment} role="tablist" aria-label="Runway gallery scope">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'rankings' && scope === 'worldwide'}
          className={
            mode === 'rankings' && scope === 'worldwide' ? styles.segmentActive : styles.segmentBtn
          }
          data-testid="runway-scope-worldwide"
          onClick={() => selectRankingsScope('worldwide')}
        >
          <Globe2 size={14} aria-hidden /> Worldwide
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'rankings' && scope === 'friends'}
          className={mode === 'rankings' && scope === 'friends' ? styles.segmentActive : styles.segmentBtn}
          data-testid="runway-scope-friends"
          onClick={() => selectRankingsScope('friends')}
        >
          <Users size={14} aria-hidden /> Friends
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'rankings' && scope === 'following'}
          className={
            mode === 'rankings' && scope === 'following' ? styles.segmentActive : styles.segmentBtn
          }
          data-testid="runway-scope-following"
          onClick={() => selectRankingsScope('following')}
        >
          <UserPlus size={14} aria-hidden /> Following
        </button>
      </div>

      {mode === 'rankings' && scope === 'worldwide' ? (
        <div className={styles.topLimitRow} role="group" aria-label="Top ranking size">
          <span className={styles.topLimitLabel}>Show</span>
          {TOP_LIMITS.map((n) => (
            <button
              key={n}
              type="button"
              className={topLimit === n ? styles.topLimitActive : styles.topLimitBtn}
              data-testid={`runway-top-limit-${n}`}
              aria-pressed={topLimit === n}
              onClick={() => setTopLimit(n)}
            >
              Top {n}
            </button>
          ))}
        </div>
      ) : null}

      <div className={styles.boardPanel}>
        <div className={styles.boardHead}>
          <div>
            <h2 className={styles.boardTitle}>{boardTitle}</h2>
            <p className={styles.boardHint}>{boardHint}</p>
          </div>
        </div>

        {mode === 'category' ? (
          <CategoryBoardPanel
            load={categoryLoad}
            onRetry={() => activeCategory && void loadCategory(activeCategory)}
          />
        ) : (
          <RankingsPanel
            state={state}
            boardTitle={boardTitle}
            scope={scope}
            onRetry={() => void loadRankings()}
          />
        )}
      </div>
    </section>
  )
}

function RankingsPanel({
  state,
  boardTitle,
  scope,
  onRetry,
}: {
  state: LoadState
  boardTitle: string
  scope: ScopeId
  onRetry: () => void
}) {
  if (state.status === 'loading') return <p className={styles.status}>Loading Runway…</p>
  if (state.status === 'error') {
    return (
      <div className={styles.errorBox} role="alert">
        <p className={styles.status}>{state.message}</p>
        <button type="button" className={styles.retryBtn} onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }
  if (state.items.length === 0) {
    return (
      <p className={styles.empty}>
        {scope === 'worldwide'
          ? 'No Top rankings yet. Publish a look from My Looks to appear here.'
          : scope === 'friends'
            ? 'Your friends circle is quiet. Add friends from FashionRise, or publish a look.'
            : 'No follows yet. Follow designers on FashionRise profiles.'}
      </p>
    )
  }
  return (
    <ol className={styles.rankList} aria-label={boardTitle}>
      {state.items.map((item, index) => (
        <RankRow key={item.id} item={item} rank={index + 1} showRank={scope === 'worldwide'} />
      ))}
    </ol>
  )
}

function CategoryBoardPanel({
  load,
  onRetry,
}: {
  load: CategoryLoad
  onRetry: () => void
}) {
  if (load.status === 'idle' || load.status === 'loading') {
    return <p className={styles.status}>Loading category board…</p>
  }
  if (load.status === 'error') {
    return (
      <div className={styles.errorBox} role="alert">
        <p className={styles.status}>{load.message}</p>
        <button type="button" className={styles.retryBtn} onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }
  const { board } = load
  if (board.entries.length === 0) {
    return <p className={styles.empty}>{board.empty_reason || 'No standings yet this week.'}</p>
  }

  const podium = board.entries.slice(0, 3)
  const rest = board.entries.slice(3)

  return (
    <div className={styles.categoryBoard}>
      <ol className={styles.podium} aria-label={`${board.label} top three`}>
        {/* Visual order: 2 · 1 · 3 */}
        {[podium[1], podium[0], podium[2]].filter(Boolean).map((entry) => (
          <PodiumCard key={`podium-${entry.user_id}-${entry.gallery_item_id ?? 'u'}`} entry={entry} />
        ))}
      </ol>
      {rest.length > 0 ? (
        <ol className={styles.profileList} aria-label={`${board.label} leaderboard`}>
          {rest.map((entry) => (
            <ProfileRow
              key={`${entry.user_id}-${entry.gallery_item_id ?? 'user'}`}
              entry={entry}
            />
          ))}
        </ol>
      ) : null}
      {/* Keep full list accessible for screen readers when only podium shows */}
      {rest.length === 0 ? (
        <ol className={styles.srOnlyList} aria-label={`${board.label} full board`}>
          {board.entries.map((entry) => (
            <li key={`sr-${entry.user_id}-${entry.rank}`}>
              #{entry.rank} {entry.display_name || entry.username || 'Designer'} {entry.score} pts
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}

function PodiumCard({ entry }: { entry: CategoryBoardEntry }) {
  const handle = entry.username?.trim() ? `@${entry.username.trim()}` : null
  const name = entry.display_name?.trim() || handle || 'Designer'
  const avatar = profileAvatarSrc(entry.user_id, entry.avatar_url)
  const tall = entry.rank === 1

  return (
    <li className={tall ? `${styles.podiumCard} ${styles.podiumCardLead}` : styles.podiumCard}>
      <div className={`${styles.podiumAvatar} ${podiumClass(entry.rank)}`} aria-hidden>
        {avatar ? <img src={avatar} alt="" /> : <span>{initialFrom(name)}</span>}
        <span className={`${styles.podiumMedal} ${podiumClass(entry.rank)}`}>
          {entry.rank === 1 ? <Crown size={10} aria-hidden /> : null}
          {entry.rank}
        </span>
      </div>
      <p className={styles.podiumName}>{name}</p>
      {handle && name !== handle ? <p className={styles.podiumHandle}>{handle}</p> : null}
      <p className={styles.podiumScore}>
        <strong>{formatCount(entry.score)}</strong> pts
      </p>
    </li>
  )
}

function ProfileRow({ entry }: { entry: CategoryBoardEntry }) {
  const handle = entry.username?.trim() ? `@${entry.username.trim()}` : null
  const name = entry.display_name?.trim() || handle || 'Designer'
  const avatar = profileAvatarSrc(entry.user_id, entry.avatar_url)
  const metal = podiumClass(entry.rank)

  return (
    <li className={styles.profileRow}>
      <span className={styles.profileRankNum}>#{entry.rank}</span>
      <div className={`${styles.avatar} ${metal}`} aria-hidden>
        {avatar ? (
          <img src={avatar} alt="" />
        ) : (
          <span className={styles.avatarFallback}>{initialFrom(name)}</span>
        )}
      </div>
      <div className={styles.profileBody}>
        <p className={styles.profileName}>{name}</p>
        {handle && name !== handle ? <p className={styles.profileHandle}>{handle}</p> : null}
        {entry.look_title ? <p className={styles.profileLook}>{entry.look_title}</p> : null}
      </div>
      <div className={styles.profileScore}>
        <strong>{formatCount(entry.score)}</strong>
        <span>pts</span>
      </div>
    </li>
  )
}

function RankRow({
  item,
  rank,
  showRank,
}: {
  item: GalleryItem
  rank: number
  showRank: boolean
}) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const lead = showRank && rank === 1
  const title = item.title?.trim() || 'Untitled look'
  const designer = item.username?.trim() ? `@${item.username.trim()}` : 'Designer'
  const metal = showRank ? podiumClass(rank) : ''

  return (
    <li className={lead ? `${styles.rankCard} ${styles.rankCardLead}` : styles.rankCard}>
      <div className={styles.rankThumb}>
        {showRank ? (
          <span className={`${styles.rankBadge} ${metal || styles.rankBadgeMuted}`}>
            {rank === 1 ? <Crown size={12} aria-hidden /> : null}#{rank}
          </span>
        ) : null}
        {src ? <img src={src} alt="" /> : null}
      </div>
      <div className={styles.rankBody}>
        <p className={styles.rankTitle}>{title}</p>
        <p className={styles.rankDesigner}>{designer}</p>
        <div className={styles.rankStats}>
          <span>
            Likes <strong>{formatCount(item.likes_count ?? 0)}</strong>
          </span>
          <span>
            Rating{' '}
            <strong>{item.rating_average != null ? item.rating_average.toFixed(1) : '—'}</strong>
          </span>
          <span>
            Ratings <strong>{formatCount(item.rating_count ?? 0)}</strong>
          </span>
        </div>
      </div>
    </li>
  )
}
