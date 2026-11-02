import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from '@/services/api/client'
import {
  enqueuePersonalTryOn,
  fetchPersonalTryOnPreflight,
  prepareFashnGarmentReference,
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
      designHints: ['pink checkerboard print', 'upper-plane ink present'],
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
          provider: 'openai',
          design_hints: ['pink checkerboard print', 'upper-plane ink present'],
        }),
      }),
    )
    const path = apiMock.mock.calls[0]?.[0]
    expect(path).not.toContain('sketch/polish')
  })

  it('prepares FASHN garment reference offline and enqueues with fashn provider', async () => {
    apiMock.mockResolvedValueOnce({
      layout: 'two_piece',
      fashn_calls: 2,
      estimate_cents: 16,
      realism_estimate_cents: 16,
      combined_estimate_cents: 32,
      prefer_local_product: false,
      quality_ok: true,
      garment_fingerprint: 'abc',
      composite_preview_base64: 'data:image/png;base64,AAAA',
      pieces: [
        { category: 'tops', image_base64: 'data:image/png;base64,TOP', bbox: [0, 0, 1, 1], opaque_pixels: 10 },
        { category: 'bottoms', image_base64: 'data:image/png;base64,BOT', bbox: [0, 0, 1, 1], opaque_pixels: 10 },
      ],
      notes: 'two',
      consent_version: 'try-on-fashn-preview-v1',
      notice_text: 'fashn notice',
      notice_hash: 'hash',
      provider: 'fashn',
      configured: true,
      live_http: true,
      openai_live_http: true,
    })
    const prep = await prepareFashnGarmentReference('data:image/png;base64,AAAA')
    expect(apiMock).toHaveBeenCalledWith('/ai/personal-try-on/fashn/prepare', {
      method: 'POST',
      body: { garment_image_base64: 'data:image/png;base64,AAAA' },
      signal: undefined,
    })
    expect(prep.layout).toBe('two_piece')
    expect(prep.prefer_local_product).toBe(false)
    expect(prep.combined_estimate_cents).toBe(32)

    apiMock.mockResolvedValueOnce({ id: 'job-fashn', job_type: 'personal_try_on', status: 'queued' })
    await enqueuePersonalTryOn({
      croquisId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      croquisVersion: 2,
      garmentImageBase64: 'data:image/png;base64,AAAA',
      idempotencyKey: 'try_on:fashn:key-1',
      sourceRevision: 7,
      contentFingerprint: 'fp-1',
      consentAcknowledged: true,
      consentVersion: 'try-on-fashn-preview-v1',
      provider: 'fashn',
      approvedGarmentPieces: [
        { category: 'tops', image_base64: 'data:image/png;base64,TOPR' },
        { category: 'bottoms', image_base64: 'data:image/png;base64,BOTR' },
      ],
      garmentRealismJobId: 'bbbbbbbb-bbbb-4ccc-8ddd-eeeeeeeeeeee',
    })
    expect(apiMock).toHaveBeenLastCalledWith(
      '/ai/personal-try-on',
      expect.objectContaining({
        body: expect.objectContaining({
          provider: 'fashn',
          consent_version: 'try-on-fashn-preview-v1',
          approved_garment_pieces: expect.any(Array),
        }),
      }),
    )
  })
})
