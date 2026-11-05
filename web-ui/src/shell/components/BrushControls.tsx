import { useMemo, useState } from 'react'
import type { BrushEngineState, BrushKind, LogicalLayer, StrokeBlendMode } from '@/lib/professionalBrushes'
import type { ToolKind } from '@/lib/strokes'
import { BrushSizeControl } from '@/shell/components/BrushSizeControl'
import styles from './BrushControls.module.css'

type Props = {
  tool: ToolKind
  brushSize: number
  opacity: number
  brushEngine?: BrushEngineState
  /** `flat` embeds into SettingsInspector without the floating sheet chrome. */
  variant?: 'sheet' | 'flat'
  onBrushSize: (px: number) => void
  onOpacity: (value: number) => void
  onBrushKind?: (kind: BrushKind) => void
  onBrushEnginePatch?: (patch: Partial<BrushEngineState>) => void
}

const BRUSH_OPTIONS: Array<{ id: BrushKind; label: string; hint: string }> = [
  { id: 'tapered', label: 'Ink', hint: 'Tapered pencil / seams' },
  { id: 'charcoal', label: 'Charcoal', hint: 'Smooth fabric shadow' },
  { id: 'airbrush', label: 'Airbrush', hint: 'Soft shade & volume' },
]

const LAYER_OPTIONS: Array<{ id: LogicalLayer; label: string }> = [
  { id: 'ink', label: 'Ink' },
  { id: 'shade', label: 'Shadows' },
  { id: 'highlight', label: 'Highlights' },
]

const BLEND_OPTIONS: Array<{ id: StrokeBlendMode; label: string }> = [
  { id: 'source-over', label: 'Normal' },
  { id: 'multiply', label: 'Multiply' },
  { id: 'soft-light', label: 'Soft light' },
  { id: 'screen', label: 'Screen' },
]

function BrushPreview({ kind }: { kind: BrushKind }) {
  const path = useMemo(() => {
    if (kind === 'tapered') {
      return 'M8 22 C 40 8, 70 8, 112 22'
    }
    if (kind === 'charcoal') {
      return 'M10 22 C 40 12, 70 12, 110 22'
    }
    return 'M8 22 C 40 14, 70 14, 112 22'
  }, [kind])
  return (
    <svg className={styles.preview} viewBox="0 0 120 36" aria-hidden="true">
      {kind === 'airbrush' || kind === 'charcoal' ? (
        <path
          d={path}
          fill="none"
          stroke="currentColor"
          strokeWidth={kind === 'charcoal' ? 16 : 14}
          strokeLinecap="round"
          opacity={kind === 'charcoal' ? 0.18 : 0.22}
        />
      ) : null}
      {kind === 'charcoal' ? (
        <>
          {/* Soft width fade (away from hard edge). */}
          <path
            d="M18 10 C 48 6, 78 8, 108 14"
            fill="none"
            stroke="currentColor"
            strokeWidth={14}
            strokeLinecap="round"
            opacity={0.12}
          />
          <path
            d="M16 14 C 48 10, 78 12, 106 18"
            fill="none"
            stroke="currentColor"
            strokeWidth={8}
            strokeLinecap="round"
            opacity={0.28}
          />
          {/* Hard solid edge along the tip path. */}
          <path
            d="M14 18 C 48 14, 78 16, 104 22"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.8}
            strokeLinecap="round"
            opacity={0.88}
          />
        </>
      ) : null}
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth={kind === 'tapered' ? 3.5 : kind === 'charcoal' ? 0 : 8}
        strokeLinecap="round"
        opacity={kind === 'airbrush' ? 0.55 : kind === 'charcoal' ? 0 : 0.9}
      />
    </svg>
  )
}

