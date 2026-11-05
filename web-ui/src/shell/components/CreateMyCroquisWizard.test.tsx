/**
 * Offline Create My Croquis harness — one-checkbox Upload & Generate flow.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PersonalCroquisRead } from '@/services/personalCroquisApi'

const attestAdults = vi.fn()
const acknowledgeStorageConsent = vi.fn()
const acknowledgeAiConsent = vi.fn()
const uploadPersonalCroquisPhoto = vi.fn()
const listPersonalCroquis = vi.fn()
const generatePersonalCroquisVersion = vi.fn()
const getPersonalCroquisVersion = vi.fn()
const acceptPersonalCroquisVersion = vi.fn()
const rejectPersonalCroquisVersion = vi.fn()
const fetchCroquisAssetBlob = vi.fn()

vi.mock('@/services/personalCroquisApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/personalCroquisApi')>(
    '@/services/personalCroquisApi',
  )
  return {
    ...actual,
    attestAdults: (...args: unknown[]) => attestAdults(...args),
    acknowledgeStorageConsent: (...args: unknown[]) => acknowledgeStorageConsent(...args),
    acknowledgeAiConsent: (...args: unknown[]) => acknowledgeAiConsent(...args),
    uploadPersonalCroquisPhoto: (...args: unknown[]) => uploadPersonalCroquisPhoto(...args),
    listPersonalCroquis: (...args: unknown[]) => listPersonalCroquis(...args),
    generatePersonalCroquisVersion: (...args: unknown[]) => generatePersonalCroquisVersion(...args),
    getPersonalCroquisVersion: (...args: unknown[]) => getPersonalCroquisVersion(...args),
    acceptPersonalCroquisVersion: (...args: unknown[]) => acceptPersonalCroquisVersion(...args),
    rejectPersonalCroquisVersion: (...args: unknown[]) => rejectPersonalCroquisVersion(...args),
    fetchCroquisAssetBlob: (...args: unknown[]) => fetchCroquisAssetBlob(...args),
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

async function selectPhotoAndAgree() {
  const file = new File([new Uint8Array([1, 2, 3])], 'pose.png', { type: 'image/png' })
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
  fireEvent.click(screen.getByRole('checkbox'))
}

describe('CreateMyCroquisWizard offline harness', () => {
  beforeEach(() => {
    attestAdults.mockResolvedValue({
      id: 'att-1',
      purpose: 'adults_beta',
      consent_version: 'adults-beta-2026-11-01',
      adults_attested: true,
      created_at: '2026-10-31T12:00:00+00:00',
    })
    acknowledgeStorageConsent.mockResolvedValue({
      id: 'consent-1',
      purpose: 'croquis_storage',
      consent_version: 'storage-2026-11-01',
      adults_attested: true,
      created_at: '2026-10-31T12:00:00+00:00',
    })
    acknowledgeAiConsent.mockResolvedValue({
      id: 'ai-consent-1',
      purpose: 'croquis_ai_provider',
      consent_version: 'ai-provider-2026-11-01',
      adults_attested: true,
      created_at: '2026-10-31T12:00:00+00:00',
    })
    listPersonalCroquis.mockResolvedValue([libraryRow])
    uploadPersonalCroquisPhoto.mockResolvedValue({
      ...libraryRow,
      id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      latest_accepted_version: null,
      source_asset_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    })
    generatePersonalCroquisVersion.mockResolvedValue({
      id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
      croquis_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      version: 1,
      status: 'generating',
      generated_asset_id: null,
      geometry_profile: 'fit_contain_768x1024_v1',
      prompt_version: null,
      created_at: '2026-10-31T12:00:00+00:00',
      accepted_at: null,
    })
    getPersonalCroquisVersion.mockResolvedValue({
      id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
      croquis_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      version: 1,
      status: 'awaiting_review',
      generated_asset_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      geometry_profile: 'fit_contain_768x1024_v1',
      prompt_version: 'croquis-lineart-v2',
      created_at: '2026-10-31T12:00:00+00:00',
      accepted_at: null,
    })
    fetchCroquisAssetBlob.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }))
    acceptPersonalCroquisVersion.mockResolvedValue({
      id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
      croquis_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      version: 1,
      status: 'accepted',
      generated_asset_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      geometry_profile: 'fit_contain_768x1024_v1',
      prompt_version: 'croquis-lineart-v2',
      created_at: '2026-10-31T12:00:00+00:00',
      accepted_at: '2026-10-31T12:06:00+00:00',
    })
    rejectPersonalCroquisVersion.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('keeps preview local until agreement; does not upload early', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    render(<CreateMyCroquisWizard open onClose={() => undefined} onPinAccepted={() => undefined} />)

    expect(screen.getByText(/Select a fully clothed fashion pose photo/i)).toBeTruthy()
    expect(screen.getByText(/children.?s clothing/i)).toBeTruthy()
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(uploadPersonalCroquisPhoto).not.toHaveBeenCalled()

    const file = new File([new Uint8Array([1, 2, 3])], 'pose.png', { type: 'image/png' })
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [file] },
    })
    expect(uploadPersonalCroquisPhoto).not.toHaveBeenCalled()
    expect(screen.getByRole('checkbox')).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /Upload & Generate/i })).toBeDisabled()
  })

  it('pins from library using latest_accepted_version', async () => {
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

    await selectPhotoAndAgree()
    fireEvent.click(screen.getByRole('button', { name: /Upload & Generate/i }))
    await waitFor(() => expect(attestAdults).toHaveBeenCalled())
    await waitFor(() => expect(acknowledgeStorageConsent).toHaveBeenCalled())
    await waitFor(() => expect(uploadPersonalCroquisPhoto).toHaveBeenCalled())
    expect(await screen.findByRole('alert')).toHaveTextContent(/not enabled/i)
    expect(onPin).not.toHaveBeenCalled()
    expect(acknowledgeAiConsent).not.toHaveBeenCalled()
    expect(generatePersonalCroquisVersion).not.toHaveBeenCalled()
  })

  it('surfaces bare 413 upload failures above Upload & Generate', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    const { ApiError } = await import('@/services/api/client')
    uploadPersonalCroquisPhoto.mockRejectedValue(
      new ApiError(
        'That photo is too large to upload. Try a smaller photo, or wait while FashionRise compresses it and try again.',
        413,
        null,
      ),
    )
    render(<CreateMyCroquisWizard open onClose={() => undefined} onPinAccepted={() => undefined} />)
    await selectPhotoAndAgree()
    fireEvent.click(screen.getByRole('button', { name: /Upload & Generate/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/too large to upload/i)
    expect(generatePersonalCroquisVersion).not.toHaveBeenCalled()
  })

  it('one checkbox records distinct consents then accepts generated preview', async () => {
    const { CreateMyCroquisWizard } = await import('./CreateMyCroquisWizard')
    const onPin = vi.fn()
    const onClose = vi.fn()
    render(<CreateMyCroquisWizard open onClose={onClose} onPinAccepted={onPin} />)

    expect(screen.getAllByRole('checkbox')).toHaveLength(1)
    await selectPhotoAndAgree()
    fireEvent.click(screen.getByRole('button', { name: /Upload & Generate/i }))

    await waitFor(() => expect(attestAdults).toHaveBeenCalled())
    await waitFor(() => expect(acknowledgeStorageConsent).toHaveBeenCalled())
    await waitFor(() => expect(uploadPersonalCroquisPhoto).toHaveBeenCalledWith(
      expect.any(File),
      'consent-1',
    ))
    await waitFor(() =>
      expect(acknowledgeAiConsent).toHaveBeenCalledWith(
        expect.objectContaining({ croquis_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd' }),
      ),
    )
    await waitFor(() => expect(generatePersonalCroquisVersion).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByAltText(/Generated croquis preview/i)).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /Accept & use in Studio/i }))
    await waitFor(() => expect(acceptPersonalCroquisVersion).toHaveBeenCalled())
    expect(onPin).toHaveBeenCalledWith('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 1)
    expect(onClose).toHaveBeenCalled()
  })
})
