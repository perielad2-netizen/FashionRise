import { canvasSrcForModel, type ModelCanvasSide } from '@/assets/modelLibrary'
import { isStudioFrontBackEnabled } from '@/config/studioFrontBack'
import { loadPersonalCroquisObjectUrl } from '@/lib/personalCroquisCache'
import { canvasToPngBlob, loadImage, renderSketchCanvas } from '@/lib/exportCanvas'
import type { SavedDesignSnapshot } from '@/lib/savedDesign'
import { getPersonalCroquisVersion } from '@/services/personalCroquisApi'

export const PREVIEW_WIDTH = 240
export const PREVIEW_HEIGHT = 320
export const PREVIEW_CONCURRENCY = 2
/** Previews are rendered for at most this many cards per page of the library. */
export const PREVIEW_PAGE_SIZE = 24
/** Thumbnail-only floor so pencil-fine strokes stay visible at 240×320. */
export const PREVIEW_MIN_INK_SIZE = 1.5

/**
 * Synchronous stock/library croquis URL for thumbnails.
 * Personal My Croquis needs an authenticated asset fetch — use
 * {@link resolvePreviewReferenceUrl} instead.
 */
export function previewReferenceUrl(
  snapshot: Pick<SavedDesignSnapshot, 'model' | 'activeSide'>,
  side: ModelCanvasSide = 'front',
): string | null {
  if (snapshot.model === 'personal' || snapshot.model === 'custom' || snapshot.model === 'blank') {
    return null
  }
  const target = isStudioFrontBackEnabled() && side === 'back' ? 'back' : 'front'
  return canvasSrcForModel(snapshot.model, target)
}

type ResolvePreviewReferenceOptions = {
  ownerId?: string | null
  side?: ModelCanvasSide
}

/**
 * Resolve the croquis underlay for a My Designs / working-draft thumbnail.
 * Built-in models use static library assets; personal pins load the exact
 * accepted version asset via the owner-bound cache (same path as Studio).
 */
export async function resolvePreviewReferenceUrl(
  snapshot: Pick<
    SavedDesignSnapshot,
    'model' | 'activeSide' | 'personalCroquisId' | 'personalCroquisVersion'
  >,
  options: ResolvePreviewReferenceOptions = {},
): Promise<string | null> {
  const side =
    options.side ??
    (isStudioFrontBackEnabled() && snapshot.activeSide === 'back' ? 'back' : 'front')

  if (snapshot.model === 'personal') {
    // V1 personal croquis is front-only underlay imagery.
    if (side === 'back') return null
    const ownerId = options.ownerId ?? null
    const croquisId = snapshot.personalCroquisId ?? null
    const version = snapshot.personalCroquisVersion ?? null
    if (!ownerId || !croquisId || version == null || !Number.isInteger(version) || version < 1) {
      return null
    }
    try {
      const ver = await getPersonalCroquisVersion(croquisId, version)
      const assetId = ver.generated_asset_id
      if (!assetId) return null
      return await loadPersonalCroquisObjectUrl({
        userId: ownerId,
        croquisId,
        version,
        assetId,
      })
    } catch {
      // Match thumbnail onReferenceError:'skip' — ink still renders without underlay.
      return null
    }
  }

  return previewReferenceUrl(snapshot, side)
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

export type RenderPreviewOptions = {
  ownerId?: string | null
}

/**
 * Saved-design thumbnail. Output is always PREVIEW_WIDTH×PREVIEW_HEIGHT; the
 * design frame is chosen automatically (legacy vs extended paper) so oversized
 * garments fit into the thumbnail without cropping margins. Legacy artwork
 * still uses the 768×1024 frame scaled into the same preview size.
 */
export async function renderPreviewBlob(
  snapshot: SavedDesignSnapshot,
  options: RenderPreviewOptions = {},
): Promise<Blob> {
  const referenceUrl = await resolvePreviewReferenceUrl(snapshot, { ownerId: options.ownerId })
  const { canvas } = await renderSketchCanvas({
    strokes: snapshot.strokes,
    fills: snapshot.fills ?? [],
    referenceUrl,
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
  render?: (snapshot: SavedDesignSnapshot, options?: RenderPreviewOptions) => Promise<Blob>
  createObjectURL?: (blob: Blob) => string
  revokeObjectURL?: (url: string) => void
  concurrency?: number
  ownerId?: string | null
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
  private readonly render: (
    snapshot: SavedDesignSnapshot,
    options?: RenderPreviewOptions,
  ) => Promise<Blob>
  private readonly createUrl: (blob: Blob) => string
  private readonly revokeUrl: (url: string) => void
  private readonly concurrency: number
  private ownerId: string | null
  private readonly urls = new Map<string, string>()
  private readonly inflight = new Map<string, Promise<string | null>>()
  private readonly queue: Job[] = []
  private readonly released = new Set<string>()
  private active = 0
  private generation = 0

  constructor(deps: PreviewDeps = {}) {
    this.ownerId = deps.ownerId ?? null
    this.render =
      deps.render ?? ((snapshot, options) => renderPreviewBlob(snapshot, options))
    this.createUrl = deps.createObjectURL ?? ((b) => URL.createObjectURL(b))
    this.revokeUrl = deps.revokeObjectURL ?? ((u) => URL.revokeObjectURL(u))
    this.concurrency = Math.max(1, deps.concurrency ?? PREVIEW_CONCURRENCY)
  }

  /** Keep owner identity aligned with the signed-in account for personal underlays. */
  setOwnerId(ownerId: string | null): void {
    this.ownerId = ownerId
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
      const blob = await this.render(job.snapshot, { ownerId: this.ownerId })
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
