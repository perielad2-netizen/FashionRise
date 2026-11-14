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
    })
    mocks.readFittingRoomAsset.mockResolvedValue(null)
  })

  it('renders gated-off copy when UI flag is false', () => {
    mocks.isFittingRoomUiEnabled.mockReturnValue(false)
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    expect(screen.getByText(/not enabled in this build/i)).toBeInTheDocument()
  })

  it('shows disclaimer and try-on disabled until consent + assets', async () => {
    render(<FittingRoomScreen userId="u1" onBackToStudio={() => undefined} />)
    await waitFor(() => expect(mocks.fetchFittingRoomPreflight).toHaveBeenCalled())
    expect(screen.getByTestId('fitting-room-screen')).toBeInTheDocument()
    expect(screen.getAllByText(/not a fit guarantee/i).length).toBeGreaterThan(0)
    const tryBtn = screen.getByTestId('fitting-room-try-on')
    expect(tryBtn).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: /Preview only/i }))
    expect(tryBtn).toBeDisabled()
  })
})
