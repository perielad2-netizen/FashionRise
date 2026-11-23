import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { __followStatusCacheTestUtils } from '@/lib/followStatusStore'
import { FriendProfilePanel } from './FriendProfilePanel'

const getPublicProfile = vi.fn()
const getFollowStatus = vi.fn()
const followCreator = vi.fn()
const unfollowCreator = vi.fn()
const listProfileFollowers = vi.fn()
const listUserGallery = vi.fn()
const updateMyProfile = vi.fn()
const uploadMyAvatar = vi.fn()

vi.mock('@/services/profilesApi', () => ({
  getPublicProfile: (...args: unknown[]) => getPublicProfile(...args),
  getFollowStatus: (...args: unknown[]) => getFollowStatus(...args),
  followCreator: (...args: unknown[]) => followCreator(...args),
  unfollowCreator: (...args: unknown[]) => unfollowCreator(...args),
  listProfileFollowers: (...args: unknown[]) => listProfileFollowers(...args),
  updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
  uploadMyAvatar: (...args: unknown[]) => uploadMyAvatar(...args),
  profileAvatarSrc: (userId: string, avatarUrl: string | null | undefined) =>
    avatarUrl ? `/api/v1/profiles/${userId}/avatar` : null,
}))

vi.mock('@/services/galleryApi', () => ({
  listUserGallery: (...args: unknown[]) => listUserGallery(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
  getGalleryItem: vi.fn(async (id: string) => ({ id, likes_count: 0, liked_by_me: false })),
  likeGalleryItem: vi.fn(async () => undefined),
  unlikeGalleryItem: vi.fn(async () => undefined),
  rateGalleryItem: vi.fn(async () => ({ score: 8 })),
  listGalleryComments: vi.fn(async () => []),
  postGalleryComment: vi.fn(async () => ({
    id: 'c1',
    gallery_item_id: 'g1',
    user_id: 'viewer-1',
    body: 'Nice',
    moderation_status: 'ok',
    likes_count: 0,
    created_at: '2026-11-17T00:00:00Z',
    username: 'viewer',
  })),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'viewer-1', username: 'viewer' },
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

const friend = {
  user_id: 'friend-1',
  username: 'yanivprbk',
  display_name: 'Yaniv',
  avatar_url: null,
}

const own = {
  user_id: 'viewer-1',
  username: 'viewer',
  display_name: 'Viewer',
  avatar_url: null,
}

describe('FriendProfilePanel (premium designer card)', () => {
  beforeEach(() => {
    __followStatusCacheTestUtils.clear()
    getPublicProfile.mockReset()
    getFollowStatus.mockReset()
    followCreator.mockReset()
    unfollowCreator.mockReset()
    listProfileFollowers.mockReset()
    listUserGallery.mockReset()
    updateMyProfile.mockReset()
    uploadMyAvatar.mockReset()
    listProfileFollowers.mockResolvedValue([])
    getPublicProfile.mockResolvedValue({
      id: 'p1',
      user_id: 'friend-1',
      display_name: 'Yaniv',
      bio: 'Public runway creator',
      avatar_url: null,
      cover_url: null,
      style_tags: [],
      designs_count: 99,
      published_count: 99,
      followers_count: 3,
      likes_received_count: 10,
      rating_average: 8,
      rating_count: 2,
      reputation_score: 40,
      reputation_tier: 'rising',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    getFollowStatus.mockResolvedValue({ user_id: 'friend-1', following: false })
    listUserGallery.mockResolvedValue([
      {
        id: 'g1',
        design_id: null,
        look_id: 'look-1',
        user_id: 'friend-1',
        title: 'Public look',
        image_url: null,
        visibility: 'public',
        rating_average: 8,
        rating_count: 1,
        likes_count: 2,
        moderation_status: 'ok',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
  })

  it('loads public profile + published looks and ignores private design counts', async () => {
    render(<FriendProfilePanel friend={friend} />)

    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Yaniv')
    expect(screen.getByTestId('friend-profile-username')).toHaveTextContent('@yanivprbk')
    expect(screen.getByTestId('friend-profile-bio')).toHaveTextContent(/Public runway creator/i)
    expect(screen.getByTestId('friend-published-count')).toHaveTextContent('1')
    expect(screen.getByTestId('designer-followers')).toHaveTextContent('3')
    expect(screen.getByTestId('designer-likes')).toHaveTextContent('10')
    expect(screen.getByTestId('designer-reputation')).toHaveTextContent('40')
    expect(screen.getByTestId('designer-tier-badge')).toHaveTextContent(/rising/i)
    expect(screen.queryByText('99')).not.toBeInTheDocument()
    expect(screen.getByTestId('friend-look-g1')).toBeInTheDocument()
    expect(getPublicProfile).toHaveBeenCalledWith('friend-1', expect.any(AbortSignal))
    expect(listUserGallery).toHaveBeenCalledWith('friend-1', expect.any(AbortSignal))
    expect(await screen.findByTestId('designer-follow-btn')).toHaveTextContent(/Follow/i)
    expect(screen.queryByTestId('designer-profile-editor')).not.toBeInTheDocument()
    expect(screen.queryByTestId('friend-profile-back')).not.toBeInTheDocument()
  })

  it('follows a designer from the profile', async () => {
    followCreator.mockResolvedValue(undefined)
    render(<FriendProfilePanel friend={friend} />)
    const btn = await screen.findByTestId('designer-follow-btn')
    fireEvent.click(btn)
    await waitFor(() => expect(followCreator).toHaveBeenCalledWith('friend-1'))
    expect(btn).toHaveTextContent(/Following/i)
    expect(__followStatusCacheTestUtils.get('viewer-1', 'friend-1')).toBe(true)
  })

  it('opens Followers and lets the viewer follow someone from the list', async () => {
    listProfileFollowers.mockResolvedValue([
      {
        user_id: 'fan-1',
        username: 'fanone',
        display_name: 'Fan One',
        avatar_url: null,
        following: false,
      },
    ])
    followCreator.mockResolvedValue(undefined)
    render(<FriendProfilePanel friend={friend} />)
    fireEvent.click(await screen.findByTestId('designer-followers-btn'))
    const sheet = await screen.findByTestId('designer-followers-sheet')
    expect(within(sheet).getByText('@fanone')).toBeInTheDocument()
    fireEvent.click(within(sheet).getByTestId('follower-follow-fan-1'))
    await waitFor(() => expect(followCreator).toHaveBeenCalledWith('fan-1'))
    expect(__followStatusCacheTestUtils.get('viewer-1', 'fan-1')).toBe(true)
  })

  it('opens a follower profile from the Followers list', async () => {
    const onOpenDesigner = vi.fn()
    listProfileFollowers.mockResolvedValue([
      {
        user_id: 'fan-1',
        username: 'fanone',
        display_name: 'Fan One',
        avatar_url: null,
        following: false,
      },
    ])
    render(<FriendProfilePanel friend={friend} onOpenDesigner={onOpenDesigner} />)
    fireEvent.click(await screen.findByTestId('designer-followers-btn'))
    fireEvent.click(await screen.findByTestId('follower-open-fan-1'))
    expect(onOpenDesigner).toHaveBeenCalledWith({
      user_id: 'fan-1',
      username: 'fanone',
      display_name: 'Fan One',
      avatar_url: null,
    })
    expect(screen.queryByTestId('designer-followers-sheet')).not.toBeInTheDocument()
  })

  it('shows an empty state when the friend has no published looks', async () => {
    listUserGallery.mockResolvedValue([])
    render(<FriendProfilePanel friend={friend} />)
    expect(await screen.findByTestId('friend-looks-empty')).toHaveTextContent(
      /No published FashionRise looks/i,
    )
    expect(screen.getByTestId('friend-published-count')).toHaveTextContent('0')
  })

  it('still shows identity when public profile fetch fails', async () => {
    getPublicProfile.mockRejectedValue(new Error('offline'))
    render(<FriendProfilePanel friend={friend} />)
    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Yaniv')
    await waitFor(() => expect(screen.getByTestId('friend-look-g1')).toBeInTheDocument())
  })

  it('shows own designed profile first and opens edit page on demand', async () => {
    getPublicProfile.mockResolvedValue({
      id: 'p-me',
      user_id: 'viewer-1',
      display_name: 'Studio Nova',
      bio: '',
      avatar_url: null,
      cover_url: null,
      style_tags: [],
      designs_count: 0,
      published_count: 0,
      followers_count: 0,
      likes_received_count: 0,
      rating_average: null,
      rating_count: 0,
      reputation_score: 12,
      reputation_tier: 'newcomer',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    listUserGallery.mockResolvedValue([])
    render(<FriendProfilePanel friend={own} />)

    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Studio Nova')
    expect(screen.queryByTestId('designer-follow-btn')).not.toBeInTheDocument()
    expect(screen.queryByTestId('designer-profile-editor')).not.toBeInTheDocument()
    expect(screen.getByTestId('designer-edit-profile')).toHaveTextContent(/Edit Designer Card/i)

    fireEvent.click(screen.getByTestId('designer-edit-profile'))
    expect(screen.getByTestId('designer-profile-editor')).toBeInTheDocument()
    expect(screen.getByTestId('designer-avatar-preview')).toBeInTheDocument()

    updateMyProfile.mockResolvedValue({
      id: 'p-me',
      user_id: 'viewer-1',
      display_name: 'Atelier Noa',
      bio: 'Evening knits.',
      avatar_url: null,
      cover_url: null,
      style_tags: [],
      designs_count: 0,
      published_count: 0,
      followers_count: 0,
      likes_received_count: 0,
      rating_average: null,
      rating_count: 0,
      reputation_score: 12,
      reputation_tier: 'newcomer',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    fireEvent.change(screen.getByTestId('designer-edit-name'), {
      target: { value: 'Atelier Noa' },
    })
    fireEvent.change(screen.getByTestId('designer-edit-bio'), {
      target: { value: 'Evening knits.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(updateMyProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          display_name: 'Atelier Noa',
          bio: 'Evening knits.',
        }),
      ),
    )
    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Atelier Noa')
    expect(screen.queryByTestId('designer-profile-editor')).not.toBeInTheDocument()
  })

  it('opens a published look preview from the collection', async () => {
    render(<FriendProfilePanel friend={friend} />)
    fireEvent.click(await screen.findByTestId('friend-look-g1'))
    const preview = await screen.findByTestId('designer-look-preview')
    expect(within(preview).getByRole('heading', { name: 'Public look' })).toBeInTheDocument()
    fireEvent.click(within(preview).getByRole('button', { name: 'Close look' }))
    expect(screen.queryByTestId('designer-look-preview')).not.toBeInTheDocument()
  })

  it('opens the profile photo lightbox when the avatar is clicked', async () => {
    getPublicProfile.mockResolvedValue({
      id: 'p1',
      user_id: 'friend-1',
      display_name: 'Yaniv',
      bio: 'Public runway creator',
      avatar_url: '/api/v1/profiles/friend-1/avatar',
      cover_url: null,
      style_tags: [],
      designs_count: 1,
      published_count: 1,
      followers_count: 3,
      likes_received_count: 10,
      rating_average: 8,
      rating_count: 2,
      reputation_score: 40,
      reputation_tier: 'rising',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    render(
      <FriendProfilePanel
        friend={{ ...friend, avatar_url: '/api/v1/profiles/friend-1/avatar' }}
      />,
    )
    fireEvent.click(await screen.findByTestId('designer-avatar-open'))
    const preview = await screen.findByTestId('designer-avatar-preview-lightbox')
    expect(within(preview).getByRole('heading', { name: 'Yaniv' })).toBeInTheDocument()
    expect(within(preview).getByAltText("Yaniv's profile photo")).toBeInTheDocument()
    fireEvent.click(within(preview).getByRole('button', { name: 'Close profile photo' }))
    expect(screen.queryByTestId('designer-avatar-preview-lightbox')).not.toBeInTheDocument()
  })

  it('honors startInEditMode for explicit edit entry', async () => {
    getPublicProfile.mockResolvedValue({
      id: 'p-me',
      user_id: 'viewer-1',
      display_name: 'Viewer',
      bio: '',
      avatar_url: null,
      cover_url: null,
      style_tags: [],
      designs_count: 0,
      published_count: 0,
      followers_count: 0,
      likes_received_count: 0,
      rating_average: null,
      rating_count: 0,
      reputation_score: 0,
      reputation_tier: 'newcomer',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    listUserGallery.mockResolvedValue([])
    render(<FriendProfilePanel friend={own} startInEditMode />)
    expect(await screen.findByTestId('designer-profile-editor')).toBeInTheDocument()
  })
})
