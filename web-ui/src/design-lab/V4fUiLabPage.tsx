import { useMemo, useState } from 'react'
import { ColorAndMaterialsPanel } from '@/shell/components/ColorAndMaterialsPanel'
import { MagicLookPanel } from '@/shell/components/MagicLookPanel'
import { solidStyle, type FillStyle } from '@/lib/fills'

/** DEV-only harness for WEB-V4F visual checks (picker + Magic modal contain). */
export function V4fUiLabPage() {
  const [color, setColor] = useState('#C2185B')
  const [fillStyle, setFillStyle] = useState<FillStyle>(() => solidStyle('#C2185B'))
  const [eyedropper, setEyedropper] = useState(false)
  const [magicOpen, setMagicOpen] = useState(true)
  const lookObjectUrl = useMemo(() => makePortraitLookUrl(), [])
  const sketchObjectUrl = useMemo(() => makeSketchUrl(), [])

  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'grid',
        gridTemplateColumns: 'minmax(280px, 340px) 1fr',
        gap: 16,
        padding: 16,
        background: 'radial-gradient(ellipse at 20% 0%, #2a1830, #0b1220 55%)',
        color: '#f4efe8',
      }}
    >
      <div style={{ minHeight: 0, maxHeight: '96dvh' }}>
        <h1 style={{ margin: '0 0 12px', fontSize: 18 }}>WEB-V4F Colors lab</h1>
        <ColorAndMaterialsPanel
          color={color}
          onColor={(next) => {
            setColor(next)
            setFillStyle(solidStyle(next))
          }}
          onColorHex={(hex) => {
            setColor(hex)
            setFillStyle(solidStyle(hex))
            return true
          }}
          fillStyle={fillStyle}
          onFillStyle={setFillStyle}
          eyedropperActive={eyedropper}
          onToggleEyedropper={() => setEyedropper((v) => !v)}
        />
      </div>
      <div>
        <button
          type="button"
          style={{
            minHeight: 40,
            padding: '0 14px',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,0.16)',
            background: 'rgba(236,72,153,0.25)',
            color: '#fff',
            cursor: 'pointer',
            marginBottom: 12,
          }}
          onClick={() => setMagicOpen(true)}
        >
          Open Your Look modal
        </button>
        <p style={{ color: 'rgba(244,239,232,0.7)', fontSize: 13 }}>
          Current Studio color: {color} · fill {fillStyle.kind}
        </p>
        <div style={{ position: 'relative', height: 'min(86dvh, 820px)' }}>
          <MagicLookPanel
            open={magicOpen}
            phase="ready"
            result={{
              jobId: 'lab',
              status: 'completed',
              summary: 'Lab preview look for contain-fit verification.',
              bullets: ['Hat visible', 'Shoes visible', 'Full 2:3 frame'],
              hasImage: true,
            }}
            lookObjectUrl={lookObjectUrl}
            sketchObjectUrl={sketchObjectUrl}
            error={null}
            canRecover={false}
            onClose={() => setMagicOpen(false)}
            onCancel={() => setMagicOpen(false)}
            onDownload={() => undefined}
            onRecover={() => undefined}
            onBackToSketch={() => setMagicOpen(false)}
          />
        </div>
      </div>
    </div>
  )
}

function makePortraitLookUrl(): string {
  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 1536
  const ctx = canvas.getContext('2d')!
  const g = ctx.createLinearGradient(0, 0, 0, 1536)
  g.addColorStop(0, '#f7d6e8')
  g.addColorStop(0.45, '#d4538c')
  g.addColorStop(1, '#2b1630')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 1024, 1536)
  ctx.fillStyle = '#1a1020'
  ctx.beginPath()
  ctx.ellipse(512, 220, 90, 110, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#fff7fb'
  ctx.font = 'bold 54px Georgia, serif'
  ctx.textAlign = 'center'
  ctx.fillText('HAT', 512, 120)
  ctx.fillText('BODY', 512, 760)
  ctx.fillText('SHOES', 512, 1460)
  ctx.strokeStyle = 'rgba(255,255,255,0.85)'
  ctx.lineWidth = 6
  ctx.strokeRect(24, 24, 976, 1488)
  return canvas.toDataURL('image/png')
}

function makeSketchUrl(): string {
  const canvas = document.createElement('canvas')
  canvas.width = 768
  canvas.height = 1152
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#f8f4f0'
  ctx.fillRect(0, 0, 768, 1152)
  ctx.strokeStyle = '#222'
  ctx.lineWidth = 4
  ctx.strokeRect(40, 40, 688, 1072)
  ctx.font = '42px sans-serif'
  ctx.fillStyle = '#333'
  ctx.textAlign = 'center'
  ctx.fillText('Sketch', 384, 580)
  return canvas.toDataURL('image/png')
}
