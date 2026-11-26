/**
 * Share AI look results with attribution.
 *
 * Caption matches store listing short description (App Store / Google Play)
 * and tells people to search FashionRise in the stores — no website URL.
 * On Android/iOS we open the **system** share sheet via `@capacitor/share`.
 * On modern browsers we use `navigator.share`. The custom ShareSheet UI is
 * desktop/fallback only.
 */

import { isNativeShell } from '@/services/native/platform'

export const FASHIONRISE_PUBLIC_URL = (
  (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.trim() ||
  'https://fashionrise.app'
).replace(/\/$/, '')

/** Same short line as Google Play / App Store listing (≤ 80 chars). */
export const FASHIONRISE_STORE_SHORT_DESCRIPTION =
  'AI fashion studio: sketch, Magic looks, models, try-on, fabrics & tech packs.'

/** CTA used in share captions instead of a bare website URL. */
export const FASHIONRISE_STORE_SEARCH_CTA =
  'Search for FashionRise on the App Store and Google Play'

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
    FASHIONRISE_STORE_SHORT_DESCRIPTION,
    FASHIONRISE_STORE_SEARCH_CTA,
  ].join('\n')
}

export function buildWhatsAppShareUrl(caption: string): string {
  return `https://wa.me/?text=${encodeURIComponent(caption)}`
}

function isShareCancel(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const name = 'name' in err ? String((err as { name: unknown }).name) : ''
  const message = 'message' in err ? String((err as { message: unknown }).message) : ''
  if (name === 'AbortError') return true
  return /cancel/i.test(message) || /dismiss/i.test(message)
}

/** True when we can open an OS share sheet (Capacitor native or Web Share API). */
export function canUseNativeShare(): boolean {
  if (isNativeShell()) return true
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function'
}

export function canNativeShareFiles(): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function') return false
  if (typeof navigator.canShare !== 'function') return false
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
  const { saveOrDownloadBlob } = await import('@/lib/exportCanvas')
  await saveOrDownloadBlob(file, file.name)
}

export type NativeShareResult = 'shared' | 'cancelled' | 'unavailable'

/** Capacitor Android/iOS system share sheet (image file + caption when possible). */
async function shareViaCapacitor(payload: SharePayload): Promise<NativeShareResult> {
  let isNative = false
  try {
    const { Capacitor } = await import('@capacitor/core')
    isNative = Capacitor.isNativePlatform()
  } catch {
    return 'unavailable'
  }
  if (!isNative) return 'unavailable'

  const { Share } = await import('@capacitor/share')
  const text = buildShareCaption(payload)
  const files: string[] = []

  if (payload.imageUrl) {
    try {
      const file = await fileFromImageUrl(
        payload.imageUrl,
        payload.imageFileName ?? 'fashionrise-look.png',
      )
      const { blobToBase64, writeCacheFileForDownload } = await import('@/lib/nativeImageSave')
      const base64 = await blobToBase64(file)
      const cachePath = `fr-share/${Date.now()}-${file.name}`
      const { uri } = await writeCacheFileForDownload(cachePath, base64)
      if (uri) files.push(uri)
    } catch {
      // Text-only share still beats the custom popup.
    }
  }

  try {
    // Do not also pass `url` — caption already includes the site once.
    // Passing both makes WhatsApp/etc. duplicate the link.
    await Share.share({
      title: 'FashionRise',
      text,
      files: files.length > 0 ? files : undefined,
      dialogTitle: payload.kind === 'look' ? 'Share your look' : 'Share FashionRise',
    })
    return 'shared'
  } catch (err) {
    if (isShareCancel(err)) return 'cancelled'
    throw err
  }
}

/** Prefer sharing the look image + attribution caption via the OS sheet. */
export async function shareNative(payload: SharePayload): Promise<NativeShareResult> {
  // Capacitor first — Android WebView often has no usable navigator.share.
  try {
    const cap = await shareViaCapacitor(payload)
    if (cap !== 'unavailable') return cap
  } catch {
    // Fall through to Web Share / unavailable.
  }

  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function') {
    return 'unavailable'
  }

  const text = buildShareCaption(payload)
  // Caption already includes the public URL once — omit separate `url`.
  const data: ShareData = {
    title: 'FashionRise',
    text,
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
    if (isShareCancel(err)) return 'cancelled'
    throw err
  }
}

export type RequestShareResult = 'shared' | 'cancelled' | 'needs-fallback'

/**
 * One-tap share: open the OS picker (WhatsApp / Instagram / …). Only when the
 * platform cannot open a system sheet should callers show the desktop fallback UI.
 */
export async function requestShare(payload: SharePayload): Promise<RequestShareResult> {
  try {
    const result = await shareNative(payload)
    if (result === 'shared') return 'shared'
    if (result === 'cancelled') return 'cancelled'
    return 'needs-fallback'
  } catch {
    return 'needs-fallback'
  }
}
