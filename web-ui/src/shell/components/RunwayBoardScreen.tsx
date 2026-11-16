import { useCallback, useEffect, useState } from 'react'
import { Crown, Globe2, Trophy, Users, UserPlus } from 'lucide-react'
import { listGallery, type GalleryItem } from '@/services/galleryApi'
import { ApiError } from '@/services/api/client'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import {
  fetchCategoryBoard,
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
}> = [
  { id: 'top_design', label: 'Top Design', stars: 50, blurb: 'Best engaged look this week' },
  { id: 'top_designer', label: 'Top Designer', stars: 50, blurb: 'Strongest published week' },
  {
    id: 'community_champion',
    label: 'Community Champion',
    stars: 50,
    blurb: 'Publish quality + giving back',
  },
  { id: 'top_supporter', label: 'Top Supporter', stars: 20, blurb: 'Likes across designers' },
  { id: 'top_commenter', label: 'Top Commenter', stars: 20, blurb: 'Meaningful comments' },
  { id: 'top_rater', label: 'Top Rater', stars: 20, blurb: 'Thoughtful ratings' },
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

/**
 * Runway — rankings + weekly competition category boards (profile lists).
 * Separate from FashionRise immersive feed.
 */
export function RunwayBoardScreen() {
  const [mode, setMode] = useState<Mode>('rankings')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [scope, setScope] = useState<ScopeId>('worldwide')
  const [topLimit, setTopLimit] = useState<TopLimit>(10)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [categoryLoad, setCategoryLoad] = useState<CategoryLoad>({ status: 'idle' })

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
        <p className={styles.eyebrow}>Competitions & rankings</p>
        <h1 id="runway-board-title" className={styles.title}>
          Runway
        </h1>
        <p className={styles.lead}>
          Tap a weekly category for the live profile board — or browse worldwide, friends, and
          following tops. FashionRise is the Instagram-style feed.
        </p>
      </header>

      <section className={styles.weekly} aria-labelledby="runway-weekly-title">
        <div className={styles.weeklyHead}>
          <h2 id="runway-weekly-title" className={styles.weeklyTitle}>
            <Trophy size={18} aria-hidden /> Weekly categories
          </h2>
          <p className={styles.weeklyHint}>
            One prize per designer each week. Open a category to see who’s climbing.
          </p>
        </div>
        <div className={styles.weeklyGrid} role="tablist" aria-label="Award categories">
          {WEEKLY_CATEGORIES.map((cat) => {
            const active = mode === 'category' && activeCategory === cat.id
            return (
              <button
                key={cat.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={active ? styles.weeklyCatActive : styles.weeklyCat}
                data-testid={`runway-cat-${cat.id}`}
                onClick={() => selectCategory(cat.id)}
              >
                <span className={styles.weeklyCatLabel}>{cat.label}</span>
                <span className={styles.weeklyStars}>{cat.stars}★</span>
                <span className={styles.weeklyCatBlurb}>{cat.blurb}</span>
              </button>
            )
          })}
        </div>
      </section>

      <div className={styles.scopes} role="tablist" aria-label="Runway gallery scope">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'rankings' && scope === 'worldwide'}
          className={mode === 'rankings' && scope === 'worldwide' ? styles.scopeActive : styles.scopeBtn}
          data-testid="runway-scope-worldwide"
          onClick={() => selectRankingsScope('worldwide')}
        >
          <Globe2 size={14} aria-hidden /> Worldwide
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'rankings' && scope === 'friends'}
          className={mode === 'rankings' && scope === 'friends' ? styles.scopeActive : styles.scopeBtn}
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
            mode === 'rankings' && scope === 'following' ? styles.scopeActive : styles.scopeBtn
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

      <div className={styles.board}>
        <div className={styles.boardHead}>
          <div>
            <h2 className={styles.boardTitle}>{boardTitle}</h2>
            <p className={styles.boardHint}>{boardHint}</p>
          </div>
          {mode === 'category' && categoryLoad.status === 'ready' && categoryLoad.board.group_index != null ? (
            <p className={styles.groupChip}>Group {categoryLoad.board.group_index + 1}</p>
          ) : null}
        </div>

        {mode === 'category' ? (
          <CategoryBoardPanel
            load={categoryLoad}
            onRetry={() => activeCategory && void loadCategory(activeCategory)}
          />
        ) : (
          <RankingsPanel state={state} boardTitle={boardTitle} scope={scope} onRetry={() => void loadRankings()} />
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
  return (
    <ol className={styles.profileList} aria-label={`${board.label} leaderboard`}>
      {board.entries.map((entry) => (
        <ProfileRow key={`${entry.user_id}-${entry.gallery_item_id ?? 'user'}`} entry={entry} />
      ))}
    </ol>
  )
}

function ProfileRow({ entry }: { entry: CategoryBoardEntry }) {
  const handle = entry.username?.trim() ? `@${entry.username.trim()}` : null
  const name = entry.display_name?.trim() || handle || 'Designer'
  const avatar = profileAvatarSrc(entry.user_id, entry.avatar_url)
  const lead = entry.rank === 1

  return (
    <li className={lead ? `${styles.profileCard} ${styles.profileCardLead}` : styles.profileCard}>
      <span className={lead ? `${styles.profileRank} ${styles.profileRankLead}` : styles.profileRank}>
        {lead ? <Crown size={12} aria-hidden /> : null}
        #{entry.rank}
      </span>
      <div className={styles.avatar} aria-hidden>
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

  return (
    <li className={lead ? `${styles.rankCard} ${styles.rankCardLead}` : styles.rankCard}>
      <div className={styles.rankThumb}>
        {showRank ? (
          <span className={lead ? `${styles.rankBadge} ${styles.rankBadgeLead}` : styles.rankBadge}>
            {lead ? <Crown size={12} aria-hidden /> : null}#{rank}
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
