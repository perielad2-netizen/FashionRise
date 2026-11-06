import { useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'
import {
  clamp,
  hexToHsv,
  hexToRgb,
  hsvToHex,
  hueToCss,
  normalizeHex,
  rgbToHex,
  type Hsv,
} from '@/lib/colorPicker'
import styles from './ProfessionalColorPicker.module.css'

type Props = {
  open: boolean
  initialColor: string
  onApply: (hex: string) => void
  onCancel: () => void
}

type Draft = {
  hsv: Hsv
  hex: string
  r: number
  g: number
  b: number
  hexDraft: string
}

function draftFromHex(hex: string): Draft {
  const normalized = normalizeHex(hex) ?? '#1C1C1E'
  const hsv = hexToHsv(normalized) ?? { h: 0, s: 0, v: 0.11 }
  const rgb = hexToRgb(normalized) ?? { r: 28, g: 28, b: 30 }
  return {
    hsv,
    hex: normalized,
    r: rgb.r,
    g: rgb.g,
    b: rgb.b,
    hexDraft: normalized,
  }
}

function draftFromHsv(hsv: Hsv, previousHue = 0): Draft {
  const s = clamp(hsv.s, 0, 1)
  const v = clamp(hsv.v, 0, 1)
  const h = s === 0 ? previousHue : (((hsv.h % 360) + 360) % 360)
  const next: Hsv = { h, s, v }
  const hex = hsvToHex(next)
  const rgb = hexToRgb(hex)!
  return {
    hsv: next,
    hex,
    r: rgb.r,
    g: rgb.g,
    b: rgb.b,
    hexDraft: hex,
  }
}

export function ProfessionalColorPicker({ open, initialColor, onApply, onCancel }: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const svRef = useRef<HTMLDivElement>(null)
  const hueRef = useRef<HTMLDivElement>(null)
  const [original, setOriginal] = useState(() => normalizeHex(initialColor) ?? '#1C1C1E')
  const [draft, setDraft] = useState<Draft>(() => draftFromHex(initialColor))
  const hueRefState = useRef(draft.hsv.h)

  useEffect(() => {
    if (!open) return
    const next = draftFromHex(initialColor)
    setOriginal(normalizeHex(initialColor) ?? '#1C1C1E')
    setDraft(next)
    hueRefState.current = next.hsv.h
  }, [open, initialColor])

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const node = dialogRef.current
    const applyBtn = node?.querySelector<HTMLButtonElement>('button[data-action="apply"]')
    ;(applyBtn ?? node)?.focus()
    return () => {
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onCancel()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, onCancel])

  if (!open) return null

  const setFromHsv = (hsv: Partial<Hsv>) => {
    setDraft((prev) => {
      const merged = { ...prev.hsv, ...hsv }
      if (typeof hsv.h === 'number') hueRefState.current = (((hsv.h % 360) + 360) % 360)
      const next = draftFromHsv(merged, hueRefState.current)
      if (next.hsv.s > 0) hueRefState.current = next.hsv.h
      return { ...next, hsv: { ...next.hsv, h: hueRefState.current } }
    })
  }

  const pointerFraction = (
    el: HTMLElement,
    clientX: number,
    clientY: number,
  ): { x: number; y: number } => {
    const rect = el.getBoundingClientRect()
    const x = clamp((clientX - rect.left) / Math.max(rect.width, 1), 0, 1)
    const y = clamp((clientY - rect.top) / Math.max(rect.height, 1), 0, 1)
    return { x, y }
  }

  const bindDrag = (
    el: HTMLElement,
    pointerId: number,
    move: (clientX: number, clientY: number) => void,
  ) => {
    el.setPointerCapture(pointerId)
    const onMove = (event: PointerEvent) => {
      event.preventDefault()
      move(event.clientX, event.clientY)
    }
    const onUp = () => {
      el.releasePointerCapture(pointerId)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointercancel', onUp)
    }
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
  }

  const onSvPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const el = svRef.current
    if (!el) return
    const apply = (clientX: number, clientY: number) => {
      const { x, y } = pointerFraction(el, clientX, clientY)
      setFromHsv({ s: x, v: 1 - y })
    }
    apply(event.clientX, event.clientY)
    bindDrag(el, event.pointerId, apply)
  }

  const onHuePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const el = hueRef.current
    if (!el) return
    const apply = (clientX: number, clientY: number) => {
      const { x } = pointerFraction(el, clientX, clientY)
      setFromHsv({ h: x * 360 })
    }
    apply(event.clientX, event.clientY)
    bindDrag(el, event.pointerId, apply)
  }

  const commitHexDraft = () => {
    const normalized = normalizeHex(draft.hexDraft)
    if (!normalized) {
      setDraft((prev) => ({ ...prev, hexDraft: prev.hex }))
      return
    }
    const next = draftFromHex(normalized)
    hueRefState.current = next.hsv.s > 0 ? next.hsv.h : hueRefState.current
    setDraft({
      ...next,
      hsv: { ...next.hsv, h: next.hsv.s > 0 ? next.hsv.h : hueRefState.current },
    })
  }

  const setChannel = (channel: 'r' | 'g' | 'b', raw: string) => {
    const n = Number.parseInt(raw, 10)
    if (!Number.isFinite(n)) return
    const value = clamp(n, 0, 255)
    setDraft((prev) => {
      const rgb = { r: prev.r, g: prev.g, b: prev.b, [channel]: value }
      const hex = rgbToHex(rgb)
      const hsv = hexToHsv(hex) ?? prev.hsv
      if (hsv.s > 0) hueRefState.current = hsv.h
      return {
        hsv: { ...hsv, h: hsv.s > 0 ? hsv.h : hueRefState.current },
        hex,
        r: rgb.r,
        g: rgb.g,
        b: rgb.b,
        hexDraft: hex,
      }
    })
  }

  const content = (
    <div
      className={styles.scrim}
      role="presentation"
      onPointerDown={(e) => {
        e.stopPropagation()
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className={styles.title}>
          Choose color
        </h2>

        <div
          ref={svRef}
          className={styles.svWrap}
          style={{ backgroundColor: hueToCss(draft.hsv.h) }}
          role="slider"
          aria-label="Saturation and brightness"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(draft.hsv.s * 100)}
          tabIndex={0}
          onPointerDown={onSvPointerDown}
          onKeyDown={(e) => {
            const step = e.shiftKey ? 0.08 : 0.02
            if (e.key === 'ArrowRight') {
              e.preventDefault()
              setFromHsv({ s: draft.hsv.s + step })
            } else if (e.key === 'ArrowLeft') {
              e.preventDefault()
              setFromHsv({ s: draft.hsv.s - step })
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setFromHsv({ v: draft.hsv.v + step })
            } else if (e.key === 'ArrowDown') {
              e.preventDefault()
              setFromHsv({ v: draft.hsv.v - step })
            }
          }}
        >
          <div className={styles.svWhite} />
          <div className={styles.svBlack} />
          <div
            className={styles.svThumb}
            style={{
              left: `${draft.hsv.s * 100}%`,
              top: `${(1 - draft.hsv.v) * 100}%`,
              background: draft.hex,
            }}
          />
        </div>

        <div
          ref={hueRef}
          className={styles.hueWrap}
          role="slider"
          aria-label="Hue"
          aria-valuemin={0}
          aria-valuemax={360}
          aria-valuenow={Math.round(draft.hsv.h)}
          tabIndex={0}
          onPointerDown={onHuePointerDown}
          onKeyDown={(e) => {
            const step = e.shiftKey ? 12 : 2
            if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
              e.preventDefault()
              setFromHsv({ h: draft.hsv.h + step })
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
              e.preventDefault()
              setFromHsv({ h: draft.hsv.h - step })
            }
          }}
        >
          <div
            className={styles.hueThumb}
            style={{
              left: `${(draft.hsv.h / 360) * 100}%`,
              background: hueToCss(draft.hsv.h),
            }}
          />
        </div>

        <div className={styles.compare} aria-label="Color comparison">
          <div className={styles.compareSwatch} style={{ background: original }}>
            Current
          </div>
          <div className={styles.compareSwatch} style={{ background: draft.hex }}>
            New
          </div>
        </div>

        <div className={styles.fields}>
          <div className={styles.hexRow}>
            <span className={styles.label}>Hex</span>
            <input
              className={styles.input}
              value={draft.hexDraft}
              aria-label="Hex color"
              spellCheck={false}
              onChange={(e) => setDraft((prev) => ({ ...prev, hexDraft: e.target.value }))}
              onBlur={commitHexDraft}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  commitHexDraft()
                }
              }}
            />
          </div>
          <div className={styles.rgbRow}>
            {(
              [
                ['r', draft.r, 'Red'],
                ['g', draft.g, 'Green'],
                ['b', draft.b, 'Blue'],
              ] as const
            ).map(([channel, value, label]) => (
              <label key={channel} className={styles.field}>
                <span className={styles.label}>{label}</span>
                <input
                  className={styles.input}
                  type="number"
                  min={0}
                  max={255}
                  value={value}
                  aria-label={label}
                  onChange={(e) => setChannel(channel, e.target.value)}
                />
              </label>
            ))}
          </div>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.cancel} onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.apply}
            data-action="apply"
            onClick={() => onApply(draft.hex)}
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
