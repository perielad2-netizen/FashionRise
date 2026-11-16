/** Premium paint-tool glyphs with glow / gradient for Studio Create. */
import { useId, type ReactNode } from 'react'

type IconProps = {
  size?: number
  className?: string
  /** Soft outer glow (active tools). */
  glow?: boolean
}

function Svg({
  size = 22,
  className,
  children,
}: {
  size?: number
  className?: string
  children: ReactNode
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden
      style={{ overflow: 'visible' }}
    >
      {children}
    </svg>
  )
}

function GlowDefs({ id, color }: { id: string; color: string }) {
  return (
    <defs>
      <filter id={id} x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="1.6" result="b" />
        <feMerge>
          <feMergeNode in="b" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
      <linearGradient id={`${id}-g`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#fff" stopOpacity="0.95" />
        <stop offset="45%" stopColor={color} stopOpacity="0.95" />
        <stop offset="100%" stopColor="#f9a8d4" stopOpacity="0.9" />
      </linearGradient>
    </defs>
  )
}

/** Tapered ink pen with pink tip glow. */
export function PenToolIcon({ size = 22, className, glow }: IconProps) {
  const uid = useId().replace(/:/g, '')
  const fid = `pen-${uid}`
  return (
    <Svg size={size} className={className}>
      <GlowDefs id={fid} color="#f472b6" />
      <g filter={glow ? `url(#${fid})` : undefined}>
        <path
          d="M14.1 3.2c.75-.75 2-.75 2.75 0l3.95 3.95c.75.75.75 2 0 2.75L9.55 21.2H3.8v-5.75L14.1 3.2Z"
          fill={`url(#${fid}-g)`}
          opacity="0.28"
        />
        <path
          d="M14.1 3.2c.75-.75 2-.75 2.75 0l3.95 3.95c.75.75.75 2 0 2.75L9.55 21.2H3.8v-5.75L14.1 3.2Z"
          stroke={`url(#${fid}-g)`}
          strokeWidth="1.7"
          strokeLinejoin="round"
        />
        <path
          d="M12.85 5.15 18.9 11.2"
          stroke="#fff"
          strokeWidth="1.35"
          strokeLinecap="round"
          opacity="0.55"
        />
        <path d="M3.8 21.2h5.75L3.8 15.45V21.2Z" fill="#f472b6" />
        <circle cx="5.35" cy="19.65" r="1.05" fill="#ffe4f1" />
      </g>
    </Svg>
  )
}

/** Soft eraser block with rose bevel + glow. */
export function EraserToolIcon({ size = 22, className, glow }: IconProps) {
  const uid = useId().replace(/:/g, '')
  const fid = `er-${uid}`
  return (
    <Svg size={size} className={className}>
      <GlowDefs id={fid} color="#fb7185" />
      <g filter={glow ? `url(#${fid})` : undefined}>
        <rect
          x="4"
          y="8"
          width="16"
          height="9.5"
          rx="2.4"
          transform="rotate(-18 12 12.75)"
          fill="#fda4af"
          opacity="0.35"
        />
        <rect
          x="4"
          y="8"
          width="16"
          height="9.5"
          rx="2.4"
          transform="rotate(-18 12 12.75)"
          stroke={`url(#${fid}-g)`}
          strokeWidth="1.65"
        />
        <path
          d="M6.9 16.9 16.4 13.7"
          stroke="#fff"
          strokeWidth="1.3"
          strokeLinecap="round"
          opacity="0.55"
        />
        <path
          d="M7.6 14.2 17.1 11"
          stroke="#fb7185"
          strokeWidth="1.45"
          strokeLinecap="round"
          opacity="0.9"
        />
      </g>
    </Svg>
  )
}

/** Paint bucket with dripping pink fill. */
export function FillToolIcon({ size = 22, className, glow }: IconProps) {
  const uid = useId().replace(/:/g, '')
  const fid = `fill-${uid}`
  return (
    <Svg size={size} className={className}>
      <GlowDefs id={fid} color="#ec4899" />
      <g filter={glow ? `url(#${fid})` : undefined}>
        <path
          d="M8 9.1 14.7 4.4a1.45 1.45 0 0 1 2 .25l2.55 3.2a1.45 1.45 0 0 1-.25 2.05L12.3 15.1"
          stroke={`url(#${fid}-g)`}
          strokeWidth="1.6"
          strokeLinejoin="round"
          fill={`url(#${fid}-g)`}
          fillOpacity="0.22"
        />
        <path
          d="M7 10.5h9.8v5.4c0 1.85-1.55 3.25-3.45 3.25H10.45C8.55 19.15 7 17.75 7 15.9v-5.4Z"
          fill={`url(#${fid}-g)`}
        />
        <path
          d="M12.15 19c0 1.45-.85 2.45-1.8 2.45S8.55 20.45 8.55 19"
          stroke="#f9a8d4"
          strokeWidth="1.55"
          strokeLinecap="round"
        />
        <circle cx="10.35" cy="21.35" r="1.15" fill="#f472b6" />
      </g>
    </Svg>
  )
}

/** Eyedropper with gold tip accent. */
export function EyedropperToolIcon({ size = 22, className, glow }: IconProps) {
  const uid = useId().replace(/:/g, '')
  const fid = `eye-${uid}`
  return (
    <Svg size={size} className={className}>
      <GlowDefs id={fid} color="#fbbf24" />
      <g filter={glow ? `url(#${fid})` : undefined}>
        <path
          d="M14.55 4c.85-.85 2.25-.85 3.1 0l2.35 2.35c.85.85.85 2.25 0 3.1l-1.45 1.45-5.45-5.45L14.55 4Z"
          fill="#fbbf24"
          opacity="0.95"
        />
        <path
          d="M12.45 6.7 17.2 11.45"
          stroke="#fff"
          strokeWidth="1.45"
          strokeLinecap="round"
          opacity="0.55"
        />
        <path
          d="M3.6 20.35 11.5 12.45l2.35 2.35-7.9 7.9H3.6v-2.35Z"
          stroke={`url(#${fid}-g)`}
          strokeWidth="1.6"
          strokeLinejoin="round"
          fill="#f472b6"
          fillOpacity="0.35"
        />
        <circle cx="5.1" cy="19.1" r="1.2" fill="#fce7f3" />
      </g>
    </Svg>
  )
}

export function AirbrushKindIcon({ size = 14, className }: IconProps) {
  const uid = useId().replace(/:/g, '')
  return (
    <Svg size={size} className={className}>
      <defs>
        <radialGradient id={`air-${uid}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff" />
          <stop offset="55%" stopColor="#f9a8d4" />
          <stop offset="100%" stopColor="#db2777" stopOpacity="0.2" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="8" fill={`url(#air-${uid})`} />
      <circle cx="12" cy="12" r="2.2" fill="#fff" />
    </Svg>
  )
}

export function CharcoalKindIcon({ size = 14, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M6.8 18.8 16.6 5.2c.45-.55 1.3-.45 1.6.2l.85 1.5c.35.65 0 1.4-.55 1.75L8.7 20.6c-.55.35-1.3.1-1.55-.5l-.85-1.55c-.25-.45 0-.95.5-1.1Z"
        fill="#e7e5e4"
      />
      <path d="M7.4 19.4 9 17.2" stroke="#a8a29e" strokeWidth="1.2" strokeLinecap="round" />
    </Svg>
  )
}

export function InkKindIcon({ size = 14, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path d="M12 3.2 14.4 12.2H9.6L12 3.2Z" fill="#f9a8d4" />
      <rect x="9.2" y="12" width="5.6" height="8.2" rx="1.5" fill="#fff" opacity="0.9" />
      <path d="M12 3.2 12.7 6.2" stroke="#fff" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
    </Svg>
  )
}

/** Dock tab glyphs */
export function ModelsDockIcon({ size = 16, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <circle cx="12" cy="7.2" r="3.1" stroke="#f9a8d4" strokeWidth="1.5" fill="#f472b6" fillOpacity="0.25" />
      <path
        d="M5.5 19.5c.8-3.4 3.1-5.2 6.5-5.2s5.7 1.8 6.5 5.2"
        stroke="#f9a8d4"
        strokeWidth="1.55"
        strokeLinecap="round"
      />
    </Svg>
  )
}

export function BrushDockIcon({ size = 16, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <path
        d="M7.2 16.8c1.6-1.1 4.2-3.8 5.6-5.4l2.8 2.8c-1.6 1.4-4.3 4-5.5 5.5-.7.9-2.1.7-2.7-.2l-.6-1.1c-.4-.7-.2-1.5.4-1.6Z"
        fill="#f472b6"
      />
      <path
        d="M13.4 10.8 17.6 6.6c.7-.7 1.8-.7 2.5 0 .7.7.7 1.8 0 2.5L15.9 13.3"
        stroke="#fce7f3"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </Svg>
  )
}

export function MaterialsDockIcon({ size = 16, className }: IconProps) {
  return (
    <Svg size={size} className={className}>
      <rect x="4.2" y="4.2" width="7" height="7" rx="1.8" fill="#f472b6" opacity="0.85" />
      <rect x="12.8" y="4.2" width="7" height="7" rx="1.8" fill="#38bdf8" opacity="0.75" />
      <rect x="4.2" y="12.8" width="7" height="7" rx="1.8" fill="#fbbf24" opacity="0.8" />
      <rect x="12.8" y="12.8" width="7" height="7" rx="1.8" fill="#a78bfa" opacity="0.75" />
    </Svg>
  )
}
