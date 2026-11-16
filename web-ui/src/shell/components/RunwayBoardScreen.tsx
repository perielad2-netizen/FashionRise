import { useCallback, useEffect, useState } from 'react'
import { Crown, Globe2, Users, UserPlus } from 'lucide-react'
import { listGallery, type GalleryItem } from '@/services/galleryApi'
import { ApiError } from '@/services/api/client'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { CompetitionStrip } from '@/shell/components/CompetitionStrip'
import styles from './RunwayBoardScreen.module.css'

type ScopeId = 'worldwide' | 'friends' | 'following'
type TopLimit = 10 | 20 | 50

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: GalleryItem[] }

const TOP_LIMITS: TopLimit[] = [10, 20, 50]

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 10_000) return `${Math.round(n / 1000)}K`
  if (n >= 1_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`
  return String(n)
}

/**
 * Runway — rankings + weekly competition results.
 * Separate from FashionRise (Instagram-style immersive feed).
 */
export function RunwayBoardScreen() {
  const [scope, setScope] = useState<ScopeId>('worldwide')
  const [topLimit, setTopLimit] = useState<TopLimit>(10)
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(async (signal?: AbortSignal) => {
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
  }, [scope, topLimit])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    return () => ac.abort()
  }, [load])

  const boardTitle =
    scope === 'worldwide'
      ? `Worldwide Top ${topLimit}`
      : scope === 'friends'
        ? 'Friends circle'
        : 'Following'

  const boardHint =
    scope === 'worldwide'
      ? 'Most liked public looks worldwide — pick Top 10, 20, or 50.'
      : scope === 'friends'
        ? 'Published looks from your friends circle.'
        : 'Looks from designers you follow.'

  return (
    <section className={styles.screen} aria-labelledby="runway-board-title">
      <header className={styles.header}>
        <p className={styles.eyebrow}>Competitions & rankings</p>
        <h1 id="runway-board-title" className={styles.title}>
          Runway
        </h1>
        <p className={styles.lead}>
          Weekly competition results and top designs — friends, worldwide, Top 10 / 20 / 50. The
          Instagram-style scroll lives on FashionRise.
        </p>
      </header>

      <CompetitionStrip defaultOpen />

      <div className={styles.scopes} role="tablist" aria-label="Runway scope">
        <button
          type="button"
          role="tab"
          aria-selected={scope === 'worldwide'}
          className={scope === 'worldwide' ? styles.scopeActive : styles.scopeBtn}
          data-testid="runway-scope-worldwide"
          onClick={() => setScope('worldwide')}
        >
          <Globe2 size={14} aria-hidden /> Worldwide
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={scope === 'friends'}
          className={scope === 'friends' ? styles.scopeActive : styles.scopeBtn}
          data-testid="runway-scope-friends"
          onClick={() => setScope('friends')}
        >
          <Users size={14} aria-hidden /> Friends
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={scope === 'following'}
          className={scope === 'following' ? styles.scopeActive : styles.scopeBtn}
          data-testid="runway-scope-following"
          onClick={() => setScope('following')}
        >
          <UserPlus size={14} aria-hidden /> Following
        </button>
      </div>

      {scope === 'worldwide' ? (
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
          <h2 className={styles.boardTitle}>{boardTitle}</h2>
          <p className={styles.boardHint}>{boardHint}</p>
        </div>

        {state.status === 'loading' ? <p className={styles.status}>Loading Runway…</p> : null}
        {state.status === 'error' ? (
          <div className={styles.errorBox} role="alert">
            <p className={styles.status}>{state.message}</p>
            <button type="button" className={styles.retryBtn} onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : null}
        {state.status === 'ready' && state.items.length === 0 ? (
          <p className={styles.empty}>
            {scope === 'worldwide'
              ? 'No Top rankings yet. Publish a look from My Looks to appear here.'
              : scope === 'friends'
                ? 'Your friends circle is quiet. Add friends from FashionRise, or publish a look.'
                : 'No follows yet. Follow designers on FashionRise profiles.'}
          </p>
        ) : null}
        {state.status === 'ready' && state.items.length > 0 ? (
          <ol className={styles.rankList} aria-label={boardTitle}>
            {state.items.map((item, index) => (
              <RankRow key={item.id} item={item} rank={index + 1} showRank={scope === 'worldwide'} />
            ))}
          </ol>
        ) : null}
      </div>
    </section>
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
            <strong>
              {item.rating_average != null ? item.rating_average.toFixed(1) : '—'}
            </strong>
          </span>
          <span>
            Ratings <strong>{formatCount(item.rating_count ?? 0)}</strong>
          </span>
        </div>
      </div>
    </li>
  )
}
