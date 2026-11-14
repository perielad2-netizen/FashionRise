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
  listSavedResults: vi.fn(async () => []),
  saveFittingResult: vi.fn(async () => undefined),
  deleteSavedResult: vi.fn(async () => undefined),
  newOutfitPieceId: () => 'piece_test',
  fileToFittingRoomDataUrl: async () => ({
    dataUrl: 'data:image/png;base64,aaa',
    mimeType: 'image/png',
  }),
}))

vi.mock('@/services/ai/pollAiJob', () => ({
  pollAiJobUntilSettled: vi.fn(),
}))

vi.mock('@/services/ai/magicApi', () => ({
  fetchJobImageBlob: vi.fn(),
}))

vi.mock('@/lib/sharePromo', () => ({
  requestShare: vi.fn(async () => 'needs-fallback'),
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
  })

  it('renders gated-off copy when UI flag is false', () => {
    mocks.isFittingRoomUiEnabled.mockReturnValue(false)
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    expect(screen.getByText(/not enabled in this build/i)).toBeInTheDocument()
  })

  it('shows flat 20 Stars cost and try-on disabled until consent + assets', async () => {
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    expect(screen.getByTestId('fitting-room-screen')).toBeInTheDocument()
    expect(screen.getByTestId('fitting-room-stars-cost')).toHaveTextContent(/20 Stars/i)
    expect(screen.getAllByText(/not a fit guarantee/i).length).toBeGreaterThan(0)
    const tryBtn = screen.getByTestId('fitting-room-try-on')
    expect(tryBtn).toBeDisabled()
    expect(tryBtn).toHaveTextContent(/−20 Stars/i)
    await userEvent.click(screen.getByRole('checkbox', { name: /Preview only/i }))
    expect(tryBtn).toBeDisabled()
  })
})
