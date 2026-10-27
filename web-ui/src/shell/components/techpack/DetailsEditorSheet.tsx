import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Plus, Trash2, X } from 'lucide-react'
import type { MeasuredValue, TechpackPiece, TechpackSpecV2 } from '@/services/techpacksApi'
import { MeasuredField } from '@/shell/components/techpack/MeasuredField'
import {
  CLOSURE_SUGGESTIONS,
  FIT_PREFERENCES,
  PIECE_CATEGORIES,
  POM_HELP_KEY,
  POM_LABELS,
  SHELL_SUGGESTIONS,
  SILHOUETTE_SUGGESTIONS,
} from '@/shell/components/techpack/fieldHelpContent'
import {
  createEmptyPiece,
  measured,
  pieceTabLabel,
  retargetFinishedMeasurements,
} from '@/shell/components/techpack/pieceHelpers'
import styles from './MeasurementsSheet.module.css'

type SectionId = 'garments' | 'body' | 'preferences' | `piece:${string}`

type Props = {
  open: boolean
  draftKey: string
  title: string
  styleCode: string
  spec: TechpackSpecV2
  pieces: TechpackPiece[]
  busy?: boolean
  saveStatus?: string | null
  onChangeTitle: (value: string) => void
  onChangeStyleCode: (value: string) => void
  onChangeSpec: (updater: (prev: TechpackSpecV2) => TechpackSpecV2) => void
  onUpdatePiece: (pieceId: string, updater: (piece: TechpackPiece) => TechpackPiece) => void
  onClose: () => void | Promise<void>
}

