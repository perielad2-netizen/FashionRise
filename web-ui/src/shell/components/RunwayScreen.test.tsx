import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayScreen } from './RunwayScreen'

const listGallery = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
}))

describe('RunwayScreen', () => {
  beforeEach(() => {
    listGallery.mockReset()
    listGallery.mockResolvedValue([])
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

  it('shows friends coming-soon without hitting the feed API', async () => {
    render(<RunwayScreen onOpenCreate={vi.fn()} onOpenLooks={vi.fn()} />)
    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    listGallery.mockClear()

    fireEvent.click(screen.getByRole('tab', { name: /Friends/i }))
    expect(await screen.findByText(/Friends circle is next/i)).toBeInTheDocument()
    expect(listGallery).not.toHaveBeenCalled()
  })
})
