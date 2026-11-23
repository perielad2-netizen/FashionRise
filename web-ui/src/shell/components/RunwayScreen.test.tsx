import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  RunwayScreen,
  __followStatusCacheTestUtils,
  followStatusCacheKey,
} from './RunwayScreen'

const listGallery = vi.fn()
const recordGalleryImpressions = vi.fn()
const getGalleryItem = vi.fn()
const likeGalleryItem = vi.fn()
const unlikeGalleryItem = vi.fn()
const rateGalleryItem = vi.fn()
const listGalleryComments = vi.fn()
const postGalleryComment = vi.fn()
const likeGalleryComment = vi.fn()
const unlikeGalleryComment = vi.fn()
const reportGalleryItem = vi.fn()
const listFriends = vi.fn()
const listFriendRequests = vi.fn()
const listOutgoingFriendRequests = vi.fn()
const searchFriends = vi.fn()
const requestFriendByUserId = vi.fn()
const acceptFriendRequest = vi.fn()
const rejectFriendRequest = vi.fn()
const listUserGallery = vi.fn()
const getPublicProfile = vi.fn()
const removeFriend = vi.fn()
const fetchGalleryImageBlob = vi.fn(async () => new Blob(['look'], { type: 'image/png' }))
const plantFittingRoomGarment = vi.fn(async () => undefined)
const blobToFittingRoomDataUrl = vi.fn(async () => ({
  dataUrl: 'data:image/png;base64,look',
  mimeType: 'image/png',
}))

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
  recordGalleryImpressions: (...args: unknown[]) => recordGalleryImpressions(...args),
  getGalleryItem: (...args: unknown[]) => getGalleryItem(...args),
  likeGalleryItem: (...args: unknown[]) => likeGalleryItem(...args),
  unlikeGalleryItem: (...args: unknown[]) => unlikeGalleryItem(...args),
  rateGalleryItem: (...args: unknown[]) => rateGalleryItem(...args),
  listGalleryComments: (...args: unknown[]) => listGalleryComments(...args),
  postGalleryComment: (...args: unknown[]) => postGalleryComment(...args),
  likeGalleryComment: (...args: unknown[]) => likeGalleryComment(...args),
  unlikeGalleryComment: (...args: unknown[]) => unlikeGalleryComment(...args),
  reportGalleryItem: (...args: unknown[]) => reportGalleryItem(...args),
  listUserGallery: (...args: unknown[]) => listUserGallery(...args),
  fetchGalleryImageBlob: (...args: unknown[]) => fetchGalleryImageBlob(...args),
}))

vi.mock('@/config/fittingRoomUi', () => ({
  isFittingRoomUiEnabled: () => true,
}))

vi.mock('@/lib/fittingRoomStore', () => ({
  plantFittingRoomGarment: (...args: unknown[]) => plantFittingRoomGarment(...args),
  blobToFittingRoomDataUrl: (...args: unknown[]) => blobToFittingRoomDataUrl(...args),
}))

const getFollowStatus = vi.fn()
const followCreator = vi.fn()
const unfollowCreator = vi.fn()
const updateMyProfile = vi.fn()
const uploadMyAvatar = vi.fn()

vi.mock('@/services/profilesApi', () => ({
  getPublicProfile: (...args: unknown[]) => getPublicProfile(...args),
  getFollowStatus: (...args: unknown[]) => getFollowStatus(...args),
  followCreator: (...args: unknown[]) => followCreator(...args),
  unfollowCreator: (...args: unknown[]) => unfollowCreator(...args),
  updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
  uploadMyAvatar: (...args: unknown[]) => uploadMyAvatar(...args),
  profileAvatarSrc: (userId: string, avatarUrl: string | null | undefined) =>
    avatarUrl ? `/api/v1/profiles/${userId}/avatar` : null,
}))

vi.mock('@/services/competitionsApi', () => ({
  fetchCompetitionStatus: vi.fn(async () => ({
    week_start: '2026-11-15T00:00:00+00:00',
    week_end: '2026-11-22T00:00:00+00:00',
    week_key: '2026-11-15',
    status: 'open',
    days_remaining: 3,
    seconds_remaining: 259200,
    group_count: 1,
    standing: null,
    top_designs: [],
    top_designers: [],
    award_categories: [{ id: 'top_design', label: 'Top Design', stars: 50 }],
    runway_note: 'Worldwide Runway stays global',
    publish_note: 'Publish anytime. Weekly Star prizes are not active yet.',
    weekly_rewards_enabled: false,
    weekly_rewards_launch_week_start: null,
  })),
  fetchCompetitionAwards: vi.fn(async () => []),
  fetchStreakStatus: vi.fn(async () => ({
    current_streak: 1,
    cycle_day: 1,
    last_checkin_date: '2026-11-16',
    lifetime_checkins: 1,
    days_until_reward: 6,
    rewarded_this_checkin: false,
    stars_awarded: 0,
    reward_every_days: 7,
    reward_stars: 10,
    rewards_enabled: false,
  })),
  streakCycleDay: (s: { current_streak?: number; cycle_day?: number; reward_every_days?: number }) => {
    const every = Math.max(1, s.reward_every_days || 7)
    if (typeof s.cycle_day === 'number' && s.cycle_day > 0) return Math.min(every, s.cycle_day)
    const raw = Math.max(0, s.current_streak || 0)
    if (raw <= 0) return 0
    return ((raw - 1) % every) + 1
  },
  postStreakCheckIn: vi.fn(async () => ({
    current_streak: 1,
    cycle_day: 1,
    last_checkin_date: '2026-11-16',
    lifetime_checkins: 1,
    days_until_reward: 6,
    rewarded_this_checkin: false,
    stars_awarded: 0,
    reward_every_days: 7,
    reward_stars: 10,
    rewards_enabled: false,
  })),
}))

