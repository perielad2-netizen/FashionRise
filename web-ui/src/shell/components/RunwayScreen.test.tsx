import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayScreen } from './RunwayScreen'

const listGallery = vi.fn()
const getGalleryItem = vi.fn()
const likeGalleryItem = vi.fn()
const unlikeGalleryItem = vi.fn()
const rateGalleryItem = vi.fn()
const listGalleryComments = vi.fn()
const postGalleryComment = vi.fn()
const likeGalleryComment = vi.fn()
const unlikeGalleryComment = vi.fn()
const listFriends = vi.fn()
const listFriendRequests = vi.fn()
const requestFriendByUsername = vi.fn()
const listUserGallery = vi.fn()
const getPublicProfile = vi.fn()
const removeFriend = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
  getGalleryItem: (...args: unknown[]) => getGalleryItem(...args),
  likeGalleryItem: (...args: unknown[]) => likeGalleryItem(...args),
  unlikeGalleryItem: (...args: unknown[]) => unlikeGalleryItem(...args),
  rateGalleryItem: (...args: unknown[]) => rateGalleryItem(...args),
  listGalleryComments: (...args: unknown[]) => listGalleryComments(...args),
  postGalleryComment: (...args: unknown[]) => postGalleryComment(...args),
  likeGalleryComment: (...args: unknown[]) => likeGalleryComment(...args),
  unlikeGalleryComment: (...args: unknown[]) => unlikeGalleryComment(...args),
  listUserGallery: (...args: unknown[]) => listUserGallery(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
}))

vi.mock('@/services/profilesApi', () => ({
  getPublicProfile: (...args: unknown[]) => getPublicProfile(...args),
}))

vi.mock('@/services/friendsApi', () => ({
  listFriends: (...args: unknown[]) => listFriends(...args),
  listFriendRequests: (...args: unknown[]) => listFriendRequests(...args),
  requestFriendByUsername: (...args: unknown[]) => requestFriendByUsername(...args),
  acceptFriendRequest: vi.fn(),
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

const authUser = { id: 'viewer-1', email: 'viewer@example.com', username: 'viewer' }

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
    listGallery.mockReset()
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
    requestFriendByUsername.mockReset()
    listUserGallery.mockReset()
    getPublicProfile.mockReset()
    removeFriend.mockReset()
    enableRunwayPush.mockReset()
    disableRunwayPush.mockReset()
    runwayPushIsEnabled.mockReset()
    ensureDefaultRunwayPush.mockReset()
    runwayPushIsEnabled.mockResolvedValue(false)
    enableRunwayPush.mockResolvedValue('granted')
    disableRunwayPush.mockResolvedValue(undefined)
    ensureDefaultRunwayPush.mockResolvedValue({ on: true, result: 'granted' })
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'top10') return [{ ...topItem }]
      return [{ ...circleItem }]
    })
    listGalleryComments.mockResolvedValue([])
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([])
    listUserGallery.mockResolvedValue([])
    getPublicProfile.mockResolvedValue(null)
  })

  async function openCircleSheet() {
    fireEvent.click(await screen.findByTestId('runway-open-circle'))
    return screen.findByRole('list', { name: 'Circle feed' })
  }

  async function openTop10Sheet() {
    fireEvent.click(await screen.findByTestId('runway-open-top10'))
    return screen.findByRole('dialog', { name: /Top 10 worldwide/i })
  }

  it('loads circle + Top 10 data and opens scrollable popups from hub buttons', async () => {
    const onOpenCreate = vi.fn()
    const onOpenLooks = vi.fn()
    render(<RunwayScreen onOpenCreate={onOpenCreate} onOpenLooks={onOpenLooks} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Runway' })).toBeInTheDocument()
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    expect(listGallery).toHaveBeenCalledWith(expect.objectContaining({ sort: 'circle' }))
    expect(listGallery).toHaveBeenCalledWith(expect.objectContaining({ sort: 'top10' }))
    expect(await screen.findByTestId('runway-open-top10')).toBeInTheDocument()
    expect(screen.getByTestId('runway-open-circle')).toBeInTheDocument()
    expect(await screen.findByTestId('runway-push-toggle')).toHaveAttribute('aria-checked', 'true')
    expect(screen.queryByRole('button', { name: /^My circle$/i })).toBeNull()
    expect(screen.queryByText('Comments')).toBeNull()
    expect(screen.queryByText('Like · Score')).toBeNull()

    const topDialog = await openTop10Sheet()
    expect(within(topDialog).getByText('Worldwide hit')).toBeInTheDocument()
    expect(within(topDialog).getByTestId('runway-browse-back')).toHaveTextContent('Back')
    fireEvent.click(within(topDialog).getByRole('button', { name: /Close Top 10 worldwide/i }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /Top 10 worldwide/i })).toBeNull())

    const circle = await openCircleSheet()
    expect(within(circle).getByText('Friend circle look')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^Create$/i }))
    expect(onOpenCreate).toHaveBeenCalled()
    fireEvent.click(screen.getAllByRole('button', { name: /My Looks/i })[0]!)
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
    expect(within(dialog).getByText(/Runway chat/i)).toBeInTheDocument()

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

  it('loads friends circle and can add by username', async () => {
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

    fireEvent.click(screen.getByRole('tab', { name: /Friends/i }))
    expect(await screen.findByText('@yanivprbk')).toBeInTheDocument()
    expect(listGallery).not.toHaveBeenCalled()
    expect(listFriends).toHaveBeenCalled()

    requestFriendByUsername.mockResolvedValue({
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
    fireEvent.change(screen.getByLabelText(/Add friend by username/i), {
      target: { value: 'newfriend' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Add$/i }))
    await waitFor(() => expect(requestFriendByUsername).toHaveBeenCalledWith('newfriend'))
  })

  it('opens a read-only friend profile from a friend row and keeps Remove', async () => {
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

    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('tab', { name: /Friends/i }))
    expect(await screen.findByTestId('friend-open-yaniv')).toBeInTheDocument()
    expect(screen.getByTestId('friend-remove-yaniv')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('friend-open-yaniv'))
    expect(await screen.findByTestId('friend-profile-panel')).toBeInTheDocument()
    expect(screen.getByTestId('friend-profile-username')).toHaveTextContent('@yanivprbk')
    expect(await screen.findByTestId('friend-look-g-public')).toBeInTheDocument()
    expect(screen.queryByText('12')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('friend-profile-back'))
    expect(await screen.findByTestId('friend-open-yaniv')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('friend-remove-yaniv'))
    await waitFor(() => expect(removeFriend).toHaveBeenCalledWith('yaniv'))
  })

  it('auto-enables Runway push by default on load', async () => {
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await screen.findByTestId('runway-open-circle')
    await waitFor(() => expect(ensureDefaultRunwayPush).toHaveBeenCalled())
    const toggle = await screen.findByTestId('runway-push-toggle')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText(/Push on — we’ll notify/i)).toBeInTheDocument()
  })

  it('can turn push off from the toggle switch', async () => {
    ensureDefaultRunwayPush.mockResolvedValue({ on: true, result: 'already' })
    runwayPushIsEnabled.mockResolvedValue(true)
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    const toggle = await screen.findByTestId('runway-push-toggle')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(toggle)
    await waitFor(() => expect(disableRunwayPush).toHaveBeenCalled())
    expect(await screen.findByTestId('runway-push-toggle')).toHaveAttribute('aria-checked', 'false')
  })
})
