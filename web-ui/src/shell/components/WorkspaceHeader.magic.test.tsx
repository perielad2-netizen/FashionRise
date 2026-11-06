import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WorkspaceHeader } from '@/shell/components/WorkspaceHeader'

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 't@example.com',
      username: 't',
      is_active: true,
      is_admin: false,
      ai_stars: 10,
      ai_stars_unlimited: false,
      created_at: '2026-01-01T00:00:00Z',
    },
    bootstrapping: false,
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    googleOAuthAvailable: false,
  }),
}))

describe('WorkspaceHeader Magic recovery', () => {
  it('exposes See last result without requiring a new Magic click', () => {
    const onRecover = vi.fn()
    render(
      <WorkspaceHeader
        canUndo={false}
        canRedo={false}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        onClear={vi.fn()}
        onMagic={vi.fn()}
        magicEnabled
        canRecoverLastMagic
        onRecoverLastMagic={onRecover}
        saveStatus="idle"
        saveStatusLabel="Ready"
        saveError={null}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^More$/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /See last result/i }))
    expect(onRecover).toHaveBeenCalledTimes(1)
  })

  it('disables Magic while busy to prevent overlapping paid jobs', () => {
    render(
      <WorkspaceHeader
        canUndo={false}
        canRedo={false}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        onClear={vi.fn()}
        onMagic={vi.fn()}
        magicEnabled
        magicBusy
        saveStatus="idle"
        saveStatusLabel="Ready"
        saveError={null}
      />,
    )
    expect(screen.getByRole('button', { name: /^Magic/i })).toBeDisabled()
  })

  it('does not expose raw sketch export actions in More', () => {
    render(
      <WorkspaceHeader
        canUndo={false}
        canRedo={false}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        onClear={vi.fn()}
        onMagic={vi.fn()}
        magicEnabled
        onSaveDesign={vi.fn()}
        onOpenLibrary={vi.fn()}
        onRetrySave={vi.fn()}
        saveStatus="idle"
        saveStatusLabel="Ready"
        saveError={null}
      />,
    )
    expect(screen.getByTestId('workspace-more')).toBeTruthy()
    expect(screen.getByRole('button', { name: /^More$/i }).textContent).toMatch(/More/i)
    fireEvent.click(screen.getByRole('button', { name: /^More$/i }))
    expect(screen.getByRole('menuitem', { name: 'Save as design…' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'My Designs' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: /Share FashionRise/i })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Clear canvas' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Save now' })).toBeTruthy()
    expect(screen.queryByRole('menuitem', { name: /Export/i })).toBeNull()
  })
})
