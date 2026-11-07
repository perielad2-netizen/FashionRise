import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  Globe2,
  Heart,
  MessageCircle,
  RefreshCw,
  Sparkles,
  Star,
  UserPlus,
  Users,
} from 'lucide-react'
import {
  getGalleryItem,
  likeGalleryItem,
  listGallery,
  rateGalleryItem,
  unlikeGalleryItem,
  type GalleryItem,
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
import { useAuth } from '@/services/auth/AuthProvider'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import styles from './RunwayScreen.module.css'

type Props = {
  onOpenCreate: () => void
  onOpenLooks: () => void
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; circle: GalleryItem[]; top10: GalleryItem[] }

type FriendsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; friends: Friendship[]; requests: Friendship[] }

type TabId = 'feed' | 'friends'

const TABS: Array<{ id: TabId; label: string; hint: string }> = [
  { id: 'feed', label: 'Feed', hint: 'Your looks and your friends’ looks' },
  { id: 'friends', label: 'Friends', hint: 'Manage your private circle' },
]

const SCORE_HINT = 'Looks earn runway scores from likes + ratings (1–10).'

export function RunwayScreen({ onOpenCreate, onOpenLooks }: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const [tab, setTab] = useState<TabId>('feed')
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
      const [circle, top10] = await Promise.all([
        listGallery({ sort: 'circle', limit: 48, signal }),
        listGallery({ sort: 'top10', limit: 10, signal }),
      ])
      if (signal?.aborted) return
      setState({ status: 'ready', circle, top10 })
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
  }, [tab])

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

  const patchItem = useCallback((next: GalleryItem) => {
    setState((prev) => {
      if (prev.status !== 'ready') return prev
      const rewrite = (rows: GalleryItem[]) =>
        rows.map((row) => (row.id === next.id ? { ...row, ...next } : row))
      return {
        status: 'ready',
        circle: rewrite(prev.circle),
        top10: rewrite(prev.top10),
      }
    })
  }, [])

  return (
    <section className={styles.screen} aria-labelledby="runway-title">
      <header className={styles.head}>
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>FashionRise</p>
          <h1 id="runway-title" className={styles.title}>
            Runway
          </h1>
          <p className={styles.subtitle}>
            Your circle’s looks first — plus a worldwide Top 10. {SCORE_HINT}
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
          {tab === 'feed' ? (
            <button
              type="button"
              className={styles.refreshBtn}
              onClick={() => void load()}
              aria-label="Refresh feed"
            >
              <RefreshCw size={14} aria-hidden />
              Refresh
            </button>
          ) : null}
        </div>
      </header>

      <div className={styles.roadmap} aria-label="Social phase roadmap">
        <span className={styles.roadLive}>Circle feed</span>
        <span className={styles.roadLive}>Top 10</span>
        <span className={styles.roadLive}>Friends</span>
        <span className={styles.roadLive}>Like · Score</span>
        <span className={styles.roadNext}>Comments · Push</span>
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
            {item.label}
          </button>
        ))}
      </div>

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
        ) : (
          <div className={styles.feedStack}>
            <section className={styles.topSection} aria-label="Top 10 worldwide">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle}>
                  <Globe2 size={16} aria-hidden />
                  Top 10 worldwide
                </h2>
                <p className={styles.sectionHint}>Most liked public looks across FashionRise</p>
              </div>
              {state.top10.length === 0 ? (
                <p className={styles.status}>No worldwide looks yet — be the first to Publish.</p>
              ) : (
                <ul className={styles.topStrip}>
                  {state.top10.map((item, index) => (
                    <RunwayCard
                      key={item.id}
                      item={item}
                      rank={index + 1}
                      compact
                      isOwn={Boolean(viewerId && item.user_id === viewerId)}
                      onItemChange={patchItem}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className={styles.circleSection} aria-label="Friends circle feed">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle}>
                  <Users size={16} aria-hidden />
                  Your circle
                </h2>
                <p className={styles.sectionHint}>Only your looks and your friends’ published looks</p>
              </div>
              {state.circle.length === 0 ? (
                <EmptyState
                  title="Your circle is quiet"
                  body="Publish a look from My Looks, or add friends so their Runway posts show up here — not the whole app."
                  actions={
                    <>
                      <button type="button" className={styles.primaryBtn} onClick={onOpenLooks}>
                        Go to My Looks
                      </button>
                      <button
                        type="button"
                        className={styles.ghostBtn}
                        onClick={() => setTab('friends')}
                      >
                        Add friends
                      </button>
                    </>
                  }
                />
              ) : (
                <ul className={styles.grid} aria-label="Circle feed">
                  {state.circle.map((item) => (
                    <RunwayCard
                      key={item.id}
                      item={item}
                      isOwn={Boolean(viewerId && item.user_id === viewerId)}
                      onItemChange={patchItem}
                    />
                  ))}
                </ul>
              )}
            </section>
          </div>
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
                body="Add someone by FashionRise username to build your private circle."
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

function RunwayCard({
  item,
  rank,
  compact = false,
  isOwn = false,
  onItemChange,
}: {
  item: GalleryItem
  rank?: number
  compact?: boolean
  isOwn?: boolean
  onItemChange: (next: GalleryItem) => void
}) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const [busy, setBusy] = useState<'like' | 'score' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const liked = Boolean(item.liked_by_me)
  const canReact = !isOwn

  const refreshItem = useCallback(async () => {
    const fresh = await getGalleryItem(item.id)
    onItemChange(fresh)
    return fresh
  }, [item.id, onItemChange])

  const onToggleLike = useCallback(async () => {
    if (!canReact || busy) return
    setBusy('like')
    setActionError(null)
    const prevLiked = liked
    const prevCount = item.likes_count
    onItemChange({
      ...item,
      liked_by_me: !prevLiked,
      likes_count: Math.max(0, prevCount + (prevLiked ? -1 : 1)),
    })
    try {
      if (prevLiked) await unlikeGalleryItem(item.id)
      else await likeGalleryItem(item.id)
      await refreshItem()
    } catch (err) {
      onItemChange({ ...item, liked_by_me: prevLiked, likes_count: prevCount })
      setActionError(err instanceof ApiError ? err.message : 'Could not update like.')
    } finally {
      setBusy(null)
    }
  }, [busy, canReact, item, liked, onItemChange, refreshItem])

  const onScore = useCallback(
    async (raw: string) => {
      const score = Number(raw)
      if (!canReact || !Number.isInteger(score) || score < 1 || score > 10 || busy) return
      setBusy('score')
      setActionError(null)
      try {
        await rateGalleryItem(item.id, score)
        await refreshItem()
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Could not save score.')
      } finally {
        setBusy(null)
      }
    },
    [busy, canReact, item.id, refreshItem],
  )

  return (
    <li className={compact ? styles.topCard : styles.card}>
      <div className={styles.thumb}>
        {rank != null ? <span className={styles.rankBadge}>#{rank}</span> : null}
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
        <div className={styles.cardActions}>
          {canReact ? (
            <button
              type="button"
              className={liked ? styles.likeBtnOn : styles.likeBtn}
              aria-pressed={liked}
              aria-label={liked ? 'Unlike look' : 'Like look'}
              disabled={busy === 'like'}
              onClick={() => void onToggleLike()}
            >
              <Heart size={13} aria-hidden fill={liked ? 'currentColor' : 'none'} />
              {item.likes_count}
            </button>
          ) : (
            <span className={styles.statChip} title="Others can like your look">
              <Heart size={12} aria-hidden />
              {item.likes_count}
            </span>
          )}
          {canReact ? (
            <label className={styles.scoreLabel}>
              <span className={styles.scoreLabelText}>
                <Star size={12} aria-hidden />
                {item.rating_average != null ? item.rating_average.toFixed(1) : 'Score'}
              </span>
              <select
                className={styles.scoreSelect}
                aria-label={`Score ${item.title || 'look'} from 1 to 10`}
                value={item.my_score ?? ''}
                disabled={busy === 'score'}
                onChange={(event) => void onScore(event.target.value)}
              >
                <option value="" disabled>
                  {item.my_score ? `Yours ${item.my_score}` : 'Rate'}
                </option>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className={styles.statChip} title="Others can score your look">
              <Star size={12} aria-hidden />
              {item.rating_average != null ? item.rating_average.toFixed(1) : '—'}
              {item.rating_count > 0 ? ` (${item.rating_count})` : ''}
            </span>
          )}
          {!compact ? (
            <span className={styles.soonChip} title="Comments coming soon">
              <MessageCircle size={12} aria-hidden /> soon
            </span>
          ) : null}
        </div>
        {isOwn ? (
          <p className={styles.ownHint}>Your look — likes & scores come from others</p>
        ) : null}
        {actionError ? (
          <p className={styles.cardError} role="alert">
            {actionError}
          </p>
        ) : null}
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
