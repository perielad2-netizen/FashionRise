import { useEffect, useId, useState } from 'react'
import { Check, Copy, Download, MessageCircle, Share2, X } from 'lucide-react'
import {
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

type Flash = 'copied-caption' | 'saved-image' | 'shared' | 'whatsapp' | null

/**
 * Fallback share UI for browsers without the Web Share API (mostly desktop).
 * On phones, callers should call `requestShare` first and only open this sheet
 * when that returns `needs-fallback`.
 */
export function ShareSheet({ open, onClose, payload }: Props) {
  const titleId = useId()
  const [flash, setFlash] = useState<Flash>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const effective: SharePayload = payload ?? { kind: 'look' }
  const caption = buildShareCaption(effective)
  const hasImage = Boolean(effective.imageUrl)
  const nativeOk = canUseNativeShare()
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
      : flash === 'saved-image'
        ? 'Image saved — attach it when you post'
        : flash === 'shared'
          ? 'Opened share options — pick an app'
          : flash === 'whatsapp'
            ? 'Opening WhatsApp with your caption'
            : null

  async function onShare() {
    setBusy(true)
    setError(null)
    try {
      if (nativeOk) {
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
          setFlash('saved-image')
        } catch {
          setFlash('copied-caption')
        }
      } else {
        setFlash('copied-caption')
      }
    } catch {
      setError('Could not prepare share. Copy the caption and save the image instead.')
    } finally {
      setBusy(false)
    }
  }

  async function onWhatsApp() {
    setBusy(true)
    setError(null)
    try {
      await copyText(caption)
      setFlash('whatsapp')
      window.open(buildWhatsAppShareUrl(caption), '_blank', 'noopener,noreferrer')
    } catch {
      setError('Could not open WhatsApp. Copy the caption instead.')
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

  async function onSaveImage() {
    if (!effective.imageUrl) return
    setBusy(true)
    setError(null)
    try {
      await downloadImageFromUrl(
        effective.imageUrl,
        effective.imageFileName ?? 'fashionrise-look.png',
      )
      setFlash('saved-image')
    } catch {
      setError('Could not download the look image.')
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
          {nativeOk
            ? 'Share opens your device’s share menu so you can pick WhatsApp, Instagram, Facebook, or any other app.'
            : 'Copy the FashionRise caption, save the look image, then paste both into the app you want to post with.'}
        </p>

        <pre className={styles.caption} data-testid="share-caption" aria-label="Share caption">
          {caption}
        </pre>

        <div className={styles.actions} role="group" aria-label="Share actions">
          <button
            type="button"
            className={`${styles.action} ${styles.actionPrimary}`}
            disabled={busy}
            onClick={() => void onShare()}
            data-testid="share-primary"
          >
            <Share2 size={18} aria-hidden />
            <span>{nativeOk ? 'Share…' : 'Copy caption & save image'}</span>
            <small>
              {nativeOk
                ? 'Choose WhatsApp, Instagram, Facebook…'
                : 'Created with FashionRise'}
            </small>
          </button>
          <button
            type="button"
            className={styles.action}
            disabled={busy}
            onClick={() => void onWhatsApp()}
            data-testid="share-whatsapp"
          >
            <MessageCircle size={18} aria-hidden />
            <span>WhatsApp text</span>
            <small>Opens chat with caption</small>
          </button>
          <button
            type="button"
            className={styles.action}
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
              className={styles.action}
              disabled={busy}
              onClick={() => void onSaveImage()}
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