vi.mock('@/services/friendsApi', () => ({
  listFriends: (...args: unknown[]) => listFriends(...args),
  listFriendRequests: (...args: unknown[]) => listFriendRequests(...args),
  listOutgoingFriendRequests: (...args: unknown[]) => listOutgoingFriendRequests(...args),
  searchFriends: (...args: unknown[]) => searchFriends(...args),
  requestFriendByUserId: (...args: unknown[]) => requestFriendByUserId(...args),
  requestFriendByUsername: vi.fn(),
  acceptFriendRequest: (...args: unknown[]) => acceptFriendRequest(...args),
  rejectFriendRequest: (...args: unknown[]) => rejectFriendRequest(...args),
  removeFriend: (...args: unknown[]) => removeFriend(...args),
}))

const enableRunwayPush = vi.fn()
const disableRunwayPush = vi.fn()
const runwayPushIsEnabled = vi.fn()
const ensureDefaultRunwayPush = vi.fn()

vi.mock('@/services/pushApi', () => ({
  pushSupported: () => true,
  runwayPushIsEnabled: (...args: unknown[]) => runwayPushIsEnabled(...args),
  enableRunwayPush: (...args: unknown[]) => enableRunwayPush(...args),
  disableRunwayPush: (...args: unknown[]) => disableRunwayPush(...args),
  ensureDefaultRunwayPush: (...args: unknown[]) => ensureDefaultRunwayPush(...args),
  isPushDesired: () => true,
  setPushDesired: vi.fn(),
}))

const unpublishLookFromRunway = vi.fn()

vi.mock('@/services/looksApi', () => ({
  unpublishLookFromRunway: (...args: unknown[]) => unpublishLookFromRunway(...args),
}))

let authUser = { id: 'viewer-1', email: 'viewer@example.com', username: 'viewer' }

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: authUser,
    refreshUser: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

const circleItem = {
  id: 'circle-1',
  design_id: null,
  look_id: 'look-circle',
  user_id: 'friend-1',
  title: 'Friend circle look',
  image_url: null,
  visibility: 'public',
  rating_average: null,
  rating_count: 0,
  likes_count: 0,
  moderation_status: 'ok',
  created_at: '2026-11-07T00:00:00Z',
  updated_at: '2026-11-07T00:00:00Z',
  liked_by_me: false,
  my_score: null,
}

const topItem = {
  id: 'top-1',
  design_id: null,
  look_id: 'look-top',
  user_id: 'u-top',
  title: 'Worldwide hit',
  image_url: null,
  visibility: 'public',
  rating_average: 9,
  rating_count: 3,
  likes_count: 12,
  moderation_status: 'ok',
  created_at: '2026-11-07T00:00:00Z',
  updated_at: '2026-11-07T00:00:00Z',
  liked_by_me: false,
  my_score: null,
}

