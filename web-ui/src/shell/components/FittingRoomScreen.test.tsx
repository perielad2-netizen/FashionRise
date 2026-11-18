import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FittingRoomScreen } from './FittingRoomScreen'

const mocks = vi.hoisted(() => ({
  isFittingRoomUiEnabled: vi.fn(() => true),
  fetchFittingRoomPreflight: vi.fn(),
  enqueueFittingRoomTryOn: vi.fn(),
  readFittingRoomAsset: vi.fn(async () => null),
  writeFittingRoomAsset: vi.fn(async () => undefined),
  deleteFittingRoomAsset: vi.fn(async () => undefined),
  listSavedResults: vi.fn(async () => []),
  saveFittingResult: vi.fn(async () => undefined),
  pollAiJobUntilSettled: vi.fn(),
  fetchJobImageBlob: vi.fn(),
}))

vi.mock('@/config/fittingRoomUi', () => ({
  isFittingRoomUiEnabled: () => mocks.isFittingRoomUiEnabled(),
}))

vi.mock('@/services/ai/fittingRoomApi', () => ({
  fetchFittingRoomPreflight: (...args: unknown[]) => mocks.fetchFittingRoomPreflight(...args),
  enqueueFittingRoomTryOn: (...args: unknown[]) => mocks.enqueueFittingRoomTryOn(...args),
}))

vi.mock('@/lib/fittingRoomStore', () => ({
  readFittingRoomAsset: (...args: unknown[]) => mocks.readFittingRoomAsset(...args),
  writeFittingRoomAsset: (...args: unknown[]) => mocks.writeFittingRoomAsset(...args),
  deleteFittingRoomAsset: (...args: unknown[]) => mocks.deleteFittingRoomAsset(...args),
  readOutfitSession: vi.fn(async () => null),
  writeOutfitSession: vi.fn(async () => undefined),
  clearOutfitSession: vi.fn(async () => undefined),
  listSavedResults: (...args: unknown[]) => mocks.listSavedResults(...args),
  saveFittingResult: (...args: unknown[]) => mocks.saveFittingResult(...args),
  deleteSavedResult: vi.fn(async () => undefined),
  newOutfitPieceId: () => 'piece_test',
  consumeFittingRoomPlantedNotice: () => null,
  fileToFittingRoomDataUrl: async () => ({
    dataUrl: 'data:image/png;base64,aaa',
    mimeType: 'image/png',
  }),
}))

vi.mock('@/services/ai/pollAiJob', () => ({
  pollAiJobUntilSettled: (...args: unknown[]) => mocks.pollAiJobUntilSettled(...args),
}))

vi.mock('@/services/ai/magicApi', () => ({
  fetchJobImageBlob: (...args: unknown[]) => mocks.fetchJobImageBlob(...args),
}))

vi.mock('@/lib/sharePromo', () => ({
  requestShare: vi.fn(async () => 'needs-fallback'),
}))

vi.mock('@/hooks/useAiStarsWallet', () => ({
  useAiStarsWallet: () => ({
    balance: null,
    unlimited: true,
    costs: { magic: 10, croquis: 10, pdf: 50, fabric: 5, fitting_room: 20 },
    loaded: true,
    reload: vi.fn(),
    refreshUser: vi.fn(),
  }),
}))

vi.mock('@/shell/components/StarsShopModal', () => ({
  StarsShopModal: () => null,
}))

