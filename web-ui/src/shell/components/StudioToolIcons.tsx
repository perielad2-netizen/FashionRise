/** Premium paint-tool glyphs for Studio Create (skeuomorphic-lite SVG). */
import type { ReactNode } from 'react'

type IconProps = {
  size?: number
  className?: string
  title?: string
}

function Svg({
  size = 20,
  className,
  title,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  )
}

/** Tapered ink pen — primary draw tool. */
export function PenToolIcon({ size, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M14.2 3.4c.7-.7 1.9-.7 2.6 0l3.8 3.8c.7.7.7 1.9 0 2.6L9.4 21H4v-5.4L14.2 3.4Z"
        fill="currentColor"
        opacity="0.22"
      />
      <path
        d="M14.2 3.4c.7-.7 1.9-.7 2.6 0l3.8 3.8c.7.7.7 1.9 0 2.6L9.4 21H4v-5.4L14.2 3.4Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M12.8 5.2 18.8 11.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        opacity="0.55"
      />
      <path d="M4 21h5.4L4 15.6V21Z" fill="currentColor" opacity="0.9" />
    </Svg>
  )
}

/** Soft pink eraser block with bevel. */
export function EraserToolIcon({ size, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <rect
        x="4.2"
        y="8.2"
        width="15.6"
        height="9.2"
        rx="2.2"
        transform="rotate(-18 12 12.8)"
        fill="currentColor"
        opacity="0.2"
      />
      <rect
        x="4.2"
        y="8.2"
        width="15.6"
        height="9.2"
        rx="2.2"
        transform="rotate(-18 12 12.8)"
        stroke="currentColor"
        strokeWidth="1.55"
      />
      <path
        d="M7.2 14.6 16.4 11.6"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
        opacity="0.45"
      />
      <path
        d="M6.4 17.1 15.8 14"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity="0.7"
      />
    </Svg>
  )
}

/** Paint bucket with drip for fill. */
export function FillToolIcon({ size, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M8.2 9.2 14.8 4.6a1.4 1.4 0 0 1 1.9.2l2.5 3.1a1.4 1.4 0 0 1-.2 2L12.4 15"
        stroke="currentColor"
        strokeWidth="1.55"
        strokeLinejoin="round"
        fill="currentColor"
        fillOpacity="0.16"
      />
      <path
        d="M7.2 10.4h9.4v5.2c0 1.7-1.5 3.1-3.3 3.1H10.5c-1.8 0-3.3-1.4-3.3-3.1v-5.2Z"
        fill="currentColor"
        opacity="0.88"
      />
      <path
        d="M12.2 18.8c0 1.3-.8 2.2-1.7 2.2s-1.6-.9-1.6-2.2"
        stroke="currentColor"
        strokeWidth="1.45"
        strokeLinecap="round"
      />
    </Svg>
  )
}

/** Eyedropper / pipette. */
export function EyedropperToolIcon({ size, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M14.6 4.2c.8-.8 2.1-.8 2.9 0l2.3 2.3c.8.8.8 2.1 0 2.9l-1.4 1.4-5.2-5.2 1.4-1.4Z"
        fill="currentColor"
        opacity="0.85"
      />
      <path
        d="M12.6 6.8 17.2 11.4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M3.8 20.2 11.4 12.6l2.2 2.2-7.6 7.6H3.8v-2.2Z"
        stroke="currentColor"
        strokeWidth="1.55"
        strokeLinejoin="round"
        fill="currentColor"
        fillOpacity="0.18"
      />
    </Svg>
  )
}

/** Soft airbrush halo for brush kind. */
export function AirbrushKindIcon({ size = 14, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.4" opacity="0.35" />
      <circle cx="12" cy="12" r="4.2" fill="currentColor" opacity="0.85" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    </Svg>
  )
}

/** Charcoal stick glyph. */
export function CharcoalKindIcon({ size = 14, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M7 18.5 16.5 5.5c.4-.5 1.2-.4 1.5.2l.8 1.4c.3.6 0 1.3-.5 1.6L8.8 20.2c-.5.3-1.2.1-1.5-.4L6.5 18.4c-.2-.4 0-.9.5-1Z"
        fill="currentColor"
        opacity="0.9"
      />
    </Svg>
  )
}

/** Fine ink tip for brush kind. */
export function InkKindIcon({ size = 14, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path d="M12 3.5 14.2 12H9.8L12 3.5Z" fill="currentColor" />
      <rect x="9.4" y="12" width="5.2" height="8" rx="1.4" fill="currentColor" opacity="0.75" />
    </Svg>
  )
}
