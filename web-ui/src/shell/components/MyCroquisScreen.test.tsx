import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MyCroquisScreen } from '@/shell/components/MyCroquisScreen'

const mocks = vi.hoisted(() => ({
  listPersonalCroquis: vi.fn(),
  erasePersonalCroquis: vi.fn(),
  fetchCroquisAssetBlob: vi.fn(),
  acceptPersonalCroquisVersion: vi.fn(),
  rejectPersonalCroquisVersion: vi.fn(),
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
    acceptPersonalCroquisVersion: mocks.acceptPersonalCroquisVersion,
    rejectPersonalCroquisVersion: mocks.rejectPersonalCroquisVersion,
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
    <div role="dialog" aria-label="Create Model wizard">
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
    latest_open_version: null,
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
    latest_open_version: null,
  },
]

describe('MyCroquisScreen', () => {
  beforeEach(() => {
    mocks.isMyCroquisUiEnabled.mockReturnValue(true)
    mocks.listPersonalCroquis.mockReset()
    mocks.erasePersonalCroquis.mockReset()
    mocks.fetchCroquisAssetBlob.mockReset()
    mocks.acceptPersonalCroquisVersion.mockReset()
    mocks.rejectPersonalCroquisVersion.mockReset()
    mocks.listPersonalCroquis.mockResolvedValue(sampleRows)
    mocks.fetchCroquisAssetBlob.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    mocks.erasePersonalCroquis.mockResolvedValue({ ...sampleRows[0], erased: true })
    mocks.acceptPersonalCroquisVersion.mockResolvedValue({
      id: 'ver-pending',
      croquis_id: 'croquis-pending',
      version: 1,
      status: 'accepted',
      generated_asset_id: 'asset-pending',
      geometry_profile: null,
      prompt_version: null,
      created_at: '2026-11-02T00:00:00Z',
      accepted_at: '2026-11-02T00:01:00Z',
    })
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
    expect(await screen.findByRole('heading', { name: 'My Models' })).toBeInTheDocument()
    expect(await screen.findByText('Croquis A')).toBeInTheDocument()
    expect(screen.getByText('Croquis B')).toBeInTheDocument()
    expect(screen.getByText('In Studio')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use Croquis B in Studio' }))
    expect(onUse).toHaveBeenCalledWith('croquis-b', 2)
  })

  it('opens create wizard and returns to gallery after accept (no auto Studio pin)', async () => {
    const onUse = vi.fn()
    mocks.listPersonalCroquis
      .mockResolvedValueOnce(sampleRows)
      .mockResolvedValueOnce([
        ...sampleRows,
        {
          id: 'new-croquis',
          display_name: 'New croquis',
          status: 'ready',
          source_asset_id: 'src-n',
          storage_consent_id: 'consent-n',
          adults_attestation_at: '2026-11-02T00:00:00Z',
          archived: false,
          erased: false,
          created_at: '2026-11-02T00:00:00Z',
          updated_at: '2026-11-02T00:00:00Z',
          latest_accepted_version: {
            version: 1,
            status: 'accepted',
            generated_asset_id: 'asset-n',
            geometry_profile: null,
            accepted_at: '2026-11-02T00:00:00Z',
          },
          latest_open_version: null,
        },
      ])
    render(<MyCroquisScreen onBackToStudio={() => undefined} onUseInStudio={onUse} />)
    await screen.findByText('Croquis A')
    fireEvent.click(screen.getByRole('button', { name: 'Create Model' }))
    expect(screen.getByRole('dialog', { name: /Create Model/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Accept new' }))
    expect(onUse).not.toHaveBeenCalled()
    expect(await screen.findByText(/New model ready/i)).toBeInTheDocument()
    expect(await screen.findByText('New croquis')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'My Models' })).toBeInTheDocument()
  })

  it('retries delete after an API error', async () => {
    const { ApiError } = await import('@/services/api/client')
    mocks.erasePersonalCroquis
      .mockRejectedValueOnce(new ApiError('temporary failure', 500, null))
      .mockResolvedValueOnce({ ...sampleRows[0], erased: true })
    render(
      <MyCroquisScreen
        onBackToStudio={() => undefined}
        onUseInStudio={() => undefined}
        activeStudioPinId={null}
      />,
    )
    await screen.findByText('Croquis A')
    fireEvent.click(screen.getByRole('button', { name: 'Delete Croquis A' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
    expect(await screen.findByRole('heading', { name: 'Could not delete model' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry delete' }))
    await waitFor(() => expect(mocks.erasePersonalCroquis).toHaveBeenCalledTimes(2))
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Could not delete model' })).not.toBeInTheDocument(),
    )
  })

  it('shows awaiting_review models with Accept after Refresh', async () => {
    mocks.listPersonalCroquis.mockResolvedValue([
      {
        id: 'croquis-pending',
        display_name: 'Partner upload',
        status: 'ready',
        source_asset_id: 'src-p',
        storage_consent_id: 'consent-p',
        adults_attestation_at: '2026-11-02T00:00:00Z',
        archived: false,
        erased: false,
        created_at: '2026-11-02T00:00:00Z',
        updated_at: '2026-11-02T00:00:00Z',
        latest_accepted_version: null,
        latest_open_version: {
          version: 1,
          status: 'awaiting_review',
          generated_asset_id: 'asset-pending',
          geometry_profile: null,
          accepted_at: null,
        },
      },
    ])
    render(<MyCroquisScreen onBackToStudio={() => undefined} onUseInStudio={() => undefined} />)
    expect(await screen.findByText('Partner upload')).toBeInTheDocument()
    expect(screen.getByText('Ready to review')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Accept Partner upload' }))
    await waitFor(() =>
      expect(mocks.acceptPersonalCroquisVersion).toHaveBeenCalledWith('croquis-pending', 1),
    )
  })

  it('shows Refresh spinner label while loading', async () => {
    let resolveList: (value: typeof sampleRows) => void = () => undefined
    mocks.listPersonalCroquis.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveList = resolve
        }),
    )
    render(<MyCroquisScreen onBackToStudio={() => undefined} onUseInStudio={() => undefined} />)
    expect(screen.getByRole('button', { name: 'Refresh My Models' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByText('Refreshing…')).toBeInTheDocument()
    resolveList(sampleRows)
    expect(await screen.findByText('Croquis A')).toBeInTheDocument()
    expect(screen.getByText('Refresh')).toBeInTheDocument()
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
    expect(screen.getByRole('heading', { name: 'Delete personal model?' })).toBeInTheDocument()
    expect(
      screen.getByText(/Studio currently uses this model/i),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
    await waitFor(() => expect(mocks.erasePersonalCroquis).toHaveBeenCalledWith('croquis-a'))
  })
})
