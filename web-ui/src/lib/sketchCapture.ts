import { exportSketchPng, type ExportOptions } from '@/lib/exportCanvas'
import { FabricAssetLoadError } from '@/lib/fabricAssetCache'
import {
  artworkExceedsLegacyBounds,
  LEGACY_FRAME_SOFT_PAD_PX,
  strokesForLegacyFrameGate,
} from '@/lib/paperBounds'
import type { FillOp } from '@/lib/fills'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'
import { liveArtworkYSpan } from '@/lib/tryOnDesignHints'

/** Soft client bound; backend also enforces max_upload_size_mb. */
export const MAGIC_MAX_SKETCH_BYTES = 8 * 1024 * 1024

/** Try On garment capture at 2× design plane so fine prints survive provider resize. */
export const TRY_ON_GARMENT_CAPTURE_SCALE = 2

export type CapturedSketch = {
  blob: Blob
  dataUrl: string
  byteLength: number
  referenceIncluded: boolean
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Failed to read sketch image'))
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== 'string' || !result.startsWith('data:image/')) {
        reject(new Error('Sketch export did not produce an image data URL'))
        return
      }
      resolve(result)
    }
    reader.readAsDataURL(blob)
  })
}

/**
 * Capture the current Studio sketch as a PNG data URL for POST /ai/sketch/polish.
 * Reuses exportSketchPng — does not mutate canvas state.
 *
 * When a model/reference URL is expected, capture fails closed if it cannot load
 * so we never enqueue a paid polish on an incomplete sketch.
 */
export async function captureSketchForMagic(options: ExportOptions): Promise<CapturedSketch> {
  const hasArtwork =
    options.strokes.length > 0 || (options.fills?.length ?? 0) > 0 || Boolean(options.referenceUrl)
  if (!hasArtwork) {
    throw new Error('Draw a sketch before using Magic.')
  }
  // Fail closed when garment ink/fills use extended paper margins — do not silently
  // crop oversized garments into the legacy Magic input frame (0 paid AI).
  // Shade/highlight Sketch Engine strokes are ignored (incidental eraser overshoot).
  // Soft pad: fill-under-ink / shoe fills at the croquis feet may sit a few px past
  // 1024 without being true extended-paper artwork.
  if (
    artworkExceedsLegacyBounds(
      strokesForLegacyFrameGate(options.strokes),
      options.fills ?? [],
      LEGACY_FRAME_SOFT_PAD_PX,
    )
  ) {
    throw new Error(
      'This sketch extends beyond the standard Magic frame. Pull oversized strokes inside the croquis area, or export a PNG instead — Magic was not started.',
    )
  }
  const expectsReference = Boolean(options.referenceUrl)
  try {
    const { blob, referenceIncluded } = await exportSketchPng({
      ...options,
      // Gate above already verified ink/fills fit 768×1024. Force legacy so
      // shade/highlight eraser overshoot cannot flip export to paper frame and
      // letterbox/crop the Magic input.
      frame: 'legacy',
      onReferenceError: expectsReference ? 'throw' : 'skip',
      onFabricError: 'throw',
    })
    if (expectsReference && !referenceIncluded) {
      throw new Error(
        'Could not capture the model reference for Magic. Check your connection and try again — your sketch was not sent.',
      )
    }
    if (blob.size > MAGIC_MAX_SKETCH_BYTES) {
      throw new Error('Sketch image is too large for Magic. Try fewer strokes or a smaller reference.')
    }
    const dataUrl = await blobToDataUrl(blob)
    return { blob, dataUrl, byteLength: blob.size, referenceIncluded }
  } catch (err) {
    if (err instanceof FabricAssetLoadError) {
      throw new Error(
        'A custom fabric in this sketch could not be loaded. Check your connection or re-upload the fabric — Magic was not started.',
      )
    }
    if (
      expectsReference &&
      err instanceof Error &&
      /reference|timed out|Failed to load/i.test(err.message)
    ) {
      throw new Error(
        'Could not capture the model reference for Magic. Check your connection and try again — your sketch was not sent.',
      )
    }
    throw err
  }
}

/**
 * #170 — compare captured garment PNG opaque span to live Studio ink.
 * Blocks paid try-on when legs / hems disappear during capture.
 */
