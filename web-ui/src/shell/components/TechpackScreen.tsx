import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Download, FileText, RefreshCw, Save } from 'lucide-react'
import { useAuthJobImage } from '@/hooks/useAuthJobImage'
import {
  exportTechpackPdf,
  fetchTechpackPdfBlob,
  getTechpackDraft,
  updateTechpackDraft,
  type MeasuredValue,
  type TechpackDraft,
} from '@/services/techpacksApi'
import styles from './TechpackScreen.module.css'

type Props = {
  draftId: string
  onBack: () => void
}

type MeasuredKey =
  | 'height'
  | 'bust'
  | 'waist'
  | 'hip'
  | 'garment_length'
  | 'shoulder_width'
  | 'sleeve_length'
  | 'inseam'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function measured(raw: unknown, unitFallback = 'cm'): MeasuredValue {
  const row = asRecord(raw)
  const source = typeof row.source === 'string' ? row.source : 'empty'
  return {
    value: (row.value as number | string | null | undefined) ?? null,
    unit: typeof row.unit === 'string' ? row.unit : unitFallback,
    source: (['empty', 'designer', 'estimate', 'ai', 'look'] as const).includes(
      source as MeasuredValue['source'],
    )
      ? (source as MeasuredValue['source'])
      : 'empty',
    note: typeof row.note === 'string' ? row.note : null,
  }
}

function MeasuredField({
  label,
  value,
  onChange,
}: {
  label: string
  value: MeasuredValue
  onChange: (next: MeasuredValue) => void
}) {
  return (
    <div className={styles.measureRow}>
      <div className={styles.field}>
        <label>{label}</label>
        <input
          type="text"
          inputMode="decimal"
          value={value.value ?? ''}
          placeholder="—"
          onChange={(e) => {
            const raw = e.target.value.trim()
            onChange({
              ...value,
              value: raw === '' ? null : Number.isFinite(Number(raw)) ? Number(raw) : raw,
              source: raw === '' ? 'empty' : value.source === 'empty' ? 'designer' : value.source,
            })
          }}
        />
      </div>
      <div className={styles.field}>
        <label>Unit</label>
        <input
          type="text"
          value={value.unit ?? ''}
          onChange={(e) => onChange({ ...value, unit: e.target.value })}
        />
      </div>
      <div className={styles.field}>
        <label>Source</label>
        <select
          value={value.source}
          onChange={(e) =>
            onChange({ ...value, source: e.target.value as MeasuredValue['source'] })
          }
        >
          <option value="empty">Empty</option>
          <option value="designer">Designer</option>
          <option value="estimate">Estimate</option>
          <option value="look">Look</option>
          <option value="ai">AI (unverified)</option>
        </select>
      </div>
    </div>
  )
}

