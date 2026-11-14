import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FriendProfilePanel } from './FriendProfilePanel'

const getPublicProfile = vi.fn()
const listUserGallery = vi.fn()

vi.mock('@/services/profilesApi', () => ({
  getPublicProfile: (...args: unknown[]) => getPublicProfile(...args),
}))

vi.mock('@/services/galleryApi', () => ({
  listUserGallery: (...args: unknown[]) => listUserGallery(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
}))

const friend = {
  user_id: 'friend-1',
  username: 'yanivprbk',
  display_name: 'Yaniv',
  avatar_url: null,
}

describe('FriendProfilePanel (V2-0010)', () => {
  beforeEach(() => {
    getPublicProfile.mockReset()
    listUserGallery.mockReset()
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
    const onBack = vi.fn()
    render(<FriendProfilePanel friend={friend} onBack={onBack} />)

    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Yaniv')
    expect(screen.getByTestId('friend-profile-username')).toHaveTextContent('@yanivprbk')
    expect(screen.getByTestId('friend-profile-bio')).toHaveTextContent(/Public runway creator/i)
    expect(screen.getByTestId('friend-published-count')).toHaveTextContent('1')
    expect(screen.queryByText('99')).not.toBeInTheDocument()
    expect(screen.getByTestId('friend-look-g1')).toBeInTheDocument()
    expect(getPublicProfile).toHaveBeenCalledWith('friend-1', expect.any(AbortSignal))
    expect(listUserGallery).toHaveBeenCalledWith('friend-1', expect.any(AbortSignal))

    fireEvent.click(screen.getByTestId('friend-profile-back'))
    expect(onBack).toHaveBeenCalled()
  })

  it('shows an empty state when the friend has no published looks', async () => {
    listUserGallery.mockResolvedValue([])
    render(<FriendProfilePanel friend={friend} onBack={vi.fn()} />)
    expect(await screen.findByTestId('friend-looks-empty')).toHaveTextContent(
      /No published Runway looks/i,
    )
    expect(screen.getByTestId('friend-published-count')).toHaveTextContent('0')
  })

  it('still shows identity when public profile fetch fails', async () => {
    getPublicProfile.mockRejectedValue(new Error('offline'))
    render(<FriendProfilePanel friend={friend} onBack={vi.fn()} />)
    expect(await screen.findByTestId('friend-profile-name')).toHaveTextContent('Yaniv')
    await waitFor(() => expect(screen.getByTestId('friend-look-g1')).toBeInTheDocument())
  })
})
