import { exportSketchPng, type ExportOptions } from '@/lib/exportCanvas'
import { FabricAssetLoadError } from '@/lib/fabricAssetCache'
import { artworkExceedsLegacyBounds } from '@/lib/paperBounds'
import type { FillOp } from '@/lib/fills'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'

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
  // Fail closed when artwork uses the extended paper margins — do not silently
  // crop oversized garments into the legacy Magic input frame (0 paid AI).
  if (artworkExceedsLegacyBounds(options.strokes, options.fills ?? [])) {
    throw new Error(
      'This sketch extends beyond the standard Magic frame. Pull oversized strokes inside the croquis area, or export a PNG instead — Magic was not started.',
    )
  }
  const expectsReference = Boolean(options.referenceUrl)
  try {
    const { blob, referenceIncluded } = await exportSketchPng({
      ...options,
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
  if (artworkExceedsLegacyBounds(options.strokes, fills)) {
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
      onReferenceError: 'skip',
      onFabricError: 'throw',
    })
    if (referenceIncluded) {
      throw new Error('Try On Person capture unexpectedly included a croquis underlay.')
    }
    if (blob.size > MAGIC_MAX_SKETCH_BYTES) {
      throw new Error('Garment artwork is too large for Try On Person.')
    }
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
