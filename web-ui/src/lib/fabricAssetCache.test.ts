import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'

const fetchFabricImageBlob = vi.fn()

vi.mock('@/services/fabricAssetsApi', () => ({
  fetchFabricImageBlob: (...args: unknown[]) => fetchFabricImageBlob(...args),
}))

function stubImageDecode() {
  vi.stubGlobal(
    'Image',
    class {
      width = 32
      height = 32
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_v: string) {
        queueMicrotask(() => this.onload?.())
      }
    },
  )
  const RealURL = globalThis.URL
  vi.stubGlobal(
    'URL',
    class extends RealURL {
      static createObjectURL = () => 'blob:fabric'
      static revokeObjectURL = vi.fn()
    },
  )
}

const sampleFill = (assetId: string): FillOp[] => [
  {
    id: 'f',
    contour: [0, 0, 10, 0, 10, 10, 0, 10],
    style: {
      kind: 'uploaded-fabric',
      assetId,
      scale: 1,
    },
    seedX: 1,
    seedY: 1,
  },
]

describe('fabricAssetCache', () => {
  afterEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('loads and caches fabric images; required mode fails closed', async () => {
    const png = new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' })
    fetchFabricImageBlob.mockResolvedValue(png)
    stubImageDecode()

    const cache = await import('@/lib/fabricAssetCache')
    cache.__resetFabricAssetCacheForTests()
    cache.bindFabricCacheToUser('user-a')

    const fills = sampleFill('33333333-3333-4333-8333-333333333333')

    await cache.ensureFabricAssetsForFills(fills, { required: true })
    expect(cache.getCachedFabricImage(fills[0]!.style.kind === 'uploaded-fabric' ? fills[0]!.style.assetId : '')).toBeTruthy()
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(1)

    // Second call hits cache.
    await cache.ensureFabricAssetsForFills(fills, { required: true })
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(1)

    cache.__resetFabricAssetCacheForTests()
    cache.bindFabricCacheToUser('user-a')
    fetchFabricImageBlob.mockRejectedValueOnce(new Error('missing'))
    await expect(cache.ensureFabricAssetsForFills(fills, { required: true })).rejects.toMatchObject({
      name: 'FabricAssetLoadError',
    })
  })

  it('clears cache on account switch and drops in-flight results from the prior owner', async () => {
    stubImageDecode()
    let resolveBlob: (b: Blob) => void = () => {}
    fetchFabricImageBlob.mockImplementation(
      () =>
        new Promise<Blob>((resolve) => {
          resolveBlob = resolve
        }),
    )

    const cache = await import('@/lib/fabricAssetCache')
    cache.__resetFabricAssetCacheForTests()
    cache.bindFabricCacheToUser('account-a')

    const assetId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    const pending = cache.loadFabricAssetImage(assetId)

    // Switch accounts before the fetch resolves — in-flight must not populate B's cache.
    cache.bindFabricCacheToUser('account-b')
    expect(cache.getCachedFabricImage(assetId)).toBeNull()

    resolveBlob(new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }))
    await expect(pending).rejects.toMatchObject({ name: 'FabricAssetLoadError' })
    expect(cache.getCachedFabricImage(assetId)).toBeNull()

    // Account B must re-fetch; unauthorized reuse is a network/API concern, but cache is empty.
    fetchFabricImageBlob.mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    )
    await cache.loadFabricAssetImage(assetId)
    expect(fetchFabricImageBlob.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(cache.getCachedFabricImage(assetId)).toBeTruthy()

    // Logout clears everything.
    cache.bindFabricCacheToUser(null)
    expect(cache.getCachedFabricImage(assetId)).toBeNull()
    await expect(cache.loadFabricAssetImage(assetId)).rejects.toMatchObject({
      name: 'FabricAssetLoadError',
    })
  })

  it('does not share cached images across owners with the same asset id', async () => {
    const png = new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' })
    fetchFabricImageBlob.mockResolvedValue(png)
    stubImageDecode()

    const cache = await import('@/lib/fabricAssetCache')
    cache.__resetFabricAssetCacheForTests()
    const assetId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'

    cache.bindFabricCacheToUser('owner-a')
    await cache.loadFabricAssetImage(assetId)
    expect(cache.getCachedFabricImage(assetId)).toBeTruthy()
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(1)

    cache.bindFabricCacheToUser('owner-b')
    expect(cache.getCachedFabricImage(assetId)).toBeNull()
    await cache.loadFabricAssetImage(assetId)
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(2)
  })
})
