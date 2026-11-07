import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  Heart,
  MessageCircle,
  RefreshCw,
  Sparkles,
  Star,
  Users,
} from 'lucide-react'
import {
  listGallery,
  type GalleryItem,
  type GallerySort,
} from '@/services/galleryApi'
import { ApiError } from '@/services/api/client'
import styles from './FashionStarsScreen.module.css'

type Props = {
  onOpenCreate: () => void
  onOpenLooks: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: GalleryItem[] }

type TabId = 'feed' | 'following' | 'friends'

const TABS: Array<{ id: TabId; label: string; hint: string }> = [
  { id: 'feed', label: 'Feed', hint: 'Newest published looks from the community' },
  { id: 'following', label: 'Following', hint: 'Creators you follow' },
  { id: 'friends', label: 'Friends', hint: 'Private circle — coming next' },
]

const SCORE_HINT = 'Looks earn Fashion Stars from likes + scores (1–10).'

export function FashionStarsScreen({ onOpenCreate, onOpenLooks }: Props) {
  const [tab, setTab] = useState<TabId>('feed')
  const [sort, setSort] = useState<GallerySort>('newest')
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  const load = useCallback(async (signal?: AbortSignal) => {
    if (tab === 'friends') {
      setState({ status: 'ready', items: [] })
      return
    }
    setState({ status: 'loading' })
    try {
      const effectiveSort: GallerySort = tab === 'following' ? 'following' : sort
      const items = await listGallery({ sort: effectiveSort, limit: 24, signal })
      if (signal?.aborted) return
      setState({ status: 'ready', items })
    } catch (err) {
      if (signal?.aborted) return
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Could not load Fashion Stars'
      setState({ status: 'error', message })
    }
  }, [sort, tab])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    return () => ac.abort()
  }, [load])

  return (
    <section className={styles.screen} aria-labelledby="fashion-stars-title">
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>Social fashion</p>
          <h1 id="fashion-stars-title" className={styles.title}>
            Fashion Stars
          </h1>
          <p className={styles.subtitle}>
            Share looks, follow creators, like and score the runway. {SCORE_HINT}
          </p>
        </div>
        <div className={styles.headActions}>
          <button type="button" className={styles.ghostBtn} onClick={onOpenLooks}>
            My Looks
          </button>
          <button type="button" className={styles.primaryBtn} onClick={onOpenCreate}>
            <Sparkles size={16} aria-hidden />
            Create
          </button>
        </div>
      </header>

      <div className={styles.roadmap} aria-label="Social phase roadmap">
        <span className={styles.roadLive}>Feed</span>
        <span className={styles.roadNext}>Like · Score</span>
        <span className={styles.roadNext}>Comments</span>
        <span className={styles.roadNext}>Profiles · Follow</span>
        <span className={styles.roadNext}>Friends · Send</span>
      </div>

      <div className={styles.tabs} role="tablist" aria-label="Fashion Stars views">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? styles.tabActive : styles.tab}
            onClick={() => setTab(item.id)}
            title={item.hint}
          >
            {item.id === 'friends' ? <Users size={14} aria-hidden /> : null}
            {item.id === 'feed' ? <Star size={14} aria-hidden /> : null}
            {item.id === 'following' ? <Heart size={14} aria-hidden /> : null}
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'feed' ? (
        <div className={styles.sortRow} role="group" aria-label="Feed sort">
          {(
            [
              ['newest', 'Newest'],
              ['trending', 'Trending'],
              ['top_rated', 'Top rated'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={sort === value ? styles.sortActive : styles.sortBtn}
              onClick={() => setSort(value)}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={() => void load()}
            aria-label="Refresh feed"
          >
            <RefreshCw size={14} aria-hidden />
            Refresh
          </button>
        </div>
      ) : null}

      <div className={styles.body}>
        {tab === 'friends' ? (
          <EmptyState
            title="Friends circle is next"
            body="Soon you’ll add friends, manage your profile, and send designs or looks privately — before or instead of publishing to the public feed."
            actions={
              <button type="button" className={styles.primaryBtn} onClick={onOpenLooks}>
                Open My Looks
              </button>
            }
          />
        ) : state.status === 'loading' ? (
          <p className={styles.status} role="status">
            Loading Fashion Stars…
          </p>
        ) : state.status === 'error' ? (
          <EmptyState
            title="Couldn’t load the feed"
            body={state.message}
            actions={
              <button type="button" className={styles.ghostBtn} onClick={() => void load()}>
                Try again
              </button>
            }
          />
        ) : state.items.length === 0 ? (
          <EmptyState
            title={tab === 'following' ? 'No posts from people you follow yet' : 'The runway is waiting'}
            body={
              tab === 'following'
                ? 'Follow creators from their profiles (coming next), then their public looks show up here.'
                : 'Publish a look from My Looks to appear here. Likes, comments, and scores land in the next slices.'
            }
            actions={
              <>
                <button type="button" className={styles.primaryBtn} onClick={onOpenLooks}>
                  Go to My Looks
                </button>
                <button type="button" className={styles.ghostBtn} onClick={onOpenCreate}>
                  Start creating
                </button>
              </>
            }
          />
        ) : (
          <ul className={styles.grid} aria-label="Fashion Stars feed">
            {state.items.map((item) => (
              <li key={item.id} className={styles.card}>
                <div className={styles.thumb}>
                  {item.image_url ? (
                    <img src={item.image_url} alt="" className={styles.thumbImg} draggable={false} />
                  ) : (
                    <span className={styles.thumbEmpty} aria-hidden>
                      <Star size={22} />
                    </span>
                  )}
                </div>
                <div className={styles.cardBody}>
                  <h2 className={styles.cardTitle}>{item.title || 'Untitled look'}</h2>
                  <p className={styles.cardMeta}>
                    <span title="Likes">
                      <Heart size={12} aria-hidden /> {item.likes_count}
                    </span>
                    <span aria-hidden>·</span>
                    <span title="Average score">
                      <Star size={12} aria-hidden />{' '}
                      {item.rating_average != null ? item.rating_average.toFixed(1) : '—'}
                      {item.rating_count > 0 ? ` (${item.rating_count})` : ''}
                    </span>
                    <span aria-hidden>·</span>
                    <span title="Comments coming soon">
                      <MessageCircle size={12} aria-hidden /> soon
                    </span>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function EmptyState({
  title,
  body,
  actions,
}: {
  title: string
  body: string
  actions?: ReactNode
}) {
  return (
    <div className={styles.empty}>
      <Star size={28} className={styles.emptyIcon} aria-hidden />
      <h2 className={styles.emptyTitle}>{title}</h2>
      <p className={styles.emptyBody}>{body}</p>
      {actions ? <div className={styles.emptyActions}>{actions}</div> : null}
    </div>
  )
}