function ChipRow({
  options,
  value,
  onPick,
}: {
  options: readonly string[]
  value: string
  onPick: (next: string) => void
}) {
  return (
    <div className={styles.groupTabs} role="group">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={value === opt ? `${styles.groupTab} ${styles.groupTabActive}` : styles.groupTab}
          onClick={() => onPick(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

export function DetailsEditorSheet({
  open,
  draftKey,
  title,
  styleCode,
  spec,
  pieces,
  busy = false,
  saveStatus = null,
  onChangeTitle,
  onChangeStyleCode,
  onChangeSpec,
  onUpdatePiece,
  onClose,
}: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const sections = useMemo(() => {
    const list: Array<{ id: SectionId; label: string }> = [
      { id: 'garments', label: 'Garments' },
      { id: 'body', label: 'Body' },
      { id: 'preferences', label: 'Preferences' },
      ...pieces.map((p) => ({
        id: `piece:${p.id}` as SectionId,
        label: `Finished · ${pieceTabLabel(p)}`,
      })),
    ]
    return list
  }, [pieces])
  const [activeId, setActiveId] = useState<SectionId>('garments')
  const [activePieceId, setActivePieceId] = useState<string | null>(pieces[0]?.id ?? null)
  const wasOpenRef = useRef(false)

  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false
      return
    }
    if (!wasOpenRef.current) {
      wasOpenRef.current = true
      setActiveId('garments')
      setActivePieceId(pieces[0]?.id ?? null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, draftKey])

  useEffect(() => {
    if (!open) return
    if (!sections.some((s) => s.id === activeId)) {
      setActiveId(sections[0]?.id ?? 'garments')
    }
  }, [open, sections, activeId])

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

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        void onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const activePiece =
    activePieceId != null ? pieces.find((p) => p.id === activePieceId) ?? null : null
  const finishedPieceId = activeId.startsWith('piece:') ? activeId.slice('piece:'.length) : null
  const finishedPiece = finishedPieceId
    ? pieces.find((p) => p.id === finishedPieceId) ?? null
    : null

  const addPiece = () => {
    const piece = createEmptyPiece({
      category: 'other',
      label: `Piece ${(pieces.length || 0) + 1}`,
      units: spec.units || 'cm',
    })
    onChangeSpec((prev) => {
      const nextPieces = [...(prev.outfit?.pieces ?? []), piece]
      return {
        ...prev,
        outfit: {
          ...(prev.outfit ?? { piece_count: 0, pieces: [] }),
          pieces: nextPieces,
          piece_count: nextPieces.length,
          needs_user_confirm: true,
        },
      }
    })
    setActivePieceId(piece.id)
    setActiveId('garments')
  }

  const removePiece = (pieceId: string) => {
    onChangeSpec((prev) => {
      if (!prev.outfit) return prev
      const nextPieces = prev.outfit.pieces.filter((p) => p.id !== pieceId)
      return {
        ...prev,
        outfit: { ...prev.outfit, pieces: nextPieces, piece_count: nextPieces.length },
      }
    })
    setActivePieceId((cur) => (cur === pieceId ? pieces.find((p) => p.id !== pieceId)?.id ?? null : cur))
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
            <p className={styles.kicker}>Optional</p>
            <h2 id={titleId} className={styles.title}>
              Measurements & details
            </h2>
            <p className={styles.progress}>
              All fields optional · empty stays unknown
              {saveStatus ? ` · ${saveStatus}` : ''}
            </p>
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            data-close
            aria-label="Close details editor"
            onClick={() => void onClose()}
            disabled={busy}
          >
            <X size={20} aria-hidden />
          </button>
        </header>

        <div className={styles.groupTabs} role="tablist" aria-label="Detail sections">
          {sections.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={s.id === activeId}
              className={
                s.id === activeId ? `${styles.groupTab} ${styles.groupTabActive}` : styles.groupTab
              }
              onClick={() => setActiveId(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div ref={scrollRef} className={styles.body}>
          {activeId === 'garments' ? (
            <>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-title">Design title</label>
                <input
                  id="de-title"
                  value={title}
                  onChange={(e) => onChangeTitle(e.target.value)}
                />
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-style">Style code</label>
                <input
                  id="de-style"
                  value={styleCode}
                  onChange={(e) => onChangeStyleCode(e.target.value)}
                />
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-notes">Look notes</label>
                <textarea
                  id="de-notes"
                  rows={3}
                  value={spec.look_notes ?? ''}
                  onChange={(e) =>
                    onChangeSpec((prev) => ({ ...prev, look_notes: e.target.value }))
                  }
                />
              </div>

              <div className={styles.groupTabs} role="tablist" aria-label="Garment pieces">
                {pieces.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    role="tab"
                    aria-selected={p.id === activePieceId}
                    className={
                      p.id === activePieceId
                        ? `${styles.groupTab} ${styles.groupTabActive}`
                        : styles.groupTab
                    }
                    onClick={() => setActivePieceId(p.id)}
                  >
                    {pieceTabLabel(p)}
                  </button>
                ))}
                <button type="button" className={styles.groupTab} onClick={addPiece}>
                  <Plus size={14} aria-hidden /> Add piece
                </button>
              </div>

              {activePiece ? (
                <>
                  <div className={styles.fieldBlock}>
                    <label htmlFor="de-piece-label">Piece label</label>
                    <input
                      id="de-piece-label"
                      value={activePiece.label}
                      onChange={(e) =>
                        onUpdatePiece(activePiece.id, (p) => ({ ...p, label: e.target.value }))
                      }
                    />
                  </div>
                  <div className={styles.fieldBlock}>
                    <label htmlFor="de-category">Garment type</label>
                    <select
                      id="de-category"
                      value={activePiece.category}
                      onChange={(e) => {
                        const category = e.target.value
                        onUpdatePiece(activePiece.id, (p) =>
                          retargetFinishedMeasurements(p, category, spec.units || 'cm'),
                        )
                      }}
                    >
                      {PIECE_CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className={styles.fieldBlock}>
                    <label htmlFor="de-shell">Material / shell</label>
                    <input
                      id="de-shell"
                      value={activePiece.materials?.shell?.name ?? ''}
                      onChange={(e) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...(p.materials ?? {}),
                            shell: {
                              ...(p.materials?.shell ?? {}),
                              name: e.target.value,
                              source: 'designer',
                            },
                          },
                        }))
                      }
                    />
                    <ChipRow
                      options={SHELL_SUGGESTIONS}
                      value={activePiece.materials?.shell?.name ?? ''}
                      onPick={(next) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          materials: {
                            ...(p.materials ?? {}),
                            shell: {
                              ...(p.materials?.shell ?? {}),
                              name: next,
                              source: 'designer',
                            },
                          },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.fieldBlock}>
                    <label htmlFor="de-silhouette">Silhouette</label>
                    <input
                      id="de-silhouette"
                      value={activePiece.fit?.silhouette ?? ''}
                      onChange={(e) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...(p.fit ?? {}), silhouette: e.target.value },
                        }))
                      }
                    />
                    <ChipRow
                      options={SILHOUETTE_SUGGESTIONS}
                      value={activePiece.fit?.silhouette ?? ''}
                      onPick={(next) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          fit: { ...(p.fit ?? {}), silhouette: next },
                        }))
                      }
                    />
                  </div>
                  <div className={styles.fieldBlock}>
                    <label htmlFor="de-closure">Closure</label>
                    <input
                      id="de-closure"
                      value={activePiece.closures?.type ?? ''}
                      onChange={(e) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: {
                            ...(p.closures ?? {}),
                            type: e.target.value,
                            source: 'designer',
                          },
                        }))
                      }
                    />
                    <ChipRow
                      options={CLOSURE_SUGGESTIONS}
                      value={activePiece.closures?.type ?? ''}
                      onPick={(next) =>
                        onUpdatePiece(activePiece.id, (p) => ({
                          ...p,
                          closures: {
                            ...(p.closures ?? {}),
                            type: next,
                            source: 'designer',
                          },
                        }))
                      }
                    />
                  </div>
                  {pieces.length > 1 ? (
                    <button
                      type="button"
                      className={styles.dangerBtn}
                      onClick={() => removePiece(activePiece.id)}
                    >
                      <Trash2 size={14} aria-hidden /> Remove piece
                    </button>
                  ) : null}
                </>
              ) : (
                <p className={styles.lead}>Add a garment piece to edit materials and construction.</p>
              )}
            </>
          ) : null}

          {activeId === 'body' ? (
            <>
              <p className={styles.lead}>
                Body measurements describe the person. Leave unknown values empty.
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
                  onChange={(next) =>
                    onChangeSpec((prev) => ({
                      ...prev,
                      body: { ...(prev.body ?? {}), [key]: next },
                    }))
                  }
                />
              ))}
            </>
          ) : null}

          {activeId === 'preferences' ? (
            <>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-fit">Fit preference</label>
                <select
                  id="de-fit"
                  value={spec.preferences?.fit_preference || 'regular'}
                  onChange={(e) =>
                    onChangeSpec((prev) => ({
                      ...prev,
                      preferences: {
                        ...(prev.preferences ?? {}),
                        fit_preference: e.target.value,
                      },
                    }))
                  }
                >
                  {FIT_PREFERENCES.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-sample">Sample size</label>
                <input
                  id="de-sample"
                  value={spec.sample_size ?? ''}
                  placeholder="e.g. 36 / M"
                  onChange={(e) =>
                    onChangeSpec((prev) => ({ ...prev, sample_size: e.target.value }))
                  }
                />
              </div>
              <div className={styles.fieldBlock}>
                <label htmlFor="de-pref-notes">Preference notes</label>
                <textarea
                  id="de-pref-notes"
                  rows={4}
                  value={spec.preferences?.notes ?? ''}
                  onChange={(e) =>
                    onChangeSpec((prev) => ({
                      ...prev,
                      preferences: {
                        ...(prev.preferences ?? {}),
                        notes: e.target.value,
                      },
                    }))
                  }
                />
              </div>
            </>
          ) : null}

          {finishedPiece ? (
            <>
              <p className={styles.lead}>
                Finished garment measurements for {pieceTabLabel(finishedPiece)}. Unknown values may
                stay empty.
              </p>
              {Object.keys(finishedPiece.finished_measurements ?? {}).length === 0 ? (
                <p className={styles.lead}>No finished POMs for this category.</p>
              ) : (
                Object.entries(finishedPiece.finished_measurements ?? {}).map(([key, value]) => (
                  <MeasuredField
                    key={key}
                    compact
                    label={POM_LABELS[key] ?? key.replace(/_/g, ' ')}
                    helpKey={POM_HELP_KEY[key]}
                    value={value as MeasuredValue}
                    onChange={(next) =>
                      onUpdatePiece(finishedPiece.id, (p) => ({
                        ...p,
                        finished_measurements: {
                          ...(p.finished_measurements ?? {}),
                          [key]: next,
                        },
                      }))
                    }
                  />
                ))
              )}
            </>
          ) : null}
        </div>

        <footer className={styles.footer}>
          <div className={styles.footerActions}>
            <span className={styles.progress} aria-live="polite">
              {saveStatus || (busy ? 'Saving…' : 'Edits save automatically')}
            </span>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={busy}
              onClick={() => void onClose()}
            >
              Done
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}