describe('FittingRoomScreen', () => {
  beforeEach(() => {
    mocks.isFittingRoomUiEnabled.mockReturnValue(true)
    mocks.fetchFittingRoomPreflight.mockResolvedValue({
      enabled: true,
      live_http: true,
      consent_version: 'fitting-room-preview-v1',
      notice_text: 'Preview only — not a fit guarantee.',
      prompt_version: 'v-test',
      supported_categories: ['auto', 'tops', 'dresses'],
      preview_disclaimer: 'Concept preview only — not a fit guarantee.',
      ai_gate: true,
      stars_cost: 20,
      stars_cost_note:
        '20 Stars per successful Fitting Room preview — flat rate whether the clothing image shows one garment or several.',
      max_outfit_pieces: 4,
      conflicting_category_sets: [['one-pieces', 'tops']],
    })
    mocks.readFittingRoomAsset.mockResolvedValue(null)
    mocks.listSavedResults.mockResolvedValue([])
    mocks.saveFittingResult.mockResolvedValue(undefined)
    mocks.enqueueFittingRoomTryOn.mockReset()
    mocks.pollAiJobUntilSettled.mockReset()
    mocks.fetchJobImageBlob.mockReset()
  })

  it('renders gated-off copy when UI flag is false', () => {
    mocks.isFittingRoomUiEnabled.mockReturnValue(false)
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    expect(screen.getByText(/not enabled in this build/i)).toBeInTheDocument()
  })

  it('Try on label has no Stars cost; stays disabled until consent + assets', async () => {
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    expect(screen.getByTestId('fitting-room-screen')).toBeInTheDocument()
    expect(screen.queryByTestId('fitting-room-stars-cost')).not.toBeInTheDocument()
    expect(screen.queryByText(/on success/i)).not.toBeInTheDocument()
    const tryBtn = screen.getByTestId('fitting-room-try-on')
    expect(tryBtn).toBeDisabled()
    expect(tryBtn).toHaveTextContent(/^Try on$/i)
    expect(tryBtn).not.toHaveTextContent(/Stars/i)
    await userEvent.click(screen.getByRole('checkbox', { name: /Preview only|visual concept preview/i }))
    expect(tryBtn).toBeDisabled()
  })

  it('offers gallery and camera pickers for person photo and clothing', async () => {
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    expect(screen.getByTestId('fitting-room-person-gallery')).toHaveTextContent(/Choose photo/i)
    expect(screen.getByTestId('fitting-room-person-take')).toHaveTextContent(/Take photo/i)
    expect(screen.getByTestId('fitting-room-garment-gallery')).toHaveTextContent(/Add clothing/i)
    expect(screen.getByTestId('fitting-room-garment-take')).toHaveTextContent(/Take clothing photo/i)
    expect(screen.getByTestId('fitting-room-person-camera')).toHaveAttribute('capture', 'environment')
    expect(screen.getByTestId('fitting-room-garment-camera')).toHaveAttribute('capture', 'environment')
  })

  it('opens Stars confirm dialog before enqueueing try-on', async () => {
    mocks.readFittingRoomAsset.mockResolvedValue({
      key: 'u1:person',
      kind: 'person',
      userId: 'u1',
      dataUrl: 'data:image/png;base64,person',
      mimeType: 'image/png',
      updatedAt: new Date().toISOString(),
    })
    const { readOutfitSession } = await import('@/lib/fittingRoomStore')
    vi.mocked(readOutfitSession).mockResolvedValue({
      key: 'u1:outfit',
      userId: 'u1',
      pieces: [
        {
          id: 'piece_1',
          dataUrl: 'data:image/png;base64,garment',
          mimeType: 'image/png',
          category: 'tops',
          addedAt: new Date().toISOString(),
        },
      ],
      updatedAt: new Date().toISOString(),
    })

    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('checkbox', { name: /Preview only|visual concept preview/i }))
    const tryBtn = screen.getByTestId('fitting-room-try-on')
    await waitFor(() => expect(tryBtn).not.toBeDisabled())
    await userEvent.click(tryBtn)
    expect(await screen.findByRole('button', { name: /Approve −20/i })).toBeInTheDocument()
    expect(mocks.enqueueFittingRoomTryOn).not.toHaveBeenCalled()
  })

  it('shows wait modal, auto-saves, and opens results sheet', async () => {
    mocks.readFittingRoomAsset.mockResolvedValue({
      key: 'u1:person',
      kind: 'person',
      userId: 'u1',
      dataUrl: 'data:image/png;base64,person',
      mimeType: 'image/png',
      updatedAt: new Date().toISOString(),
    })
    const { readOutfitSession } = await import('@/lib/fittingRoomStore')
    vi.mocked(readOutfitSession).mockResolvedValue({
      key: 'u1:outfit',
      userId: 'u1',
      pieces: [
        {
          id: 'piece_1',
          dataUrl: 'data:image/png;base64,garment',
          mimeType: 'image/png',
          category: 'dresses',
          source: 'fashionrise_look',
          addedAt: new Date().toISOString(),
        },
      ],
      updatedAt: new Date().toISOString(),
    })

    let resolvePoll: ((value: unknown) => void) | null = null
    mocks.enqueueFittingRoomTryOn.mockResolvedValue({ id: 'job-fr-1' })
    mocks.pollAiJobUntilSettled.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePoll = resolve
        }),
    )
    mocks.fetchJobImageBlob.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }))
    mocks.listSavedResults.mockResolvedValue([
      {
        id: 'frsave_job-fr-1',
        userId: 'u1',
        jobId: 'job-fr-1',
        dataUrl: 'data:image/png;base64,saved',
        label: 'Outfit test',
        outfitCategories: ['dresses'],
        createdAt: new Date().toISOString(),
      },
    ])

    // FileReader for auto-save data URL
    class FakeFileReader {
      result: string | null = null
      onload: ((ev: ProgressEvent<FileReader>) => void) | null = null
      onerror: ((ev: ProgressEvent<FileReader>) => void) | null = null
      readAsDataURL() {
        this.result = 'data:image/png;base64,autosaved'
        this.onload?.({} as ProgressEvent<FileReader>)
      }
    }
    vi.stubGlobal('FileReader', FakeFileReader as unknown as typeof FileReader)

    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('checkbox', { name: /Preview only|visual concept preview/i }))
    const tryBtn = screen.getByTestId('fitting-room-try-on')
    await waitFor(() => expect(tryBtn).not.toBeDisabled())
    await userEvent.click(tryBtn)
    await userEvent.click(await screen.findByRole('button', { name: /Approve −20/i }))

    expect(await screen.findByTestId('fitting-room-wait-modal')).toBeInTheDocument()
    expect(screen.getByTestId('fitting-room-try-on')).toHaveTextContent(/^Try on$/i)

    resolvePoll?.({ id: 'job-fr-1', status: 'completed' })
    await waitFor(() => expect(mocks.saveFittingResult).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByTestId('fitting-room-wait-modal')).not.toBeInTheDocument())

    await userEvent.click(screen.getByTestId('fitting-room-results-open'))
    expect(await screen.findByTestId('fitting-room-results-modal')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Fitting Room results/i })).toBeInTheDocument()
  })
})
