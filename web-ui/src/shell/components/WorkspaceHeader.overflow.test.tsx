import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({ user: { ai_stars: 10, ai_stars_unlimited: false } }),
}))

vi.mock('@/shell/components/StarsShopModal', () => ({
  StarsShopModal: () => null,
}))

vi.mock('@/shell/components/AiSpendConfirmDialog', () => ({
  AiSpendConfirmDialog: () => null,
}))

import { WorkspaceHeader } from './WorkspaceHeader'

describe('WorkspaceHeader overflow menu (V2-0001)', () => {
  const props = {
    canUndo: false,
    canRedo: false,
    onUndo: vi.fn(),
    onRedo: vi.fn(),
    onClear: vi.fn(),
    onMagic: vi.fn(),
    saveStatus: 'saved' as const,
    saveStatusLabel: 'Saved',
    saveError: null,
    onSaveDesign: vi.fn(),
    onOpenSettings: vi.fn(),
  }

  it('closes the More menu on outside pointerdown', () => {
    render(<WorkspaceHeader {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes the More menu on Escape', () => {
    render(<WorkspaceHeader {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
