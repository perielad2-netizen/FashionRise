import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'

const fetchFabricImageBlob = vi.fn()

vi.mock('@/services/fabricAssetsApi', () => ({
  fetchFabricImageBlob: (...args: unknown[]) => fetchFabricImageBlob(...args),
}))

describe('fabricAssetCache', () => {
  afterEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  it('loads and caches fabric images; required mode fails closed', async () => {
    const png = new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' })
    fetchFabricImageBlob.mockResolvedValue(png)

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

    const cache = await import('@/lib/fabricAssetCache')
    cache.__resetFabricAssetCacheForTests()

    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: {
          kind: 'uploaded-fabric',
          assetId: '33333333-3333-4333-8333-333333333333',
          scale: 1,
        },
        seedX: 1,
        seedY: 1,
      },
    ]

    await cache.ensureFabricAssetsForFills(fills, { required: true })
    expect(cache.getCachedFabricImage(fills[0]!.style.kind === 'uploaded-fabric' ? fills[0]!.style.assetId : '')).toBeTruthy()
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(1)

    // Second call hits cache.
    await cache.ensureFabricAssetsForFills(fills, { required: true })
    expect(fetchFabricImageBlob).toHaveBeenCalledTimes(1)

    cache.__resetFabricAssetCacheForTests()
    fetchFabricImageBlob.mockRejectedValueOnce(new Error('missing'))
    await expect(cache.ensureFabricAssetsForFills(fills, { required: true })).rejects.toMatchObject({
      name: 'FabricAssetLoadError',
    })
  })
})
