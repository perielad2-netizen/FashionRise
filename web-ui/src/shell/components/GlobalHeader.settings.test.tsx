import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAiStarsWallet', () => ({
  useAiStarsWallet: () => ({
    balance: 10,
    unlimited: false,
    costs: { magic: 10 },
    reload: vi.fn(),
  }),
}))

vi.mock('@/services/native/iap', () => ({
  isNativeIosStarsShop: () => false,
  isNativeAndroidShell: () => false,
}))

vi.mock('@/shell/components/StarsShopModal', () => ({
  StarsShopModal: () => null,
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'peri' },
    refreshUser: vi.fn(),
  }),
}))

vi.mock('@/services/profilesApi', () => ({
  getMyProfile: vi.fn(async () => ({
    id: 'p1',
    user_id: 'u1',
    display_name: 'Peri',
    bio: null,
    avatar_url: null,
    cover_url: null,
    style_tags: [],
    published_count: 0,
    followers_count: 0,
    likes_received_count: 0,
    rating_average: null,
    rating_count: 0,
    reputation_score: 0,
    reputation_tier: 'new',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  })),
  profileAvatarSrc: () => null,
}))

import { GlobalHeader } from './GlobalHeader'

describe('GlobalHeader settings gear (V2-0006)', () => {
  it('opens a Settings panel with About / Privacy / Contact — not About alone', () => {
    render(<GlobalHeader username="peri" onLogout={vi.fn()} />)
    fireEvent.click(screen.getByTestId('global-settings'))
    const panel = screen.getByTestId('global-settings-panel')
    expect(panel).toHaveTextContent('Settings')
    expect(panel).toHaveTextContent('About FashionRise')
    expect(panel).toHaveTextContent('Privacy Policy')
    expect(panel).toHaveTextContent('Contact us')
    expect(screen.queryByRole('heading', { name: 'About FashionRise' })).not.toBeInTheDocument()
  })
})
