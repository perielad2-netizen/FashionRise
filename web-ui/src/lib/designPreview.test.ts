import { describe, expect, it, vi } from 'vitest'
import { PreviewRenderer, previewReferenceUrl } from '@/lib/designPreview'
import type { SavedDesignSnapshot } from '@/lib/savedDesign'

const snapshot: SavedDesignSnapshot = {
  strokes: [],
  model: 'female',
  brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
  dimmed: false,
}

function deferred() {
  let resolve!: (b: Blob) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<Blob>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function setup(concurrency = 2) {
  const pending: ReturnType<typeof deferred>[] = []
  let urlCount = 0
  const revoke = vi.fn()
  const renderer = new PreviewRenderer({
    concurrency,
    render: () => {
      const d = deferred()
      pending.push(d)
      return d.promise
    },
    createObjectURL: () => `blob:preview-${++urlCount}`,
    revokeObjectURL: revoke,
  })
  return { renderer, pending, revoke }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('PreviewRenderer', () => {
  it('never runs more than the concurrency limit', async () => {
    const { renderer, pending } = setup(2)
    const results = ['a', 'b', 'c', 'd', 'e'].map((k) => renderer.request(k, snapshot))
    expect(renderer.activeCount).toBe(2)
    expect(pending).toHaveLength(2)
    pending[0]!.resolve(new Blob(['x']))
    await flush()
    expect(renderer.activeCount).toBe(2)
    expect(pending).toHaveLength(3)
    pending.slice(1).forEach((d) => d.resolve(new Blob(['x'])))
    await flush()
    pending.slice(3).forEach((d) => d.resolve(new Blob(['x'])))
    await expect(Promise.all(results)).resolves.toHaveLength(5)
    expect(renderer.activeCount).toBe(0)
  })

  it('caches by key and shares in-flight work', async () => {
    const { renderer, pending } = setup()
    const first = renderer.request('a', snapshot)
    const second = renderer.request('a', snapshot)
    expect(pending).toHaveLength(1)
    pending[0]!.resolve(new Blob(['x']))
    const [u1, u2] = await Promise.all([first, second])
    expect(u1).toBe(u2)
    await expect(renderer.request('a', snapshot)).resolves.toBe(u1)
    expect(pending).toHaveLength(1)
  })

  it('a failed render yields no URL', async () => {
    const { renderer, pending } = setup()
    const p = renderer.request('a', snapshot)
    pending[0]!.reject(new Error('Canvas 2D unavailable'))
    await expect(p).resolves.toBeNull()
    expect(renderer.liveUrlCount).toBe(0)
  })

  it('dispose revokes every URL, cancels queued work and discards in-flight results', async () => {
    const { renderer, pending, revoke } = setup(1)
    const done = renderer.request('a', snapshot)
    pending[0]!.resolve(new Blob(['x']))
    const url = await done
    const inflight = renderer.request('b', snapshot)
    const queued = renderer.request('c', snapshot)
    renderer.dispose()
    expect(revoke).toHaveBeenCalledWith(url)
    await expect(queued).resolves.toBeNull()
    pending[1]!.resolve(new Blob(['x']))
    await expect(inflight).resolves.toBeNull()
    expect(renderer.liveUrlCount).toBe(0)
  })

  it('release revokes one key, including a render still in flight', async () => {
    const { renderer, pending, revoke } = setup()
    const a = renderer.request('a', snapshot)
    pending[0]!.resolve(new Blob(['x']))
    const urlA = await a
    renderer.release('a')
    expect(revoke).toHaveBeenCalledWith(urlA)
    const b = renderer.request('b', snapshot)
    renderer.release('b')
    pending[1]!.resolve(new Blob(['x']))
    await expect(b).resolves.toBeNull()
    expect(renderer.liveUrlCount).toBe(0)
  })

  it('uses the croquis only for built-in models', () => {
    expect(previewReferenceUrl({ model: 'female' })).toMatch(/female/)
    expect(previewReferenceUrl({ model: 'male' })).toMatch(/male/)
    expect(previewReferenceUrl({ model: 'custom' })).toBeNull()
    expect(previewReferenceUrl({ model: 'blank' })).toBeNull()
  })
})
