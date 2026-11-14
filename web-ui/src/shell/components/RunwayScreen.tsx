import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import {
  Bell,
  BellOff,
  ChevronLeft,
  Globe2,
  Heart,
  MessageCircle,
  RefreshCw,
  Sparkles,
  Star,
  UserPlus,
  Users,
  X,
} from 'lucide-react'
import {
  getGalleryItem,
  likeGalleryItem,
  listGallery,
  likeGalleryComment,
  listGalleryComments,
  postGalleryComment,
  rateGalleryItem,
  unlikeGalleryComment,
  unlikeGalleryItem,
  type GalleryComment,
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
import {
  disableRunwayPush,
  enableRunwayPush,
  ensureDefaultRunwayPush,
  pushSupported,
  runwayPushIsEnabled,
} from '@/services/pushApi'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import { isNativeShell } from '@/services/native/platform'
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
type BrowseSheet = 'top10' | 'circle'

const TABS: Array<{ id: TabId; label: string; hint: string }> = [
  { id: 'feed', label: 'Feed', hint: 'Open Top 10 or your circle as a scrollable list' },
  { id: 'friends', label: 'Friends', hint: 'Manage your private circle' },
]

const SCORE_HINT = 'Looks earn runway scores from likes + ratings (1–10).'

export function RunwayScreen({ onOpenCreate, onOpenLooks }: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const viewerUsername = user?.username ?? null
  const [tab, setTab] = useState<TabId>('feed')
  const [browseSheet, setBrowseSheet] = useState<BrowseSheet | null>(null)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [friendsState, setFriendsState] = useState<FriendsState>({ status: 'loading' })
  const [friendUsername, setFriendUsername] = useState('')
  const [friendBusy, setFriendBusy] = useState(false)
  const [friendNotice, setFriendNotice] = useState<string | null>(null)
  const [pushOn, setPushOn] = useState(false)
  const [pushBusy, setPushBusy] = useState(false)
  const [pushNotice, setPushNotice] = useState<string | null>(null)
  const [pushNeedsGesture, setPushNeedsGesture] = useState(false)

  const applyPushAutoEnable = useCallback(async (fromGesture: boolean) => {
    setPushBusy(true)
    try {
      // Native shell: leave toggle off until #303 + operator FCM/APNs (V2-0008).
      if (isNativeShell()) {
        setPushOn(false)
        setPushNeedsGesture(false)
        return
      }
      const { on, result } = await ensureDefaultRunwayPush()
      if (on) {
        setPushOn(true)
        setPushNeedsGesture(false)
        if (result === 'granted') {
          setPushNotice('Push on — we’ll notify likes, scores, and comments')
        }
        return
      }
      if (result === 'skipped') {
        setPushOn(false)
        setPushNeedsGesture(false)
        return
      }
      if (result === 'denied' && !fromGesture && Notification.permission === 'default') {
        // Browsers often block permission prompts without a tap — retry on next interaction.
        setPushNeedsGesture(true)
        return
      }
      if (result === 'denied') {
        setPushNotice('Notifications blocked in browser settings')
        setPushNeedsGesture(false)
      } else if (result === 'disabled') {
        setPushNotice('Push isn’t configured on the server yet')
      } else if (result === 'unsupported') {
        setPushNotice('Push needs a modern browser (or install the app to Home Screen on iPhone).')
      }
      setPushOn(false)
    } catch {
      setPushOn(false)
    } finally {
      setPushBusy(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const on = await runwayPushIsEnabled()
        if (cancelled) return
        if (on) {
          setPushOn(true)
          return
        }
        await applyPushAutoEnable(false)
      } catch {
        if (!cancelled) setPushOn(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [applyPushAutoEnable])

  const onRunwayGestureForPush = useCallback(() => {
    if (!pushNeedsGesture || pushBusy) return
    void applyPushAutoEnable(true)
  }, [applyPushAutoEnable, pushBusy, pushNeedsGesture])

  const onTogglePush = useCallback(async () => {
    setPushBusy(true)
    setPushNotice(null)
    setPushNeedsGesture(false)
    try {
      // V2-0008: native app push is blocked until #303 + FCM/APNs operator config.
      // Do not pretend Web Push works inside the Capacitor shell.
      if (isNativeShell()) {
        setPushOn(false)
        setPushNotice(
          'App notifications aren’t enabled in this build yet (needs native push config). Web push still works in a browser.',
        )
        return
      }
      if (pushOn) {
        await disableRunwayPush()
        setPushOn(false)
        setPushNotice('Push off for this device')
        return
      }
      if (!pushSupported()) {
        setPushNotice('Push needs a modern browser (or install the app to Home Screen on iPhone).')
        return
      }
      const result = await enableRunwayPush()
      if (result === 'granted') {
        setPushOn(true)
        setPushNotice('Push on — we’ll notify likes, scores, and comments')
      } else if (result === 'denied') {
        setPushNotice('Notifications blocked in browser settings')
      } else if (result === 'disabled') {
        setPushNotice('Push isn’t configured on the server yet')
      } else {
        setPushNotice('Push isn’t supported here')
      }
    } catch (err) {
      setPushNotice(err instanceof ApiError ? err.message : 'Could not update push')
    } finally {
      setPushBusy(false)
    }
  }, [pushOn])

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
    <section
      className={styles.screen}
      aria-labelledby="runway-title"
      onPointerDown={onRunwayGestureForPush}
    >
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

      <div className={styles.pushRow}>
        <div className={styles.pushCopy}>
          <span className={styles.pushLabel}>
            {pushOn ? <Bell size={14} aria-hidden /> : <BellOff size={14} aria-hidden />}
            Push notifications
          </span>
          <span className={styles.pushHint}>
            {pushNotice ||
              (pushOn
                ? 'On — likes, scores, and comments'
                : isNativeShell()
                  ? 'Off — app notifications pending native push setup'
                  : 'Off until you turn it on (browser / PWA)')}
          </span>
        </div>
        <button
          type="button"
          role="switch"
          className={pushOn ? styles.pushToggleOn : styles.pushToggle}
          aria-checked={pushOn}
          aria-label="Push notifications"
          disabled={pushBusy}
          data-testid="runway-push-toggle"
          onClick={() => void onTogglePush()}
        />
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
          <div className={styles.feedHub}>
            <p className={styles.feedHubLead}>
              Open a list to scroll looks — Top 10 worldwide, or only your friends’ circle.
            </p>
            <div className={styles.feedHubActions}>
              <button
                type="button"
                className={styles.hubPrimary}
                onClick={() => setBrowseSheet('top10')}
                data-testid="runway-open-top10"
              >
                <Globe2 size={18} aria-hidden />
                <span className={styles.hubBtnText}>
                  <strong>Show Top 10</strong>
                  <small>
                    {state.top10.length === 0
                      ? 'No worldwide looks yet'
                      : `${state.top10.length} worldwide look${state.top10.length === 1 ? '' : 's'}`}
                  </small>
                </span>
              </button>
              <button
                type="button"
                className={styles.hubSecondary}
                onClick={() => setBrowseSheet('circle')}
                data-testid="runway-open-circle"
              >
                <Users size={18} aria-hidden />
                <span className={styles.hubBtnText}>
                  <strong>My circle</strong>
                  <small>
                    {state.circle.length === 0
                      ? 'Quiet for now — publish or add friends'
                      : `${state.circle.length} look${state.circle.length === 1 ? '' : 's'} from you & friends`}
                  </small>
                </span>
              </button>
            </div>
            {state.circle.length === 0 ? (
              <div className={styles.feedHubHints}>
                <button type="button" className={styles.ghostBtn} onClick={onOpenLooks}>
                  Go to My Looks
                </button>
                <button type="button" className={styles.ghostBtn} onClick={() => setTab('friends')}>
                  Add friends
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {browseSheet && state.status === 'ready' ? (
        <RunwayBrowseSheet
          kind={browseSheet}
          items={browseSheet === 'top10' ? state.top10 : state.circle}
          viewerId={viewerId}
          viewerUsername={viewerUsername}
          onItemChange={patchItem}
          onClose={() => setBrowseSheet(null)}
          onOpenLooks={onOpenLooks}
          onOpenFriends={() => {
            setBrowseSheet(null)
            setTab('friends')
          }}
        />
      ) : null}
    </section>
  )
}

function RunwayBrowseSheet({
  kind,
  items,
  viewerId,
  viewerUsername,
  onItemChange,
  onClose,
  onOpenLooks,
  onOpenFriends,
}: {
  kind: BrowseSheet
  items: GalleryItem[]
  viewerId: string | null
  viewerUsername: string | null
  onItemChange: (next: GalleryItem) => void
  onClose: () => void
  onOpenLooks: () => void
  onOpenFriends: () => void
}) {
  const titleId = useId()
  const isTop10 = kind === 'top10'
  const title = isTop10 ? 'Top 10 worldwide' : 'My circle'
  const hint = isTop10
    ? 'Most liked public looks across FashionRise — scroll down to see more.'
    : 'Only your looks and your friends’ published looks — scroll down to see more.'

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return createPortal(
    <div
      className={styles.sheetScrim}
      role="presentation"
      onClick={onClose}
      data-testid="runway-browse-scrim"
    >
      <div
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.sheetHead}>
          <button
            type="button"
            className={styles.sheetBack}
            aria-label={`Close ${title}`}
            data-testid="runway-browse-back"
            onClick={onClose}
          >
            <ChevronLeft size={18} aria-hidden />
            <span>Back</span>
          </button>
          <div className={styles.sheetTitleBlock}>
            <h2 id={titleId} className={styles.sheetTitle}>
              {isTop10 ? <Globe2 size={18} aria-hidden /> : <Users size={18} aria-hidden />}
              {title}
            </h2>
            <p className={styles.sheetHint}>{hint}</p>
          </div>
        </div>

        <div className={styles.sheetBody}>
          {items.length === 0 ? (
            <EmptyState
              title={isTop10 ? 'No Top 10 yet' : 'Your circle is quiet'}
              body={
                isTop10
                  ? 'Publish a look from My Looks to appear on the worldwide board.'
                  : 'Publish a look from My Looks, or add friends so their Runway posts show up here.'
              }
              actions={
                <>
                  <button type="button" className={styles.primaryBtn} onClick={onOpenLooks}>
                    Go to My Looks
                  </button>
                  {!isTop10 ? (
                    <button type="button" className={styles.ghostBtn} onClick={onOpenFriends}>
                      Add friends
                    </button>
                  ) : null}
                </>
              }
            />
          ) : (
            <ul
              className={styles.sheetList}
              aria-label={isTop10 ? 'Top 10 worldwide' : 'Circle feed'}
            >
              {items.map((item, index) => (
                <RunwayCard
                  key={item.id}
                  item={item}
                  rank={isTop10 ? index + 1 : undefined}
                  isOwn={Boolean(viewerId && item.user_id === viewerId)}
                  viewerId={viewerId}
                  viewerUsername={viewerUsername}
                  onItemChange={onItemChange}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>,
    document.body,
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
  const formRef = useRef<HTMLFormElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [keyboardPad, setKeyboardPad] = useState(0)

  // V2-0011: keep Add friend row above the Android soft keyboard.
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const sync = () => {
      const occluded = Math.max(0, window.innerHeight - vv.height - vv.offsetTop)
      setKeyboardPad(occluded > 40 ? occluded : 0)
      if (document.activeElement === inputRef.current && occluded > 40) {
        formRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    }
    sync()
    vv.addEventListener('resize', sync)
    vv.addEventListener('scroll', sync)
    return () => {
      vv.removeEventListener('resize', sync)
      vv.removeEventListener('scroll', sync)
    }
  }, [])

  return (
    <div className={styles.friendsPanel} style={{ paddingBottom: keyboardPad || undefined }}>
      <form
        ref={formRef}
        className={styles.addFriendForm}
        onSubmit={onAdd}
        data-testid="add-friend-form"
      >
        <label className={styles.addFriendLabel} htmlFor="runway-friend-username">
          Add friend by username
        </label>
        <div className={styles.addFriendRow}>
          <input
            ref={inputRef}
            id="runway-friend-username"
            className={styles.addFriendInput}
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            onFocus={() => {
              // Defer until the keyboard animates open.
              window.setTimeout(() => {
                formRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
              }, 120)
            }}
            placeholder="e.g. yanivprbk"
            autoComplete="username"
            enterKeyHint="send"
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
  viewerId,
  viewerUsername,
  onItemChange,
}: {
  item: GalleryItem
  rank?: number
  compact?: boolean
  isOwn?: boolean
  viewerId: string | null
  viewerUsername: string | null
  onItemChange: (next: GalleryItem) => void
}) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const [busy, setBusy] = useState<'like' | 'score' | 'comment' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [comments, setComments] = useState<GalleryComment[] | null>(null)
  const [commentsError, setCommentsError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const liked = Boolean(item.liked_by_me)
  const canReact = !isOwn
  const chatTitleId = useId()
  const chatInputId = useId()

  const refreshItem = useCallback(async () => {
    const fresh = await getGalleryItem(item.id)
    onItemChange(fresh)
    return fresh
  }, [item.id, onItemChange])

  const loadComments = useCallback(async () => {
    setCommentsError(null)
    try {
      const rows = await listGalleryComments(item.id)
      setComments(rows)
    } catch (err) {
      setCommentsError(err instanceof ApiError ? err.message : 'Could not load comments.')
    }
  }, [item.id])

  const openComments = useCallback(() => {
    setCommentsOpen(true)
    void loadComments()
  }, [loadComments])

  const closeComments = useCallback(() => {
    setCommentsOpen(false)
    setActionError(null)
  }, [])

  useEffect(() => {
    if (!commentsOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      // Capture phase + stop so the browse sheet Escape handler does not also close.
      event.stopImmediatePropagation()
      closeComments()
    }
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey, true)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', onKey, true)
    }
  }, [closeComments, commentsOpen])

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

  const onPostComment = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const body = draft.trim()
      if (!body || busy) return
      setBusy('comment')
      setActionError(null)
      try {
        const row = await postGalleryComment(item.id, body)
        setDraft('')
        setComments((prev) => [
          ...(prev ?? []),
          {
            ...row,
            likes_count: row.likes_count ?? 0,
            liked_by_me: false,
            username: row.username || viewerUsername,
          },
        ])
        setCommentsOpen(true)
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Could not post comment.')
      } finally {
        setBusy(null)
      }
    },
    [busy, draft, item.id, viewerUsername],
  )

  const onToggleCommentLike = useCallback(
    async (comment: GalleryComment) => {
      if (!viewerId || comment.user_id === viewerId || busy) return
      const liked = Boolean(comment.liked_by_me)
      const prevCount = comment.likes_count ?? 0
      setComments((prev) =>
        (prev ?? []).map((row) =>
          row.id === comment.id
            ? {
                ...row,
                liked_by_me: !liked,
                likes_count: Math.max(0, prevCount + (liked ? -1 : 1)),
              }
            : row,
        ),
      )
      try {
        if (liked) await unlikeGalleryComment(comment.id)
        else await likeGalleryComment(comment.id)
      } catch (err) {
        setComments((prev) =>
          (prev ?? []).map((row) =>
            row.id === comment.id
              ? { ...row, liked_by_me: liked, likes_count: prevCount }
              : row,
          ),
        )
        setActionError(err instanceof ApiError ? err.message : 'Could not update comment like.')
      }
    },
    [busy, viewerId],
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
            <button
              type="button"
              className={commentsOpen ? styles.commentBtnOn : styles.commentBtn}
              aria-haspopup="dialog"
              aria-expanded={commentsOpen}
              onClick={openComments}
            >
              <MessageCircle size={12} aria-hidden />
              {comments ? comments.length : 'Chat'}
            </button>
          ) : null}
        </div>
        {isOwn ? (
          <p className={styles.ownHint}>Your look — likes & scores come from others</p>
        ) : null}
        {actionError && !commentsOpen ? (
          <p className={styles.cardError} role="alert">
            {actionError}
          </p>
        ) : null}
      </div>
      {!compact && commentsOpen
        ? createPortal(
            <div
              className={styles.chatScrim}
              role="presentation"
              onClick={(event) => {
                if (event.target === event.currentTarget) closeComments()
              }}
            >
              <div
                className={styles.chatDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby={chatTitleId}
              >
                <header className={styles.chatHead}>
                  <div className={styles.chatHeadText}>
                    <p className={styles.chatEyebrow}>Runway chat</p>
                    <h3 id={chatTitleId} className={styles.chatTitle}>
                      {item.title || 'Untitled look'}
                    </h3>
                  </div>
                  <button
                    type="button"
                    className={styles.chatClose}
                    aria-label="Close chat"
                    onClick={closeComments}
                  >
                    <X size={18} aria-hidden />
                  </button>
                </header>

                <div className={styles.chatBody}>
                  {commentsError ? (
                    <p className={styles.cardError} role="alert">
                      {commentsError}
                    </p>
                  ) : comments == null ? (
                    <p className={styles.commentsStatus}>Loading comments…</p>
                  ) : comments.length === 0 ? (
                    <p className={styles.commentsStatus}>No comments yet — say something nice.</p>
                  ) : (
                    <ul className={styles.commentList} aria-label="Comments">
                      {comments.map((row) => {
                        const ownComment = Boolean(viewerId && row.user_id === viewerId)
                        const commentLiked = Boolean(row.liked_by_me)
                        return (
                          <li key={row.id} className={styles.commentItem}>
                            <div className={styles.commentMain}>
                              <span className={styles.commentAuthor}>
                                @{row.username || 'member'}
                              </span>
                              <span className={styles.commentBody}>{row.body}</span>
                            </div>
                            {ownComment ? (
                              <span
                                className={styles.commentLikeStat}
                                title="Others can like your comment"
                              >
                                <Heart size={11} aria-hidden />
                                {row.likes_count ?? 0}
                              </span>
                            ) : (
                              <button
                                type="button"
                                className={
                                  commentLiked ? styles.commentLikeBtnOn : styles.commentLikeBtn
                                }
                                aria-pressed={commentLiked}
                                aria-label={commentLiked ? 'Unlike comment' : 'Like comment'}
                                onClick={() => void onToggleCommentLike(row)}
                              >
                                <Heart
                                  size={11}
                                  aria-hidden
                                  fill={commentLiked ? 'currentColor' : 'none'}
                                />
                                {row.likes_count ?? 0}
                              </button>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>

                <form className={styles.chatForm} onSubmit={(e) => void onPostComment(e)}>
                  <label className={styles.srOnly} htmlFor={chatInputId}>
                    Add a comment
                  </label>
                  <input
                    id={chatInputId}
                    className={styles.commentInput}
                    value={draft}
                    maxLength={500}
                    placeholder="Add a comment…"
                    disabled={busy === 'comment'}
                    autoFocus
                    onChange={(event) => setDraft(event.target.value)}
                  />
                  <button
                    type="submit"
                    className={styles.commentSend}
                    disabled={busy === 'comment' || !draft.trim()}
                  >
                    Post
                  </button>
                </form>
                {actionError ? (
                  <p className={styles.chatError} role="alert">
                    {actionError}
                  </p>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}
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