/** Brush size, opacity, professional brush kind, and advanced engine controls. */
export function BrushControls({
  tool,
  brushSize,
  opacity,
  brushEngine,
  variant = 'sheet',
  onBrushSize,
  onOpacity,
  onBrushKind,
  onBrushEnginePatch,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const title = tool === 'erase' ? 'Eraser' : 'Brush'
  const kind = brushEngine?.brushKind ?? 'tapered'
  const layer = brushEngine?.logicalLayer ?? 'ink'

  return (
    <div
      className={variant === 'flat' ? styles.flat : styles.sheet}
      aria-label="Brush settings"
      data-testid="brush-controls"
    >
      {variant === 'sheet' ? <p className={styles.title}>{title}</p> : null}

      {tool !== 'erase' && onBrushKind ? (
        <div className={styles.kindGrid} role="radiogroup" aria-label="Brush type">
          {BRUSH_OPTIONS.map((opt) => {
            const selected = kind === opt.id
            return (
              <button
                key={opt.id}
                type="button"
                role="radio"
                aria-checked={selected}
                className={selected ? styles.kindActive : styles.kind}
                data-testid={`brush-kind-${opt.id}`}
                onClick={() => onBrushKind(opt.id)}
              >
                <BrushPreview kind={opt.id} />
                <strong>{opt.label}</strong>
                <span>{opt.hint}</span>
              </button>
            )
          })}
        </div>
      ) : null}

      {onBrushEnginePatch ? (
        <div className={styles.layerRow} role="radiogroup" aria-label="Paint layer">
          <span className={styles.layerLabel}>Layer</span>
          {LAYER_OPTIONS.map((opt) => {
            const selected = layer === opt.id
            return (
              <button
                key={opt.id}
                type="button"
                role="radio"
                aria-checked={selected}
                className={selected ? styles.layerActive : styles.layerBtn}
                onClick={() => onBrushEnginePatch({ logicalLayer: opt.id })}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      ) : null}

      <BrushSizeControl
        tool={tool}
        brushSize={brushSize}
        opacity={opacity}
        onBrushSize={onBrushSize}
        tone="light"
      />
      <div className={styles.row}>
        <span>Opacity</span>
        <strong>{Math.round(opacity * 100)}%</strong>
      </div>
      <input
        className={styles.slider}
        type="range"
        min={5}
        max={100}
        step={1}
        value={Math.round(opacity * 100)}
        aria-label="Brush opacity"
        disabled={tool === 'erase'}
        onChange={(e) => onOpacity(Number(e.target.value) / 100)}
      />

      {tool !== 'erase' && brushEngine && onBrushEnginePatch ? (
        <div className={styles.advanced}>
          <button
            type="button"
            className={styles.advancedToggle}
            aria-expanded={advancedOpen}
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? 'Hide advanced' : 'Advanced'}
          </button>
          {advancedOpen ? (
            <div className={styles.advancedBody}>
              <label className={styles.advRow}>
                <span>Flow</span>
                <strong>{Math.round(brushEngine.flow * 100)}%</strong>
              </label>
              <input
                className={styles.slider}
                type="range"
                min={5}
                max={100}
                value={Math.round(brushEngine.flow * 100)}
                aria-label="Brush flow"
                onChange={(e) => onBrushEnginePatch({ flow: Number(e.target.value) / 100 })}
              />
              <label className={styles.advRow}>
                <span>Softness</span>
                <strong>{Math.round(brushEngine.softness * 100)}%</strong>
              </label>
              <input
                className={styles.slider}
                type="range"
                min={0}
                max={100}
                value={Math.round(brushEngine.softness * 100)}
                aria-label="Brush softness"
                disabled={kind === 'tapered'}
                onChange={(e) => onBrushEnginePatch({ softness: Number(e.target.value) / 100 })}
              />
              <label className={styles.advRow}>
                <span>Texture</span>
                <strong>{Math.round(brushEngine.textureIntensity * 100)}%</strong>
              </label>
              <input
                className={styles.slider}
                type="range"
                min={0}
                max={100}
                value={Math.round(brushEngine.textureIntensity * 100)}
                aria-label="Texture intensity"
                disabled={kind !== 'charcoal'}
                onChange={(e) =>
                  onBrushEnginePatch({ textureIntensity: Number(e.target.value) / 100 })
                }
              />
              <label className={styles.advRow}>
                <span>Blend</span>
                <select
                  className={styles.select}
                  aria-label="Blend mode"
                  value={brushEngine.blendMode}
                  onChange={(e) =>
                    onBrushEnginePatch({ blendMode: e.target.value as StrokeBlendMode })
                  }
                >
                  {BLEND_OPTIONS.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.checkRow}>
                <input
                  type="checkbox"
                  checked={brushEngine.garmentMask}
                  onChange={(e) => onBrushEnginePatch({ garmentMask: e.target.checked })}
                />
                <span>Clip shade to garment fill (when available)</span>
              </label>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
