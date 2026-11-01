import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/personalCroquisApi', () => ({
  fetchCroquisAssetBlob: vi.fn(async (assetId: string) => new Blob([`png:${assetId}`])),
}))

describe('personalCroquisCache identity binding', () => {
  afterEach(async () => {
    const { clearPersonalCroquisCache } = await import('./personalCroquisCache')
    clearPersonalCroquisCache()
    vi.clearAllMocks()
  })

  it('keeps distinct object URLs per (user,croquis,version,asset)', async () => {
    const { loadPersonalCroquisObjectUrl, peekPersonalCroquisObjectUrl } = await import(
      './personalCroquisCache'
    )
    const a = {
      userId: 'u1',
      croquisId: 'c1',
      version: 1,
      assetId: 'asset-a',
    }
    const b = { ...a, version: 2, assetId: 'asset-b' }
    const urlA = await loadPersonalCroquisObjectUrl(a)
    const urlB = await loadPersonalCroquisObjectUrl(b)
    expect(urlA).not.toBe(urlB)
    expect(peekPersonalCroquisObjectUrl(a)).toBe(urlA)
    expect(peekPersonalCroquisObjectUrl(b)).toBe(urlB)
    expect(peekPersonalCroquisObjectUrl({ ...a, version: 2, assetId: 'asset-a' })).toBeNull()
  })

  it('underlayMatchesPin rejects A→B identity mismatch (stale URL safety)', async () => {
    const { underlayMatchesPin } = await import('./personalCroquisCache')
    const identityA = {
      userId: 'u1',
      croquisId: 'c1',
      version: 1,
      assetId: 'asset-a',
    }
    expect(
      underlayMatchesPin(identityA, { userId: 'u1', croquisId: 'c1', version: 1 }),
    ).toBe(true)
    expect(
      underlayMatchesPin(identityA, { userId: 'u1', croquisId: 'c1', version: 2 }),
    ).toBe(false)
    expect(
      underlayMatchesPin(identityA, { userId: 'u2', croquisId: 'c1', version: 1 }),
    ).toBe(false)
    expect(underlayMatchesPin(null, { userId: 'u1', croquisId: 'c1', version: 1 })).toBe(false)
  })

  it('clears cache on user switch', async () => {
    const {
      bindPersonalCroquisCacheToUser,
      loadPersonalCroquisObjectUrl,
      peekPersonalCroquisObjectUrl,
    } = await import('./personalCroquisCache')
    const id = { userId: 'u1', croquisId: 'c1', version: 1, assetId: 'asset-a' }
    const url = await loadPersonalCroquisObjectUrl(id)
    expect(peekPersonalCroquisObjectUrl(id)).toBe(url)
    bindPersonalCroquisCacheToUser('u2')
    expect(peekPersonalCroquisObjectUrl(id)).toBeNull()
  })
})
