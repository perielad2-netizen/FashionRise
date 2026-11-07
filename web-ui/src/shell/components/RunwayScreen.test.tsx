import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayScreen } from './RunwayScreen'

const listGallery = vi.fn()
const getGalleryItem = vi.fn()
const likeGalleryItem = vi.fn()
const unlikeGalleryItem = vi.fn()
const rateGalleryItem = vi.fn()
const listFriends = vi.fn()
const listFriendRequests = vi.fn()
const requestFriendByUsername = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
  getGalleryItem: (...args: unknown[]) => getGalleryItem(...args),
  likeGalleryItem: (...args: unknown[]) => likeGalleryItem(...args),
  unlikeGalleryItem: (...args: unknown[]) => unlikeGalleryItem(...args),
  rateGalleryItem: (...args: unknown[]) => rateGalleryItem(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
}))

vi.mock('@/services/friendsApi', () => ({
  listFriends: (...args: unknown[]) => listFriends(...args),
  listFriendRequests: (...args: unknown[]) => listFriendRequests(...args),
  requestFriendByUsername: (...args: unknown[]) => requestFriendByUsername(...args),
  acceptFriendRequest: vi.fn(),
  removeFriend: vi.fn(),
}))

const circleItem = {
  id: 'circle-1',
  design_id: null,
  look_id: 'look-circle',
  user_id: 'u-me',
  title: 'My circle look',
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
    listFriends.mockReset()
    listFriendRequests.mockReset()
    requestFriendByUsername.mockReset()
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'top10') return [{ ...topItem }]
      return [{ ...circleItem }]
    })
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([])
  })

  it('loads circle feed + Top 10 worldwide on the home tab', async () => {
    const onOpenCreate = vi.fn()
    const onOpenLooks = vi.fn()
    render(<RunwayScreen onOpenCreate={onOpenCreate} onOpenLooks={onOpenLooks} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Runway' })).toBeInTheDocument()
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    expect(listGallery).toHaveBeenCalledWith(expect.objectContaining({ sort: 'circle' }))
    expect(listGallery).toHaveBeenCalledWith(expect.objectContaining({ sort: 'top10' }))
    expect(await screen.findByText('Top 10 worldwide')).toBeInTheDocument()
    expect(screen.getByText('Worldwide hit')).toBeInTheDocument()
    expect(screen.getByText('My circle look')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^Create$/i }))
    expect(onOpenCreate).toHaveBeenCalled()
    fireEvent.click(screen.getAllByRole('button', { name: /My Looks/i })[0]!)
    expect(onOpenLooks).toHaveBeenCalled()
  })

  it('likes and scores a circle look', async () => {
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
    const circle = await screen.findByRole('list', { name: 'Circle feed' })
    const likeBtn = within(circle).getByRole('button', { name: /Like look/i })
    fireEvent.click(likeBtn)
    await waitFor(() => expect(likeGalleryItem).toHaveBeenCalledWith('circle-1'))
    await waitFor(() => expect(getGalleryItem).toHaveBeenCalledWith('circle-1'))
    expect(await within(circle).findByRole('button', { name: /Unlike look/i })).toBeInTheDocument()

    const score = within(circle).getByLabelText(/Score My circle look from 1 to 10/i)
    fireEvent.change(score, { target: { value: '9' } })
    await waitFor(() => expect(rateGalleryItem).toHaveBeenCalledWith('circle-1', 9))
    await waitFor(() => expect((score as HTMLSelectElement).value).toBe('9'))
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
})
