import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayScreen } from './RunwayScreen'

const listGallery = vi.fn()
const listFriends = vi.fn()
const listFriendRequests = vi.fn()
const requestFriendByUsername = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
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
    listGallery.mockResolvedValue([])
    listFriends.mockResolvedValue([])
    listFriendRequests.mockResolvedValue([])
  })

  it('loads the community feed and routes Create / My Looks', async () => {
    const onOpenCreate = vi.fn()
    const onOpenLooks = vi.fn()
    render(<RunwayScreen onOpenCreate={onOpenCreate} onOpenLooks={onOpenLooks} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Runway' })).toBeInTheDocument()
    expect(screen.getByText('FashionRise')).toBeInTheDocument()
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    expect(await screen.findByText(/runway is waiting/i)).toBeInTheDocument()

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
