/**
 * Share AI look results with attribution.
 *
 * Caption always includes “Created with FashionRise” and tells people to
 * search Google for FashionRise. On phones we prefer the OS share sheet so the
 * user picks WhatsApp / Instagram / Facebook themselves. There is no reliable
 * web API to open those apps straight into a photo compose screen.
 */

export const FASHIONRISE_PUBLIC_URL = (
  (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.trim() ||
  'https://fashionrise.app'
).replace(/\/$/, '')

export const FASHIONRISE_GOOGLE_SEARCH_URL =
  'https://www.google.com/search?q=FashionRise'

export type ShareKind = 'app' | 'look'

export type SharePayload = {
  kind: ShareKind
  /**
   * Optional look title kept for callers / filenames — never included in the
   * public share caption (attribution only).
   */
  title?: string | null
  /** Object URL or same-origin image URL to attach when the OS supports files. */
  imageUrl?: string | null
  /** Suggested download filename when saving for a post. */
  imageFileName?: string | null
}

/** Attribution caption for WhatsApp / Instagram / Facebook posts. */
export function buildShareCaption(_payload: SharePayload = { kind: 'look' }): string {
  return [
    'Created with FashionRise',
    'Search Google for FashionRise to design your own looks',
    FASHIONRISE_PUBLIC_URL,
  ].join('\n')
}

export function buildWhatsAppShareUrl(caption: string): string {
  return `https://wa.me/?text=${encodeURIComponent(caption)}`
}

export function canUseNativeShare(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function'
}

export function canNativeShareFiles(): boolean {
  if (!canUseNativeShare() || typeof navigator.canShare !== 'function') return false
  try {
    const probe = new File(['x'], 'probe.png', { type: 'image/png' })
    return navigator.canShare({ files: [probe] })
  } catch {
    return false
  }
}

export async function fileFromImageUrl(
  imageUrl: string,
  fileName = 'fashionrise-look.png',
): Promise<File> {
  const res = await fetch(imageUrl)
  if (!res.ok) throw new Error('Could not load look image for sharing')
  const blob = await res.blob()
  const type = blob.type && blob.type.startsWith('image/') ? blob.type : 'image/png'
  const safeName =
    fileName.replace(/[^\w.\-]+/g, '-').replace(/^-|-$/g, '') || 'fashionrise-look.png'
  return new File(
    [blob],
    safeName.endsWith('.png') || safeName.endsWith('.jpg') || safeName.endsWith('.jpeg')
      ? safeName
      : `${safeName}.png`,
    { type },
  )
}

export async function copyText(text: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.left = '-9999px'
  document.body.appendChild(ta)
  ta.select()
  const ok = document.execCommand('copy')
  ta.remove()
  if (!ok) throw new Error('Clipboard copy failed')
}

export async function downloadImageFromUrl(imageUrl: string, fileName: string): Promise<void> {
  const file = await fileFromImageUrl(imageUrl, fileName)
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = file.name
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export type NativeShareResult = 'shared' | 'cancelled' | 'unavailable'

/** Prefer sharing the look image + attribution caption via the OS sheet. */
export async function shareNative(payload: SharePayload): Promise<NativeShareResult> {
  if (!canUseNativeShare()) return 'unavailable'
  const text = buildShareCaption(payload)
  const data: ShareData = {
    title: 'Created with FashionRise',
    text,
    url: FASHIONRISE_PUBLIC_URL,
  }
  if (payload.imageUrl && canNativeShareFiles()) {
    try {
      const file = await fileFromImageUrl(
        payload.imageUrl,
        payload.imageFileName ?? 'fashionrise-look.png',
      )
      const withFiles: ShareData = { title: data.title, text, files: [file] }
      if (navigator.canShare?.(withFiles)) {
        await navigator.share(withFiles)
        return 'shared'
      }
    } catch {
      // Fall through to text-only share.
    }
  }
  try {
    await navigator.share(data)
    return 'shared'
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return 'cancelled'
    throw err
  }
}

export type RequestShareResult = 'shared' | 'cancelled' | 'needs-fallback'

/**
 * One-tap share: open the OS picker when available so the user chooses
 * WhatsApp / Instagram / Facebook / etc. Otherwise callers should show a
 * simple fallback sheet (copy caption + save image).
 */
export async function requestShare(payload: SharePayload): Promise<RequestShareResult> {
  if (!canUseNativeShare()) return 'needs-fallback'
  try {
    const result = await shareNative(payload)
    if (result === 'shared') return 'shared'
    if (result === 'cancelled') return 'cancelled'
    return 'needs-fallback'
  } catch {
    return 'needs-fallback'
  }
}
