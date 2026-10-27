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
  pieceDisplayLabel,
  retargetFinishedMeasurements,
} from '@/shell/components/techpack/pieceHelpers'
import styles from './DetailsEditorSheet.module.css'

type SectionId = 'garments' | 'body' | 'preferences' | 'finished'

type Props = {
  open: boolean
  draftKey: string
  title: string
  styleCode: string
  spec: TechpackSpecV2
  pieces: TechpackPiece[]
  busy?: boolean
  saveStatus?: string | null
  lookThumbnailUrl?: string | null
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
    <div className={styles.chipRow} role="group">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={value === opt ? `${styles.chip} ${styles.chipActive}` : styles.chip}
          onClick={() => onPick(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

function provenanceKey(raw: unknown): 'visual' | 'ai' | 'user' | 'unknown' | null {
  const v = typeof raw === 'string' ? raw : ''
  if (v === 'visually_supported') return 'visual'
  if (v === 'ai_inferred') return 'ai'
  if (v === 'designer') return 'user'
  if (v === 'unknown') return 'unknown'
  return null
}

function ProvenanceBadge({ kind }: { kind: ReturnType<typeof provenanceKey> }) {
  if (!kind) return null
  const label =
    kind === 'visual'
      ? 'Visually supported'
      : kind === 'ai'
        ? 'AI proposed'
        : kind === 'user'
          ? 'Confirmed'
          : 'Unknown'
  return (
    <span className={kind === 'unknown' ? `${styles.badge} ${styles.badgeMuted}` : styles.badge}>
      {label}
    </span>
  )
}

function categoryProvenance(piece: TechpackPiece): ReturnType<typeof provenanceKey> {
  if (piece.category_user_confirmed) return 'user'
  if (piece.category_provenance) return provenanceKey(piece.category_provenance)
  if (String(piece.detection_source || '').startsWith('heuristic')) return 'ai'
  if (piece.detection_source === 'look_identity' || piece.detection_source === 'ai_vision') {
    return 'visual'
  }
  return null
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
  lookThumbnailUrl = null,
  onChangeTitle,
  onChangeStyleCode,
  onChangeSpec,
  onUpdatePiece,
  onClose,
}: Props) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const [activeId, setActiveId] = useState<SectionId>('garments')
  const [activePieceId, setActivePieceId] = useState<string | null>(pieces[0]?.id ?? null)
  const wasOpenRef = useRef(false)

  const navItems = useMemo(
    () =>
      [
        { id: 'garments' as const, label: 'Garments' },
        { id: 'body' as const, label: 'Body measurements' },
        { id: 'preferences' as const, label: 'Preferences' },
        { id: 'finished' as const, label: 'Finished measurements' },
      ] as const,
    [],
  )

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
    if (activePieceId && !pieces.some((p) => p.id === activePieceId)) {
      setActivePieceId(pieces[0]?.id ?? null)
    }
  }, [open, pieces, activePieceId])

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

  const selectPiece = (id: string) => {
    setActivePieceId(id)
    if (activeId === 'finished') setActiveId('finished')
    else setActiveId('garments')
  }

  const renderGarmentPills = (variant: 'mobile' | 'side') => (
    <div className={variant === 'side' ? undefined : styles.garmentPills} role="tablist" aria-label="Garment pieces">
      {pieces.map((p) => {
        const active = p.id === activePieceId
        const cls =
          variant === 'side'
            ? active
              ? `${styles.sideGarmentBtn} ${styles.sideGarmentBtnActive}`
              : styles.sideGarmentBtn
            : active
              ? `${styles.garmentPill} ${styles.garmentPillActive}`
              : styles.garmentPill
        return (
          <button
            key={p.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={cls}
            onClick={() => selectPiece(p.id)}
          >
            {pieceDisplayLabel(p)}
          </button>
        )
      })}
      {variant === 'mobile' ? (
        <button type="button" className={styles.addPieceBtn} onClick={addPiece}>
          <Plus size={14} aria-hidden /> Add piece
        </button>
      ) : null}
    </div>
  )

  const renderPieceEditor = (piece: TechpackPiece) => {
    const vd =
      piece.visible_details && typeof piece.visible_details === 'object'
        ? (piece.visible_details as Record<string, unknown>)
        : null
    const visualRows = (
      [
        ['color', piece.color_hint, piece.color_hint_provenance],
        ['neckline', vd?.neckline, vd?.neckline_provenance ?? 'visually_supported'],
        ['sleeves', vd?.sleeves, vd?.sleeves_provenance ?? 'visually_supported'],
        ['panels', vd?.panels_seams, vd?.panels_seams_provenance],
      ] as const
    ).filter(([, value]) => typeof value === 'string' && String(value).trim())

    return (
      <>
        {Array.isArray(piece.ai_conflicts) && piece.ai_conflicts.length > 0 ? (
          <div className={styles.conflictBox} role="status">
            AI suggestion differs from your confirmed values — kept your data.
            {(piece.ai_conflicts as Array<Record<string, unknown>>).map((c, i) => (
              <div key={i}>
                {String(c.message || `${c.field}: you=${c.user_value}, AI=${c.ai_value}`)}
              </div>
            ))}
          </div>
        ) : null}

        <section className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>Identity</h3>
          <div className={styles.fieldGrid}>
            <div className={styles.fieldBlock}>
              <label htmlFor="de-piece-label">Piece label</label>
              <input
                id="de-piece-label"
                value={piece.label}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({ ...p, label: e.target.value }))
                }
              />
            </div>
            <div className={styles.fieldBlock}>
              <label htmlFor="de-category">
                Garment type
                <ProvenanceBadge kind={categoryProvenance(piece)} />
              </label>
              <select
                id="de-category"
                value={piece.category}
                onChange={(e) => {
                  const category = e.target.value
                  onUpdatePiece(piece.id, (p) =>
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
          </div>
        </section>

        <section className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>Visual design</h3>
          {visualRows.length ? (
            <div className={styles.visibleDetails}>
              {visualRows.map(([key, value, prov]) => (
                <div key={key} className={styles.detailRow}>
                  <strong>
                    {key === 'color'
                      ? 'Color'
                      : key === 'neckline'
                        ? 'Neckline'
                        : key === 'sleeves'
                          ? 'Sleeves'
                          : 'Construction'}
                  </strong>
                  <span>{String(value)}</span>
                  <ProvenanceBadge kind={provenanceKey(prov) ?? (key === 'panels' ? 'ai' : 'visual')} />
                </div>
              ))}
            </div>
          ) : (
            <p className={styles.lead}>No per-garment visual details yet — edit fields below or generate AI PDF.</p>
          )}
          <div className={styles.fieldGrid}>
            <div className={styles.fieldBlock}>
              <label htmlFor="de-color">
                Color hint
                <ProvenanceBadge kind={provenanceKey(piece.color_hint_provenance)} />
              </label>
              <input
                id="de-color"
                value={piece.color_hint ?? ''}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    color_hint: e.target.value,
                    color_hint_provenance: 'designer',
                  }))
                }
              />
            </div>
            <div className={styles.fieldBlock}>
              <label htmlFor="de-silhouette">
                Silhouette
                <ProvenanceBadge
                  kind={provenanceKey(
                    (piece.fit as { silhouette_provenance?: string } | undefined)
                      ?.silhouette_provenance,
                  )}
                />
              </label>
              <input
                id="de-silhouette"
                value={piece.fit?.silhouette ?? ''}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    fit: {
                      ...(p.fit ?? {}),
                      silhouette: e.target.value,
                      silhouette_provenance: 'designer',
                    },
                  }))
                }
              />
              <ChipRow
                options={SILHOUETTE_SUGGESTIONS}
                value={piece.fit?.silhouette ?? ''}
                onPick={(next) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    fit: {
                      ...(p.fit ?? {}),
                      silhouette: next,
                      silhouette_provenance: 'designer',
                    },
                  }))
                }
              />
            </div>
          </div>
        </section>

        <section className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>Materials & fabric</h3>
          <div className={styles.fieldGrid}>
            <div className={`${styles.fieldBlock} ${styles.fieldBlockWide}`}>
              <label htmlFor="de-shell">
                Material / shell
                <ProvenanceBadge
                  kind={
                    provenanceKey(piece.materials?.shell?.provenance) ||
                    (piece.materials?.shell?.source === 'ai'
                      ? 'ai'
                      : piece.materials?.shell?.source === 'designer'
                        ? 'user'
                        : null)
                  }
                />
              </label>
              <input
                id="de-shell"
                value={piece.materials?.shell?.name ?? ''}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    materials: {
                      ...(p.materials ?? {}),
                      shell: {
                        ...(p.materials?.shell ?? {}),
                        name: e.target.value,
                        source: 'designer',
                        provenance: 'designer',
                      },
                    },
                  }))
                }
              />
              {piece.materials?.shell?.composition === 'Unknown' ? (
                <p className={styles.lead}>Composition unknown — confirm before production.</p>
              ) : null}
              <ChipRow
                options={SHELL_SUGGESTIONS}
                value={piece.materials?.shell?.name ?? ''}
                onPick={(next) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    materials: {
                      ...(p.materials ?? {}),
                      shell: {
                        ...(p.materials?.shell ?? {}),
                        name: next,
                        source: 'designer',
                        provenance: 'designer',
                      },
                    },
                  }))
                }
              />
            </div>
          </div>
        </section>

        <section className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>Fit & construction</h3>
          <div className={styles.fieldGrid}>
            <div className={`${styles.fieldBlock} ${styles.fieldBlockWide}`}>
              <label htmlFor="de-closure">
                Closure
                <ProvenanceBadge
                  kind={
                    provenanceKey(
                      (piece.closures as { provenance?: string } | undefined)?.provenance,
                    ) || (piece.closures?.source === 'ai' ? 'ai' : null)
                  }
                />
              </label>
              <input
                id="de-closure"
                value={piece.closures?.type ?? ''}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    closures: {
                      ...(p.closures ?? {}),
                      type: e.target.value,
                      source: 'designer',
                      provenance: 'designer',
                    },
                  }))
                }
              />
              <ChipRow
                options={CLOSURE_SUGGESTIONS}
                value={piece.closures?.type ?? ''}
                onPick={(next) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    closures: {
                      ...(p.closures ?? {}),
                      type: next,
                      source: 'designer',
                      provenance: 'designer',
                    },
                  }))
                }
              />
            </div>
          </div>
          <details className={styles.detailsCollapse}>
            <summary>Advanced notes</summary>
            <div className={styles.fieldBlock}>
              <label htmlFor="de-ease">Ease / fit note</label>
              <input
                id="de-ease"
                value={piece.fit?.ease_note ?? ''}
                onChange={(e) =>
                  onUpdatePiece(piece.id, (p) => ({
                    ...p,
                    fit: { ...(p.fit ?? {}), ease_note: e.target.value },
                  }))
                }
              />
            </div>
          </details>
        </section>

        {pieces.length > 1 ? (
          <button
            type="button"
            className={styles.dangerBtn}
            onClick={() => removePiece(piece.id)}
          >
            <Trash2 size={14} aria-hidden /> Remove piece
          </button>
        ) : null}
      </>
    )
  }

  const renderFinished = (piece: TechpackPiece) => (
    <>
      <p className={styles.lead}>
        Finished garment measurements for {pieceDisplayLabel(piece)}. Unknown values may stay empty.
      </p>
      <div className={styles.fieldGrid}>
        {Object.keys(piece.finished_measurements ?? {}).length === 0 ? (
          <p className={styles.lead}>No finished POMs for this category.</p>
        ) : (
          Object.entries(piece.finished_measurements ?? {}).map(([key, value]) => (
            <MeasuredField
              key={key}
              compact
              label={POM_LABELS[key] ?? key.replace(/_/g, ' ')}
              helpKey={POM_HELP_KEY[key]}
              value={value as MeasuredValue}
              onChange={(next) =>
                onUpdatePiece(piece.id, (p) => ({
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
      </div>
    </>
  )

  return (
    <div className={styles.scrim} role="presentation">
      <div
        ref={dialogRef}
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="details-editor"
      >
        <header className={styles.header}>
          <div className={styles.headerText}>
            <p className={styles.kicker}>Create Real Design</p>
            <h2 id={titleId} className={styles.title}>
              Measurements & details
            </h2>
            <p className={styles.subtitle}>
              Optional corrections · autosave on · same data on every screen size
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

        <nav className={styles.navTabs} role="tablist" aria-label="Detail sections">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={activeId === item.id}
              className={
                activeId === item.id ? `${styles.navTab} ${styles.navTabActive}` : styles.navTab
              }
              onClick={() => setActiveId(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <aside className={styles.sidebar} aria-label="Editor navigation">
          {lookThumbnailUrl ? (
            <div className={styles.lookPreview}>
              <img src={lookThumbnailUrl} alt="" />
            </div>
          ) : null}
          <p className={styles.sideNavLabel}>Sections</p>
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={
                activeId === item.id
                  ? `${styles.sideNavBtn} ${styles.sideNavBtnActive}`
                  : styles.sideNavBtn
              }
              onClick={() => setActiveId(item.id)}
            >
              {item.label}
            </button>
          ))}
          <p className={styles.sideNavLabel}>Garments</p>
          {renderGarmentPills('side')}
          <button type="button" className={styles.addPieceBtn} onClick={addPiece}>
            <Plus size={14} aria-hidden /> Add piece
          </button>
        </aside>

        <div className={styles.main}>
          {activeId === 'garments' ? (
            <>
              <div className={styles.fieldGrid}>
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
                <div className={`${styles.fieldBlock} ${styles.fieldBlockWide}`}>
                  <label htmlFor="de-notes">Look notes</label>
                  <textarea
                    id="de-notes"
                    rows={2}
                    value={spec.look_notes ?? ''}
                    onChange={(e) =>
                      onChangeSpec((prev) => ({ ...prev, look_notes: e.target.value }))
                    }
                  />
                </div>
              </div>

              <p className={styles.sideNavLabel} style={{ marginTop: 8 }}>
                Active garment
              </p>
              {renderGarmentPills('mobile')}

              {activePiece ? (
                renderPieceEditor(activePiece)
              ) : (
                <p className={styles.lead}>Add a garment piece to edit materials and construction.</p>
              )}
            </>
          ) : null}

          {activeId === 'body' ? (
            <>
              <h3 className={styles.sectionHeading}>Body measurements</h3>
              <p className={styles.lead}>
                Body measurements describe the person. Leave unknown values empty.
              </p>
              <div className={styles.fieldGrid}>
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
              </div>
            </>
          ) : null}

          {activeId === 'preferences' ? (
            <>
              <h3 className={styles.sectionHeading}>Preferences</h3>
              <div className={styles.fieldGrid}>
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
                <div className={`${styles.fieldBlock} ${styles.fieldBlockWide}`}>
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
              </div>
            </>
          ) : null}

          {activeId === 'finished' ? (
            <>
              <p className={styles.sideNavLabel}>Garment</p>
              {renderGarmentPills('mobile')}
              {activePiece ? (
                renderFinished(activePiece)
              ) : (
                <p className={styles.lead}>Select a garment to edit finished measurements.</p>
              )}
            </>
          ) : null}
        </div>

        <footer className={styles.footer}>
          <div className={styles.footerStack}>
            <p className={styles.saveStatusLine} role="status" aria-live="polite">
              {saveStatus || (busy ? 'Saving…' : 'Edits save automatically')}
            </p>
            <button
              type="button"
              className={styles.doneBtn}
              data-testid="details-done"
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
