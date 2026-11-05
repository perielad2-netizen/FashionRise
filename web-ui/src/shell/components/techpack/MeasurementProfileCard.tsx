import { useEffect, useMemo, useState } from 'react'
import { Plus, UserRound } from 'lucide-react'
import type {
  BodyMeasurementProfile,
  MeasuredValue,
} from '@/services/techpacksApi'
import {
  createBodyMeasurementProfile,
  deleteBodyMeasurementProfile,
  listBodyMeasurementProfiles,
  updateBodyMeasurementProfile,
} from '@/services/techpacksApi'
import styles from './MeasurementProfileCard.module.css'

const BODY_FIELDS = [
  { key: 'height', label: 'Height' },
  { key: 'bust', label: 'Bust / chest' },
  { key: 'waist', label: 'Waist' },
  { key: 'hip', label: 'Hip' },
  { key: 'inseam', label: 'Inseam' },
] as const

type DraftForm = {
  name: string
  sample_size: string
  values: Record<string, string>
}

function emptyForm(name = ''): DraftForm {
  return {
    name,
    sample_size: '',
    values: Object.fromEntries(BODY_FIELDS.map((f) => [f.key, ''])),
  }
}

function formFromProfile(p: BodyMeasurementProfile): DraftForm {
  const values: Record<string, string> = {}
  for (const f of BODY_FIELDS) {
    const cell = p.measurements?.[f.key]
    const v = cell?.value
    values[f.key] = v === null || v === undefined || v === '' ? '' : String(v)
  }
  return {
    name: p.name,
    sample_size: p.sample_size || '',
    values,
  }
}

function toMeasurements(form: DraftForm, units: string): Record<string, MeasuredValue> {
  const out: Record<string, MeasuredValue> = {}
  for (const f of BODY_FIELDS) {
    const raw = (form.values[f.key] || '').trim()
    if (!raw) {
      out[f.key] = { value: null, unit: units, source: 'empty' }
      continue
    }
    const num = Number(raw)
    out[f.key] = {
      value: Number.isFinite(num) ? num : raw,
      unit: units,
      source: 'designer',
    }
  }
  return out
}

type Props = {
  selectedId: string | null
  onSelect: (profileId: string | null) => void
  disabled?: boolean
}

export function MeasurementProfileCard({ selectedId, onSelect, disabled = false }: Props) {
  const [profiles, setProfiles] = useState<BodyMeasurementProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<DraftForm>(emptyForm('Me'))
  const [busy, setBusy] = useState(false)

  const selected = useMemo(
    () => profiles.find((p) => p.id === selectedId) ?? null,
    [profiles, selectedId],
  )

  const refresh = async (preferId?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listBodyMeasurementProfiles()
      setProfiles(rows)
      const pick =
        (preferId && rows.find((r) => r.id === preferId)?.id) ||
        rows.find((r) => r.is_default)?.id ||
        rows[0]?.id ||
        null
      onSelect(pick)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load measurement profiles')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startCreate = () => {
    setEditId(null)
    setForm(emptyForm(profiles.length ? '' : 'Me'))
    setEditing(true)
    setError(null)
  }

  const startEdit = (p: BodyMeasurementProfile) => {
    setEditId(p.id)
    setForm(formFromProfile(p))
    setEditing(true)
    setError(null)
  }

  const save = async () => {
    const name = form.name.trim()
    if (!name) {
      setError('Give this person a name — for example “Me” or “Mom”.')
      return
    }
    const filled = BODY_FIELDS.some((f) => (form.values[f.key] || '').trim())
    if (!filled) {
      setError('Enter at least one body measurement.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = {
        name,
        units: 'cm',
        sample_size: form.sample_size.trim() || null,
        measurements: toMeasurements(form, 'cm'),
        is_default: editId ? undefined : profiles.length === 0,
      }
      const saved = editId
        ? await updateBodyMeasurementProfile(editId, payload)
        : await createBodyMeasurementProfile(payload)
      setEditing(false)
      setEditId(null)
      await refresh(saved.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save measurements')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (p: BodyMeasurementProfile) => {
    if (!window.confirm(`Delete measurements for “${p.name}”?`)) return
    setBusy(true)
    setError(null)
    try {
      await deleteBodyMeasurementProfile(p.id)
      await refresh(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete profile')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={styles.card} aria-label="Body measurements">
      <div className={styles.head}>
        <div className={styles.headTitle}>
          <UserRound size={16} aria-hidden />
          <h2>Who is this for?</h2>
        </div>
        <p className={styles.hint}>
          Save full body measurements once — reuse them for every outfit. AI reads the rest from
          your Magic look.
        </p>
      </div>

      {loading ? <p className={styles.muted}>Loading saved measurements…</p> : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {!editing && !loading ? (
        <>
          {profiles.length ? (
            <div className={styles.chipRow} role="listbox" aria-label="Saved people">
              {profiles.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={p.id === selectedId}
                  className={
                    p.id === selectedId ? `${styles.chip} ${styles.chipActive}` : styles.chip
                  }
                  disabled={disabled || busy}
                  onClick={() => onSelect(p.id)}
                >
                  {p.name}
                  {p.is_default ? <span className={styles.defaultTag}>Default</span> : null}
                </button>
              ))}
            </div>
          ) : (
            <p className={styles.muted}>No saved people yet — add body measurements to continue.</p>
          )}

          {selected ? (
            <dl className={styles.summary}>
              {BODY_FIELDS.map((f) => {
                const cell = selected.measurements?.[f.key]
                const v = cell?.value
                if (v === null || v === undefined || v === '') return null
                return (
                  <div key={f.key}>
                    <dt>{f.label}</dt>
                    <dd>
                      {v}
                      {cell?.unit ? ` ${cell.unit}` : ' cm'}
                    </dd>
                  </div>
                )
              })}
              {selected.sample_size ? (
                <div>
                  <dt>Sample size</dt>
                  <dd>{selected.sample_size}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={disabled || busy}
              onClick={startCreate}
            >
              <Plus size={14} aria-hidden /> New person
            </button>
            {selected ? (
              <>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  disabled={disabled || busy}
                  onClick={() => startEdit(selected)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  disabled={disabled || busy}
                  onClick={() => void remove(selected)}
                >
                  Delete
                </button>
              </>
            ) : null}
          </div>
        </>
      ) : null}

      {editing ? (
        <div className={styles.form}>
          <label className={styles.field}>
            <span>Name</span>
            <input
              value={form.name}
              disabled={busy}
              placeholder="Me, Mom, Client — Anna…"
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
          </label>
          <div className={styles.grid}>
            {BODY_FIELDS.map((f) => (
              <label key={f.key} className={styles.field}>
                <span>{f.label} (cm)</span>
                <input
                  inputMode="decimal"
                  value={form.values[f.key] || ''}
                  disabled={busy}
                  placeholder="—"
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      values: { ...prev.values, [f.key]: e.target.value },
                    }))
                  }
                />
              </label>
            ))}
            <label className={styles.field}>
              <span>Sample size (optional)</span>
              <input
                value={form.sample_size}
                disabled={busy}
                placeholder="M / 38 / 8…"
                onChange={(e) => setForm((prev) => ({ ...prev, sample_size: e.target.value }))}
              />
            </label>
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={busy}
              onClick={() => void save()}
            >
              {busy ? 'Saving…' : 'Save measurements'}
            </button>
            <button
              type="button"
              className={styles.ghostBtn}
              disabled={busy}
              onClick={() => {
                setEditing(false)
                setEditId(null)
                setError(null)
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
