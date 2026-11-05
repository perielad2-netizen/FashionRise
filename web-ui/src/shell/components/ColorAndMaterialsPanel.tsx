import { useEffect, useId, useRef, useState } from 'react'
import { Plus, Pipette } from 'lucide-react'
import {
  CUSTOM_GRADIENT_ID,
  FABRIC_PRESETS,
  FASHION_PALETTE,
  GRADIENT_PRESETS,
  UPLOADED_FABRIC_SCALE_DEFAULT,
  UPLOADED_FABRIC_SCALE_MAX,
  UPLOADED_FABRIC_SCALE_MIN,
  clampUploadedFabricScale,
  gradientPreviewCss,
  type FillStyle,
  type GradientFillStyle,
  uploadedFabricStyle,
} from '@/lib/fills'
import { INK_SWATCHES } from '@/lib/strokes'
import {
  deleteFabric,
  listMyFabrics,
  uploadFabric,
  type FabricAsset,
} from '@/services/fabricAssetsApi'
import { ApiError } from '@/services/api/client'
import { loadFabricAssetImage } from '@/lib/fabricAssetCache'
import { CustomGradientDesigner } from '@/shell/components/CustomGradientDesigner'
import { ProfessionalColorPicker } from '@/shell/components/ProfessionalColorPicker'
import styles from './ColorAndMaterialsPanel.module.css'

type Props = {
  color: string
  onColor: (color: string) => void
  onColorHex: (hex: string) => boolean
  fillStyle: FillStyle
  onFillStyle: (style: FillStyle) => void
  eyedropperActive: boolean
  onToggleEyedropper: () => void
  onNotice?: (message: string) => void
}

type PreviewMap = Record<string, string>

