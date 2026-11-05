/**
 * Client-side prepare for Create My Croquis photo upload.
 *
 * Phone camera JPEGs routinely exceed nginx `client_max_body_size` (12m) and the
 * backend croquis cap (10 MB). Without compression the edge returns bare 413 HTML,
 * the wizard re-enables Upload & Generate, and no croquis appears.
 */

/** Stay under nginx 12m and backend 10 MB with multipart overhead. */
export const CROQUIS_UPLOAD_SOFT_MAX_BYTES = 8 * 1024 * 1024

/** Long-edge cap — matches backend max_croquis_dimension_px spirit, keeps bytes down. */
export const CROQUIS_UPLOAD_MAX_EDGE_PX = 2048

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error('Could not encode photo for upload.'))
        else resolve(blob)
      },
      type,
      quality,
    )
  })
}

async function loadImageElement(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('Could not read that photo.'))
      el.src = url
    })
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}

function drawScaled(img: HTMLImageElement, maxEdge: number): HTMLCanvasElement {
  const srcW = img.naturalWidth || img.width
  const srcH = img.naturalHeight || img.height
  const scale = Math.min(1, maxEdge / Math.max(srcW, srcH, 1))
  const w = Math.max(1, Math.round(srcW * scale))
  const h = Math.max(1, Math.round(srcH * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Could not prepare photo for upload.')
  ctx.drawImage(img, 0, 0, w, h)
  return canvas
}

/**
 * Downscale + JPEG-encode large phone photos so Upload & Generate can reach the API.
 * Small / already-safe files are returned unchanged. Unreadable blobs pass through
 * so the server can reject with a clear validation error.
 */
export async function prepareCroquisUpload(file: File): Promise<File> {
  if (!file || file.size <= 0) return file
  // Tiny fixtures / already under soft max: skip work unless clearly huge.
  if (file.size <= CROQUIS_UPLOAD_SOFT_MAX_BYTES && file.size < 512 * 1024) {
    return file
  }

  let img: HTMLImageElement
  try {
    img = await loadImageElement(file)
  } catch {
    return file
  }

  const srcW = img.naturalWidth || img.width
  const srcH = img.naturalHeight || img.height
  const needsResize =
    srcW > CROQUIS_UPLOAD_MAX_EDGE_PX ||
    srcH > CROQUIS_UPLOAD_MAX_EDGE_PX ||
    file.size > CROQUIS_UPLOAD_SOFT_MAX_BYTES
  if (!needsResize) return file

  let edge = CROQUIS_UPLOAD_MAX_EDGE_PX
  let quality = 0.85
  let blob: Blob | null = null
  for (let attempt = 0; attempt < 6; attempt++) {
    const canvas = drawScaled(img, edge)
    blob = await canvasToBlob(canvas, 'image/jpeg', quality)
    if (blob.size <= CROQUIS_UPLOAD_SOFT_MAX_BYTES) break
    if (quality > 0.55) quality -= 0.1
    else edge = Math.max(1024, Math.round(edge * 0.75))
  }
  if (!blob) return file

  const base = file.name.replace(/\.[^.]+$/, '') || 'croquis-photo'
  return new File([blob], `${base}.jpg`, {
    type: 'image/jpeg',
    lastModified: Date.now(),
  })
}
