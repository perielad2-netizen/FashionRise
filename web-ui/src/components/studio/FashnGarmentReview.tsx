import { useMemo, useState } from 'react'
import type { FashnGarmentPrepareResult, FashnRealisticPiece } from '@/services/ai/magicApi'
import { confirmDialogStyles as styles } from './ConfirmDialog'

type Props = {
  prep: FashnGarmentPrepareResult
  realisticPieces: FashnRealisticPiece[] | null
  realismBusy: boolean
  realismError: string | null
  detailsOpen: boolean
  onToggleDetails: () => void
}

function pieceLabel(category: string, index: number, total: number): string {
  const c = category.toLowerCase()
  if (c === 'tops') return 'Top'
  if (c === 'bottoms') return 'Bottom'
  if (total === 1) return 'Garment'
  return `Piece ${index + 1}`
}

export function FashnGarmentReview({
  prep,
  realisticPieces,
  realismBusy,
  realismError,
  detailsOpen,
  onToggleDetails,
}: Props) {
  const [lightbox, setLightbox] = useState<{ src: string; label: string } | null>(null)

  const sketchPieces = prep.pieces
  const hasRealistic = Boolean(realisticPieces && realisticPieces.length > 0)
  const fidelityFailures = useMemo(
    () => (realisticPieces ?? []).filter((p) => p.fidelity && p.fidelity.ok === false),
    [realisticPieces],
  )
  const softWarnings = useMemo(
    () =>
      (realisticPieces ?? []).filter(
        (p) =>
          p.fidelity &&
          p.fidelity.ok !== false &&
          typeof p.fidelity.message === 'string' &&
          p.fidelity.message.trim().length > 0 &&
          p.fidelity.code &&
          p.fidelity.code !== 'FIDELITY_OK',
      ),
    [realisticPieces],
  )

  const costSummary = useMemo(() => {
    const realism = prep.realism_estimate_cents ?? 0
    const fashn = prep.estimate_cents
    const combined = prep.combined_estimate_cents ?? realism + fashn
    return { realism, fashn, combined }
  }, [prep])

  return (
    <>
      <div className={styles.costRow} data-testid="fashn-cost-summary">
        <div>
          <strong>1. Realistic garment (OpenAI)</strong> — about {costSummary.realism}¢
          {prep.realism_calls && prep.realism_calls > 1 ? ` · ${prep.realism_calls} images` : ''}
          {hasRealistic ? ' · already generated for this review' : ''}
        </div>
        <div>
          <strong>2. FASHN try-on</strong> — about {costSummary.fashn}¢ · {prep.fashn_calls} credit
          {prep.fashn_calls === 1 ? '' : 's'} · charged only after Accept & Try On
        </div>
        <div>
          Combined estimate about <strong>{costSummary.combined}¢</strong> if you run both stages.
          Regenerate Garment charges OpenAI again with a new key. Cancel never starts FASHN.
        </div>
      </div>

      {!prep.quality_ok ? (
        <p className={styles.error} role="alert">
          {prep.quality_notes ||
            'Prepared plates do not look like a filled garment. Adjust your sketch fills, then retry.'}
        </p>
      ) : null}

      <p className={styles.hint} style={{ marginBottom: 8 }}>
        Layout: <strong>{prep.layout === 'two_piece' ? 'two-piece' : 'one-piece'}</strong>.{' '}
        {hasRealistic
          ? 'Compare your sketch with the realistic product image, then Accept before FASHN.'
          : 'Review the sketch plates, then generate a realistic product garment.'}
      </p>

      <button type="button" className={styles.detailsToggle} onClick={onToggleDetails}>
        {detailsOpen ? 'Hide provider details' : 'Show provider details'}
      </button>
      {detailsOpen ? (
        <p className={styles.hint} style={{ marginBottom: 10 }}>
          {prep.notice_text}
        </p>
      ) : null}

      {realismError ? (
        <p className={styles.error} role="alert" data-testid="fashn-realism-error">
          {realismError}
        </p>
      ) : null}
      {fidelityFailures.length > 0 ? (
        <p className={styles.error} role="alert" data-testid="fashn-fidelity-hard-fail">
          {fidelityFailures[0].fidelity?.message ||
            'Fidelity checks failed. Accept is disabled — regenerate or edit the sketch.'}
        </p>
      ) : null}
      {softWarnings.length > 0 && fidelityFailures.length === 0 ? (
        <p className={styles.hint} role="status" data-testid="fashn-fidelity-warning">
          Fidelity note: {softWarnings[0].fidelity?.message}
        </p>
      ) : null}
      {realismBusy ? (
        <p className={styles.hint} data-testid="fashn-realism-busy">
          Generating realistic garment…
        </p>
      ) : null}

      <section aria-label="Your design">
        <p className={styles.pieceLabel}>Step 1 — Your design</p>
        <div
          className={styles.pieceGrid}
          data-testid="fashn-sketch-pieces"
          data-layout={prep.layout}
        >
          {sketchPieces.map((piece, index) => {
            const label = pieceLabel(piece.category, index, sketchPieces.length)
            return (
              <div key={`sketch-${piece.category}-${index}`} className={styles.pieceCard}>
                <p className={styles.pieceLabel}>{label}</p>
                <button
                  type="button"
                  className={styles.pieceActions}
                  style={{ padding: 0, border: 0, background: 'none', display: 'block', width: '100%' }}
                  onClick={() => setLightbox({ src: piece.image_base64, label: `${label} sketch` })}
                  aria-label={`Enlarge ${label} sketch`}
                >
                  <img
                    className={styles.pieceThumb}
                    src={piece.image_base64}
                    alt={`${label} sketch plate`}
                  />
                </button>
              </div>
            )
          })}
        </div>
      </section>

      {hasRealistic ? (
        <section aria-label="Realistic garment" style={{ marginTop: 12 }}>
          <p className={styles.pieceLabel}>Step 2 — Realistic garment</p>
          <div
            className={styles.pieceGrid}
            data-testid="fashn-realistic-pieces"
            data-layout={prep.layout}
          >
            {(realisticPieces ?? []).map((piece, index) => {
              const label = pieceLabel(piece.category, index, realisticPieces!.length)
              const failed = piece.fidelity && piece.fidelity.ok === false
              return (
                <div key={`real-${piece.category}-${index}`} className={styles.pieceCard}>
                  <p className={styles.pieceLabel}>
                    {label}
                    {failed ? ' · fidelity failed' : ''}
                  </p>
                  <button
                    type="button"
                    style={{ padding: 0, border: 0, background: 'none', display: 'block', width: '100%' }}
                    onClick={() =>
                      setLightbox({ src: piece.image_base64, label: `${label} realistic` })
                    }
                    aria-label={`Enlarge ${label} realistic garment`}
                  >
                    <img
                      className={styles.pieceThumb}
                      src={piece.image_base64}
                      alt={`${label} realistic product`}
                    />
                  </button>
                </div>
              )
            })}
          </div>
        </section>
      ) : null}

      {!prep.live_http ? (
        <p className={styles.error}>FASHN is not live-armed yet. Confirm stay disabled.</p>
      ) : null}
      {prep.openai_live_http === false ? (
        <p className={styles.error}>
          OpenAI live HTTP is off — realistic garment generation cannot run on this server yet.
        </p>
      ) : null}

      {lightbox ? (
        <div
          className={styles.lightbox}
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.label}
          data-testid="fashn-piece-lightbox"
          onClick={() => setLightbox(null)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setLightbox(null)
          }}
        >
          <button
            type="button"
            className={styles.lightboxClose}
            onClick={() => setLightbox(null)}
          >
            Close
          </button>
          <img
            className={styles.lightboxImg}
            src={lightbox.src}
            alt={lightbox.label}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}
    </>
  )
}