export function TechpackScreen({ draftId, onBack }: Props) {
  const [draft, setDraft] = useState<TechpackDraft | null>(null)
  const [title, setTitle] = useState('')
  const [styleCode, setStyleCode] = useState('')
  const [shellName, setShellName] = useState('')
  const [shellComp, setShellComp] = useState('')
  const [closure, setClosure] = useState('')
  const [silhouette, setSilhouette] = useState('')
  const [designerNotes, setDesignerNotes] = useState('')
  const [body, setBody] = useState<Record<string, MeasuredValue>>({})
  const [garment, setGarment] = useState<Record<string, MeasuredValue>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const frontImg = useAuthJobImage(draft?.front_job_id ?? null, Boolean(draft?.front_job_id))
  const backImg = useAuthJobImage(draft?.back_job_id ?? null, Boolean(draft?.back_job_id))

  const hydrate = useCallback((row: TechpackDraft) => {
    setDraft(row)
    setTitle(row.title)
    setStyleCode(row.style_code)
    const spec = asRecord(row.spec)
    const materials = asRecord(spec.materials)
    const shell = asRecord(materials.shell)
    const closures = asRecord(spec.closures)
    const fit = asRecord(spec.fit)
    setShellName(typeof shell.name === 'string' ? shell.name : '')
    setShellComp(typeof shell.composition === 'string' ? shell.composition : '')
    setClosure(typeof closures.type === 'string' ? closures.type : '')
    setSilhouette(typeof fit.silhouette === 'string' ? fit.silhouette : '')
    setDesignerNotes(typeof spec.designer_notes === 'string' ? spec.designer_notes : '')
    const bodySpec = asRecord(spec.body)
    setBody({
      height: measured(bodySpec.height),
      bust: measured(bodySpec.bust),
      waist: measured(bodySpec.waist),
      hip: measured(bodySpec.hip),
    })
    const garmentSpec = asRecord(spec.garment)
    setGarment({
      garment_length: measured(garmentSpec.garment_length),
      shoulder_width: measured(garmentSpec.shoulder_width),
      sleeve_length: measured(garmentSpec.sleeve_length),
      inseam: measured(garmentSpec.inseam),
    })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    getTechpackDraft(draftId, controller.signal)
      .then((row) => {
        if (controller.signal.aborted) return
        hydrate(row)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Could not load tech pack')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [draftId, hydrate])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const statusLabel = useMemo(() => {
    if (!draft) return 'DRAFT / UNVERIFIED'
    return `${draft.status} / ${draft.verification}`
  }, [draft])

  const buildSpecPatch = () => {
    const prev = asRecord(draft?.spec)
    return {
      ...prev,
      designer_notes: designerNotes,
      materials: {
        ...asRecord(prev.materials),
        shell: {
          ...asRecord(asRecord(prev.materials).shell),
          name: shellName,
          composition: shellComp,
          source: shellName.trim() ? 'designer' : 'empty',
        },
      },
      closures: {
        ...asRecord(prev.closures),
        type: closure,
        source: closure.trim() ? 'designer' : 'empty',
      },
      fit: {
        ...asRecord(prev.fit),
        silhouette,
      },
      body: {
        height: body.height,
        bust: body.bust,
        waist: body.waist,
        hip: body.hip,
      },
      garment: {
        garment_length: garment.garment_length,
        shoulder_width: garment.shoulder_width,
        sleeve_length: garment.sleeve_length,
        inseam: garment.inseam,
      },
    }
  }

  const save = async (bump = false) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const next = await updateTechpackDraft(draftId, {
        title: title.trim(),
        style_code: styleCode.trim(),
        spec: buildSpecPatch(),
        bump_revision: bump,
      })
      hydrate(next)
      setNotice(bump ? 'Saved and bumped revision.' : 'Draft saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save draft')
    } finally {
      setBusy(false)
    }
  }

  const exportAndPreview = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await updateTechpackDraft(draftId, {
        title: title.trim(),
        style_code: styleCode.trim(),
        spec: buildSpecPatch(),
      })
      const exported = await exportTechpackPdf(draftId)
      const blob = await fetchTechpackPdfBlob(exported.id)
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      const url = URL.createObjectURL(blob)
      setPreviewUrl(url)
      const refreshed = await getTechpackDraft(draftId)
      hydrate(refreshed)
      setNotice(`PDF ready · ${exported.page_count} pages · ${exported.status}/${exported.verification}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not export PDF')
    } finally {
      setBusy(false)
    }
  }

  const downloadPdf = async () => {
    const exportId = draft?.latest_export?.id
    if (!exportId) {
      setError('Export a PDF preview first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const blob = await fetchTechpackPdfBlob(exportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = draft?.latest_export?.filename || `${styleCode}_techpack.pdf`
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download PDF')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.screen}>
        <div className={styles.head}>
          <p className={styles.subtitle}>Loading Create Real Design…</p>
        </div>
      </div>
    )
  }

  if (!draft) {
    return (
      <div className={styles.screen}>
        <div className={styles.head}>
          <button type="button" className={styles.ghostBtn} onClick={onBack}>
            <ArrowLeft size={14} aria-hidden />
            Back to My Looks
          </button>
          <p className={styles.error}>{error || 'Tech pack not found'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.screen}>
      <div className={styles.head}>
        <div>
          <h1 className={styles.title}>Create Real Design</h1>
          <p className={styles.subtitle}>
            {draft.style_code} · Rev {draft.revision} · editable fashion tech-pack from your Magic look
          </p>
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.ghostBtn} onClick={onBack} disabled={busy}>
            <ArrowLeft size={14} aria-hidden />
            My Looks
          </button>
          <button type="button" className={styles.ghostBtn} onClick={() => void save(false)} disabled={busy}>
            <Save size={14} aria-hidden />
            Save draft
          </button>
          <button type="button" className={styles.primaryBtn} onClick={() => void exportAndPreview()} disabled={busy}>
            <FileText size={14} aria-hidden />
            {busy ? 'Working…' : 'Preview PDF'}
          </button>
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => void downloadPdf()}
            disabled={busy || !draft.latest_export}
          >
            <Download size={14} aria-hidden />
            Download
          </button>
        </div>
      </div>

      <p className={styles.banner}>
        {statusLabel} — measurements may be designer-entered or estimates. Patternmaker review required
        before production. Missing Front/Back sides are never invented.
      </p>

      <div className={styles.body}>
        <div className={styles.formPane}>
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Look references</h2>
            <div className={styles.lookThumbs}>
              <div>
                <p className={styles.lookLabel}>Front</p>
                <div className={styles.lookThumb}>
                  {frontImg.url ? (
                    <img src={frontImg.url} alt="Front look" />
                  ) : (
                    <span>{draft.front_job_id ? 'Loading…' : 'Not available'}</span>
                  )}
                </div>
              </div>
              <div>
                <p className={styles.lookLabel}>Back</p>
                <div className={styles.lookThumb}>
                  {backImg.url ? (
                    <img src={backImg.url} alt="Back look" />
                  ) : (
                    <span>{draft.back_job_id ? 'Loading…' : 'Not fabricated'}</span>
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Style</h2>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label htmlFor="tp-title">Title</label>
                <input id="tp-title" value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className={styles.field}>
                <label htmlFor="tp-style">Style code</label>
                <input
                  id="tp-style"
                  value={styleCode}
                  maxLength={64}
                  onChange={(e) => setStyleCode(e.target.value.toUpperCase())}
                />
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Materials & fit</h2>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label htmlFor="tp-shell">Shell fabric</label>
                <input id="tp-shell" value={shellName} onChange={(e) => setShellName(e.target.value)} />
              </div>
              <div className={styles.field}>
                <label htmlFor="tp-comp">Composition</label>
                <input id="tp-comp" value={shellComp} onChange={(e) => setShellComp(e.target.value)} />
              </div>
              <div className={styles.field}>
                <label htmlFor="tp-closure">Closure</label>
                <input id="tp-closure" value={closure} onChange={(e) => setClosure(e.target.value)} />
              </div>
              <div className={styles.field}>
                <label htmlFor="tp-silhouette">Silhouette</label>
                <input id="tp-silhouette" value={silhouette} onChange={(e) => setSilhouette(e.target.value)} />
              </div>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Body measurements</h2>
            <p className={styles.sourceHint}>Height appears once. Mark Designer vs Estimate — empty stays empty.</p>
            {(['height', 'bust', 'waist', 'hip'] as const).map((key) => (
              <MeasuredField
                key={key}
                label={key[0].toUpperCase() + key.slice(1)}
                value={body[key] ?? measured(null)}
                onChange={(next) => setBody((prev) => ({ ...prev, [key]: next }))}
              />
            ))}
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Finished garment</h2>
            {(
              [
                ['garment_length', 'Garment length'],
                ['shoulder_width', 'Shoulder width'],
                ['sleeve_length', 'Sleeve length'],
                ['inseam', 'Inseam'],
              ] as const
            ).map(([key, label]) => (
              <MeasuredField
                key={key}
                label={label}
                value={garment[key] ?? measured(null)}
                onChange={(next) => setGarment((prev) => ({ ...prev, [key]: next }))}
              />
            ))}
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Designer notes</h2>
            <div className={styles.field}>
              <label htmlFor="tp-notes" className="sr-only">
                Designer notes
              </label>
              <textarea
                id="tp-notes"
                value={designerNotes}
                onChange={(e) => setDesignerNotes(e.target.value)}
                placeholder="Construction preferences, fit intent, trims…"
              />
            </div>
            <div className={styles.actions} style={{ marginTop: 10 }}>
              <button type="button" className={styles.ghostBtn} disabled={busy} onClick={() => void save(true)}>
                <RefreshCw size={14} aria-hidden />
                Save + bump revision
              </button>
            </div>
            {error ? <p className={styles.error}>{error}</p> : null}
            {notice ? <p className={styles.notice}>{notice}</p> : null}
          </section>
        </div>

        <div className={styles.previewPane}>
          <h2 className={styles.sectionTitle}>PDF preview</h2>
          {previewUrl ? (
            <iframe className={styles.previewFrame} title="Tech pack PDF preview" src={previewUrl} />
          ) : (
            <div className={styles.previewEmpty}>
              Save your specs, then Preview PDF.
              <br />
              Every export starts as DRAFT / UNVERIFIED.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Keep MeasuredKey exported for tests / future garment-conditional fields.
export type { MeasuredKey }
