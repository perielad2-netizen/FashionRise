import { useEffect, useId, useState } from 'react'
import {
  AtSign,
  Check,
  Copy,
  Download,
  MessageCircle,
  Share2,
  X,
} from 'lucide-react'
import {
  FASHIONRISE_PUBLIC_URL,
  buildFacebookShareUrl,
  buildInstagramCreateUrl,
  buildShareCaption,
  buildWhatsAppShareUrl,
  canNativeShareFiles,
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

type Flash =
  | 'copied-caption'
  | 'saved-instagram'
  | 'saved-facebook'
  | 'whatsapp'
  | 'shared'
  | null

export function ShareSheet({ open, onClose, payload }: Props) {
  const titleId = useId()
  const [flash, setFlash] = useState<Flash>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const effective: SharePayload = payload ?? { kind: 'look' }
  const caption = buildShareCaption(effective)
  const hasImage = Boolean(effective.imageUrl)
  const nativeOk = canUseNativeShare()
  const nativeFilesOk = hasImage && canNativeShareFiles()
  const sheetTitle =
    effective.kind === 'look' && hasImage ? 'Share your look' : 'Share FashionRise'

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
    const t = window.setTimeout(() => setFlash(null), 2800)
    return () => window.clearTimeout(t)
  }, [flash])

  if (!open) return null

  const flashLabel =
    flash === 'copied-caption'
      ? 'Caption copied'
      : flash === 'saved-instagram'
        ? 'Image saved + caption copied — paste into your Instagram post'
        : flash === 'saved-facebook'
          ? 'Image saved + caption copied — paste into your Facebook post'
          : flash === 'whatsapp'
            ? 'Opening WhatsApp with your caption'
            : flash === 'shared'
              ? 'Opened share sheet — pick WhatsApp, Instagram, or Facebook'
              : null

  async function prepareCaptionAndImage(channel: 'instagram' | 'facebook') {
    await copyText(caption)
    if (effective.imageUrl) {
      await downloadImageFromUrl(
        effective.imageUrl,
        effective.imageFileName ?? 'fashionrise-look.png',
      )
    }
    setFlash(channel === 'instagram' ? 'saved-instagram' : 'saved-facebook')
  }

  async function onWhatsApp() {
    setBusy(true)
    setError(null)
    try {
      // Prefer OS share with the look image when available (mobile WhatsApp target).
      if (nativeFilesOk) {
        const result = await shareNative(effective)
        if (result === 'shared') {
          setFlash('shared')
          return
        }
        if (result === 'cancelled') return
      }
      await copyText(caption)
      if (effective.imageUrl) {
        try {
          await downloadImageFromUrl(
            effective.imageUrl,
            effective.imageFileName ?? 'fashionrise-look.png',
          )
        } catch {
          // Text-only WhatsApp is still useful.
        }
      }
      setFlash('whatsapp')
      window.open(buildWhatsAppShareUrl(caption), '_blank', 'noopener,noreferrer')
    } catch {
      setError('Could not open WhatsApp. Copy the caption and share the saved image instead.')
    } finally {
      setBusy(false)
    }
  }

  async function onInstagram() {
    setBusy(true)
    setError(null)
    try {
      if (nativeFilesOk) {
        const result = await shareNative(effective)
        if (result === 'shared') {
          setFlash('shared')
          return
        }
        if (result === 'cancelled') return
      }
      await prepareCaptionAndImage('instagram')
      window.open(buildInstagramCreateUrl(), '_blank', 'noopener,noreferrer')
    } catch {
      setError('Caption copied if possible — open Instagram and paste when you post.')
      window.open(buildInstagramCreateUrl(), '_blank', 'noopener,noreferrer')
    } finally {
      setBusy(false)
    }
  }

  async function onFacebook() {
    setBusy(true)
    setError(null)
    try {
      if (nativeFilesOk) {
        const result = await shareNative(effective)
        if (result === 'shared') {
          setFlash('shared')
          return
        }
        if (result === 'cancelled') return
      }
      await prepareCaptionAndImage('facebook')
      window.open(buildFacebookShareUrl(FASHIONRISE_PUBLIC_URL), '_blank', 'noopener,noreferrer')
    } catch {
      setError('Open Facebook and paste the caption with your saved look image.')
      window.open(buildFacebookShareUrl(FASHIONRISE_PUBLIC_URL), '_blank', 'noopener,noreferrer')
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

  async function onCopyCaption() {
    setBusy(true)
    setError(null)
    try {
      await copyText(caption)
      setFlash('copied-caption')
    } catch {
      setError('Could not copy caption.')
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
            <h2 id={titleId}>{sheetTitle}</h2>
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

        {hasImage ? (
          <div className={styles.preview}>
            <img src={effective.imageUrl!} alt="Look to share" />
          </div>
        ) : null}

        <p className={styles.hint}>
          Post your AI look with a FashionRise caption. WhatsApp can take the text (and the image
          on phones). Instagram and Facebook need you to paste the caption onto a new post after we
          save the image.
        </p>

        <pre className={styles.caption} data-testid="share-caption" aria-label="Share caption">
          {caption}
        </pre>

        <div className={styles.channels} role="group" aria-label="Share to">
          <button
            type="button"
            className={`${styles.channel} ${styles.channelPrimary}`}
            disabled={busy}
            onClick={() => void onWhatsApp()}
            data-testid="share-whatsapp"
          >
            <MessageCircle size={18} aria-hidden />
            <span>WhatsApp</span>
            <small>{nativeFilesOk ? 'Look + caption' : 'Caption ready to send'}</small>
          </button>
          <button
            type="button"
            className={`${styles.channel} ${styles.channelPrimary}`}
            disabled={busy}
            onClick={() => void onInstagram()}
            data-testid="share-instagram"
          >
            <AtSign size={18} aria-hidden />
            <span>Instagram post</span>
            <small>{hasImage ? 'Save image + copy caption' : 'Copy caption + open'}</small>
          </button>
          <button
            type="button"
            className={`${styles.channel} ${styles.channelPrimary}`}
            disabled={busy}
            onClick={() => void onFacebook()}
            data-testid="share-facebook"
          >
            <Share2 size={18} aria-hidden />
            <span>Facebook post</span>
            <small>{hasImage ? 'Save image + copy caption' : 'Share FashionRise link'}</small>
          </button>
          {nativeOk ? (
            <button
              type="button"
              className={styles.channel}
              disabled={busy}
              onClick={() => void onSystemShare()}
              data-testid="share-system"
            >
              <Share2 size={18} aria-hidden />
              <span>More apps</span>
              <small>Device share sheet</small>
            </button>
          ) : null}
          <button
            type="button"
            className={styles.channel}
            disabled={busy}
            onClick={() => void onCopyCaption()}
            data-testid="share-copy-caption"
          >
            <Copy size={18} aria-hidden />
            <span>Copy caption</span>
            <small>Created with FashionRise…</small>
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
                    setFlash('saved-instagram')
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
              <small>For your post</small>
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