describe('RunwayScreen', () => {
  beforeEach(() => {
    authUser = { id: 'viewer-1', email: 'viewer@example.com', username: 'viewer' }
    __followStatusCacheTestUtils.clear()
    listGallery.mockReset()
    recordGalleryImpressions.mockReset()
    getGalleryItem.mockReset()
    likeGalleryItem.mockReset()
    unlikeGalleryItem.mockReset()
    rateGalleryItem.mockReset()
    listGalleryComments.mockReset()
    postGalleryComment.mockReset()
    likeGalleryComment.mockReset()
    unlikeGalleryComment.mockReset()
    listFriends.mockReset()
    listFriendRequests.mockReset()
    listOutgoingFriendRequests.mockReset()
    searchFriends.mockReset()
    requestFriendByUserId.mockReset()
    acceptFriendRequest.mockReset()
    rejectFriendRequest.mockReset()
    listUserGallery.mockReset()
    getPublicProfile.mockReset()
    getFollowStatus.mockReset()
    followCreator.mockReset()
    followCreator.mockResolvedValue(undefined)
    unfollowCreator.mockReset()
    unfollowCreator.mockResolvedValue(undefined)
    updateMyProfile.mockReset()
    removeFriend.mockReset()
    enableRunwayPush.mockReset()
    disableRunwayPush.mockReset()
    runwayPushIsEnabled.mockReset()
    ensureDefaultRunwayPush.mockReset()
    unpublishLookFromRunway.mockReset()
    unpublishLookFromRunway.mockResolvedValue({ id: 'look-mine' })
    fetchGalleryImageBlob.mockReset()
    fetchGalleryImageBlob.mockResolvedValue(new Blob(['look'], { type: 'image/png' }))
    plantFittingRoomGarment.mockReset()
    plantFittingRoomGarment.mockResolvedValue(undefined)
    blobToFittingRoomDataUrl.mockReset()
    blobToFittingRoomDataUrl.mockResolvedValue({
      dataUrl: 'data:image/png;base64,look',
      mimeType: 'image/png',
    })
    runwayPushIsEnabled.mockResolvedValue(false)
    enableRunwayPush.mockResolvedValue('granted')
    disableRunwayPush.mockResolvedValue(undefined)
    ensureDefaultRunwayPush.mockResolvedValue({ on: true, result: 'granted' })
    recordGalleryImpressions.mockResolvedValue({ recorded: 0 })
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'top10') return [{ ...topItem, username: 'topstar' }]
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'discover-1',
            title: 'Discover look',
            user_id: 'creator-a',
            username: 'atelier_a',
            avatar_url: '/api/v1/profiles/creator-a/avatar',
          },
        ]
      }
      if (opts?.sort === 'circle') return [{ ...circleItem, username: 'friendone' }]
      if (opts?.sort === 'following') return []
      return [{ ...circleItem, username: 'friendone' }]
    })
    listGalleryComments.mockResolvedValue([])
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([])
    listOutgoingFriendRequests.mockResolvedValue([])
    listUserGallery.mockResolvedValue([])
    getPublicProfile.mockResolvedValue(null)
    getFollowStatus.mockResolvedValue({ user_id: 'friend-1', following: false })
    updateMyProfile.mockImplementation(async (payload: Record<string, unknown>) => ({
      user_id: 'viewer-1',
      username: 'viewer',
      display_name: (payload.display_name as string) || 'viewer',
      bio: (payload.bio as string) || '',
      avatar_url: null,
      designs_count: 0,
      looks_count: 0,
      followers_count: 0,
      following_count: 0,
      reputation_score: 0,
    }))
  })

  it('keeps Follow in sync across looks from the same designer', async () => {
    const OriginalIO = globalThis.IntersectionObserver
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        cb: IntersectionObserverCallback
        constructor(cb: IntersectionObserverCallback) {
          this.cb = cb
        }
        observe(el: Element) {
          this.cb(
            [
              {
                isIntersecting: true,
                intersectionRatio: 1,
                target: el,
              } as IntersectionObserverEntry,
            ],
            this as unknown as IntersectionObserver,
          )
        }
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return []
        }
        root = null
        rootMargin = ''
        thresholds = []
      },
    )

    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'look-a1',
            title: 'Look A1',
            user_id: 'creator-a',
            username: 'atelier_a',
          },
          {
            ...circleItem,
            id: 'look-a2',
            title: 'Look A2',
            user_id: 'creator-a',
            username: 'atelier_a',
          },
        ]
      }
      return []
    })
    getFollowStatus.mockResolvedValue({ user_id: 'creator-a', following: false })

    try {
      render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
      const buttons = await screen.findAllByTestId('runway-follow-creator-a')
      expect(buttons).toHaveLength(2)
      await waitFor(() => expect(buttons[0]).not.toBeDisabled())
      expect(buttons[0]).toHaveTextContent('Follow')
      expect(buttons[1]).toHaveTextContent('Follow')

      fireEvent.click(buttons[0])
      await waitFor(() => expect(followCreator).toHaveBeenCalledWith('creator-a'))
      await waitFor(() => {
        const synced = screen.getAllByTestId('runway-follow-creator-a')
        expect(synced[0]).toHaveTextContent('Following')
        expect(synced[1]).toHaveTextContent('Following')
        expect(synced[0]).toHaveAttribute('aria-pressed', 'true')
        expect(synced[1]).toHaveAttribute('aria-pressed', 'true')
      })
      expect(__followStatusCacheTestUtils.get('viewer-1', 'creator-a')).toBe(true)
    } finally {
      if (OriginalIO) vi.stubGlobal('IntersectionObserver', OriginalIO)
      else vi.unstubAllGlobals()
    }
  })

  it('scopes Follow cache by viewer+designer so account switches do not leak state', async () => {
    expect(followStatusCacheKey('viewer-1', 'creator-a')).toBe('viewer-1:creator-a')
    expect(followStatusCacheKey('viewer-2', 'creator-a')).toBe('viewer-2:creator-a')

    const OriginalIO = globalThis.IntersectionObserver
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        cb: IntersectionObserverCallback
        constructor(cb: IntersectionObserverCallback) {
          this.cb = cb
        }
        observe(el: Element) {
          this.cb(
            [
              {
                isIntersecting: true,
                intersectionRatio: 1,
                target: el,
              } as IntersectionObserverEntry,
            ],
            this as unknown as IntersectionObserver,
          )
        }
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return []
        }
        root = null
        rootMargin = ''
        thresholds = []
      },
    )

    getFollowStatus.mockImplementation(async (userId: string) => {
      if (authUser.id === 'viewer-1') return { user_id: userId, following: true }
      return { user_id: userId, following: false }
    })

    try {
      const first = render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
      expect(await screen.findByTestId('runway-follow-creator-a')).toBeInTheDocument()
      await waitFor(() =>
        expect(getFollowStatus).toHaveBeenCalledWith('creator-a'),
      )
      await waitFor(() =>
        expect(screen.getByTestId('runway-follow-creator-a')).toHaveAttribute(
          'aria-pressed',
          'true',
        ),
      )
      expect(__followStatusCacheTestUtils.get('viewer-1', 'creator-a')).toBe(true)
      expect(__followStatusCacheTestUtils.get('viewer-2', 'creator-a')).toBeUndefined()

      first.unmount()
      getFollowStatus.mockClear()
      authUser = { id: 'viewer-2', email: 'viewer2@example.com', username: 'viewer2' }

      render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
      expect(await screen.findByTestId('runway-follow-creator-a')).toBeInTheDocument()
      await waitFor(() =>
        expect(getFollowStatus).toHaveBeenCalledWith('creator-a'),
      )
      await waitFor(() =>
        expect(screen.getByTestId('runway-follow-creator-a')).toHaveAttribute(
          'aria-pressed',
          'false',
        ),
      )
      expect(__followStatusCacheTestUtils.get('viewer-1', 'creator-a')).toBe(true)
      expect(__followStatusCacheTestUtils.get('viewer-2', 'creator-a')).toBe(false)
      expect(screen.getByTestId('runway-follow-creator-a')).not.toHaveTextContent('Following')
    } finally {
      if (OriginalIO) vi.stubGlobal('IntersectionObserver', OriginalIO)
      else vi.unstubAllGlobals()
    }
  })

  async function openMoreMenu() {
    fireEvent.click(await screen.findByTestId('runway-more-menu'))
  }

  async function openBrowseList(tabId: 'feed' | 'following' | 'top') {
    fireEvent.click(await screen.findByTestId(`runway-tab-${tabId}`))
  }

  it('closes the Account menu on outside pointerdown', async () => {
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openMoreMenu()
    expect(screen.getByRole('menu', { name: 'FashionRise menu' })).toBeInTheDocument()
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu', { name: 'FashionRise menu' })).not.toBeInTheDocument()
  })

  it('closes the Account menu on Escape', async () => {
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openMoreMenu()
    expect(screen.getByRole('menu', { name: 'FashionRise menu' })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu', { name: 'FashionRise menu' })).not.toBeInTheDocument()
  })

  it('opens My Profile when openOwnProfile deep-link is set', async () => {
    getPublicProfile.mockResolvedValue({
      user_id: 'viewer-1',
      username: 'viewer',
      display_name: 'Viewer',
      bio: '',
      avatar_url: null,
      designs_count: 0,
      looks_count: 0,
      followers_count: 0,
      following_count: 0,
      reputation_score: 0,
    })
    listUserGallery.mockResolvedValue([])
    render(
      <RunwayScreen
        onOpenCreate={vi.fn()}
        onOpenLooks={vi.fn()}
        openOwnProfile
        onOwnProfileConsumed={vi.fn()}
      />,
    )
    expect(await screen.findByTestId('friend-profile-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('designer-profile-editor')).not.toBeInTheDocument()
    expect(await screen.findByTestId('designer-edit-profile')).toHaveTextContent(/Edit Designer Card/i)
  })

  it('opens My Profile for signed-in users with empty published designs and edits it', async () => {
    getPublicProfile.mockResolvedValue({
      user_id: 'viewer-1',
      username: 'viewer',
      display_name: 'viewer',
      bio: '',
      avatar_url: null,
      designs_count: 0,
      looks_count: 0,
      followers_count: 0,
      following_count: 0,
      reputation_score: 0,
      reputation_tier: 'newcomer',
    })
    listUserGallery.mockResolvedValue([])
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openMoreMenu()
    fireEvent.click(await screen.findByTestId('runway-my-profile'))
    expect(await screen.findByTestId('friend-profile-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('designer-profile-editor')).not.toBeInTheDocument()
    fireEvent.click(await screen.findByTestId('designer-edit-profile'))
    expect(await screen.findByTestId('designer-profile-editor')).toBeInTheDocument()
    expect(screen.getByTestId('designer-avatar-preview')).toBeInTheDocument()
    expect(screen.getByTestId('designer-edit-avatar')).toHaveTextContent(/Change photo/i)
    fireEvent.change(screen.getByTestId('designer-edit-name'), {
      target: { value: 'Studio Nova' },
    })
    fireEvent.change(screen.getByTestId('designer-edit-bio'), {
      target: { value: 'Knitwear and evening.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(updateMyProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          display_name: 'Studio Nova',
          bio: 'Knitwear and evening.',
        }),
      ),
    )
    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Studio Nova')
  })

  async function openCircleSheet() {
    await openBrowseList('feed')
    return screen.findByRole('list', { name: 'Circle feed' })
  }

  async function openTop10Sheet() {
    await openBrowseList('top')
    return screen.findByRole('dialog', { name: /Top rankings worldwide/i })
  }

  it('loads Following tab from following sort', async () => {
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'following') {
        return [{ ...circleItem, id: 'follow-1', title: 'Followed designer look' }]
      }
      if (opts?.sort === 'top10') return [{ ...topItem }]
      return [{ ...circleItem }]
    })
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openBrowseList('following')
    await waitFor(() =>
      expect(listGallery).toHaveBeenCalledWith(
        expect.objectContaining({ sort: 'following' }),
      ),
    )
    const followingSheet = await screen.findByRole('dialog', { name: /Following/i })
    expect(within(followingSheet).getByText('Followed designer look')).toBeInTheDocument()
    fireEvent.click(
      within(followingSheet).getByTestId(`runway-open-designer-${circleItem.user_id}`),
    )
    expect(await screen.findByTestId('friend-profile-panel')).toBeInTheDocument()
  })

  it('auto-loads more Discover results near the end with exclude dedupe', async () => {
    const OriginalIO = globalThis.IntersectionObserver
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        cb: IntersectionObserverCallback
        constructor(cb: IntersectionObserverCallback) {
          this.cb = cb
        }
        observe(el: Element) {
          if (el.getAttribute('data-testid') === 'runway-discover-load-more') {
            this.cb(
              [
                {
                  isIntersecting: true,
                  intersectionRatio: 1,
                  target: el,
                } as IntersectionObserverEntry,
              ],
              this as unknown as IntersectionObserver,
            )
          }
        }
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return []
        }
        root = null
        rootMargin = ''
        thresholds = []
      },
    )
    listGallery.mockImplementation(async (opts?: { sort?: string; exclude?: string[] }) => {
      if (opts?.sort === 'discover' && (opts.exclude?.length ?? 0) > 0) {
        return [
          {
            ...circleItem,
            id: 'discover-next',
            title: 'Discover page two',
            user_id: 'creator-b',
            username: 'creator_b',
          },
        ]
      }
      if (opts?.sort === 'discover') {
        return Array.from({ length: 24 }, (_, i) => ({
          ...circleItem,
          id: `discover-${i + 1}`,
          title: i === 0 ? 'Discover look' : `Discover filler ${i + 1}`,
          user_id: `creator-${i % 5}`,
          username: `creator_${i % 5}`,
        }))
      }
      return []
    })
    try {
      render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
      expect(await screen.findByTestId('runway-discover-card-discover-1')).toBeInTheDocument()
      await waitFor(() =>
        expect(listGallery).toHaveBeenCalledWith(
          expect.objectContaining({
            sort: 'discover',
            exclude: expect.arrayContaining(['discover-1', 'discover-24']),
          }),
        ),
      )
      expect(await screen.findByTestId('runway-discover-card-discover-next')).toBeInTheDocument()
      // Exhausted after short page-two → sentinel removed; no visible Load more CTA.
      expect(screen.queryByTestId('runway-discover-load-more')).toBeNull()
      expect(screen.queryByRole('button', { name: /Load more/i })).toBeNull()
      expect(recordGalleryImpressions).not.toHaveBeenCalled()
    } finally {
      if (OriginalIO) vi.stubGlobal('IntersectionObserver', OriginalIO)
      else vi.unstubAllGlobals()
    }
  })

  it('defaults to algorithmic Discover feed with no feed filters in the menu', async () => {
    const onOpenCreate = vi.fn()
    const onOpenLooks = vi.fn()
    render(<RunwayScreen onOpenCreate={onOpenCreate} onOpenLooks={onOpenLooks} />)

    expect(screen.getByRole('heading', { level: 1, name: 'FashionRise' })).toBeInTheDocument()
    expect(screen.queryByText(/Social fashion/i)).toBeNull()
    expect(screen.queryByText(/Fair Discover/i)).toBeNull()
    expect(screen.queryByRole('tab', { name: 'Discover' })).toBeNull()
    expect(screen.queryByText('Discover', { selector: 'span' })).toBeNull()
    await waitFor(() =>
      expect(listGallery).toHaveBeenCalledWith(expect.objectContaining({ sort: 'discover' })),
    )
    // Impressions fire only when cards are meaningfully visible — not on API load.
    expect(recordGalleryImpressions).not.toHaveBeenCalled()
    expect(listGallery).not.toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'top10' }),
    )
    expect(await screen.findByTestId('runway-open-discover')).toBeInTheDocument()
    expect(await screen.findByText('@atelier_a')).toBeInTheDocument()
    const avatar = await screen.findByTestId('designer-avatar-photo')
    expect(avatar).toHaveAttribute('src', '/api/v1/profiles/creator-a/avatar')
    expect(screen.queryByTestId('designer-avatar-fallback')).toBeNull()
    expect(screen.queryByText('@Designer')).toBeNull()
    expect(screen.queryByText('Look ·')).toBeNull()
    expect(screen.queryByTestId('runway-top-limit')).toBeNull()
    expect(screen.queryByText('Worldwide hit')).toBeNull()

    await openMoreMenu()
    const menu = await screen.findByRole('menu', { name: /FashionRise menu/i })
    expect(await screen.findByTestId('runway-push-toggle')).toHaveAttribute('aria-checked', 'true')
    expect(within(menu).getByRole('menuitem', { name: /Start creating/i })).toBeInTheDocument()
    expect(within(menu).queryByRole('menuitem', { name: /^Following$/i })).toBeNull()
    expect(within(menu).queryByRole('menuitem', { name: /Friends circle/i })).toBeNull()
    expect(within(menu).queryByRole('menuitem', { name: /Top rankings/i })).toBeNull()
    expect(within(menu).queryByTestId('runway-top-limit')).toBeNull()
    expect(within(menu).queryByTestId('runway-top-10')).toBeNull()
    expect(within(menu).queryByText(/Lists/i)).toBeNull()
    fireEvent.click(screen.getByTestId('runway-more-menu'))

    expect(await screen.findByText('@atelier_a')).toBeInTheDocument()

    await openMoreMenu()
    fireEvent.click(screen.getByRole('menuitem', { name: /Start creating/i }))
    expect(onOpenCreate).toHaveBeenCalled()
    await openMoreMenu()
    fireEvent.click(screen.getByRole('menuitem', { name: /My Looks/i }))
    expect(onOpenLooks).toHaveBeenCalled()
  })

  it('likes and scores a circle look inside the My circle popup', async () => {
    likeGalleryItem.mockResolvedValue(undefined)
    rateGalleryItem.mockResolvedValue({
      id: 'rating-1',
      gallery_item_id: 'circle-1',
      user_id: 'viewer',
      score: 9,
      created_at: '2026-11-07T00:00:00Z',
      updated_at: '2026-11-07T00:00:00Z',
    })
    getGalleryItem
      .mockResolvedValueOnce({
        ...circleItem,
        liked_by_me: true,
        likes_count: 1,
      })
      .mockResolvedValueOnce({
        ...circleItem,
        liked_by_me: true,
        likes_count: 1,
        my_score: 9,
        rating_average: 9,
        rating_count: 1,
      })

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const circle = await openCircleSheet()
    const likeBtn = within(circle).getByRole('button', { name: /Like look/i })
    fireEvent.click(likeBtn)
    await waitFor(() => expect(likeGalleryItem).toHaveBeenCalledWith('circle-1'))
    await waitFor(() => expect(getGalleryItem).toHaveBeenCalledWith('circle-1'))
    expect(await within(circle).findByRole('button', { name: /Unlike look/i })).toBeInTheDocument()

    const score = within(circle).getByLabelText(/Score Friend circle look from 1 to 10/i)
    fireEvent.change(score, { target: { value: '9' } })
    await waitFor(() => expect(rateGalleryItem).toHaveBeenCalledWith('circle-1', 9))
    await waitFor(() => expect((score as HTMLSelectElement).value).toBe('9'))
  })

  it('opens chat popup, posts, and likes on a circle look', async () => {
    listGalleryComments.mockResolvedValue([
      {
        id: 'c1',
        gallery_item_id: 'circle-1',
        user_id: 'friend-1',
        body: 'Love this silhouette',
        moderation_status: 'ok',
        likes_count: 0,
        created_at: '2026-11-07T00:00:00Z',
        username: 'friendOne',
        liked_by_me: false,
      },
    ])
    postGalleryComment.mockResolvedValue({
      id: 'c2',
      gallery_item_id: 'circle-1',
      user_id: 'viewer-1',
      body: 'The hem is perfect',
      moderation_status: 'ok',
      likes_count: 0,
      created_at: '2026-11-07T00:01:00Z',
      username: 'viewer',
      liked_by_me: false,
    })
    likeGalleryComment.mockResolvedValue(undefined)

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const circle = await openCircleSheet()
    fireEvent.click(within(circle).getByRole('button', { name: /Chat/i }))
    await waitFor(() => expect(listGalleryComments).toHaveBeenCalledWith('circle-1'))

    const dialog = await screen.findByRole('dialog', { name: /Friend circle look/i })
    expect(within(dialog).getByText('Love this silhouette')).toBeInTheDocument()
    expect(within(dialog).getByText('@friendOne')).toBeInTheDocument()
    expect(within(dialog).getByText(/FashionRise chat/i)).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: /Like comment/i }))
    await waitFor(() => expect(likeGalleryComment).toHaveBeenCalledWith('c1'))
    expect(await within(dialog).findByRole('button', { name: /Unlike comment/i })).toBeInTheDocument()

    fireEvent.change(within(dialog).getByLabelText(/Add a comment/i), {
      target: { value: 'The hem is perfect' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: /^Post$/i }))
    await waitFor(() =>
      expect(postGalleryComment).toHaveBeenCalledWith('circle-1', 'The hem is perfect'),
    )
    expect(await within(dialog).findByText('The hem is perfect')).toBeInTheDocument()
    expect(within(dialog).getByText('@viewer')).toBeInTheDocument()
    // Own comment has no like button
    expect(within(dialog).getAllByRole('button', { name: /Unlike comment|Like comment/i })).toHaveLength(
      1,
    )

    fireEvent.click(within(dialog).getByRole('button', { name: /Close chat/i }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /Friend circle look/i })).toBeNull())
  })

  it('Escape closes chat first while My circle sheet stays open', async () => {
    listGalleryComments.mockResolvedValue([])
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const circle = await openCircleSheet()
    fireEvent.click(within(circle).getByRole('button', { name: /Chat/i }))
    const dialog = await screen.findByRole('dialog', { name: /Friend circle look/i })
    expect(dialog).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /Friend circle look/i })).toBeNull())
    expect(screen.getByRole('dialog', { name: /My circle/i })).toBeInTheDocument()
  })

  it('does not let you like or score your own look', async () => {
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'top10') return []
      return [
        {
          ...circleItem,
          id: 'own-1',
          user_id: 'viewer-1',
          title: 'My published look',
          likes_count: 4,
          rating_average: 8.5,
          rating_count: 2,
        },
      ]
    })
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const circle = await openCircleSheet()
    expect(within(circle).getByText('My published look')).toBeInTheDocument()
    expect(within(circle).queryByRole('button', { name: /Like look/i })).toBeNull()
    expect(within(circle).queryByLabelText(/Score My published look from 1 to 10/i)).toBeNull()
    expect(within(circle).getByText(/Your look — likes & scores come from others/i)).toBeInTheDocument()
    expect(likeGalleryItem).not.toHaveBeenCalled()
    expect(rateGalleryItem).not.toHaveBeenCalled()
  })

  it('loads friends circle and can find + request by contains name', async () => {
    listFriends.mockResolvedValue([
      {
        id: 'fs-1',
        status: 'accepted',
        requester_id: 'me',
        addressee_id: 'yaniv',
        created_at: '2026-11-07T00:00:00Z',
        accepted_at: '2026-11-07T00:00:00Z',
        friend: {
          user_id: 'yaniv',
          username: 'yanivprbk',
          display_name: 'Yaniv',
          avatar_url: null,
        },
      },
    ])
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    listGallery.mockClear()

    await openMoreMenu()
    fireEvent.click(screen.getByTestId('runway-tab-friends'))
    expect(await screen.findByText('@yanivprbk')).toBeInTheDocument()
    expect(listGallery).not.toHaveBeenCalled()
    expect(listFriends).toHaveBeenCalled()

    searchFriends.mockResolvedValue([
      {
        user: {
          user_id: 'other',
          username: 'newfriend',
          display_name: 'New Friend',
          avatar_url: null,
        },
        relationship: 'none',
        friendship_id: null,
      },
    ])
    requestFriendByUserId.mockResolvedValue({
      id: 'fs-2',
      status: 'pending',
      requester_id: 'me',
      addressee_id: 'other',
      created_at: '2026-11-07T00:00:00Z',
      accepted_at: null,
      friend: {
        user_id: 'other',
        username: 'newfriend',
        display_name: 'New Friend',
        avatar_url: null,
      },
    })
    fireEvent.change(screen.getByTestId('find-friends-input'), {
      target: { value: 'new' },
    })
    fireEvent.click(screen.getByTestId('find-friends-search'))
    expect(await screen.findByTestId('find-friends-results')).toBeInTheDocument()
    await waitFor(() => expect(searchFriends).toHaveBeenCalledWith('new'))
    fireEvent.click(screen.getByTestId('find-add-other'))
    await waitFor(() => expect(requestFriendByUserId).toHaveBeenCalledWith('other'))
    expect(await screen.findByTestId('request-sent-status')).toBeInTheDocument()
  })

  it('shows incoming friend requests with approve and reject', async () => {
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([
      {
        id: 'req-1',
        status: 'pending',
        requester_id: 'maya',
        addressee_id: 'me',
        created_at: '2026-11-07T00:00:00Z',
        accepted_at: null,
        friend: {
          user_id: 'maya',
          username: 'MayaRose',
          display_name: 'Maya',
          avatar_url: null,
        },
      },
    ])
    acceptFriendRequest.mockResolvedValue({
      id: 'req-1',
      status: 'accepted',
      requester_id: 'maya',
      addressee_id: 'me',
      created_at: '2026-11-07T00:00:00Z',
      accepted_at: '2026-11-07T01:00:00Z',
      friend: {
        user_id: 'maya',
        username: 'MayaRose',
        display_name: 'Maya',
        avatar_url: null,
      },
    })
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    await openMoreMenu()
    fireEvent.click(screen.getByTestId('runway-tab-friends'))
    expect(await screen.findByTestId('friend-requests-list')).toBeInTheDocument()
    expect(screen.getByTestId('request-open-maya')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('friend-accept-req-1'))
    await waitFor(() => expect(acceptFriendRequest).toHaveBeenCalledWith('req-1'))
  })

  it('keeps outgoing pending requests visible when returning to Friends', async () => {
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([])
    listOutgoingFriendRequests.mockResolvedValue([
      {
        id: 'sent-1',
        status: 'pending',
        requester_id: 'me',
        addressee_id: 'noa',
        created_at: '2026-11-07T00:00:00Z',
        accepted_at: null,
        friend: {
          user_id: 'noa',
          username: 'NoaPeri',
          display_name: 'NoaPeri',
          avatar_url: null,
        },
      },
    ])
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    await openMoreMenu()
    fireEvent.click(screen.getByTestId('runway-tab-friends'))
    expect(await screen.findByTestId('friend-sent-list')).toBeInTheDocument()
    expect(screen.getByTestId('sent-open-noa')).toBeInTheDocument()
    expect(screen.getByText(/Request pending/i)).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('friend-cancel-sent-noa'))
    await waitFor(() => expect(removeFriend).toHaveBeenCalledWith('noa'))
  })

  it('opens the full designer profile from a friend row (not nested in Friends chrome)', async () => {
    listFriends.mockResolvedValue([
      {
        id: 'fs-1',
        status: 'accepted',
        requester_id: 'me',
        addressee_id: 'yaniv',
        created_at: '2026-11-07T00:00:00Z',
        accepted_at: '2026-11-07T00:00:00Z',
        friend: {
          user_id: 'yaniv',
          username: 'yanivprbk',
          display_name: 'Yaniv',
          avatar_url: null,
        },
      },
    ])
    getPublicProfile.mockResolvedValue({
      id: 'p1',
      user_id: 'yaniv',
      display_name: 'Yaniv',
      bio: 'Hello',
      avatar_url: null,
      cover_url: null,
      style_tags: [],
      designs_count: 12,
      published_count: 1,
      followers_count: 2,
      likes_received_count: 4,
      rating_average: 9,
      rating_count: 1,
      reputation_score: 20,
      reputation_tier: 'rising',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    listUserGallery.mockResolvedValue([
      {
        id: 'g-public',
        design_id: null,
        look_id: 'look-1',
        user_id: 'yaniv',
        title: 'Runway gown',
        image_url: null,
        visibility: 'public',
        rating_average: 9,
        rating_count: 1,
        likes_count: 4,
        moderation_status: 'ok',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    removeFriend.mockResolvedValue(undefined)

    const onImmersiveFeedChange = vi.fn()
    const { rerender } = render(
      <RunwayScreen
        onOpenCreate={vi.fn()}
        onOpenLooks={vi.fn()}
        onImmersiveFeedChange={onImmersiveFeedChange}
        feedFocusToken={0}
      />,
    )
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    expect(onImmersiveFeedChange).toHaveBeenCalledWith(true)
    await openMoreMenu()
    fireEvent.click(screen.getByTestId('runway-tab-friends'))
    expect(await screen.findByTestId('friend-open-yaniv')).toBeInTheDocument()
    expect(screen.getByTestId('friend-remove-yaniv')).toBeInTheDocument()
    expect(onImmersiveFeedChange).toHaveBeenCalledWith(false)

    fireEvent.click(screen.getByTestId('friend-open-yaniv'))
    expect(await screen.findByTestId('friend-profile-panel')).toBeInTheDocument()
    expect(screen.getByTestId('friend-profile-username')).toHaveTextContent('@yanivprbk')
    expect(await screen.findByTestId('friend-look-g-public')).toBeInTheDocument()
    expect(screen.getByTestId('designer-follow-btn')).toBeInTheDocument()
    expect(screen.queryByTestId('friend-profile-back')).not.toBeInTheDocument()
    // Full-screen profile — Friends manage chrome must not remain around it.
    expect(screen.queryByRole('heading', { name: 'Friends' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Add people by username/i)).not.toBeInTheDocument()
    expect(screen.queryByText('12')).not.toBeInTheDocument()
    expect(onImmersiveFeedChange).toHaveBeenCalledWith(false)

    // Shell nav → Runway bumps feedFocusToken and returns to the feed.
    rerender(
      <RunwayScreen
        onOpenCreate={vi.fn()}
        onOpenLooks={vi.fn()}
        onImmersiveFeedChange={onImmersiveFeedChange}
        feedFocusToken={1}
      />,
    )
    expect(await screen.findByTestId('runway-open-discover')).toBeInTheDocument()
    expect(screen.queryByTestId('friend-profile-panel')).not.toBeInTheDocument()
    expect(onImmersiveFeedChange).toHaveBeenCalledWith(true)
  })

  it('auto-enables Runway push by default on load', async () => {
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await screen.findByTestId('runway-open-discover')
    await waitFor(() => expect(ensureDefaultRunwayPush).toHaveBeenCalled())
    await openMoreMenu()
    const toggle = await screen.findByTestId('runway-push-toggle')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText(/Push on — we’ll notify/i)).toBeInTheDocument()
  })

  it('can turn push off from the toggle switch', async () => {
    ensureDefaultRunwayPush.mockResolvedValue({ on: true, result: 'already' })
    runwayPushIsEnabled.mockResolvedValue(true)
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openMoreMenu()
    const toggle = await screen.findByTestId('runway-push-toggle')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(toggle)
    await waitFor(() => expect(disableRunwayPush).toHaveBeenCalled())
    expect(await screen.findByTestId('runway-push-toggle')).toHaveAttribute('aria-checked', 'false')
  })

  it('locks the push toggle when the server has push disabled', async () => {
    ensureDefaultRunwayPush.mockResolvedValue({ on: false, result: 'disabled' })
    runwayPushIsEnabled.mockResolvedValue(false)
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await openMoreMenu()
    const toggle = await screen.findByTestId('runway-push-toggle')
    await waitFor(() => expect(toggle).toBeDisabled())
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(/isn’t (enabled|configured) on the server yet/i)).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(enableRunwayPush).not.toHaveBeenCalled()
  })

  it('hides immersive cards when look media fails (deleted look orphan)', async () => {
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'orphan-1',
            title: 'Deleted look reel',
            username: 'NoaPeri',
            look_id: 'look-deleted',
          },
        ]
      }
      if (opts?.sort === 'circle') return []
      if (opts?.sort === 'following') return []
      if (opts?.sort === 'top10') return []
      return []
    })
    fetchGalleryImageBlob.mockRejectedValue(new Error('Gallery image not available'))

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    // Media 404 can win the race before the caption paints — assert the card is gone.
    await waitFor(() => {
      expect(screen.queryByTestId('runway-double-tap-orphan-1')).not.toBeInTheDocument()
      expect(screen.queryByText(/Deleted look reel/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/@NoaPeri/i)).not.toBeInTheDocument()
    })
  })

  it('plants the look into Fitting Room and navigates on Try on me', async () => {
    const onOpenFittingRoom = vi.fn()
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'tryon-1',
            title: 'Try me look',
            username: 'yanivprbk',
            look_id: 'look-tryon',
          },
        ]
      }
      if (opts?.sort === 'circle') return []
      if (opts?.sort === 'following') return []
      if (opts?.sort === 'top10') return []
      return []
    })

    render(
      <RunwayScreen
        onOpenCreate={vi.fn()}
        onOpenLooks={vi.fn()}
        onOpenFittingRoom={onOpenFittingRoom}
      />,
    )
    const tryOn = await screen.findByTestId('runway-try-on-tryon-1')
    fireEvent.click(tryOn)
    await waitFor(() => expect(fetchGalleryImageBlob).toHaveBeenCalledWith('tryon-1'))
    await waitFor(() => expect(blobToFittingRoomDataUrl).toHaveBeenCalled())
    await waitFor(() =>
      expect(plantFittingRoomGarment).toHaveBeenCalledWith(
        expect.objectContaining({
          userId: 'viewer-1',
          dataUrl: 'data:image/png;base64,look',
          category: 'dresses',
          source: 'fashionrise_look',
          notice: expect.objectContaining({
            galleryItemId: 'tryon-1',
            title: 'Try me look',
          }),
        }),
      ),
    )
    expect(onOpenFittingRoom).toHaveBeenCalled()
  })

  it('double-taps immersive media to like a look with a heart burst', async () => {
    likeGalleryItem.mockResolvedValue(undefined)
    getGalleryItem.mockResolvedValue({
      ...circleItem,
      id: 'dbl-1',
      title: 'Double tap look',
      username: 'atelier_a',
      liked_by_me: true,
      likes_count: 4,
    })
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'dbl-1',
            title: 'Double tap look',
            username: 'atelier_a',
            likes_count: 3,
            liked_by_me: false,
          },
        ]
      }
      if (opts?.sort === 'circle') return []
      if (opts?.sort === 'following') return []
      if (opts?.sort === 'top10') return []
      return []
    })

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const media = await screen.findByTestId('runway-double-tap-dbl-1')
    const tap = (x = 120, y = 240) => {
      fireEvent.pointerDown(media, { clientX: x, clientY: y, pointerType: 'touch', button: 0 })
      fireEvent.pointerUp(media, { clientX: x, clientY: y, pointerType: 'touch', button: 0 })
    }
    tap()
    tap()

    expect(await screen.findByTestId('runway-like-burst-dbl-1')).toBeInTheDocument()
    await waitFor(() => expect(likeGalleryItem).toHaveBeenCalledWith('dbl-1'))
    expect(unlikeGalleryItem).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: /Unlike look/i })).toBeInTheDocument()

    // Second double-tap while already liked: burst again, no unlike.
    likeGalleryItem.mockClear()
    tap(130, 250)
    tap(132, 252)
    expect(await screen.findByTestId('runway-like-burst-dbl-1')).toBeInTheDocument()
    expect(likeGalleryItem).not.toHaveBeenCalled()
    expect(unlikeGalleryItem).not.toHaveBeenCalled()
  })

  it('lets the owner remove their own look from FashionRise with StarOff confirm', async () => {
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'discover') {
        return [
          {
            ...circleItem,
            id: 'mine-1',
            look_id: 'look-mine',
            user_id: 'viewer-1',
            title: 'My published look',
            username: 'viewer',
          },
        ]
      }
      if (opts?.sort === 'circle') return []
      if (opts?.sort === 'following') return []
      if (opts?.sort === 'top10') return []
      return []
    })

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const unpublish = await screen.findByTestId('runway-unpublish-mine-1')
    expect(unpublish).toHaveAttribute('aria-label', 'Remove from FashionRise')
    fireEvent.click(unpublish)
    expect(await screen.findByRole('heading', { name: /Remove from FashionRise/i })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Remove$/i }))
    await waitFor(() => expect(unpublishLookFromRunway).toHaveBeenCalledWith('look-mine'))
    await waitFor(() => expect(screen.queryByTestId('runway-unpublish-mine-1')).toBeNull())
  })
})
