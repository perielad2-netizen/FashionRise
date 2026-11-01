import { canvasSrcForModel, type ModelCanvasSide } from '@/assets/modelLibrary'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import { canvasToPngBlob, loadImage, renderSketchCanvas } from '@/lib/exportCanvas'
import type { SavedDesignSnapshot } from '@/lib/savedDesign'

export const PREVIEW_WIDTH = 240
export const PREVIEW_HEIGHT = 320
export const PREVIEW_CONCURRENCY = 2
/** Previews are rendered for at most this many cards per page of the library. */
export const PREVIEW_PAGE_SIZE = 24
/** Thumbnail-only floor so pencil-fine strokes stay visible at 240×320. */
export const PREVIEW_MIN_INK_SIZE = 1.5

export function previewReferenceUrl(
  snapshot: Pick<SavedDesignSnapshot, 'model' | 'activeSide'>,
  side: ModelCanvasSide = 'front',
): string | null {
  const target = isStudioFrontBackEnabled() && side === 'back' ? 'back' : 'front'
  return canvasSrcForModel(snapshot.model, target)
}

const referenceCache = new Map<string, Promise<HTMLImageElement>>()

function cachedReference(src: string): Promise<HTMLImageElement> {
  let pending = referenceCache.get(src)
  if (!pending) {
    pending = loadImage(src)
    pending.catch(() => referenceCache.delete(src))
    referenceCache.set(src, pending)
  }
  return pending
}

/**
 * Saved-design thumbnail. Output is always PREVIEW_WIDTH×PREVIEW_HEIGHT; the
 * design frame is chosen automatically (legacy vs extended paper) so oversized
 * garments fit into the thumbnail without cropping margins. Legacy artwork
 * still uses the 768×1024 frame scaled into the same preview size.
 */
export async function renderPreviewBlob(snapshot: SavedDesignSnapshot): Promise<Blob> {
  const { canvas } = await renderSketchCanvas({
    strokes: snapshot.strokes,
    fills: snapshot.fills ?? [],
    referenceUrl: previewReferenceUrl(snapshot),
    referenceOpacity: snapshot.dimmed ? 0.4 : 1,
    width: PREVIEW_WIDTH,
    height: PREVIEW_HEIGHT,
    frame: 'auto',
    onReferenceError: 'skip',
    onFabricError: 'skip',
    loadReference: cachedReference,
    minInkSize: PREVIEW_MIN_INK_SIZE,
  })
  return canvasToPngBlob(canvas)
}

type PreviewDeps = {
  render?: (snapshot: SavedDesignSnapshot) => Promise<Blob>
  createObjectURL?: (blob: Blob) => string
  revokeObjectURL?: (url: string) => void
  concurrency?: number
}

type Job = {
  key: string
  snapshot: SavedDesignSnapshot
  resolve: (url: string | null) => void
  generation: number
}

/**
 * Bounded thumbnail renderer: at most `concurrency` renders run at once, results are
 * cached per key, and every object URL it creates is revoked by `release()` or `dispose()`.
 * `dispose()` discards in-flight work by generation, so the instance stays reusable
 * (React StrictMode runs effect cleanups and re-mounts with the same state).
 */
export class PreviewRenderer {
  private readonly render: (snapshot: SavedDesignSnapshot) => Promise<Blob>
  private readonly createUrl: (blob: Blob) => string
  private readonly revokeUrl: (url: string) => void
  private readonly concurrency: number
  private readonly urls = new Map<string, string>()
  private readonly inflight = new Map<string, Promise<string | null>>()
  private readonly queue: Job[] = []
  private readonly released = new Set<string>()
  private active = 0
  private generation = 0

  constructor(deps: PreviewDeps = {}) {
    this.render = deps.render ?? renderPreviewBlob
    this.createUrl = deps.createObjectURL ?? ((b) => URL.createObjectURL(b))
    this.revokeUrl = deps.revokeObjectURL ?? ((u) => URL.revokeObjectURL(u))
    this.concurrency = Math.max(1, deps.concurrency ?? PREVIEW_CONCURRENCY)
  }

  get activeCount(): number {
    return this.active
  }

  get liveUrlCount(): number {
    return this.urls.size
  }

  request(key: string, snapshot: SavedDesignSnapshot): Promise<string | null> {
    const ready = this.urls.get(key)
    if (ready) return Promise.resolve(ready)
    const pending = this.inflight.get(key)
    if (pending) {
      this.released.delete(key)
      return pending
    }
    const promise = new Promise<string | null>((resolve) => {
      this.queue.push({ key, snapshot, resolve, generation: this.generation })
    })
    this.inflight.set(key, promise)
    this.pump()
    return promise
  }

  /** Revoke one key's URL now, or as soon as its in-flight render finishes. */
  release(key: string): void {
    const url = this.urls.get(key)
    if (url) {
      this.revokeUrl(url)
      this.urls.delete(key)
    }
    if (this.inflight.has(key)) this.released.add(key)
  }

  dispose(): void {
    this.generation += 1
    for (const job of this.queue.splice(0)) job.resolve(null)
    for (const url of this.urls.values()) this.revokeUrl(url)
    this.urls.clear()
    this.inflight.clear()
    this.released.clear()
  }

  private pump(): void {
    while (this.active < this.concurrency && this.queue.length > 0) {
      const job = this.queue.shift()!
      this.active += 1
      void this.run(job)
    }
  }

  private async run(job: Job): Promise<void> {
    let url: string | null = null
    const current = () => job.generation === this.generation
    try {
      const blob = await this.render(job.snapshot)
      if (current() && !this.released.has(job.key)) {
        url = this.createUrl(blob)
        this.urls.set(job.key, url)
      }
    } catch {
      url = null
    } finally {
      this.active -= 1
      if (current()) {
        this.inflight.delete(job.key)
        this.released.delete(job.key)
      }
      job.resolve(url)
      this.pump()
    }
  }
}
