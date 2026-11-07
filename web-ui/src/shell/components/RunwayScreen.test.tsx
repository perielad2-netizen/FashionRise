import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayScreen } from './RunwayScreen'

const listGallery = vi.fn()
const listFriends = vi.fn()
const listFriendRequests = vi.fn()
const requestFriendByUsername = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
}))

vi.mock('@/services/friendsApi', () => ({
  listFriends: (...args: unknown[]) => listFriends(...args),
  listFriendRequests: (...args: unknown[]) => listFriendRequests(...args),
  requestFriendByUsername: (...args: unknown[]) => requestFriendByUsername(...args),
  acceptFriendRequest: vi.fn(),
  removeFriend: vi.fn(),
}))

describe('RunwayScreen', () => {
  beforeEach(() => {
    listGallery.mockReset()
    listFriends.mockReset()
    listFriendRequests.mockReset()
    requestFriendByUsername.mockReset()
    listGallery.mockImplementation(async (opts?: { sort?: string }) => {
      if (opts?.sort === 'top10') {
        return [
          {
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
          },
        ]
      }
      return [
        {
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
        },
      ]
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
