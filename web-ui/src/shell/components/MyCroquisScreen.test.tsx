import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MyCroquisScreen } from '@/shell/components/MyCroquisScreen'

const mocks = vi.hoisted(() => ({
  listPersonalCroquis: vi.fn(),
  erasePersonalCroquis: vi.fn(),
  fetchCroquisAssetBlob: vi.fn(),
  isMyCroquisUiEnabled: vi.fn(() => true),
}))

vi.mock('@/config/myCroquisUi', () => ({
  isMyCroquisUiEnabled: () => mocks.isMyCroquisUiEnabled(),
}))

vi.mock('@/services/personalCroquisApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/personalCroquisApi')>()
  return {
    ...actual,
    listPersonalCroquis: mocks.listPersonalCroquis,
    erasePersonalCroquis: mocks.erasePersonalCroquis,
    fetchCroquisAssetBlob: mocks.fetchCroquisAssetBlob,
  }
})

vi.mock('@/shell/components/CreateMyCroquisWizard', () => ({
  CreateMyCroquisWizard: ({
    onClose,
    onPinAccepted,
  }: {
    open: boolean
    onClose: () => void
    onPinAccepted: (id: string, version: number) => void
  }) => (
    <div role="dialog" aria-label="Create My Croquis wizard">
      <button type="button" onClick={onClose}>
        Close wizard
      </button>
      <button type="button" onClick={() => onPinAccepted('new-croquis', 1)}>
        Accept new
      </button>
    </div>
  ),
}))

const sampleRows = [
  {
    id: 'croquis-a',
    display_name: 'Croquis A',
    status: 'ready',
    source_asset_id: 'src-a',
    storage_consent_id: 'consent-a',
    adults_attestation_at: '2026-11-01T00:00:00Z',
    archived: false,
    erased: false,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
    latest_accepted_version: {
      version: 1,
      status: 'accepted',
      generated_asset_id: 'asset-a',
      geometry_profile: null,
      accepted_at: '2026-11-01T00:00:00Z',
    },
  },
  {
    id: 'croquis-b',
    display_name: 'Croquis B',
    status: 'ready',
    source_asset_id: 'src-b',
    storage_consent_id: 'consent-b',
    adults_attestation_at: '2026-11-01T00:00:00Z',
    archived: false,
    erased: false,
    created_at: '2026-11-01T01:00:00Z',
    updated_at: '2026-11-01T01:00:00Z',
    latest_accepted_version: {
      version: 2,
      status: 'accepted',
      generated_asset_id: 'asset-b',
      geometry_profile: null,
      accepted_at: '2026-11-01T01:00:00Z',
    },
  },
]

describe('MyCroquisScreen', () => {
  beforeEach(() => {
    mocks.isMyCroquisUiEnabled.mockReturnValue(true)
    mocks.listPersonalCroquis.mockReset()
    mocks.erasePersonalCroquis.mockReset()
    mocks.fetchCroquisAssetBlob.mockReset()
    mocks.listPersonalCroquis.mockResolvedValue(sampleRows)
    mocks.fetchCroquisAssetBlob.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    mocks.erasePersonalCroquis.mockResolvedValue({ ...sampleRows[0], erased: true })
    // jsdom lacks IntersectionObserver — treat thumbs as immediately visible.
    window.IntersectionObserver = class {
      private cb: IntersectionObserverCallback
      constructor(cb: IntersectionObserverCallback) {
        this.cb = cb
      }
      observe(target: Element) {
        this.cb(
          [{ isIntersecting: true, target } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        )
      }
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return []
      }
      root = null
      rootMargin = ''
      thresholds = []
    } as unknown as typeof IntersectionObserver
  })

  it('lists croquis with Use in Studio and Delete actions', async () => {
    const onUse = vi.fn()
    render(
      <MyCroquisScreen
        onBackToStudio={() => undefined}
        onUseInStudio={onUse}
        activeStudioPinId="croquis-a"
      />,
    )
    expect(await screen.findByRole('heading', { name: 'My Croquis' })).toBeInTheDocument()
    expect(await screen.findByText('Croquis A')).toBeInTheDocument()
    expect(screen.getByText('Croquis B')).toBeInTheDocument()
    expect(screen.getByText('In Studio')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use Croquis B in Studio' }))
    expect(onUse).toHaveBeenCalledWith('croquis-b', 2)
  })

  it('opens create wizard and pins accepted croquis into Studio', async () => {
    const onUse = vi.fn()
    render(<MyCroquisScreen onBackToStudio={() => undefined} onUseInStudio={onUse} />)
    await screen.findByText('Croquis A')
    fireEvent.click(screen.getByRole('button', { name: 'Create New Croquis' }))
    expect(screen.getByRole('dialog', { name: 'Create My Croquis wizard' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Accept new' }))
    expect(onUse).toHaveBeenCalledWith('new-croquis', 1)
  })

  it('confirms delete and warns when croquis is pinned in Studio', async () => {
    render(
      <MyCroquisScreen
        onBackToStudio={() => undefined}
        onUseInStudio={() => undefined}
        activeStudioPinId="croquis-a"
      />,
    )
    await screen.findByText('Croquis A')
    fireEvent.click(screen.getByRole('button', { name: 'Delete Croquis A' }))
    expect(screen.getByRole('heading', { name: 'Delete personal croquis?' })).toBeInTheDocument()
    expect(
      screen.getByText(/Studio currently uses this croquis/i),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
    await waitFor(() => expect(mocks.erasePersonalCroquis).toHaveBeenCalledWith('croquis-a'))
  })
})