export async function assertGarmentCaptureCompleteness(
  blob: Blob,
  options: { strokes: Stroke[]; fills?: FillOp[] },
): Promise<void> {
  const live = liveArtworkYSpan({ strokes: options.strokes, fills: options.fills ?? [] })
  if (!live) return
  const liveSpan = Math.max(1, live.maxY - live.minY)
  // jsdom / older browsers may lack createImageBitmap — skip rather than false-fail.
  if (typeof createImageBitmap !== 'function') return
  const bitmap = await createImageBitmap(blob)
  try {
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(bitmap, 0, 0)
    const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height)
    let minY = height
    let maxY = 0
    let found = false
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const a = data[(y * width + x) * 4 + 3]!
        if (a >= 24) {
          found = true
          minY = Math.min(minY, y)
          maxY = Math.max(maxY, y)
        }
      }
    }
    if (!found) {
      throw new Error(
        'Garment capture is empty. Redraw the filled design, then retry — Try On was not started.',
      )
    }
    // Capture is at TRY_ON_GARMENT_CAPTURE_SCALE; live ink is design-plane coords.
    const scaleY = height / DESIGN_HEIGHT
    const captureSpanDesign = (maxY - minY) / Math.max(scaleY, 1e-6)
    const retention = captureSpanDesign / liveSpan
    const liveHemFrac = live.maxY / DESIGN_HEIGHT
    const captureHemFrac = maxY / height
    if (retention < 0.82 || (liveHemFrac - captureHemFrac) > 0.12) {
      throw new Error(
        'Garment capture lost lower parts of your design (trouser legs or hem). ' +
          'Refill the legs as solid connected regions, then retry — Try On was not started.',
      )
    }
  } finally {
    bitmap.close()
  }
}

/**
 * Transparent garment-only PNG for Try On Person — strokes + fills + fabrics,
 * no paper background and no croquis/mannequin underlay. Preserves spatial
 * alignment with the Studio design plane.
 */
export async function captureGarmentArtworkForTryOn(options: {
  strokes: Stroke[]
  fills?: FillOp[]
}): Promise<CapturedSketch> {
  const fills = options.fills ?? []
  const hasArtwork = options.strokes.length > 0 || fills.length > 0
  if (!hasArtwork) {
    throw new Error('Draw a garment before using Try On Person.')
  }
  // Same gate as Magic: ink/fills only. Shade-layer eraser tips outside 768×1024
  // were blocking all Try On after Sketch Engine V1 (generic SMART_TRY_ON_FAILURE).
  // Soft pad so shoe/hem fills that tuck a few px under outline ink still start.
  if (
    artworkExceedsLegacyBounds(
      strokesForLegacyFrameGate(options.strokes),
      fills,
      LEGACY_FRAME_SOFT_PAD_PX,
    )
  ) {
    throw new Error(
      'This sketch extends beyond the standard try-on frame. Pull oversized strokes inside the croquis area — Try On Person was not started.',
    )
  }
  try {
    const width = DESIGN_WIDTH * TRY_ON_GARMENT_CAPTURE_SCALE
    const height = DESIGN_HEIGHT * TRY_ON_GARMENT_CAPTURE_SCALE
    const { blob, referenceIncluded } = await exportSketchPng({
      strokes: options.strokes,
      fills,
      referenceUrl: null,
      garmentOnly: true,
      width,
      height,
      // Same as Magic: after the ink/fills legacy gate, never let shade-layer
      // eraser overshoot select the extended-paper frame (letterboxes hems).
      frame: 'legacy',
      onReferenceError: 'skip',
      onFabricError: 'throw',
    })
    if (referenceIncluded) {
      throw new Error('Try On Person capture unexpectedly included a croquis underlay.')
    }
    if (blob.size > MAGIC_MAX_SKETCH_BYTES) {
      throw new Error('Garment artwork is too large for Try On Person.')
    }
    await assertGarmentCaptureCompleteness(blob, { strokes: options.strokes, fills })
    const dataUrl = await blobToDataUrl(blob)
    return { blob, dataUrl, byteLength: blob.size, referenceIncluded: false }
  } catch (err) {
    if (err instanceof FabricAssetLoadError) {
      throw new Error(
        'A custom fabric in this sketch could not be loaded. Check your connection or re-upload the fabric — Try On Person was not started.',
      )
    }
    throw err
  }
}
