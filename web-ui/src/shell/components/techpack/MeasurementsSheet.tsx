import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import type { MeasuredValue, TechpackPiece, TechpackSpecV2 } from '@/services/techpacksApi'
import { MeasuredField } from '@/shell/components/techpack/MeasuredField'
import {
  FIT_PREFERENCES,
  POM_HELP_KEY,
  POM_LABELS,
} from '@/shell/components/techpack/fieldHelpContent'
import { measured, pieceTabLabel } from '@/shell/components/techpack/pieceHelpers'
import styles from './MeasurementsSheet.module.css'

export type MeasurementGroupId = 'body' | 'preferences' | `piece:${string}`

type Props = {
  open: boolean
  spec: TechpackSpecV2
  pieces: TechpackPiece[]
  /** Stable draft id — when it changes while open, re-initialize group selection. */
  draftKey?: string
  initialGroupId?: MeasurementGroupId
  busy?: boolean
  /** Unobtrusive autosave status shown in the footer ("Saved", "Saving…"). */
  saveStatus?: string | null
  onChangeSpec: (updater: (prev: TechpackSpecV2) => TechpackSpecV2) => void
  onUpdatePiece: (pieceId: string, updater: (piece: TechpackPiece) => TechpackPiece) => void
  /** Persist then close — preferred for the simplified Create Real Design flow. */
  onSaveAndDone: () => void | Promise<void>
  onDiscardAndClose: () => void
  /** When true, Close autosaves valid edits instead of requiring Save & Done. */
  autosaveOnClose?: boolean
}

function groupsFor(pieces: TechpackPiece[]): Array<{ id: MeasurementGroupId; label: string }> {
  return [
    { id: 'body', label: 'Body measurements' },
    { id: 'preferences', label: 'Preferences' },
    ...pieces.map((p) => ({
      id: `piece:${p.id}` as MeasurementGroupId,
      label: `Finished · ${pieceTabLabel(p)}`,
    })),
  ]
}

function resolveInitialGroup(
  groups: Array<{ id: MeasurementGroupId }>,
  initialGroupId?: MeasurementGroupId,
): MeasurementGroupId {
  if (initialGroupId && groups.some((g) => g.id === initialGroupId)) return initialGroupId
  return groups[0]?.id ?? 'body'
}

