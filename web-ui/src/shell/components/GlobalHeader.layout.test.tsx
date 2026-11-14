import { fireEvent, render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAiStarsWallet', () => ({
  useAiStarsWallet: () => ({
    balance: 1_000_019,
    unlimited: false,
    costs: { magic: 10, croquis: 20, fabric: 5, pdf: 15 },
    reload: vi.fn(),
  }),
}))

vi.mock('@/services/native/iap', () => ({
  isNativeIosStarsShop: () => false,
  isNativeAndroidShell: () => true,
}))

vi.mock('@/shell/components/StarsShopModal', () => ({
  StarsShopModal: () => null,
}))

import { GlobalHeader } from './GlobalHeader'
import styles from './GlobalHeader.module.css'

const headerCss = readFileSync(resolve(__dirname, './GlobalHeader.module.css'), 'utf8')

describe('GlobalHeader Android layout (header overlap)', () => {
  it('formats long Stars balances and keeps brand + actions in separate grid tracks', () => {
    const { container } = render(<GlobalHeader username="peri" onLogout={vi.fn()} />)

    const badge = screen.getByTestId('global-stars-badge')
    expect(badge).toHaveTextContent('1,000,019')
    expect(badge).toHaveAccessibleName(/1,000,019 Stars/i)

    expect(screen.getByText(/Fashion/i).closest('p')).toHaveClass(styles.wordmark)
    expect(container.querySelector(`.${styles.brand}`)).toBeTruthy()
    expect(container.querySelector(`.${styles.actions}`)).toBeTruthy()

    // Narrow Android: brand track can shrink; Stars badge is capped so it cannot cover the wordmark.
    expect(headerCss).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/)
    expect(headerCss).toMatch(/\.starsBadge[\s\S]*max-width:\s*min\(/)
    expect(headerCss).toMatch(/\.wordmark[\s\S]*text-overflow:\s*ellipsis/)
    // Account chevron menu must paint above the page body (not clipped under it).
    expect(headerCss).toMatch(/\.header\s*\{[\s\S]*?overflow:\s*visible/)
    expect(headerCss).toMatch(/\.headerMenuOpen\s*\{[\s\S]*?z-index:\s*60/)
  })

  it('lifts the header stacking context while the account chevron menu is open', () => {
    const { container } = render(<GlobalHeader username="peri" onLogout={vi.fn()} />)
    const header = container.querySelector('header')
    expect(header).not.toHaveClass(styles.headerMenuOpen)
    fireEvent.click(screen.getByTestId('global-account-menu'))
    expect(screen.getByTestId('global-account-menu-panel')).toBeInTheDocument()
    expect(header).toHaveClass(styles.headerMenuOpen)
  })
})
