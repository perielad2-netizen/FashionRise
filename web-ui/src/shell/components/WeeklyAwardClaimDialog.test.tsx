import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchPendingAwardClaims = vi.fn()
const claimCompetitionAward = vi.fn()
const refreshUser = vi.fn()

vi.mock('@/services/competitionsApi', () => ({
  fetchPendingAwardClaims: (...args: unknown[]) => fetchPendingAwardClaims(...args),
  claimCompetitionAward: (...args: unknown[]) => claimCompetitionAward(...args),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'winner' },
    refreshUser,
  }),
}))

describe('WeeklyAwardClaimDialog', () => {
  beforeEach(() => {
    fetchPendingAwardClaims.mockReset()
    claimCompetitionAward.mockReset()
    refreshUser.mockReset()
  })

  it('shows a one-time confirm and claims Stars on Receive', async () => {
    fetchPendingAwardClaims.mockResolvedValue([
      {
        id: 'award-1',
        category: 'top_designer',
        label: 'Top Designer',
        stars_amount: 50,
        week_start: '2026-11-15T00:00:00+00:00',
        week_label: 'Week of 2026-11-15',
      },
    ])
    claimCompetitionAward.mockResolvedValue({
      id: 'award-1',
      category: 'top_designer',
      label: 'Top Designer',
      stars_amount: 50,
      week_start: '2026-11-15T00:00:00+00:00',
      claimed_at: '2026-11-23T00:00:00+00:00',
      newly_credited: true,
      already_claimed: false,
      ai_stars: 150,
    })

    const { WeeklyAwardClaimDialog } = await import('./WeeklyAwardClaimDialog')
    render(<WeeklyAwardClaimDialog />)

    expect(
      await screen.findByRole('heading', { name: /You won a weekly award/i }),
    ).toBeTruthy()
    expect(screen.getByTestId('weekly-award-claim-body')).toHaveTextContent(/Top Designer/i)
    fireEvent.click(screen.getByRole('button', { name: /Receive 50 Stars/i }))
    await waitFor(() => expect(claimCompetitionAward).toHaveBeenCalledWith('award-1'))
    await waitFor(() => expect(refreshUser).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: /You won a weekly award/i })).toBeNull(),
    )
  })

  it('renders nothing when there are no pending awards', async () => {
    fetchPendingAwardClaims.mockResolvedValue([])
    const { WeeklyAwardClaimDialog } = await import('./WeeklyAwardClaimDialog')
    const { container } = render(<WeeklyAwardClaimDialog />)
    await waitFor(() => expect(fetchPendingAwardClaims).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
