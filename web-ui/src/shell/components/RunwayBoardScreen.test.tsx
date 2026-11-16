import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunwayBoardScreen } from './RunwayBoardScreen'

const listGallery = vi.fn()

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
    award_categories: [
      { id: 'top_design', label: 'Top Design', stars: 50 },
      { id: 'top_designer', label: 'Top Designer', stars: 50 },
      { id: 'community_champion', label: 'Community Champion', stars: 50 },
      { id: 'top_supporter', label: 'Top Supporter', stars: 20 },
      { id: 'top_commenter', label: 'Top Commenter', stars: 20 },
      { id: 'top_rater', label: 'Top Rater', stars: 20 },
    ],
    runway_note: 'Worldwide Runway Top 10/20/50 stays global',
    publish_note: 'Publish anytime.',
    weekly_rewards_enabled: false,
    weekly_rewards_launch_week_start: null,
  })),
  fetchCompetitionAwards: vi.fn(async () => []),
  fetchStreakStatus: vi.fn(async () => null),
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
    listGallery.mockResolvedValue([item('g1', 'Pink gown')])
  })

  it('shows Runway rankings with Top 10/20/50 and weekly categories', async () => {
    render(<RunwayBoardScreen />)
    expect(screen.getByRole('heading', { level: 1, name: 'Runway' })).toBeInTheDocument()
    expect(screen.getByText(/Instagram-style scroll lives on FashionRise/i)).toBeInTheDocument()

    await waitFor(() => expect(listGallery).toHaveBeenCalled())
    expect(listGallery.mock.calls[0][0]).toMatchObject({ sort: 'top10', limit: 10 })
    expect(await screen.findByText('Pink gown')).toBeInTheDocument()

    expect(screen.getByLabelText('Award categories')).toHaveTextContent('Top Design')
    expect(screen.getByLabelText('Award categories')).toHaveTextContent('Community Champion')
    expect(screen.getByLabelText('Award categories')).toHaveTextContent('Top Rater')

    fireEvent.click(screen.getByTestId('runway-top-limit-50'))
    await waitFor(() =>
      expect(listGallery.mock.calls.at(-1)?.[0]).toMatchObject({ sort: 'top10', limit: 50 }),
    )

    fireEvent.click(screen.getByTestId('runway-scope-friends'))
    await waitFor(() =>
      expect(listGallery.mock.calls.at(-1)?.[0]).toMatchObject({ sort: 'circle' }),
    )
  })
})
