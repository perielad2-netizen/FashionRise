import { useEffect, useId, useState } from 'react'
import {
  AtSign,
  Check,
  Copy,
  Download,
  Link2,
  MessageCircle,
  Share2,
  X,
} from 'lucide-react'
import {
  FASHIONRISE_INSTAGRAM,
  FASHIONRISE_PUBLIC_URL,
  buildInstagramProfileUrl,
  buildShareCaption,
  buildWhatsAppShareUrl,
  canUseNativeShare,
  copyText,
  downloadImageFromUrl,
  shareNative,
  type SharePayload,
} from '@/lib/sharePromo'
import styles from './ShareSheet.module.css'

type Props = {
  open: boolean
  onClose: () => void
  payload?: SharePayload
}

type Flash = 'copied-caption' | 'copied-link' | 'saved-image' | 'shared' | null

export function ShareSheet({ open, onClose, payload }: Props) {
  const titleId = useId()
  const [flash, setFlash] = useState<Flash>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const effective: SharePayload = payload ?? { kind: 'app' }
  const caption = buildShareCaption(effective)
  const hasImage = Boolean(effective.imageUrl)
  const nativeOk = canUseNativeShare()

  useEffect(() => {
    if (!open) {
      setFlash(null)
      setError(null)
      setBusy(false)
      return
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!flash) return
    const t = window.setTimeout(() => setFlash(null), 2200)
    return () => window.clearTimeout(t)
  }, [flash])

  if (!open) return null

  const flashLabel =
    flash === 'copied-caption'
      ? 'Caption copied'
      : flash === 'copied-link'
        ? 'Link copied'
        : flash === 'saved-image'
          ? 'Image saved — paste the caption in Instagram'
          : flash === 'shared'
            ? 'Opened share sheet'
            : null

  async function onCopyCaption() {
    setBusy(true)
    setError(null)
    try {
      await copyText(caption)
      setFlash('copied-caption')
    } catch {
      setError('Could not copy caption. Long-press and copy manually.')
    } finally {
      setBusy(false)
    }
  }

  async function onCopyLink() {
    setBusy(true)
    setError(null)
    try {
      await copyText(FASHIONRISE_PUBLIC_URL)
      setFlash('copied-link')
    } catch {
      setError('Could not copy link.')
    } finally {
      setBusy(false)
    }
  }

  function onWhatsApp() {
    window.open(buildWhatsAppShareUrl(caption), '_blank', 'noopener,noreferrer')
  }

  async function onInstagram() {
    setBusy(true)
    setError(null)
    try {
      await copyText(caption)
      if (effective.imageUrl) {
        await downloadImageFromUrl(
          effective.imageUrl,
          effective.imageFileName ?? 'fashionrise-look.png',
        )
        setFlash('saved-image')
      } else {
        setFlash('copied-caption')
      }
      window.open(buildInstagramProfileUrl(), '_blank', 'noopener,noreferrer')
    } catch {
      setError('Caption copied if possible — open Instagram and paste when you post.')
      window.open(buildInstagramProfileUrl(), '_blank', 'noopener,noreferrer')
    } finally {
      setBusy(false)
    }
  }

  async function onSystemShare() {
    setBusy(true)
    setError(null)
    try {
      const result = await shareNative(effective)
      if (result === 'shared') setFlash('shared')
      if (result === 'unavailable') setError('System share is not available on this device.')
    } catch {
      setError('Could not open the system share sheet.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="share-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.titleRow}>
            <Share2 size={18} aria-hidden />
            <h2 id={titleId}>Share FashionRise</h2>
          </div>
          <button
            type="button"
            className={styles.close}
            aria-label="Close share"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        <p className={styles.hint}>
          Invite friends with a promo caption. WhatsApp gets the text ready to send. Instagram
          cannot be posted from the browser — we copy the caption
          {hasImage ? ', save the image,' : ''} and open @{FASHIONRISE_INSTAGRAM} so you can paste
          into Stories or a new post.
        </p>

        <pre className={styles.caption} data-testid="share-caption" aria-label="Share caption">
          {caption}
        </pre>

        <div className={styles.channels} role="group" aria-label="Share channels">
          {nativeOk ? (
            <button
              type="button"
              className={styles.channel}
              disabled={busy}
              onClick={() => void onSystemShare()}
              data-testid="share-system"
            >
              <Share2 size={18} aria-hidden />
              <span>Device share</span>
              <small>Instagram, Messages, more</small>
            </button>
          ) : null}
          <button
            type="button"
            className={styles.channel}
            disabled={busy}
            onClick={onWhatsApp}
            data-testid="share-whatsapp"
          >
            <MessageCircle size={18} aria-hidden />
            <span>WhatsApp</span>
            <small>Opens with promo text</small>
          </button>
          <button
            type="button"
            className={styles.channel}
            disabled={busy}
            onClick={() => void onInstagram()}
            data-testid="share-instagram"
          >
            <AtSign size={18} aria-hidden />
            <span>Instagram</span>
            <small>{hasImage ? 'Copy + save image' : 'Copy caption + open'}</small>
          </button>
          <button
            type="button"
            className={styles.channel}
            disabled={busy}
            onClick={() => void onCopyCaption()}
            data-testid="share-copy-caption"
          >
            <Copy size={18} aria-hidden />
            <span>Copy caption</span>
            <small>Paste anywhere</small>
          </button>
          <button
            type="button"
            className={styles.channel}
            disabled={busy}
            onClick={() => void onCopyLink()}
            data-testid="share-copy-link"
          >
            <Link2 size={18} aria-hidden />
            <span>Copy link</span>
            <small>{FASHIONRISE_PUBLIC_URL.replace(/^https?:\/\//, '')}</small>
          </button>
          {hasImage ? (
            <button
              type="button"
              className={styles.channel}
              disabled={busy}
              onClick={() => {
                void (async () => {
                  setBusy(true)
                  setError(null)
                  try {
                    await downloadImageFromUrl(
                      effective.imageUrl!,
                      effective.imageFileName ?? 'fashionrise-look.png',
                    )
                    setFlash('saved-image')
                  } catch {
                    setError('Could not download the look image.')
                  } finally {
                    setBusy(false)
                  }
                })()
              }}
              data-testid="share-save-image"
            >
              <Download size={18} aria-hidden />
              <span>Save image</span>
              <small>For Instagram upload</small>
            </button>
          ) : null}
        </div>

        {flashLabel ? (
          <p className={styles.flash} role="status" data-testid="share-flash">
            <Check size={14} aria-hidden /> {flashLabel}
          </p>
        ) : null}
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  )
}
