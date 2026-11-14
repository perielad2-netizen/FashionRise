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
