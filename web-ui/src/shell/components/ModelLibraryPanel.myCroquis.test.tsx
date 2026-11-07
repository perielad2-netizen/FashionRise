import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const listPersonalCroquis = vi.fn()

vi.mock('@/services/personalCroquisApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/personalCroquisApi')>(
    '@/services/personalCroquisApi',
  )
  return {
    ...actual,
    listPersonalCroquis: (...args: unknown[]) => listPersonalCroquis(...args),
  }
})

describe('ModelLibraryPanel Create My Croquis entry', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
    listPersonalCroquis.mockReset()
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
    expect(screen.queryByTestId('models-tab-mine')).toBeNull()
  })

  it('shows My Models tab when UI gate is ON', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', 'true')
    vi.resetModules()
    listPersonalCroquis.mockResolvedValue([])
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
    expect(screen.getByTestId('models-tab-system')).toBeTruthy()
    expect(screen.getByTestId('models-tab-mine')).toBeTruthy()
    expect(screen.queryByText(/My Gallery/i)).toBeNull()
  })

  it('shows empty My Models state with Create Model CTA', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', 'true')
    vi.resetModules()
    listPersonalCroquis.mockResolvedValue([])
    const onCreate = vi.fn()
    const { ModelLibraryPanel: Panel } = await import('@/shell/components/ModelLibraryPanel')
    render(
      <Panel
        selected="female-straight"
        customPreviewUrl={null}
        onSelect={() => undefined}
        onCustomFile={() => undefined}
        onCreateMyCroquis={onCreate}
      />,
    )
    fireEvent.click(screen.getByTestId('models-tab-mine'))
    expect(await screen.findByTestId('my-models-empty')).toBeTruthy()
    expect(screen.getByText(/Your model library is empty/i)).toBeTruthy()
    fireEvent.click(screen.getByTestId('my-models-empty-create'))
    expect(onCreate).toHaveBeenCalled()
  })

  it('lists accepted personal models for selection', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', 'true')
    vi.resetModules()
    listPersonalCroquis.mockResolvedValue([
      {
        id: 'pc-1',
        display_name: 'Studio Muse',
        status: 'ready',
        source_asset_id: null,
        storage_consent_id: null,
        adults_attestation_at: null,
        archived: false,
        erased: false,
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
        latest_accepted_version: {
          version: 2,
          status: 'accepted',
          generated_asset_id: 'asset-1',
          geometry_profile: null,
          accepted_at: '2026-11-01T00:00:00Z',
        },
      },
    ])
    const onSelectPersonal = vi.fn()
    const { ModelLibraryPanel: Panel } = await import('@/shell/components/ModelLibraryPanel')
    render(
      <Panel
        selected="personal"
        customPreviewUrl={null}
        onSelect={() => undefined}
        onCustomFile={() => undefined}
        onCreateMyCroquis={() => undefined}
        onSelectPersonal={onSelectPersonal}
        personalCroquisId="pc-1"
      />,
    )
    fireEvent.click(screen.getByTestId('models-tab-mine'))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Use Studio Muse in Studio/i })).toBeTruthy()
    })
    fireEvent.click(screen.getByRole('button', { name: /Use Studio Muse in Studio/i }))
    expect(onSelectPersonal).toHaveBeenCalledWith('pc-1', 2)
  })
})
