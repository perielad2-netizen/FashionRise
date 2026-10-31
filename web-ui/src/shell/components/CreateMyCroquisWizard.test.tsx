/**
 * Offline Stage B wizard harness — mocked Stage A JSON only.
 * Never hits a provider; not a production mock generate path.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PersonalCroquisRead } from '@/services/personalCroquisApi'

const attestAdults = vi.fn()
const acknowledgeStorageConsent = vi.fn()
const uploadPersonalCroquisPhoto = vi.fn()
const listPersonalCroquis = vi.fn()

vi.mock('@/services/personalCroquisApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/personalCroquisApi')>(
    '@/services/personalCroquisApi',
  )
  return {
    ...actual,
    attestAdults: (...args: unknown[]) => attestAdults(...args),
    acknowledgeStorageConsent: (...args: unknown[]) => acknowledgeStorageConsent(...args),
    uploadPersonalCroquisPhoto: (...args: unknown[]) => uploadPersonalCroquisPhoto(...args),
    listPersonalCroquis: (...args: unknown[]) => listPersonalCroquis(...args),
  }
})

vi.mock('@/lib/personalCroquisNotices', async () => {
  const actual = await vi.importActual<typeof import('@/lib/personalCroquisNotices')>(
    '@/lib/personalCroquisNotices',
  )
  return {
    ...actual,
    croquisNoticesAuthorized: () => true,
    approvedCroquisNoticeText: (purpose: 'adults' | 'storage' | 'ai') =>
      purpose === 'adults'
        ? 'SYNTHETIC_TEST_ADULTS_NOTICE_V1'
        : purpose === 'storage'
          ? 'SYNTHETIC_TEST_STORAGE_NOTICE_V1'
          : 'SYNTHETIC_TEST_AI_NOTICE_V1',
  }
})

const libraryRow: PersonalCroquisRead = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  display_name: 'Accepted subject',
  status: 'ready',
  source_asset_id: null,
  storage_consent_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  adults_attestation_at: '2026-10-31T12:00:00+00:00',
  archived: false,
  erased: false,
  created_at: '2026-10-31T12:00:00+00:00',
  updated_at: '2026-10-31T12:05:00+00:00',
  latest_accepted_version: {
    version: 1,
    status: 'accepted',
    generated_asset_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    geometry_profile: 'fit_contain_768x1024_v1',
    accepted_at: '2026-10-31T12:05:00+00:00',
  },
}

describe('CreateMyCroquisWizard offline harness', () => {
  beforeEach(() => {
    attestAdults.mockResolvedValue({
      id: 'att-1',
      purpose: 'adults_beta',
      consent_version: 'adults-beta-2026-10-30-draft',
      adults_attested: true,
      created_at: '2026-10-31T12:00:00+00:00',
    })
    acknowledgeStorageConsent.mockResolvedValue({
      id: 'consent-1',
      purpose: 'croquis_storage',
      consent_version: 'storage-2026-10-30-draft',
      adults_attested: true,
      created_at: '2026-10-31T12:00:00+00:00',
    })
    listPersonalCroquis.mockResolvedValue([libraryRow])
    uploadPersonalCroquisPhoto.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('keeps preview local until storage consent; does not upload early', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    render(<CreateMyCroquisWizard open onClose={() => undefined} onPinAccepted={() => undefined} />)

    expect(screen.getByText(/SYNTHETIC_TEST_ADULTS_NOTICE_V1/)).toBeTruthy()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(attestAdults).toHaveBeenCalled())

    expect(uploadPersonalCroquisPhoto).not.toHaveBeenCalled()
    expect(screen.getByText(/Preview stays on this device/i)).toBeTruthy()

    const file = new File([new Uint8Array([1, 2, 3])], 'pose.png', { type: 'image/png' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    expect(uploadPersonalCroquisPhoto).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Continue to storage consent/i }))
    expect(screen.getByText(/SYNTHETIC_TEST_STORAGE_NOTICE_V1/)).toBeTruthy()
    expect(uploadPersonalCroquisPhoto).not.toHaveBeenCalled()
  })

  it('pins from library using latest_accepted_version (Stage A field name)', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    const onPin = vi.fn()
    const onClose = vi.fn()
    render(<CreateMyCroquisWizard open onClose={onClose} onPinAccepted={onPin} />)

    fireEvent.click(screen.getByRole('button', { name: /My Croquis library/i }))
    await waitFor(() => expect(listPersonalCroquis).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /Accepted subject · v1/i }))
    expect(onPin).toHaveBeenCalledWith(libraryRow.id, 1)
    expect(onClose).toHaveBeenCalled()
  })

  it('surfaces upload-disabled 403 without inventing a generated pin', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    const { ApiError } = await import('@/services/api/client')
    uploadPersonalCroquisPhoto.mockRejectedValue(
      new ApiError('Create My Croquis upload is not enabled.', 403, null),
    )
    const onPin = vi.fn()
    render(<CreateMyCroquisWizard open onClose={() => undefined} onPinAccepted={onPin} />)

    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(attestAdults).toHaveBeenCalled())

    const file = new File([new Uint8Array([1, 2, 3])], 'pose.png', { type: 'image/png' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /Continue to storage consent/i }))
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(acknowledgeStorageConsent).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /Upload privately/i }))
    await waitFor(() => expect(uploadPersonalCroquisPhoto).toHaveBeenCalled())
    expect(await screen.findByRole('alert')).toHaveTextContent(/not enabled/i)
    expect(onPin).not.toHaveBeenCalled()
  })
})
