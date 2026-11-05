import { describe, expect, it, vi, afterEach } from 'vitest'
import * as client from '@/services/api/client'
import { enqueueSketchPolishDual, toApiContentFingerprint } from '@/services/ai/magicApi'

describe('toApiContentFingerprint', () => {
  it('passes short fingerprints through', async () => {
    await expect(toApiContentFingerprint('fp-test')).resolves.toBe('fp-test')
    await expect(toApiContentFingerprint(null)).resolves.toBeNull()
  })

  it('hashes fingerprints longer than 128 chars to sha256 hex', async () => {
    const long = `{"schema":"fashionrise.studio.draft.v2","strokes":[${'x'.repeat(200)}]}`
    expect(long.length).toBeGreaterThan(128)
    const digest = await toApiContentFingerprint(long)
    expect(digest).toMatch(/^[a-f0-9]{64}$/)
    expect(digest).toBe(await toApiContentFingerprint(long))
  })
})

describe('enqueueSketchPolishDual content_fingerprint wire form', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends digested fingerprint when draft JSON exceeds 128 chars', async () => {
    const long = `{"activeSide":"back","strokes":[${'1'.repeat(300)}]}`
    const expected = await toApiContentFingerprint(long)
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValue({
      magic_operation_id: '11111111-1111-1111-1111-111111111111',
      front_job: { id: 'jf' },
      back_job: { id: 'jb' },
    } as never)

    await enqueueSketchPolishDual({
      magic_operation_id: '11111111-1111-1111-1111-111111111111',
      shared_garment_spec: { notes: 'n', colors: ['#000'], main_colors: ['#000'] },
      content_fingerprint: long,
      front: { image_base64: 'data:image/png;base64,aa', idempotency_key: 'op:front' },
      back: { image_base64: 'data:image/png;base64,bb', idempotency_key: 'op:back' },
    })

    const body = spy.mock.calls[0]?.[1]?.body as { content_fingerprint?: string }
    expect(body.content_fingerprint).toBe(expected)
    expect(body.content_fingerprint?.length).toBeLessThanOrEqual(128)
  })
})
