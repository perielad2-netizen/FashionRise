import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('ModelLibraryPanel Create My Croquis entry', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('hides Create My Croquis entry when UI gate is OFF (default)', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', undefined)
    const { ModelLibraryPanel: Panel } = await import('@/shell/components/ModelLibraryPanel')
    render(
      <Panel
        selected="female-straight"
        customPreviewUrl={null}
        onSelect={() => undefined}
        onCustomFile={() => undefined}
        onCreateMyCroquis={() => undefined}
      />,
    )
    expect(screen.queryByTestId('create-my-croquis-entry')).toBeNull()
  })

  it('shows Create My Croquis entry when UI gate is ON', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', 'true')
    vi.resetModules()
    const { ModelLibraryPanel: Panel } = await import('@/shell/components/ModelLibraryPanel')
    render(
      <Panel
        selected="female-straight"
        customPreviewUrl={null}
        onSelect={() => undefined}
        onCustomFile={() => undefined}
        onCreateMyCroquis={() => undefined}
      />,
    )
    expect(screen.getByTestId('create-my-croquis-entry')).toBeTruthy()
  })
})
