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
  Crown,
  Globe2,
  Heart,
  MessageCircle,
  MoreHorizontal,
  RefreshCw,
  Sparkles,
  Star,
  User,
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
  recordGalleryImpressions,
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
import { isNativeShell } from '@/services/native/platform'
import {
  disableRunwayPush,
  enableRunwayPush,
  ensureDefaultRunwayPush,
  pushSupported,
  runwayPushIsEnabled,
} from '@/services/pushApi'
import { useAuthGalleryImage } from '@/hooks/useAuthGalleryImage'
import {
  followCreator,
  getFollowStatus,
  profileAvatarSrc,
  unfollowCreator,
} from '@/services/profilesApi'
import { FriendProfilePanel, type DesignerRef } from '@/shell/components/FriendProfilePanel'
import styles from './RunwayScreen.module.css'

type Props = {
  onOpenCreate: () => void
  onOpenLooks: () => void
  /** Deep-link from Home header avatar → open own editable profile. */
  openOwnProfile?: boolean
  onOwnProfileConsumed?: () => void
  /**
   * Notify shell whether FashionRise is showing the immersive feed.
   * false → GlobalHeader (profile, Friends manage, etc.); true → full-bleed feed.
   */
  onImmersiveFeedChange?: (immersiveFeed: boolean) => void
  /** Bump from shell when user chooses FashionRise in the nav — closes profile and returns to the feed. */
  feedFocusToken?: number
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | {
      status: 'ready'
      discover: GalleryItem[]
      circle: GalleryItem[]
      following: GalleryItem[]
      top10: GalleryItem[]
    }

type FriendsState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; friends: Friendship[]; requests: Friendship[] }

type TabId = 'discover' | 'feed' | 'following' | 'top' | 'friends'
type BrowseSheet = 'top10' | 'circle' | 'following' | 'discover'
type TopLimit = 10 | 20 | 50

/** Browse sheets stay available for tests/deep links — not shown as feed filters. */
const TOP_LIMIT_DEFAULT: TopLimit = 10
const DISCOVER_PAGE_SIZE = 24

/** Session cache keyed by viewer + designer so account switches cannot leak Follow state. */
const followStatusCache = new Map<string, boolean>()
const followStatusListeners = new Map<string, Set<(following: boolean) => void>>()

export function followStatusCacheKey(viewerId: string, designerId: string): string {
  return `${viewerId}:${designerId}`
}

function publishFollowStatus(cacheKey: string, following: boolean) {
  followStatusCache.set(cacheKey, following)
  const listeners = followStatusListeners.get(cacheKey)
  if (!listeners) return
  for (const listener of listeners) listener(following)
}

function subscribeFollowStatus(
  cacheKey: string,
  listener: (following: boolean) => void,
): () => void {
  let bucket = followStatusListeners.get(cacheKey)
  if (!bucket) {
    bucket = new Set()
    followStatusListeners.set(cacheKey, bucket)
  }
  bucket.add(listener)
  return () => {
    bucket?.delete(listener)
    if (bucket && bucket.size === 0) followStatusListeners.delete(cacheKey)
  }
}

/** Apply a server Follow status only when the session cache is still empty. */
function applyFetchedFollowStatus(cacheKey: string, following: boolean): boolean {
  const existing = followStatusCache.get(cacheKey)
  if (existing !== undefined) return existing
  publishFollowStatus(cacheKey, following)
  return following
}

/** Test-only helpers for account-switch Follow cache coverage. */
export const __followStatusCacheTestUtils = {
  clear() {
    followStatusCache.clear()
    followStatusListeners.clear()
  },
  set(viewerId: string, designerId: string, following: boolean) {
    publishFollowStatus(followStatusCacheKey(viewerId, designerId), following)
  },
  get(viewerId: string, designerId: string): boolean | undefined {
    return followStatusCache.get(followStatusCacheKey(viewerId, designerId))
  },
  size() {
    return followStatusCache.size
  },
}

