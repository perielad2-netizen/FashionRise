import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  Heart,
  MessageCircle,
  RefreshCw,
  Sparkles,
  Star,
  UserPlus,
  Users,
} from 'lucide-react'
import {
  listGallery,
  type GalleryItem,
  type GallerySort,
} from '@/services/galleryApi'
import {
  acceptFriendRequest,
  listFriendRequests,
  listFriends,
  removeFriend,
  requestFriendByUsername,
  type Friendship,
} from '@/services/friendsApi'
import { ApiError } from '@/services/api/client'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import styles from './RunwayScreen.module.css'

type Props = {
  onOpenCreate: () => void
  onOpenLooks: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; items: GalleryItem[] }

type FriendsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; friends: Friendship[]; requests: Friendship[] }

type TabId = 'feed' | 'following' | 'friends'

const TABS: Array<{ id: TabId; label: string; hint: string }> = [
  { id: 'feed', label: 'Feed', hint: 'Newest published looks from the community' },
  { id: 'following', label: 'Following', hint: 'Creators you follow' },
  { id: 'friends', label: 'Friends', hint: 'Your private circle' },
]

const SCORE_HINT = 'Looks earn runway scores from likes + ratings (1–10).'

export function RunwayScreen({ onOpenCreate, onOpenLooks }: Props) {
  const [tab, setTab] = useState<TabId>('feed')
  const [sort, setSort] = useState<GallerySort>('newest')
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [friendsState, setFriendsState] = useState<FriendsState>({ status: 'loading' })
  const [friendUsername, setFriendUsername] = useState('')
  const [friendBusy, setFriendBusy] = useState(false)
  const [friendNotice, setFriendNotice] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    if (tab === 'friends') {
      setFriendsState({ status: 'loading' })
      setFriendNotice(null)
      try {
        const [friends, requests] = await Promise.all([
          listFriends(signal),
          listFriendRequests(signal),
        ])
        if (signal?.aborted) return
        setFriendsState({ status: 'ready', friends, requests })
      } catch (err) {
        if (signal?.aborted) return
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Could not load friends'
        setFriendsState({ status: 'error', message })
      }
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
            : 'Could not load FashionRise Runway'
      setState({ status: 'error', message })
    }
  }, [sort, tab])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    return () => ac.abort()
  }, [load])

  const onAddFriend = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const username = friendUsername.trim()
      if (!username || friendBusy) return
      setFriendBusy(true)
      setFriendNotice(null)
      try {
        const row = await requestFriendByUsername(username)
        setFriendUsername('')
        setFriendNotice(
          row.status === 'accepted'
            ? `${row.friend.display_name || row.friend.username} is now in your friends circle.`
            : `Friend request sent to ${row.friend.display_name || row.friend.username}.`,
        )
        await load()
      } catch (err) {
        setFriendNotice(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Could not add friend.',
        )
      } finally {
        setFriendBusy(false)
      }
    },
    [friendBusy, friendUsername, load],
  )

  const onAccept = useCallback(
    async (friendshipId: string) => {
      setFriendBusy(true)
      setFriendNotice(null)
      try {
        const row = await acceptFriendRequest(friendshipId)
        setFriendNotice(`${row.friend.display_name || row.friend.username} accepted.`)
        await load()
      } catch (err) {
        setFriendNotice(err instanceof ApiError ? err.message : 'Could not accept request.')
      } finally {
        setFriendBusy(false)
      }
    },
    [load],
  )

  const onRemove = useCallback(
    async (friendUserId: string, label: string) => {
      setFriendBusy(true)
      setFriendNotice(null)
      try {
        await removeFriend(friendUserId)
        setFriendNotice(`Removed ${label} from friends.`)
        await load()
      } catch (err) {
        setFriendNotice(err instanceof ApiError ? err.message : 'Could not remove friend.')
      } finally {
        setFriendBusy(false)
      }
    },
    [load],
  )

  return (
    <section className={styles.screen} aria-labelledby="runway-title">
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>FashionRise</p>
          <h1 id="runway-title" className={styles.title}>
            Runway
          </h1>
          <p className={styles.subtitle}>
            Share looks, follow creators, like and score the community runway. {SCORE_HINT}
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
        <span className={styles.roadLive}>Friends</span>
      </div>

      <div className={styles.tabs} role="tablist" aria-label="Runway views">
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
          <FriendsPanel
            state={friendsState}
            username={friendUsername}
            busy={friendBusy}
            notice={friendNotice}
            onUsernameChange={setFriendUsername}
            onAdd={(e) => void onAddFriend(e)}
            onAccept={(id) => void onAccept(id)}
            onRemove={(id, label) => void onRemove(id, label)}
            onRetry={() => void load()}
          />
        ) : state.status === 'loading' ? (
          <p className={styles.status} role="status">
            Loading Runway…
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
                : 'Open a look in My Looks and tap Publish to Runway. Add friends under the Friends tab.'
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
          <ul className={styles.grid} aria-label="Runway feed">
            {state.items.map((item) => (
              <RunwayCard key={item.id} item={item} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function FriendsPanel({
  state,
  username,
  busy,
  notice,
  onUsernameChange,
  onAdd,
  onAccept,
  onRemove,
  onRetry,
}: {
  state: FriendsState
  username: string
  busy: boolean
  notice: string | null
  onUsernameChange: (value: string) => void
  onAdd: (event: FormEvent) => void
  onAccept: (friendshipId: string) => void
  onRemove: (friendUserId: string, label: string) => void
  onRetry: () => void
}) {
  return (
    <div className={styles.friendsPanel}>
      <form className={styles.addFriendForm} onSubmit={onAdd}>
        <label className={styles.addFriendLabel} htmlFor="runway-friend-username">
          Add friend by username
        </label>
        <div className={styles.addFriendRow}>
          <input
            id="runway-friend-username"
            className={styles.addFriendInput}
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            placeholder="e.g. yanivprbk"
            autoComplete="username"
            disabled={busy}
          />
          <button type="submit" className={styles.primaryBtn} disabled={busy || !username.trim()}>
            <UserPlus size={14} aria-hidden />
            {busy ? 'Adding…' : 'Add'}
          </button>
        </div>
      </form>

      {notice ? (
        <p className={styles.friendNotice} role="status">
          {notice}
        </p>
      ) : null}

      {state.status === 'loading' ? (
        <p className={styles.status} role="status">
          Loading friends…
        </p>
      ) : null}

      {state.status === 'error' ? (
        <EmptyState
          title="Couldn’t load friends"
          body={state.message}
          actions={
            <button type="button" className={styles.ghostBtn} onClick={onRetry}>
              Try again
            </button>
          }
        />
      ) : null}

      {state.status === 'ready' ? (
        <>
          {state.requests.length > 0 ? (
            <section className={styles.friendSection} aria-label="Friend requests">
              <h2 className={styles.friendSectionTitle}>Requests</h2>
              <ul className={styles.friendList}>
                {state.requests.map((row) => (
                  <li key={row.id} className={styles.friendCard}>
                    <div className={styles.friendText}>
                      <strong>{row.friend.display_name || row.friend.username}</strong>
                      <span>@{row.friend.username}</span>
                    </div>
                    <button
                      type="button"
                      className={styles.primaryBtn}
                      disabled={busy}
                      onClick={() => onAccept(row.id)}
                    >
                      Accept
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className={styles.friendSection} aria-label="Your friends">
            <h2 className={styles.friendSectionTitle}>Your circle</h2>
            {state.friends.length === 0 ? (
              <EmptyState
                title="No friends yet"
                body="Add someone by FashionRise username to build your private circle. Private send of looks comes next."
              />
            ) : (
              <ul className={styles.friendList}>
                {state.friends.map((row) => {
                  const label = row.friend.display_name || row.friend.username
                  return (
                    <li key={row.id} className={styles.friendCard}>
                      <div className={styles.friendText}>
                        <strong>{label}</strong>
                        <span>@{row.friend.username}</span>
                      </div>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        disabled={busy}
                        onClick={() => onRemove(row.friend.user_id, label)}
                      >
                        Remove
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}

function RunwayCard({ item }: { item: GalleryItem }) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  return (
    <li className={styles.card}>
      <div className={styles.thumb}>
        {src ? (
          <img src={src} alt="" className={styles.thumbImg} draggable={false} />
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
