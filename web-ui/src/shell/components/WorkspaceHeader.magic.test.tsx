import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WorkspaceHeader } from '@/shell/components/WorkspaceHeader'

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
    fireEvent.click(screen.getByRole('button', { name: /^More$/i }))
    expect(screen.getByRole('menuitem', { name: 'Save as design…' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'My Designs' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Clear canvas' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Save now' })).toBeTruthy()
    expect(screen.queryByRole('menuitem', { name: /Export/i })).toBeNull()
  })
})