/** Batch unique Discover impressions only after cards become meaningfully visible. */
function useDiscoverImpressionReporter() {
  const pendingRef = useRef<Set<string>>(new Set())
  const sentRef = useRef<Set<string>>(new Set())
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return useCallback((galleryItemId: string) => {
    if (!galleryItemId || sentRef.current.has(galleryItemId)) return
    pendingRef.current.add(galleryItemId)
    if (timerRef.current) return
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      const ids = [...pendingRef.current]
      pendingRef.current.clear()
      if (ids.length === 0) return
      for (const id of ids) sentRef.current.add(id)
      void recordGalleryImpressions(ids).catch(() => {
        for (const id of ids) sentRef.current.delete(id)
      })
    }, 350)
  }, [])
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 10_000) return `${Math.round(n / 1000)}K`
  if (n >= 1_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`
  return String(n)
}

export function RunwayScreen({
  onOpenCreate,
  onOpenLooks,
  openOwnProfile = false,
  onOwnProfileConsumed,
  onImmersiveFeedChange,
  feedFocusToken = 0,
}: Props) {
  const { user } = useAuth()
  const viewerId = user?.id ?? null
  const viewerUsername = user?.username ?? null
  const [tab, setTab] = useState<TabId>('discover')
  const [browseSheet, setBrowseSheet] = useState<BrowseSheet | null>(null)
  const [topLimit] = useState<TopLimit>(TOP_LIMIT_DEFAULT)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [discoverHasMore, setDiscoverHasMore] = useState(true)
  const [discoverLoadingMore, setDiscoverLoadingMore] = useState(false)
  const reportDiscoverImpression = useDiscoverImpressionReporter()
  const [friendsState, setFriendsState] = useState<FriendsState>({ status: 'loading' })
  const [friendUsername, setFriendUsername] = useState('')
  const [friendBusy, setFriendBusy] = useState(false)
  const [friendNotice, setFriendNotice] = useState<string | null>(null)
  const [pushOn, setPushOn] = useState(false)
  const [pushBusy, setPushBusy] = useState(false)
  const [pushLocked, setPushLocked] = useState(false)
  const [pushNotice, setPushNotice] = useState<string | null>(null)
  const [pushNeedsGesture, setPushNeedsGesture] = useState(false)
  const [viewingDesigner, setViewingDesigner] = useState<DesignerRef | null>(null)
  const [openOwnProfileEditing, setOpenOwnProfileEditing] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!openOwnProfile || !viewerId) return
    // Show the designed profile first — edit opens from Edit Designer Card.
    setOpenOwnProfileEditing(false)
    setViewingDesigner({
      user_id: viewerId,
      username: viewerUsername || undefined,
    })
    onOwnProfileConsumed?.()
  }, [openOwnProfile, onOwnProfileConsumed, viewerId, viewerUsername])

  const immersiveFeed = !viewingDesigner && tab !== 'friends'
  useEffect(() => {
    onImmersiveFeedChange?.(immersiveFeed)
    return () => onImmersiveFeedChange?.(true)
  }, [immersiveFeed, onImmersiveFeedChange])

  const feedFocusSeenRef = useRef(feedFocusToken)
  useEffect(() => {
    if (feedFocusSeenRef.current === feedFocusToken) return
    feedFocusSeenRef.current = feedFocusToken
    setViewingDesigner(null)
    setOpenOwnProfileEditing(false)
    setBrowseSheet(null)
    setMenuOpen(false)
    setTab('discover')
  }, [feedFocusToken])

  const applyPushAutoEnable = useCallback(async (fromGesture: boolean) => {
    setPushBusy(true)
    try {
      // #303: native shell uses fail-closed nativePush via pushApi (flags OFF ⇒ disabled).
      const { on, result } = await ensureDefaultRunwayPush()
      if (on) {
        setPushOn(true)
        setPushLocked(false)
        setPushNeedsGesture(false)
        if (result === 'granted') {
          setPushNotice('Push on — we’ll notify likes, scores, and comments')
        }
        return
      }
      if (result === 'disabled') {
        setPushOn(false)
        setPushLocked(true)
        setPushNeedsGesture(false)
        setPushNotice(
          isNativeShell()
            ? 'Native push isn’t enabled on the server yet'
            : 'Push isn’t configured on the server yet',
        )
        return
      }
      if (result === 'skipped') {
        setPushOn(false)
        setPushNeedsGesture(false)
        return
      }
      if (
        result === 'denied' &&
        !fromGesture &&
        !isNativeShell() &&
        typeof Notification !== 'undefined' &&
        Notification.permission === 'default'
      ) {
        // Browsers often block permission prompts without a tap — retry on next interaction.
        setPushNeedsGesture(true)
        return
      }
      if (result === 'denied') {
        setPushNotice(
          isNativeShell()
            ? 'Notifications blocked in system settings'
            : 'Notifications blocked in browser settings',
        )
        setPushNeedsGesture(false)
      } else if (result === 'unsupported') {
        setPushLocked(true)
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
          setPushLocked(false)
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
    if (pushLocked || !pushNeedsGesture || pushBusy) return
    void applyPushAutoEnable(true)
  }, [applyPushAutoEnable, pushBusy, pushLocked, pushNeedsGesture])

  const onTogglePush = useCallback(async () => {
    if (pushLocked && !pushOn) return
    setPushBusy(true)
    setPushNotice(null)
    setPushNeedsGesture(false)
    try {
      // #303: Capacitor uses nativePush through pushApi (never Web Push in the shell).
      if (pushOn) {
        await disableRunwayPush()
        setPushOn(false)
        setPushNotice('Push off for this device')
        return
      }
      if (!isNativeShell() && !pushSupported()) {
        setPushLocked(true)
        setPushNotice('Push needs a modern browser (or install the app to Home Screen on iPhone).')
        return
      }
      const result = await enableRunwayPush()
      if (result === 'granted') {
        setPushOn(true)
        setPushLocked(false)
        setPushNotice('Push on — we’ll notify likes, scores, and comments')
      } else if (result === 'denied') {
        setPushNotice(
          isNativeShell()
            ? 'Notifications blocked in system settings'
            : 'Notifications blocked in browser settings',
        )
      } else if (result === 'disabled') {
        setPushOn(false)
        setPushLocked(true)
        setPushNotice(
          isNativeShell()
            ? 'Native push isn’t enabled on the server yet'
            : 'Push isn’t configured on the server yet',
        )
      } else {
        setPushLocked(true)
        setPushNotice('Push isn’t supported here')
      }
    } catch (err) {
      setPushNotice(err instanceof ApiError ? err.message : 'Could not update push')
    } finally {
      setPushBusy(false)
    }
  }, [pushLocked, pushOn])

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
      if (tab === 'top') {
        const top10 = await listGallery({ sort: 'top10', limit: topLimit, signal })
        if (signal?.aborted) return
        setState({ status: 'ready', discover: [], circle: [], following: [], top10 })
        return
      }
      if (tab === 'following') {
        const following = await listGallery({ sort: 'following', limit: 48, signal })
        if (signal?.aborted) return
        setState({ status: 'ready', discover: [], circle: [], following, top10: [] })
        return
      }
      if (tab === 'discover') {
        const discover = await listGallery({
          sort: 'discover',
          limit: DISCOVER_PAGE_SIZE,
          signal,
        })
        if (signal?.aborted) return
        setDiscoverHasMore(discover.length >= DISCOVER_PAGE_SIZE)
        setState({ status: 'ready', discover, circle: [], following: [], top10: [] })
        // Impressions are recorded only when cards become meaningfully visible
        // (IntersectionObserver) — never for an entire API batch on load.
        return
      }
      const circle = await listGallery({ sort: 'circle', limit: 48, signal })
      if (signal?.aborted) return
      setState({ status: 'ready', discover: [], circle, following: [], top10: [] })
    } catch (err) {
      if (signal?.aborted) return
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Could not load FashionRise'
      setState({ status: 'error', message })
    }
  }, [tab, topLimit])

  useEffect(() => {
    const ac = new AbortController()
    void load(ac.signal)
    return () => ac.abort()
  }, [load])

  const loadMoreDiscover = useCallback(async () => {
    if (discoverLoadingMore || !discoverHasMore || state.status !== 'ready') return
    setDiscoverLoadingMore(true)
    try {
      const exclude = state.discover.map((item) => item.id)
      const more = await listGallery({
        sort: 'discover',
        limit: DISCOVER_PAGE_SIZE,
        exclude,
      })
      setDiscoverHasMore(more.length >= DISCOVER_PAGE_SIZE)
      if (more.length === 0) return
      setState((prev) => {
        if (prev.status !== 'ready') return prev
        const seen = new Set(prev.discover.map((item) => item.id))
        const merged = [...prev.discover]
        for (const item of more) {
          if (seen.has(item.id)) continue
          seen.add(item.id)
          merged.push(item)
        }
        return { ...prev, discover: merged }
      })
    } catch {
      // Keep hasMore true so a later scroll near the end can retry.
    } finally {
      setDiscoverLoadingMore(false)
    }
  }, [discoverHasMore, discoverLoadingMore, state])

  const openBrowseSheet = useCallback(
    async (sheet: Exclude<BrowseSheet, 'discover'>) => {
      setMenuOpen(false)
      try {
        if (sheet === 'top10') {
          const top10 = await listGallery({ sort: 'top10', limit: topLimit })
          setState((prev) =>
            prev.status === 'ready'
              ? { ...prev, top10 }
              : { status: 'ready', discover: [], circle: [], following: [], top10 },
          )
        } else if (sheet === 'following') {
          const following = await listGallery({ sort: 'following', limit: 48 })
          setState((prev) =>
            prev.status === 'ready'
              ? { ...prev, following }
              : { status: 'ready', discover: [], circle: [], following, top10: [] },
          )
        } else {
          const circle = await listGallery({ sort: 'circle', limit: 48 })
          setState((prev) =>
            prev.status === 'ready'
              ? { ...prev, circle }
              : { status: 'ready', discover: [], circle, following: [], top10: [] },
          )
        }
        setBrowseSheet(sheet)
      } catch (err) {
        setState({
          status: 'error',
          message:
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : 'Could not load FashionRise',
        })
      }
    },
    [topLimit],
  )

  const discoverSentinelRef = useRef<HTMLLIElement | null>(null)
  const discoverCount = state.status === 'ready' ? state.discover.length : 0
  useEffect(() => {
    if (tab !== 'discover' || !discoverHasMore || state.status !== 'ready') return
    const node = discoverSentinelRef.current
    if (!node || typeof IntersectionObserver === 'undefined') return
    const root = node.parentElement
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        void loadMoreDiscover()
      },
      { root, rootMargin: '140% 0px', threshold: 0 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [discoverCount, discoverHasMore, loadMoreDiscover, state.status, tab])

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
        discover: rewrite(prev.discover),
        circle: rewrite(prev.circle),
        following: rewrite(prev.following),
        top10: rewrite(prev.top10),
      }
    })
  }, [])

  if (viewingDesigner) {
    return (
      <section
        className={`${styles.screen} ${styles.profileScreen}`}
        aria-label="Designer profile"
      >
        <FriendProfilePanel
          friend={viewingDesigner}
          startInEditMode={openOwnProfileEditing && viewingDesigner.user_id === viewerId}
        />
      </section>
    )
  }

  const feedItems =
    state.status === 'ready'
      ? tab === 'top'
        ? state.top10
        : tab === 'following'
          ? state.following
          : tab === 'feed'
            ? state.circle
            : state.discover
      : []

  const feedLabel = 'FashionRise feed'

  return (
    <section
      className={styles.screen}
      aria-labelledby="runway-title"
      onPointerDown={onRunwayGestureForPush}
    >
      {tab !== 'friends' ? (
        <header className={styles.chrome}>
          <h1 id="runway-title" className={styles.srOnly}>
            FashionRise
          </h1>
          <div className={styles.chromeTop}>
            <div className={styles.chromeActions}>
              <button
                type="button"
                className={styles.iconBtn}
                aria-label="More"
                aria-expanded={menuOpen}
                data-testid="runway-more-menu"
                onClick={() => setMenuOpen((v) => !v)}
              >
                <MoreHorizontal size={18} aria-hidden />
              </button>
            </div>
          </div>
        </header>
      ) : null}

      {menuOpen ? (
        <div className={styles.menuPanel} role="menu" aria-label="FashionRise menu">
          <p className={styles.menuSectionLabel}>Account</p>
          {viewerId ? (
            <button
              type="button"
              className={styles.menuItem}
              role="menuitem"
              data-testid="runway-my-profile"
              onClick={() => {
                setMenuOpen(false)
                setOpenOwnProfileEditing(false)
                setViewingDesigner({
                  user_id: viewerId,
                  username: viewerUsername || undefined,
                })
              }}
            >
              <User size={14} aria-hidden />
              My Profile
            </button>
          ) : null}
          <button
            type="button"
            className={styles.menuItem}
            role="menuitem"
            onClick={() => {
              setMenuOpen(false)
              onOpenLooks()
            }}
          >
            My Looks
          </button>
          <button
            type="button"
            className={styles.menuItem}
            role="menuitem"
            onClick={() => {
              setMenuOpen(false)
              onOpenCreate()
            }}
          >
            <Sparkles size={14} aria-hidden />
            Start creating
          </button>
          <button
            type="button"
            className={styles.menuItem}
            role="menuitem"
            data-testid="runway-tab-friends"
            onClick={() => {
              setMenuOpen(false)
              setTab('friends')
            }}
          >
            <Users size={14} aria-hidden />
            Manage friends
          </button>
          {tab === 'discover' || tab === 'feed' || tab === 'following' || tab === 'top' ? (
            <button
              type="button"
              className={styles.menuItem}
              role="menuitem"
              onClick={() => {
                setMenuOpen(false)
                void load()
              }}
            >
              <RefreshCw size={14} aria-hidden />
              Refresh feed
            </button>
          ) : null}
          <div className={styles.menuPush}>
            <div className={styles.pushCopy}>
              <span className={styles.pushLabel}>
                {pushOn ? <Bell size={14} aria-hidden /> : <BellOff size={14} aria-hidden />}
                Push notifications
              </span>
              <span className={styles.pushHint}>
                {pushNotice ||
                  (pushOn
                    ? 'On — likes, scores, and comments'
                    : pushLocked
                      ? isNativeShell()
                        ? 'Unavailable until native push is enabled on the server'
                        : 'Unavailable until push is configured on the server'
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
              aria-disabled={pushLocked && !pushOn}
              disabled={pushBusy || (pushLocked && !pushOn)}
              data-testid="runway-push-toggle"
              onClick={() => void onTogglePush()}
            />
          </div>
        </div>
      ) : null}

      {/* Browse-sheet entry points for interaction tests only — not feed filters. */}
      <div className={styles.srOnly} aria-hidden={false}>
        <button type="button" data-testid="runway-open-discover" onClick={() => setBrowseSheet('discover')}>
          Open discover sheet
        </button>
        <button
          type="button"
          data-testid="runway-open-circle"
          onClick={() => void openBrowseSheet('circle')}
        >
          Open circle sheet
        </button>
        <button
          type="button"
          data-testid="runway-open-following"
          onClick={() => void openBrowseSheet('following')}
        >
          Open following sheet
        </button>
        <button
          type="button"
          data-testid="runway-open-top10"
          onClick={() => void openBrowseSheet('top10')}
        >
          Open top sheet
        </button>
        <button type="button" data-testid="runway-tab-feed" onClick={() => void openBrowseSheet('circle')}>
          Friends circle
        </button>
        <button
          type="button"
          data-testid="runway-tab-following"
          onClick={() => void openBrowseSheet('following')}
        >
          Following
        </button>
        <button type="button" data-testid="runway-tab-top" onClick={() => void openBrowseSheet('top10')}>
          Top rankings
        </button>
      </div>

      <div className={styles.body}>
        {tab === 'friends' ? (
          <div className={styles.friendsWrap}>
            <header className={styles.friendsHeader}>
              <div className={styles.friendsTitleBlock}>
                <p className={styles.friendsEyebrow}>FashionRise</p>
                <h1 id="runway-title" className={styles.friendsTitle}>
                  Friends
                </h1>
                <p className={styles.friendsLead}>Invite designers into your private circle.</p>
              </div>
            </header>
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
              onOpenDesigner={(designer) => setViewingDesigner(designer)}
            />
          </div>
        ) : state.status === 'loading' ? (
          <p className={styles.status} role="status">
            Loading FashionRise…
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
        ) : feedItems.length === 0 ? (
          <EmptyState
            title={
              tab === 'top'
                ? 'No Top rankings yet'
                : tab === 'following'
                  ? 'No follows yet'
                  : tab === 'feed'
                    ? 'Your circle is quiet'
                    : 'Nothing to discover yet'
            }
            body={
              tab === 'top'
                ? 'Publish a look from My Looks to appear on the worldwide board.'
                : tab === 'following'
                  ? 'Follow designers from their FashionRise profiles to fill this feed.'
                  : tab === 'feed'
                    ? 'Publish a look or add friends to fill this feed.'
                    : 'Publish a look from My Looks — new designs get a fair chance here.'
            }
            actions={
              <div className={styles.feedHubHints}>
                <button type="button" className={styles.ghostBtn} onClick={onOpenLooks}>
                  Go to My Looks
                </button>
                {tab === 'feed' ? (
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={() => setTab('friends')}
                  >
                    Add friends
                  </button>
                ) : null}
              </div>
            }
          />
        ) : (
          <>
            <ul className={`${styles.immersiveFeed} ${styles.feedSnap}`} aria-label={feedLabel}>
              {feedItems.map((item, index) => (
                <RunwayCard
                  key={item.id}
                  item={item}
                  rank={tab === 'top' ? index + 1 : undefined}
                  layout="immersive"
                  isOwn={Boolean(viewerId && item.user_id === viewerId)}
                  viewerId={viewerId}
                  viewerUsername={viewerUsername}
                  onItemChange={patchItem}
                  onOpenDesigner={(designer) => setViewingDesigner(designer)}
                  onVisibleImpression={
                    tab === 'discover' && viewerId && item.user_id !== viewerId
                      ? reportDiscoverImpression
                      : undefined
                  }
                />
              ))}
              {tab === 'discover' && discoverHasMore ? (
                <li
                  ref={discoverSentinelRef}
                  className={styles.discoverSentinel}
                  data-testid="runway-discover-load-more"
                  aria-hidden={discoverLoadingMore ? undefined : true}
                >
                  {discoverLoadingMore ? (
                    <span className={styles.status} role="status">
                      Loading more looks…
                    </span>
                  ) : null}
                </li>
              ) : null}
            </ul>
          </>
        )}
      </div>

      {browseSheet && state.status === 'ready' ? (
        <RunwayBrowseSheet
          kind={browseSheet}
          items={
            browseSheet === 'top10'
              ? state.top10
              : browseSheet === 'following'
                ? state.following
                : browseSheet === 'discover'
                  ? state.discover
                  : state.circle
          }
          viewerId={viewerId}
          viewerUsername={viewerUsername}
          onItemChange={patchItem}
          onClose={() => setBrowseSheet(null)}
          onOpenLooks={onOpenLooks}
          onOpenFriends={() => {
            setBrowseSheet(null)
            setTab('friends')
          }}
          onOpenDesigner={(designer) => {
            setBrowseSheet(null)
            setViewingDesigner(designer)
          }}
          onVisibleImpression={
            browseSheet === 'discover' ? reportDiscoverImpression : undefined
          }
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
  onOpenDesigner,
  onVisibleImpression,
}: {
  kind: BrowseSheet
  items: GalleryItem[]
  viewerId: string | null
  viewerUsername: string | null
  onItemChange: (next: GalleryItem) => void
  onClose: () => void
  onOpenLooks: () => void
  onOpenFriends: () => void
  onOpenDesigner: (designer: DesignerRef) => void
  onVisibleImpression?: (galleryItemId: string) => void
}) {
  const titleId = useId()
  const isTop10 = kind === 'top10'
  const isFollowing = kind === 'following'
  const isDiscover = kind === 'discover'
  const title = isTop10
    ? 'Top rankings worldwide'
    : isFollowing
      ? 'Following'
      : isDiscover
        ? 'Discover'
        : 'My circle'
  const hint = isTop10
    ? 'Most liked public looks across FashionRise — scroll to see the full board.'
    : isFollowing
      ? 'Looks from designers you follow — scroll down to see more.'
      : isDiscover
        ? 'Fair Discover — seven-day looks, fresh exposure, many creators — scroll for more.'
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
              {isTop10 || isDiscover ? (
                <Globe2 size={18} aria-hidden />
              ) : isFollowing ? (
                <UserPlus size={18} aria-hidden />
              ) : (
                <Users size={18} aria-hidden />
              )}
              {title}
            </h2>
            <p className={styles.sheetHint}>{hint}</p>
          </div>
        </div>

        <div className={styles.sheetBody}>
          {items.length === 0 ? (
            <EmptyState
              title={
                isTop10
                  ? 'No Top rankings yet'
                  : isFollowing
                    ? 'No follows yet'
                    : isDiscover
                      ? 'Nothing to discover yet'
                      : 'Your circle is quiet'
              }
              body={
                isTop10
                  ? 'Publish a look from My Looks to appear on the worldwide board.'
                  : isFollowing
                    ? 'Follow designers from their FashionRise profiles to fill this feed.'
                    : isDiscover
                      ? 'Publish a look from My Looks — new designs get a fair chance for seven days.'
                      : 'Publish a look from My Looks, or add friends so their FashionRise posts show up here.'
              }
              actions={
                <>
                  <button type="button" className={styles.primaryBtn} onClick={onOpenLooks}>
                    Go to My Looks
                  </button>
                  {!isTop10 && !isFollowing && !isDiscover ? (
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
              aria-label={
                isTop10
                  ? 'Top rankings worldwide'
                  : isFollowing
                    ? 'Following feed'
                    : isDiscover
                      ? 'Discover feed'
                      : 'Circle feed'
              }
            >
              {items.map((item, index) => (
                <RunwayCard
                  key={item.id}
                  item={item}
                  rank={isTop10 ? index + 1 : undefined}
                  layout={isTop10 ? 'rank' : 'stack'}
                  isOwn={Boolean(viewerId && item.user_id === viewerId)}
                  viewerId={viewerId}
                  viewerUsername={viewerUsername}
                  onItemChange={onItemChange}
                  onOpenDesigner={onOpenDesigner}
                  onVisibleImpression={
                    onVisibleImpression && viewerId && item.user_id !== viewerId
                      ? onVisibleImpression
                      : undefined
                  }
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
  onOpenDesigner,
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
  /** Open the same full-screen designer profile used from Discover (not nested in Friends). */
  onOpenDesigner: (designer: DesignerRef) => void
}) {
  const formRef = useRef<HTMLFormElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // V2-0011: keep Add friend row visible when the soft keyboard opens.
  // Do NOT pad by visualViewport occlusion — that stacked with `--fr-vv-height`
  // shrinking `#root` and produced a full-bleed black void (Android native).
  // Android uses adjustResize; scroll the sticky form into view gently instead.
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const sync = () => {
      if (document.activeElement !== inputRef.current) return
      formRef.current?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
    }
    vv.addEventListener('resize', sync)
    vv.addEventListener('scroll', sync)
    return () => {
      vv.removeEventListener('resize', sync)
      vv.removeEventListener('scroll', sync)
    }
  }, [])

  const ready = state.status === 'ready'
  const circlePreview = ready ? state.friends.slice(0, 4) : []

  return (
    <div className={styles.friendsPanel}>
      <div className={styles.friendsHeroCard} aria-hidden={false}>
        <div className={styles.friendsHeroCopy}>
          <p className={styles.friendsHeroKicker}>Your private circle</p>
          <p className={styles.friendsHeroTitle}>Design together</p>
          <p className={styles.friendsHeroBody}>
            {ready
              ? state.friends.length > 0
                ? `${state.friends.length} designer${state.friends.length === 1 ? '' : 's'} in your circle`
                : 'Add someone by username to start'
              : 'Loading your circle…'}
          </p>
        </div>
        <div className={styles.friendsHeroAvatars} aria-hidden>
          {circlePreview.length > 0 ? (
            circlePreview.map((row) => {
              const label = row.friend.display_name || row.friend.username
              return (
                <span key={row.id} className={styles.friendsHeroAvatar}>
                  <DesignerAvatar
                    userId={row.friend.user_id}
                    label={label}
                    avatarUrl={row.friend.avatar_url}
                  />
                </span>
              )
            })
          ) : (
            <>
              <span className={styles.friendsHeroSlot}>+</span>
              <span className={styles.friendsHeroSlot}>+</span>
              <span className={styles.friendsHeroSlot}>+</span>
            </>
          )}
        </div>
      </div>

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
          <span className={styles.addFriendAt} aria-hidden>
            @
          </span>
          <input
            ref={inputRef}
            id="runway-friend-username"
            className={styles.addFriendInput}
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            onFocus={() => {
              // nearest — center scroll left a black empty band above the keyboard.
              window.setTimeout(() => {
                formRef.current?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
                inputRef.current?.focus({ preventScroll: true })
              }, 50)
            }}
            placeholder="yanivprbk"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            inputMode="text"
            enterKeyHint="done"
            disabled={busy}
          />
        </div>
        <button
          type="submit"
          className={styles.addFriendSubmit}
          disabled={busy || !username.trim()}
        >
          <UserPlus size={16} aria-hidden />
          {busy ? 'Adding…' : 'Add friend'}
        </button>
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

      {ready ? (
        <>
          {state.requests.length > 0 ? (
            <section className={styles.friendSection} aria-label="Friend requests">
              <div className={styles.friendSectionHead}>
                <h2 className={styles.friendSectionTitle}>Requests</h2>
                <span className={styles.friendSectionCount}>{state.requests.length}</span>
              </div>
              <ul className={styles.friendList}>
                {state.requests.map((row) => {
                  const label = row.friend.display_name || row.friend.username
                  return (
                    <li key={row.id} className={`${styles.friendCard} ${styles.friendCardRequest}`}>
                      <div className={styles.friendCardMain}>
                        <DesignerAvatar
                          userId={row.friend.user_id}
                          label={label}
                          avatarUrl={row.friend.avatar_url}
                        />
                        <div className={styles.friendText}>
                          <strong>{label}</strong>
                          <span>@{row.friend.username}</span>
                          <em className={styles.friendAsk}>Add as a friend?</em>
                        </div>
                      </div>
                      <div className={styles.friendCardActions}>
                        <button
                          type="button"
                          className={styles.friendAccept}
                          disabled={busy}
                          onClick={() => onAccept(row.id)}
                        >
                          Accept
                        </button>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
          ) : null}

          <section className={styles.friendSection} aria-label="Your friends">
            <div className={styles.friendSectionHead}>
              <h2 className={styles.friendSectionTitle}>Your circle</h2>
              <span className={styles.friendSectionCount}>{state.friends.length}</span>
            </div>
            {state.friends.length === 0 ? (
              <div className={styles.friendsEmpty}>
                <button
                  type="button"
                  className={styles.friendsEmptyBtn}
                  aria-label="Focus add friend"
                  onClick={() => inputRef.current?.focus()}
                >
                  <UserPlus size={28} aria-hidden />
                </button>
                <p className={styles.friendsEmptyTitle}>Add a friend</p>
                <p className={styles.friendsEmptyBody}>
                  Invite the designers closest to you by FashionRise username.
                </p>
              </div>
            ) : (
              <ul className={styles.friendList}>
                {state.friends.map((row) => {
                  const label = row.friend.display_name || row.friend.username
                  return (
                    <li key={row.id} className={styles.friendCard}>
                      <button
                        type="button"
                        className={styles.friendOpen}
                        data-testid={`friend-open-${row.friend.user_id}`}
                        onClick={() =>
                          onOpenDesigner({
                            user_id: row.friend.user_id,
                            username: row.friend.username,
                            display_name: row.friend.display_name,
                            avatar_url: row.friend.avatar_url,
                          })
                        }
                      >
                        <DesignerAvatar
                          userId={row.friend.user_id}
                          label={label}
                          avatarUrl={row.friend.avatar_url}
                        />
                        <span className={styles.friendText}>
                          <strong>{label}</strong>
                          <span>@{row.friend.username}</span>
                        </span>
                      </button>
                      <button
                        type="button"
                        className={styles.friendRemove}
                        disabled={busy}
                        data-testid={`friend-remove-${row.friend.user_id}`}
                        aria-label={`Remove ${label}`}
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

/** Profile photo on FashionRise look chips — falls back to initial when missing. */
function DesignerAvatar({
  userId,
  label,
  avatarUrl,
}: {
  userId: string
  label: string
  avatarUrl?: string | null
}) {
  const [broken, setBroken] = useState(false)
  const initial = (label.trim()[0] || '·').toUpperCase()
  // null = API says no photo; undefined = older payload — still try the avatar route.
  const src =
    avatarUrl === null
      ? null
      : profileAvatarSrc(userId, avatarUrl || `/api/v1/profiles/${encodeURIComponent(userId)}/avatar`)

  if (!src || broken) {
    return (
      <span className={styles.designerAvatar} aria-hidden data-testid="designer-avatar-fallback">
        {initial}
      </span>
    )
  }

  return (
    <img
      src={src}
      alt=""
      className={styles.designerAvatarImg}
      data-testid="designer-avatar-photo"
      draggable={false}
      onError={() => setBroken(true)}
    />
  )
}

function RunwayCard({
  item,
  rank,
  compact = false,
  layout = 'stack',
  isOwn = false,
  viewerId,
  viewerUsername,
  onItemChange,
  onOpenDesigner,
  onVisibleImpression,
}: {
  item: GalleryItem
  rank?: number
  compact?: boolean
  layout?: 'stack' | 'rank' | 'immersive'
  isOwn?: boolean
  viewerId: string | null
  viewerUsername: string | null
  onItemChange: (next: GalleryItem) => void
  onOpenDesigner?: (designer: DesignerRef) => void
  /** Discover: fire once when the card is meaningfully on-screen (not on API load). */
  onVisibleImpression?: (galleryItemId: string) => void
}) {
  const authImg = useAuthGalleryImage(item.look_id ? item.id : null, Boolean(item.look_id))
  const src = authImg.url || item.image_url
  const cardRef = useRef<HTMLLIElement | null>(null)
  const impressionSentRef = useRef(false)
  const [busy, setBusy] = useState<'like' | 'score' | 'comment' | 'follow' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [comments, setComments] = useState<GalleryComment[] | null>(null)
  const [commentsError, setCommentsError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [followingDesigner, setFollowingDesigner] = useState(false)
  const [followKnown, setFollowKnown] = useState(false)
  const liked = Boolean(item.liked_by_me)
  const canReact = !isOwn
  const immersive = layout === 'immersive'
  const chatTitleId = useId()
  const chatInputId = useId()
  const designerLabel = item.username?.trim() || null
  const designerAvatar = (
    <DesignerAvatar
      userId={item.user_id}
      label={designerLabel || item.title || '·'}
      avatarUrl={item.avatar_url}
    />
  )

  useEffect(() => {
    impressionSentRef.current = false
  }, [item.id])

  useEffect(() => {
    if (!immersive || isOwn || !viewerId) {
      setFollowKnown(false)
      setFollowingDesigner(false)
      return
    }
    const cacheKey = followStatusCacheKey(viewerId, item.user_id)
    const cached = followStatusCache.get(cacheKey)
    if (cached !== undefined) {
      setFollowingDesigner(cached)
      setFollowKnown(true)
    }

    // Keep every card for this designer in sync after Follow/Unfollow on another look.
    const unsubscribe = subscribeFollowStatus(cacheKey, (following) => {
      setFollowingDesigner(following)
      setFollowKnown(true)
    })

    if (cached !== undefined) {
      return unsubscribe
    }

    const applyRow = (row: { following?: boolean }) => {
      const next = applyFetchedFollowStatus(cacheKey, Boolean(row.following))
      setFollowingDesigner(next)
      setFollowKnown(true)
    }

    const node = cardRef.current
    if (!node || typeof IntersectionObserver === 'undefined') {
      let cancelled = false
      void getFollowStatus(item.user_id)
        .then((row) => {
          if (cancelled) return
          applyRow(row)
        })
        .catch(() => {
          if (!cancelled) setFollowKnown(true)
        })
      return () => {
        cancelled = true
        unsubscribe()
      }
    }
    let cancelled = false
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.4)) {
          return
        }
        observer.disconnect()
        // Prefer session cache if another card already followed while we waited.
        const latest = followStatusCache.get(cacheKey)
        if (latest !== undefined) {
          setFollowingDesigner(latest)
          setFollowKnown(true)
          return
        }
        void getFollowStatus(item.user_id)
          .then((row) => {
            if (cancelled) return
            applyRow(row)
          })
          .catch(() => {
            if (!cancelled) setFollowKnown(true)
          })
      },
      { threshold: [0.4] },
    )
    observer.observe(node)
    return () => {
      cancelled = true
      observer.disconnect()
      unsubscribe()
    }
  }, [immersive, isOwn, item.user_id, viewerId])

  useEffect(() => {
    if (!onVisibleImpression || isOwn) return
    const node = cardRef.current
    if (!node || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.55) continue
          if (impressionSentRef.current) continue
          impressionSentRef.current = true
          onVisibleImpression(item.id)
          observer.disconnect()
          return
        }
      },
      { threshold: [0.55], rootMargin: '0px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [isOwn, item.id, onVisibleImpression])

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

  const onToggleFollow = useCallback(async () => {
    if (isOwn || !viewerId || busy) return
    setBusy('follow')
    setActionError(null)
    const prev = followingDesigner
    const cacheKey = followStatusCacheKey(viewerId, item.user_id)
    publishFollowStatus(cacheKey, !prev)
    try {
      if (prev) await unfollowCreator(item.user_id)
      else await followCreator(item.user_id)
      setFollowKnown(true)
    } catch (err) {
      publishFollowStatus(cacheKey, prev)
      setActionError(err instanceof ApiError ? err.message : 'Could not update follow.')
    } finally {
      setBusy(null)
    }
  }, [busy, followingDesigner, isOwn, item.user_id, viewerId])

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

  const ranked = layout === 'rank' && rank != null
  const cardClass = immersive
    ? styles.immersiveCard
    : compact
      ? styles.topCard
      : ranked
        ? rank === 1
          ? `${styles.rankCard} ${styles.rankCardLead}`
          : styles.rankCard
        : styles.card
  const badgeClass =
    rank === 1
      ? styles.rankBadgeGold
      : rank === 2
        ? styles.rankBadgeSilver
        : rank === 3
          ? styles.rankBadgeBronze
          : styles.rankBadge

  const followControl =
    immersive && !isOwn && viewerId ? (
      <button
        type="button"
        className={followingDesigner ? styles.followChipOn : styles.followChip}
        aria-pressed={followingDesigner}
        disabled={busy === 'follow' || !followKnown}
        data-testid={`runway-follow-${item.user_id}`}
        onClick={() => void onToggleFollow()}
      >
        {followingDesigner ? 'Following' : 'Follow'}
      </button>
    ) : null

  const actionRail = (
    <div className={immersive ? styles.immersiveActions : styles.cardActions}>
      {canReact ? (
        <button
          type="button"
          className={liked ? styles.likeBtnOn : styles.likeBtn}
          aria-pressed={liked}
          aria-label={liked ? 'Unlike look' : 'Like look'}
          disabled={busy === 'like'}
          onClick={() => void onToggleLike()}
        >
          <Heart size={immersive ? 26 : 13} aria-hidden fill={liked ? 'currentColor' : 'none'} />
          <span className={immersive ? styles.actionCount : undefined}>
            {formatCount(item.likes_count)}
          </span>
        </button>
      ) : (
        <span className={styles.statChip} title="Others can like your look">
          <Heart size={immersive ? 26 : 12} aria-hidden />
          <span className={immersive ? styles.actionCount : undefined}>
            {formatCount(item.likes_count)}
          </span>
        </span>
      )}
      {canReact ? (
        <label className={immersive ? styles.immersiveScore : styles.scoreLabel}>
          <span className={styles.scoreLabelText}>
            <Star size={immersive ? 24 : 12} aria-hidden />
            <span className={immersive ? styles.actionCount : undefined}>
              {item.rating_average != null
                ? item.rating_average.toFixed(1)
                : immersive
                  ? 'Rate'
                  : 'Score'}
            </span>
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
          <Star size={immersive ? 24 : 12} aria-hidden />
          <span className={immersive ? styles.actionCount : undefined}>
            {item.rating_average != null ? item.rating_average.toFixed(1) : '—'}
            {!immersive && item.rating_count > 0 ? ` (${item.rating_count})` : ''}
          </span>
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
          <MessageCircle size={immersive ? 26 : 12} aria-hidden />
          <span className={immersive ? styles.actionCount : undefined}>
            {comments ? comments.length : immersive ? '0' : 'Chat'}
          </span>
        </button>
      ) : null}
      {!immersive && !isOwn && viewerId ? (
        <button
          type="button"
          className={followingDesigner ? styles.followBtnOn : styles.followBtn}
          aria-pressed={followingDesigner}
          disabled={busy === 'follow' || !followKnown}
          data-testid={`runway-follow-${item.user_id}`}
          onClick={() => void onToggleFollow()}
        >
          <UserPlus size={16} aria-hidden />
          {followingDesigner ? 'Following' : 'Follow'}
        </button>
      ) : null}
    </div>
  )

  return (
    <li
      ref={cardRef}
      className={cardClass}
      data-gallery-item-id={item.id}
      data-testid={onVisibleImpression ? `runway-discover-card-${item.id}` : undefined}
    >
      {immersive ? (
        <>
          <div className={styles.immersiveMedia}>
            {rank != null ? (
              <span className={badgeClass}>
                {rank <= 3 ? <Crown size={10} aria-hidden /> : null}#{rank}
              </span>
            ) : null}
            {src ? (
              <img
                src={src}
                alt=""
                className={styles.immersiveImg}
                draggable={false}
                decoding="async"
              />
            ) : (
              <span className={styles.thumbEmpty} aria-hidden>
                <Star size={36} />
              </span>
            )}
            <div className={styles.immersiveShade} aria-hidden />
          </div>
          <div className={styles.immersiveOverlay}>
            <div className={styles.immersiveMeta}>
              <div className={styles.designerRow}>
                {onOpenDesigner ? (
                  <button
                    type="button"
                    className={styles.designerChip}
                    data-testid={`runway-open-designer-${item.user_id}`}
                    onClick={() =>
                      onOpenDesigner({
                        user_id: item.user_id,
                        username: item.username || undefined,
                      })
                    }
                  >
                    {designerAvatar}
                    <span className={styles.designerChipText}>
                      <strong>
                        {designerLabel ? `@${designerLabel}` : 'View designer'}
                      </strong>
                    </span>
                  </button>
                ) : (
                  <div className={styles.designerChip}>
                    {designerAvatar}
                    <span className={styles.designerChipText}>
                      <strong>
                        {designerLabel ? `@${designerLabel}` : 'Designer'}
                      </strong>
                    </span>
                  </div>
                )}
                {followControl}
              </div>
              {item.title?.trim() ? (
                <p className={styles.immersiveCaption}>{item.title.trim()}</p>
              ) : null}
              {actionError && !commentsOpen ? (
                <p className={styles.cardError} role="alert">
                  {actionError}
                </p>
              ) : null}
            </div>
            {actionRail}
          </div>
        </>
      ) : (
        <>
          <div className={ranked ? styles.rankThumb : styles.thumb}>
            {rank != null ? (
              <span className={badgeClass}>
                {rank <= 3 ? <Crown size={10} aria-hidden /> : null}#{rank}
              </span>
            ) : null}
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
            {onOpenDesigner && !isOwn ? (
              <button
                type="button"
                className={styles.designerLink}
                data-testid={`runway-open-designer-${item.user_id}`}
                onClick={() => onOpenDesigner({ user_id: item.user_id })}
              >
                View designer
              </button>
            ) : null}
            {ranked ? (
              <div className={styles.rankStats} aria-label="Look stats">
                <span>
                  <Heart size={12} aria-hidden />
                  {formatCount(item.likes_count)}
                  <small>Likes</small>
                </span>
                <span>
                  <Star size={12} aria-hidden />
                  {item.rating_average != null ? item.rating_average.toFixed(2) : '—'}
                  <small>Avg. Score</small>
                </span>
                <span>
                  <Users size={12} aria-hidden />
                  {formatCount(item.rating_count)}
                  <small>Raters</small>
                </span>
              </div>
            ) : null}
            {actionRail}
            {isOwn ? (
              <p className={styles.ownHint}>Your look — likes & scores come from others</p>
            ) : null}
            {actionError && !commentsOpen ? (
              <p className={styles.cardError} role="alert">
                {actionError}
              </p>
            ) : null}
          </div>
        </>
      )}
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
                    <p className={styles.chatEyebrow}>FashionRise chat</p>
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
