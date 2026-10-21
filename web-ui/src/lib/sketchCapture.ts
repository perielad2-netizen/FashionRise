import { exportSketchPng, type ExportOptions } from '@/lib/exportCanvas'

/** Soft client bound; backend also enforces max_upload_size_mb. */
export const MAGIC_MAX_SKETCH_BYTES = 8 * 1024 * 1024

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
 */
export async function captureSketchForMagic(options: ExportOptions): Promise<CapturedSketch> {
  if (!options.strokes.length && !options.referenceUrl) {
    throw new Error('Draw a sketch before using Magic.')
  }
  const { blob, referenceIncluded } = await exportSketchPng({
    ...options,
    onReferenceError: 'skip',
  })
  if (blob.size > MAGIC_MAX_SKETCH_BYTES) {
    throw new Error('Sketch image is too large for Magic. Try fewer strokes or a smaller reference.')
  }
  const dataUrl = await blobToDataUrl(blob)
  return { blob, dataUrl, byteLength: blob.size, referenceIncluded }
}