export function ColorAndMaterialsPanel({
  color,
  onColor,
  onColorHex,
  fillStyle,
  onFillStyle,
  eyedropperActive,
  onToggleEyedropper,
  onNotice,
}: Props) {
  const [hexDraft, setHexDraft] = useState(color)
  const [myFabrics, setMyFabrics] = useState<FabricAsset[]>([])
  const [previews, setPreviews] = useState<PreviewMap>({})
  const [libraryBusy, setLibraryBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [pendingPreview, setPendingPreview] = useState<string | null>(null)
  const [pendingName, setPendingName] = useState('')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [tab, setTab] = useState<'colors' | 'fabrics' | 'gradients'>('colors')
  const [colorPickerOpen, setColorPickerOpen] = useState(false)
  const [gradientDesignerOpen, setGradientDesignerOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const nameFieldId = useId()
  const scale =
    fillStyle.kind === 'uploaded-fabric' ? fillStyle.scale : UPLOADED_FABRIC_SCALE_DEFAULT
  const inferredTab: 'colors' | 'fabrics' | 'gradients' =
    fillStyle.kind === 'fabric' || fillStyle.kind === 'uploaded-fabric'
      ? 'fabrics'
      : fillStyle.kind === 'gradient'
        ? 'gradients'
        : 'colors'

  useEffect(() => {
    setHexDraft(color)
  }, [color])

  useEffect(() => {
    setTab(inferredTab)
  }, [inferredTab])

  useEffect(() => {
    let cancelled = false
    setLibraryBusy(true)
    void listMyFabrics()
      .then((rows) => {
        if (!cancelled) setMyFabrics(rows)
      })
      .catch(() => {
        if (!cancelled) setMyFabrics([])
      })
      .finally(() => {
        if (!cancelled) setLibraryBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const urls: string[] = []
    void (async () => {
      const next: PreviewMap = {}
      for (const fabric of myFabrics) {
        try {
          const img = await loadFabricAssetImage(fabric.id)
          if (cancelled) return
          const canvas = document.createElement('canvas')
          canvas.width = 64
          canvas.height = 64
          const ctx = canvas.getContext('2d')
          if (!ctx) continue
          ctx.drawImage(img, 0, 0, 64, 64)
          const url = canvas.toDataURL('image/png')
          next[fabric.id] = url
          urls.push(url)
        } catch {
          /* preview optional */
        }
      }
      if (!cancelled) setPreviews(next)
    })()
    return () => {
      cancelled = true
    }
  }, [myFabrics])

  useEffect(() => {
    return () => {
      if (pendingPreview) URL.revokeObjectURL(pendingPreview)
    }
  }, [pendingPreview])

  const commitHex = () => {
    const ok = onColorHex(hexDraft.startsWith('#') ? hexDraft : `#${hexDraft}`)
    if (!ok) setHexDraft(color)
  }

  const selectSolid = (next: string) => {
    onColor(next)
    setHexDraft(next)
  }

  const openPicker = () => {
    setUploadError(null)
    fileInputRef.current?.click()
  }

  const onFileChosen = (file: File | null) => {
    if (!file) return
    const allowed = ['image/jpeg', 'image/png', 'image/webp']
    if (file.type && !allowed.includes(file.type)) {
      setUploadError('Use a JPG, PNG, or WebP image.')
      setDialogOpen(true)
      return
    }
    if (pendingPreview) URL.revokeObjectURL(pendingPreview)
    const url = URL.createObjectURL(file)
    setPendingFile(file)
    setPendingPreview(url)
    setPendingName(file.name.replace(/\.[^.]+$/, '').slice(0, 80) || 'My fabric')
    setUploadError(null)
    setDialogOpen(true)
  }

  const closeDialog = () => {
    setDialogOpen(false)
    setPendingFile(null)
    if (pendingPreview) URL.revokeObjectURL(pendingPreview)
    setPendingPreview(null)
    setPendingName('')
    setUploadError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const confirmUpload = async () => {
    if (!pendingFile || uploading) return
    setUploading(true)
    setUploadError(null)
    try {
      const created = await uploadFabric(pendingFile, pendingName)
      setMyFabrics((prev) => [created, ...prev.filter((f) => f.id !== created.id)])
      const style = uploadedFabricStyle(created.id, scale)
      if (style) onFillStyle(style)
      onNotice?.(`Fabric “${created.name}” added. Tap Fill inside a closed region.`)
      closeDialog()
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : 'Fabric upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const selectUploaded = (fabric: FabricAsset) => {
    const style = uploadedFabricStyle(fabric.id, scale)
    if (style) onFillStyle(style)
  }

  const removeUploaded = async (fabric: FabricAsset) => {
    try {
      await deleteFabric(fabric.id)
      setMyFabrics((prev) => prev.filter((f) => f.id !== fabric.id))
      if (fillStyle.kind === 'uploaded-fabric' && fillStyle.assetId === fabric.id) {
        onFillStyle({ kind: 'fabric', fabricId: 'satin' })
      }
      onNotice?.(
        `“${fabric.name}” removed from My Fabrics. Designs that already use it can still reopen.`,
      )
    } catch (err) {
      onNotice?.(err instanceof ApiError ? err.message : 'Could not remove fabric.')
    }
  }

  const onScaleChange = (raw: number) => {
    const next = clampUploadedFabricScale(raw)
    if (fillStyle.kind === 'uploaded-fabric') {
      onFillStyle({ ...fillStyle, scale: next })
    }
  }

  return (
    <div className={styles.stack} aria-label="Colors and materials">
      <div className={styles.panelChrome}>
        <div className={styles.materialTabs} role="tablist" aria-label="Material tools">
          {(
            [
              ['colors', 'Colors'],
              ['fabrics', 'Fabrics'],
              ['gradients', 'Gradients'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? styles.materialTabActive : styles.materialTab}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'colors' ? (
          <section className={styles.card} role="tabpanel" aria-label="Colors">
            <button
              type="button"
              className={styles.currentInkBtn}
              aria-label="Choose any color"
              title="Choose any color"
              onClick={() => setColorPickerOpen(true)}
            >
              <span className={styles.currentSwatch} style={{ background: color }} />
              <span className={styles.currentInkMeta}>
                <strong>Current color</strong>
                <em>Choose any color</em>
              </span>
            </button>
            <button
              type="button"
              className={styles.chooseAny}
              onClick={() => setColorPickerOpen(true)}
            >
              Choose any color
            </button>
            <p className={styles.note}>Quick shortcuts</p>
            <div className={styles.swatches}>
              {INK_SWATCHES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={
                    color.toLowerCase() === s.color.toLowerCase() ? styles.swatchActive : styles.swatch
                  }
                  style={{ background: s.color }}
                  aria-label={s.label}
                  title={s.label}
                  onClick={() => selectSolid(s.color)}
                />
              ))}
            </div>
            <p className={styles.note}>Fashion palette</p>
            <div className={styles.swatches}>
              {FASHION_PALETTE.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={
                    color.toLowerCase() === s.color.toLowerCase() ? styles.swatchActive : styles.swatch
                  }
                  style={{ background: s.color }}
                  aria-label={s.label}
                  title={s.label}
                  onClick={() => selectSolid(s.color)}
                />
              ))}
            </div>
            <div className={styles.hexRow}>
              <input
                className={styles.hex}
                value={hexDraft}
                aria-label="Hex color"
                onChange={(e) => setHexDraft(e.target.value)}
                onBlur={commitHex}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitHex()
                }}
              />
              <button
                type="button"
                className={styles.openPickerBtn}
                aria-label="Open color picker"
                title="Open professional color picker"
                style={{ background: color }}
                onClick={() => setColorPickerOpen(true)}
              />
              <button
                type="button"
                className={eyedropperActive ? styles.iconBtnActive : styles.iconBtn}
                aria-label={eyedropperActive ? 'Eyedropper on' : 'Eyedropper'}
                aria-pressed={eyedropperActive}
                title="Sample a color from your sketch"
                onClick={onToggleEyedropper}
              >
                <Pipette size={14} />
              </button>
            </div>
          </section>
        ) : null}

        {tab === 'fabrics' ? (
          <section className={styles.card} role="tabpanel" aria-label="Fabrics">
            <div className={styles.head}>
              <h3>Fabrics</h3>
              <button
                type="button"
                className={styles.addFabric}
                onClick={openPicker}
                disabled={uploading}
              >
                <Plus size={14} aria-hidden="true" />
                Add Fabric
              </button>
            </div>
            <p className={styles.note}>Select a fabric, then use Fill on a closed outline.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
              className={styles.hiddenFile}
              aria-hidden="true"
              tabIndex={-1}
              onChange={(e) => onFileChosen(e.target.files?.[0] ?? null)}
            />
            <div className={styles.fabrics}>
              {FABRIC_PRESETS.map((fabric) => {
                const active = fillStyle.kind === 'fabric' && fillStyle.fabricId === fabric.id
                return (
                  <button
                    key={fabric.id}
                    type="button"
                    className={active ? styles.fabricActive : styles.fabric}
                    style={{ background: fabric.preview }}
                    aria-label={fabric.label}
                    aria-pressed={active}
                    title={fabric.label}
                    onClick={() => onFillStyle({ kind: 'fabric', fabricId: fabric.id })}
                  />
                )
              })}
            </div>

            <p className={styles.note}>My Fabrics {libraryBusy ? '· loading…' : ''}</p>
            {myFabrics.length === 0 ? (
              <p className={styles.note}>Upload a JPG, PNG, or WebP to reuse across your designs.</p>
            ) : (
              <div className={styles.myFabrics}>
                {myFabrics.map((fabric) => {
                  const active =
                    fillStyle.kind === 'uploaded-fabric' && fillStyle.assetId === fabric.id
                  return (
                    <div key={fabric.id} className={styles.myFabricRow}>
                      <button
                        type="button"
                        className={active ? styles.fabricActive : styles.fabric}
                        style={{
                          backgroundImage: previews[fabric.id]
                            ? `url(${previews[fabric.id]})`
                            : undefined,
                          backgroundSize: 'cover',
                          backgroundPosition: 'center',
                          backgroundColor: '#3f3340',
                        }}
                        aria-label={fabric.name}
                        aria-pressed={active}
                        title={fabric.name}
                        onClick={() => selectUploaded(fabric)}
                      />
                      <div className={styles.myFabricMeta}>
                        <span className={styles.myFabricName}>{fabric.name}</span>
                        <button
                          type="button"
                          className={styles.removeFabric}
                          onClick={() => void removeUploaded(fabric)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {fillStyle.kind === 'uploaded-fabric' ? (
              <label className={styles.scaleRow}>
                <span>Pattern scale</span>
                <input
                  type="range"
                  min={UPLOADED_FABRIC_SCALE_MIN}
                  max={UPLOADED_FABRIC_SCALE_MAX}
                  step={0.05}
                  value={scale}
                  aria-label="Uploaded fabric pattern scale"
                  onChange={(e) => onScaleChange(Number(e.target.value))}
                />
                <span className={styles.scaleValue}>{scale.toFixed(2)}×</span>
              </label>
            ) : null}
          </section>
        ) : null}

        {tab === 'gradients' ? (
          <section className={styles.card} role="tabpanel" aria-label="Gradients">
            <p className={styles.note}>Select a gradient, then Fill a closed region.</p>
            <button
              type="button"
              className={styles.createGradient}
              onClick={() => setGradientDesignerOpen(true)}
            >
              Create gradient
            </button>
            {fillStyle.kind === 'gradient' && fillStyle.gradientId === CUSTOM_GRADIENT_ID ? (
              <button
                type="button"
                className={styles.gradientActive}
                style={{
                  background: gradientPreviewCss(fillStyle.colors, fillStyle.angle),
                  marginBottom: 8,
                }}
                aria-label="Custom gradient selected"
                aria-pressed
                title="Custom gradient"
                onClick={() => setGradientDesignerOpen(true)}
              >
                <span className={styles.gradientLabel}>
                  Custom · {Math.round(fillStyle.angle)}°
                </span>
              </button>
            ) : null}
            <div className={styles.gradients}>
              {GRADIENT_PRESETS.map((g) => {
                const active = fillStyle.kind === 'gradient' && fillStyle.gradientId === g.id
                return (
                  <button
                    key={g.id}
                    type="button"
                    className={active ? styles.gradientActive : styles.gradient}
                    style={{ background: g.preview }}
                    aria-label={g.label}
                    aria-pressed={active}
                    title={g.label}
                    onClick={() =>
                      onFillStyle({
                        kind: 'gradient',
                        gradientId: g.id,
                        colors: [...g.colors] as [string, string],
                        angle: g.angle,
                      })
                    }
                  >
                    <span className={styles.gradientLabel}>{g.label}</span>
                  </button>
                )
              })}
            </div>
          </section>
        ) : null}
      </div>

      {dialogOpen ? (
        <div className={styles.uploadScrim} role="presentation">
          <div
            className={styles.uploadDialog}
            role="dialog"
            aria-modal="true"
            aria-label="Add fabric"
          >
            <h3 className={styles.uploadTitle}>Add fabric</h3>
            {pendingPreview ? (
              <img src={pendingPreview} alt="" className={styles.uploadPreview} />
            ) : (
              <div className={styles.uploadPreviewEmpty}>Choose an image to preview</div>
            )}
            <label className={styles.uploadField} htmlFor={nameFieldId}>
              Name
              <input
                id={nameFieldId}
                className={styles.hex}
                value={pendingName}
                maxLength={80}
                onChange={(e) => setPendingName(e.target.value)}
                disabled={uploading}
              />
            </label>
            {uploadError ? (
              <p className={styles.uploadError} role="alert">
                {uploadError}
              </p>
            ) : (
              <p className={styles.note}>JPG, PNG, or WebP · private to your account</p>
            )}
            <div className={styles.uploadActions}>
              <button type="button" className={styles.uploadGhost} onClick={closeDialog} disabled={uploading}>
                Cancel
              </button>
              <button
                type="button"
                className={styles.uploadPrimary}
                onClick={() => void confirmUpload()}
                disabled={!pendingFile || uploading}
              >
                {uploading ? 'Uploading…' : 'Save fabric'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ProfessionalColorPicker
        open={colorPickerOpen}
        initialColor={color}
        onApply={(hex) => {
          selectSolid(hex)
          setColorPickerOpen(false)
        }}
        onCancel={() => setColorPickerOpen(false)}
      />

      <CustomGradientDesigner
        open={gradientDesignerOpen}
        initial={
          fillStyle.kind === 'gradient' && fillStyle.gradientId === CUSTOM_GRADIENT_ID
            ? (fillStyle as GradientFillStyle)
            : null
        }
        onCancel={() => setGradientDesignerOpen(false)}
        onApply={(style) => {
          onFillStyle(style)
          setGradientDesignerOpen(false)
        }}
      />
    </div>
  )
}
