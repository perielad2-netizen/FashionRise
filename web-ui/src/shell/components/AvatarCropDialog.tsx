import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import styles from './AvatarCropDialog.module.css'

type Props = {
  file: File
  onCancel: () => void
  onConfirm: (cropped: File) => void
  busy?: boolean
}

const OUTPUT_PX = 512
const VIEWPORT_PX = 280
const MIN_SCALE = 1
const MAX_SCALE = 3

/**
 * Square move/scale crop before uploading a FashionRise profile photo.
 */
export function AvatarCropDialog({ file, onCancel, onConfirm, busy = false }: Props) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const dragRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    originX: number
    originY: number
  } | null>(null)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    if (!objectUrl) return
    const img = new Image()
    img.onload = () => setNatural({ w: img.naturalWidth, h: img.naturalHeight })
    img.onerror = () => setNatural(null)
    img.src = objectUrl
  }, [objectUrl])

  const coverScale = useMemo(() => {
    if (!natural) return 1
    return Math.max(VIEWPORT_PX / natural.w, VIEWPORT_PX / natural.h)
  }, [natural])

  const displayScale = coverScale * scale

  const clampOffset = (next: { x: number; y: number }, nextScale = scale) => {
    if (!natural) return next
    const dw = natural.w * coverScale * nextScale
    const dh = natural.h * coverScale * nextScale
    const maxX = Math.max(0, (dw - VIEWPORT_PX) / 2)
    const maxY = Math.max(0, (dh - VIEWPORT_PX) / 2)
    return {
      x: Math.min(maxX, Math.max(-maxX, next.x)),
      y: Math.min(maxY, Math.max(-maxY, next.y)),
    }
  }

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (busy) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      originX: offset.x,
      originY: offset.y,
    }
  }

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== e.pointerId) return
    setOffset(
      clampOffset({
        x: drag.originX + (e.clientX - drag.startX),
        y: drag.originY + (e.clientY - drag.startY),
      }),
    )
  }

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === e.pointerId) dragRef.current = null
  }

  const onScaleChange = (value: number) => {
    const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
    setScale(next)
    setOffset((prev) => clampOffset(prev, next))
  }

  const exportCropped = async () => {
    if (!natural || !objectUrl || busy) return
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('Could not load image'))
      el.src = objectUrl
    })
    const canvas = document.createElement('canvas')
    canvas.width = OUTPUT_PX
    canvas.height = OUTPUT_PX
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#0c0c10'
    ctx.fillRect(0, 0, OUTPUT_PX, OUTPUT_PX)

    const drawW = natural.w * displayScale
    const drawH = natural.h * displayScale
    const dx = (VIEWPORT_PX - drawW) / 2 + offset.x
    const dy = (VIEWPORT_PX - drawH) / 2 + offset.y
    const scaleOut = OUTPUT_PX / VIEWPORT_PX
    ctx.drawImage(img, dx * scaleOut, dy * scaleOut, drawW * scaleOut, drawH * scaleOut)

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92),
    )
    if (!blob) return
    onConfirm(new File([blob], 'avatar.jpg', { type: 'image/jpeg' }))
  }

  return (
    <div className={styles.backdrop} role="presentation">
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="avatar-crop-title"
        data-testid="avatar-crop-dialog"
      >
        <h2 id="avatar-crop-title" className={styles.title}>
          Adjust photo
        </h2>
        <p className={styles.hint}>Drag to move. Pinch the slider to zoom. Frame what others will see.</p>
        <div
          ref={viewportRef}
          className={styles.viewport}
          style={{ width: VIEWPORT_PX }}
          data-testid="avatar-crop-viewport"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          {objectUrl && natural ? (
            <img
              src={objectUrl}
              alt=""
              draggable={false}
              className={styles.image}
              style={{
                width: natural.w * displayScale,
                height: natural.h * displayScale,
                transform: `translate(-50%, -50%) translate(${offset.x}px, ${offset.y}px)`,
              }}
            />
          ) : (
            <p className={styles.loading}>Loading…</p>
          )}
        </div>
        <label className={styles.zoomLabel}>
          Zoom
          <input
            type="range"
            min={MIN_SCALE}
            max={MAX_SCALE}
            step={0.01}
            value={scale}
            disabled={busy || !natural}
            data-testid="avatar-crop-zoom"
            onChange={(e) => onScaleChange(Number(e.target.value))}
          />
        </label>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.ghost}
            disabled={busy}
            onClick={onCancel}
            data-testid="avatar-crop-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            className={styles.primary}
            disabled={busy || !natural}
            onClick={() => void exportCropped()}
            data-testid="avatar-crop-confirm"
          >
            {busy ? 'Uploading…' : 'Use photo'}
          </button>
        </div>
      </div>
    </div>
  )
}
