/**
 * FashionRise social share copy + channel helpers.
 *
 * Instagram has no public web “compose post” URL. We copy a promo caption
 * (and optionally hand the image to the OS share sheet / download) so the
 * designer can paste into Instagram Stories or Feed after opening the app.
 * WhatsApp accepts a prefilled text deep link.
 */

export const FASHIONRISE_PUBLIC_URL = (
  (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.trim() ||
  'https://fashionrise.app'
).replace(/\/$/, '')

/** Instagram handle without @ — set VITE_SOCIAL_INSTAGRAM once the account is live. */
export const FASHIONRISE_INSTAGRAM = (
  (import.meta.env.VITE_SOCIAL_INSTAGRAM as string | undefined)?.trim() || 'fashionrise'
).replace(/^@/, '')

export const FASHIONRISE_TIKTOK = (
  (import.meta.env.VITE_SOCIAL_TIKTOK as string | undefined)?.trim() || 'fashionrise'
).replace(/^@/, '')

export type ShareKind = 'app' | 'look'

export type SharePayload = {
  kind: ShareKind
  /** Optional look / design title for richer captions. */
  title?: string | null
  /** Object URL or same-origin image URL to attach when the OS supports files. */
  imageUrl?: string | null
  /** Suggested download filename when saving for Instagram. */
  imageFileName?: string | null
}

export function buildShareCaption(payload: SharePayload = { kind: 'app' }): string {
  const url = FASHIONRISE_PUBLIC_URL
  const ig = FASHIONRISE_INSTAGRAM
  const title = payload.title?.trim()

  if (payload.kind === 'look') {
    const lead = title
      ? `I designed “${title}” in FashionRise`
      : 'I designed this look in FashionRise'
    return [
      `${lead} ✨`,
      'Dream · Sketch · Create your own fashion looks:',
      url,
      `Follow @${ig} on Instagram`,
    ].join('\n')
  }

  return [
    'Design fashion looks with FashionRise ✨',
    'Dream · Sketch · Create — sketch on a croquis, Magic your look, make a tech pack.',
    url,
    `Follow @${ig} on Instagram`,
  ].join('\n')
}

export function buildWhatsAppShareUrl(caption: string): string {
  return `https://wa.me/?text=${encodeURIComponent(caption)}`
}

export function buildInstagramProfileUrl(handle = FASHIONRISE_INSTAGRAM): string {
  return `https://www.instagram.com/${encodeURIComponent(handle)}/`
}

export function buildTikTokProfileUrl(handle = FASHIONRISE_TIKTOK): string {
  return `https://www.tiktok.com/@${encodeURIComponent(handle)}`
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
  const safeName = fileName.replace(/[^\w.\-]+/g, '-').replace(/^-|-$/g, '') || 'fashionrise-look.png'
  return new File([blob], safeName.endsWith('.png') || safeName.endsWith('.jpg') ? safeName : `${safeName}.png`, {
    type,
  })
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

export async function shareNative(payload: SharePayload): Promise<NativeShareResult> {
  if (!canUseNativeShare()) return 'unavailable'
  const text = buildShareCaption(payload)
  const data: ShareData = {
    title: 'FashionRise',
    text,
    url: FASHIONRISE_PUBLIC_URL,
  }
  if (payload.imageUrl && canNativeShareFiles()) {
    try {
      const file = await fileFromImageUrl(
        payload.imageUrl,
        payload.imageFileName ?? 'fashionrise-look.png',
      )
      const withFiles: ShareData = { ...data, files: [file] }
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