export function MeasurementsSheet({
  open,
  spec,
  pieces,
  draftKey,
  initialGroupId,
  busy = false,
  saveStatus = null,
  onChangeSpec,
  onUpdatePiece,
  onSaveAndDone,
  onDiscardAndClose,
  autosaveOnClose = false,
}: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const groups = useMemo(() => groupsFor(pieces), [pieces])
  /** Stable selection by group id — never reset merely because `pieces` identity changes. */
  const [activeGroupId, setActiveGroupId] = useState<MeasurementGroupId>(() =>
    resolveInitialGroup(groupsFor(pieces), initialGroupId),
  )
  const [dirty, setDirty] = useState(false)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const wasOpenRef = useRef(false)
  const initKeyRef = useRef<string>('')

  // Initialize group only when the sheet opens, the draft changes, or the
  // explicit initial selection changes — NOT when garment measurements edit
  // and recompute the `groups` array identity.
  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false
      return
    }
    const justOpened = !wasOpenRef.current
    wasOpenRef.current = true
    const key = `${draftKey ?? ''}::${initialGroupId ?? ''}`
    if (justOpened || initKeyRef.current !== key) {
      initKeyRef.current = key
      setActiveGroupId(resolveInitialGroup(groupsFor(pieces), initialGroupId))
      setDirty(false)
      setConfirmDiscard(false)
    }
    // intentionally omit `groups` / `pieces` — edits must not re-init
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, draftKey, initialGroupId])

  // If a piece is removed, fall back to a still-valid group without clearing dirty.
  useEffect(() => {
    if (!open) return
    if (!groups.some((g) => g.id === activeGroupId)) {
      setActiveGroupId(groups[0]?.id ?? 'body')
    }
  }, [open, groups, activeGroupId])

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const closeBtn = dialogRef.current?.querySelector<HTMLButtonElement>('[data-close]')
    ;(closeBtn ?? dialogRef.current)?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [open])

  const groupIndex = Math.max(
    0,
    groups.findIndex((g) => g.id === activeGroupId),
  )
  const current = groups[groupIndex] ?? groups[0]

  useEffect(() => {
    if (!open) return
    const node = scrollRef.current
    if (!node) return
    if (typeof node.scrollTo === 'function') node.scrollTo({ top: 0 })
    else node.scrollTop = 0
  }, [activeGroupId, open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        requestClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, dirty])

  if (!open) return null

  const pieceId =
    current?.id.startsWith('piece:') ? current.id.slice('piece:'.length) : null
  const activePiece = pieceId ? pieces.find((p) => p.id === pieceId) ?? null : null

  const markDirty = () => setDirty(true)

  const requestClose = () => {
    if (autosaveOnClose) {
      void onSaveAndDone()
      return
    }
    if (dirty) {
      setConfirmDiscard(true)
      return
    }
    onDiscardAndClose()
  }

  const goPrev = () => {
    const next = Math.max(0, groupIndex - 1)
    setActiveGroupId(groups[next]?.id ?? 'body')
  }
  const goNext = () => {
    const next = Math.min(groups.length - 1, groupIndex + 1)
    setActiveGroupId(groups[next]?.id ?? 'body')
  }

  return (
    <div className={styles.scrim} role="presentation">
      <div
        ref={dialogRef}
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className={styles.header}>
          <div className={styles.headerText}>
            <p className={styles.kicker}>
              {autosaveOnClose ? 'Measurements & details' : 'Step 3 · Measurements'}
            </p>
            <h2 id={titleId} className={styles.title}>
              {current?.label ?? 'Measurements'}
            </h2>
            <p className={styles.progress}>
              Group {groupIndex + 1} of {groups.length} · empty fields stay unknown
              {saveStatus ? ` · ${saveStatus}` : ''}
            </p>
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            data-close
            aria-label="Close measurements editor"
            onClick={requestClose}
            disabled={busy}
          >
            <X size={20} aria-hidden />
          </button>
        </header>

        <div className={styles.groupTabs} role="tablist" aria-label="Measurement groups">
          {groups.map((g) => (
            <button
              key={g.id}
              type="button"
              role="tab"
              aria-selected={g.id === activeGroupId}
              className={
                g.id === activeGroupId ? `${styles.groupTab} ${styles.groupTabActive}` : styles.groupTab
              }
              onClick={() => setActiveGroupId(g.id)}
            >
              {g.label}
            </button>
          ))}
        </div>

        <div ref={scrollRef} className={styles.body}>
          {current?.id === 'body' ? (
            <>
              <p className={styles.lead}>
                Body measurements describe the person. Leave unknown values empty — you can continue
                without filling every field.
              </p>
              {(
                [
                  ['height', 'Height', 'height'],
                  ['bust', 'Bust', 'bust'],
                  ['waist', 'Waist', 'waist'],
                  ['hip', 'Hip', 'hip'],
                  ['inseam', 'Inseam', 'body_inseam'],
                ] as const
              ).map(([key, label, helpKey]) => (
                <MeasuredField
                  key={key}
                  compact
                  label={label}
                  helpKey={helpKey}
                  value={spec.body?.[key] ?? measured(null, spec.units || 'cm')}
                  onChange={(next) => {
                    markDirty()
                    onChangeSpec((prev) => ({
                      ...prev,
                      body: { ...(prev.body ?? {}), [key]: next },
                    }))
                  }}
                />
              ))}
            </>
          ) : null}

          {current?.id === 'preferences' ? (
            <>
              <p className={styles.lead}>Fit preference and sample size for this tech pack.</p>
              <div className={styles.fieldBlock}>
                <label htmlFor="ms-fit-pref">Fit preference</label>
                <select
                  id="ms-fit-pref"
                  value={spec.preferences?.fit_preference || 'regular'}
                  onChange={(e) => {
                    markDirty()
                    onChangeSpec((prev) => ({
                      ...prev,
                      preferences: {
                        ...(prev.preferences ?? {}),
                        fit_preference: e.target.value,
                      },
                    }))
                  }}
                >
                  {FIT_PREFERENCES.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="ms-sample-size">Sample size</label>
                <input
                  id="ms-sample-size"
                  value={spec.sample_size ?? ''}
                  placeholder="e.g. 36 / M"
                  onChange={(e) => {
                    markDirty()
                    onChangeSpec((prev) => ({ ...prev, sample_size: e.target.value }))
                  }}
                />
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="ms-pref-notes">Preference notes</label>
                <textarea
                  id="ms-pref-notes"
                  value={spec.preferences?.notes ?? ''}
                  rows={4}
                  onChange={(e) => {
                    markDirty()
                    onChangeSpec((prev) => ({
                      ...prev,
                      preferences: {
                        ...(prev.preferences ?? {}),
                        notes: e.target.value,
                      },
                    }))
                  }}
                />
              </div>
            </>
          ) : null}

          {activePiece ? (
            <>
              <p className={styles.lead}>
                Finished garment measurements for {pieceTabLabel(activePiece)} only. Unknown values
                may stay empty.
              </p>
              {Object.keys(activePiece.finished_measurements ?? {}).length === 0 ? (
                <p className={styles.lead}>
                  No finished POMs for this category. Skip this group or add notes on Customize.
                </p>
              ) : (
                Object.entries(activePiece.finished_measurements ?? {}).map(([key, value]) => (
                  <MeasuredField
                    key={key}
                    compact
                    label={POM_LABELS[key] ?? key.replace(/_/g, ' ')}
                    helpKey={POM_HELP_KEY[key]}
                    value={value as MeasuredValue}
                    onChange={(next) => {
                      markDirty()
                      onUpdatePiece(activePiece.id, (p) => ({
                        ...p,
                        finished_measurements: {
                          ...(p.finished_measurements ?? {}),
                          [key]: next,
                        },
                      }))
                    }}
                  />
                ))
              )}
            </>
          ) : null}
        </div>

        <footer className={styles.footer}>
          {confirmDiscard ? (
            <div className={styles.discardBar} role="alertdialog" aria-label="Unsaved changes">
              <p>Discard unsaved measurement edits?</p>
              <div className={styles.footerActions}>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => setConfirmDiscard(false)}
                >
                  Keep editing
                </button>
                <button type="button" className={styles.dangerBtn} onClick={onDiscardAndClose}>
                  Discard
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.footerActions}>
              <button
                type="button"
                className={styles.ghostBtn}
                disabled={busy || groupIndex === 0}
                onClick={goPrev}
              >
                <ChevronLeft size={16} aria-hidden />
                Back
              </button>
              {groupIndex < groups.length - 1 ? (
                <button type="button" className={styles.ghostBtn} disabled={busy} onClick={goNext}>
                  Next
                  <ChevronRight size={16} aria-hidden />
                </button>
              ) : null}
              {autosaveOnClose ? (
                <button
                  type="button"
                  className={styles.primaryBtn}
                  disabled={busy}
                  onClick={() => void onSaveAndDone()}
                >
                  {busy ? 'Saving…' : 'Done'}
                </button>
              ) : (
                <button
                  type="button"
                  className={styles.primaryBtn}
                  disabled={busy}
                  onClick={() => void onSaveAndDone()}
                >
                  {busy ? 'Saving…' : 'Save & Done'}
                </button>
              )}
            </div>
          )}
        </footer>
      </div>
    </div>
  )
}
