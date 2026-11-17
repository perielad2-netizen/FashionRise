import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayBoardScreen } from './RunwayBoardScreen'

function renderBoard() {
  return render(
    <MemoryRouter>
      <RunwayBoardScreen />
    </MemoryRouter>,
  )
}

const listGallery = vi.fn()
const fetchCategoryBoard = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGallery: (...args: unknown[]) => listGallery(...args),
  fetchGalleryImageBlob: vi.fn(async () => new Blob()),
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
    award_categories: [],
    runway_note: 'Worldwide Runway stays global',
    publish_note: 'Publish anytime.',
    weekly_rewards_enabled: false,
    weekly_rewards_launch_week_start: null,
  })),
  fetchCompetitionAwards: vi.fn(async () => []),
  fetchStreakStatus: vi.fn(async () => null),
  fetchCategoryBoard: (...args: unknown[]) => fetchCategoryBoard(...args),
}))

vi.mock('@/services/profilesApi', () => ({
  profileAvatarSrc: () => null,
}))

function item(id: string, title: string): Record<string, unknown> {
  return {
    id,
    design_id: null,
    look_id: null,
    user_id: 'u1',
    title,
    image_url: null,
    visibility: 'public',
    rating_average: 4.5,
    rating_count: 2,
    likes_count: 12,
    moderation_status: 'ok',
    created_at: '2026-11-16T00:00:00.000Z',
    updated_at: '2026-11-16T00:00:00.000Z',
    username: 'maya',
  }
}

describe('RunwayBoardScreen', () => {
  beforeEach(() => {
    listGallery.mockReset()
    fetchCategoryBoard.mockReset()
    listGallery.mockResolvedValue([item('g1', 'Pink gown')])
    fetchCategoryBoard.mockResolvedValue({
      category: 'top_designer',
      label: 'Top Designer',
      stars: 50,
      week_start: '2026-11-15T00:00:00+00:00',
      week_end: '2026-11-22T00:00:00+00:00',
      group_index: 0,
      empty_reason: null,
      entries: [
        {
          rank: 1,
          user_id: 'u-noa',
          username: 'NoaPeri',
          display_name: 'Noa Peri',
          avatar_url: null,
          score: 42,
          gallery_item_id: null,
          look_title: null,
        },
        {
          rank: 2,
          user_id: 'u-peri',
          username: 'PeriShilat',
          display_name: 'Peri Shilat',
          avatar_url: null,
          score: 31,
          gallery_item_id: null,
          look_title: null,
        },
      ],
    })
  })

  it('opens a weekly category profile board on click', async () => {
    renderBoard()
    expect(screen.getByRole('heading', { level: 1, name: 'Runway' })).toBeInTheDocument()
    expect(screen.getByTestId('runway-open-fashionrise')).toHaveTextContent(/FashionRise Social/i)
    expect(screen.getByTestId('runway-cat-top_design')).toHaveTextContent(/Top Designs/i)
    expect(await screen.findByText('Pink gown')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('runway-cat-top_designer'))
    await waitFor(() =>
      expect(fetchCategoryBoard).toHaveBeenCalledWith('top_designer', 20),
    )
    expect(await screen.findByText('Noa Peri')).toBeInTheDocument()
    expect(screen.getByText('@NoaPeri')).toBeInTheDocument()
    expect(screen.getByText('Peri Shilat')).toBeInTheDocument()
    expect(screen.queryByText('Group 1')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Top Designer' })).toBeInTheDocument()
    expect(screen.getByLabelText('Top Designer top three')).toBeInTheDocument()
  })
})
