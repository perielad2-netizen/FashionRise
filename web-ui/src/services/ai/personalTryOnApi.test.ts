import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from '@/services/api/client'
import {
  enqueuePersonalTryOn,
  fetchPersonalTryOnPreflight,
} from '@/services/ai/magicApi'

vi.mock('@/services/api/client', () => ({
  ApiError: class ApiError extends Error {
    status: number
    body: unknown
    constructor(message: string, status: number, body: unknown) {
      super(message)
      this.status = status
      this.body = body
    }
  },
  apiRequest: vi.fn(),
  getApiBaseUrl: () => 'http://test',
}))

const apiMock = vi.mocked(apiRequest)

describe('personal try-on API client', () => {
  beforeEach(() => {
    apiMock.mockReset()
  })

  it('loads preflight without billable work', async () => {
    apiMock.mockResolvedValue({
      enabled: true,
      live_http: false,
      consent_version: 'try-on-person-preview-v1',
      notice_text: 'notice',
      notice_hash: 'abc',
      prompt_version: 'try-on-person-v1',
      estimate_cents: 3,
      max_exposure_cents: 100,
    })
    const pre = await fetchPersonalTryOnPreflight()
    expect(apiMock).toHaveBeenCalledWith('/ai/personal-try-on/preflight', {
      method: 'GET',
      signal: undefined,
    })
    expect(pre.consent_version).toBe('try-on-person-preview-v1')
  })

  it('enqueues try-on with croquis binding and consent, not polish path', async () => {
    apiMock.mockResolvedValue({
      id: 'job-1',
      job_type: 'personal_try_on',
      status: 'queued',
    })
    await enqueuePersonalTryOn({
      croquisId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      croquisVersion: 2,
      garmentImageBase64: 'data:image/png;base64,AAAA',
      idempotencyKey: 'try_on:key-1',
      sourceRevision: 7,
      contentFingerprint: 'fp-1',
      consentAcknowledged: true,
      consentVersion: 'try-on-person-preview-v1',
    })
    expect(apiMock).toHaveBeenCalledWith(
      '/ai/personal-try-on',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({
          croquis_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
          croquis_version: 2,
          consent_acknowledged: true,
          consent_version: 'try-on-person-preview-v1',
          garment_image_base64: 'data:image/png;base64,AAAA',
          source_revision: 7,
          content_fingerprint: 'fp-1',
        }),
      }),
    )
    const path = apiMock.mock.calls[0]?.[0]
    expect(path).not.toContain('sketch/polish')
  })
})
