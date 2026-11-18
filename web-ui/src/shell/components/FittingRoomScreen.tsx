import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { isFittingRoomUiEnabled } from '@/config/fittingRoomUi'
import {
  clearOutfitSession,
  consumeFittingRoomPlantedNotice,
  deleteFittingRoomAsset,
  deleteSavedResult,
  compressFittingRoomDataUrl,
  fileToFittingRoomDataUrl,
  listSavedResults,
  newOutfitPieceId,
  readFittingRoomAsset,
  readOutfitSession,
  saveFittingResult,
  writeFittingRoomAsset,
  writeOutfitSession,
  type FittingRoomOutfitPiece,
  type FittingRoomSavedResult,
} from '@/lib/fittingRoomStore'
import { requestShare } from '@/lib/sharePromo'
import {
  enqueueFittingRoomTryOn,
  fetchFittingRoomPreflight,
  type FittingRoomPreflight,
} from '@/services/ai/fittingRoomApi'
import { fetchJobImageBlob } from '@/services/ai/magicApi'
import { pollAiJobUntilSettled } from '@/services/ai/pollAiJob'
import { ApiError } from '@/services/api/client'
import { useAiStarsWallet } from '@/hooks/useAiStarsWallet'
import { armNativeFilePickerForInput } from '@/services/native/filePickerGuard'
import { AiSpendConfirmDialog } from '@/shell/components/AiSpendConfirmDialog'
import { StarsShopModal } from '@/shell/components/StarsShopModal'
import styles from './FittingRoomScreen.module.css'

type Props = {
  userId: string
  onBackToStudio: () => void
}

const DEFAULT_CATEGORIES = ['auto', 'tops', 'bottoms', 'one-pieces', 'dresses', 'outerwear', 'shoes']

function downloadSuccessCopy(method: 'web' | 'gallery' | 'share'): string {
  if (method === 'gallery') return 'Saved to your gallery ✓'
  if (method === 'share') return 'Opened the system share sheet — save from there to finish.'
  return 'Download started.'
}

function comboWarning(categories: string[], sets: string[][]): string | null {
  const cats = new Set(categories.filter((c) => c && c !== 'auto'))
  for (const set of sets) {
    if (set.every((c) => cats.has(c))) {
      return `Selected categories (${set.join(' + ')}) usually conflict on one body. The AI will still try, but results may look inconsistent — prefer replacing one piece.`
    }
  }
  return null
}

/** Never show raw OpenAI moderation / BadRequest dumps in the Fitting Room UI. */
function ownerSafeFittingRoomError(raw: string | null | undefined): string {
  const text = (raw || '').trim()
  if (!text) {
    return 'Fitting Room could not finish this preview. No Stars were charged.'
  }
  const lower = text.toLowerCase()
  if (
    lower.includes('moderation_blocked') ||
    lower.includes('badrequesterror') ||
    lower.includes('request_id=') ||
    lower.includes('images.edit rejected') ||
    lower.includes('categories=sexual')
  ) {
    return 'Fitting Room could not finish this preview. No Stars were charged.'
  }
  return text
}

export function FittingRoomScreen({ userId, onBackToStudio }: Props) {
  const personInputId = useId()
  const personCameraInputId = useId()
  const garmentInputId = useId()
  const garmentCameraInputId = useId()
  const personRef = useRef<HTMLInputElement>(null)
  const personCameraRef = useRef<HTMLInputElement>(null)
  const garmentRef = useRef<HTMLInputElement>(null)
  const garmentCameraRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const noticeTimer = useRef<number | null>(null)
  const replacePieceId = useRef<string | null>(null)

  const openNativePicker = (el: HTMLInputElement | null, opts: { camera: boolean }) => {
    if (!el) return
    // Always arm on Android camera/gallery sheets — Back during CAMERA permission
    // must not finish the Activity (crash + stuck file-chooser loop).
    armNativeFilePickerForInput(el, { camera: opts.camera })
    el.click()
  }

  const openGarmentPicker = (mode: 'gallery' | 'camera', replaceId: string | null = null) => {
    replacePieceId.current = replaceId
    const el = mode === 'camera' ? garmentCameraRef.current : garmentRef.current
    openNativePicker(el, { camera: mode === 'camera' })
  }

  const [personUrl, setPersonUrl] = useState<string | null>(null)
  const [pieces, setPieces] = useState<FittingRoomOutfitPiece[]>([])
  const [draftCategory, setDraftCategory] = useState('auto')
  const [preflight, setPreflight] = useState<FittingRoomPreflight | null>(null)
  const [consent, setConsent] = useState(false)
  const [phase, setPhase] = useState<'idle' | 'running' | 'done' | 'failed'>('idle')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [resultJobId, setResultJobId] = useState<string | null>(null)
  const [resultBlobUrl, setResultBlobUrl] = useState<string | null>(null)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeTone, setNoticeTone] = useState<'ok' | 'info' | 'error'>('ok')
  const [saved, setSaved] = useState<FittingRoomSavedResult[]>([])
  const [spendOpen, setSpendOpen] = useState(false)
  const [shopOpen, setShopOpen] = useState(false)
  const [resultsOpen, setResultsOpen] = useState(false)
  /** Wait modal stays open after success so the preview appears in-place (no scroll hunt). */
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [waitTick, setWaitTick] = useState(0)
  const { balance, unlimited, costs } = useAiStarsWallet()

  const waitMessages = useMemo(
    () => [
      'Creating your Fitting Room preview…',
      'Matching fabric and colors…',
      'Almost ready…',
    ],
    [],
  )

  const showNotice = useCallback((text: string, tone: 'ok' | 'info' | 'error') => {
    setNotice(text)
    setNoticeTone(tone)
    if (noticeTimer.current != null) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => {
      setNotice(null)
      noticeTimer.current = null
    }, 4200)
  }, [])

  const persistOutfit = useCallback(
    async (next: FittingRoomOutfitPiece[]) => {
      setPieces(next)
      await writeOutfitSession({
        key: `${userId}:outfit`,
        userId,
        pieces: next,
        updatedAt: new Date().toISOString(),
      })
    },
    [userId],
  )

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      if (noticeTimer.current != null) window.clearTimeout(noticeTimer.current)
      if (resultBlobUrl) URL.revokeObjectURL(resultBlobUrl)
    }
  }, [resultBlobUrl])

  useEffect(() => {
    if (!isFittingRoomUiEnabled()) return
    let cancelled = false
    ;(async () => {
      const [person, outfit, savedRows] = await Promise.all([
        readFittingRoomAsset(userId, 'person'),
        readOutfitSession(userId),
        listSavedResults(userId),
      ])
      if (cancelled) return
      if (person?.dataUrl) setPersonUrl(person.dataUrl)
      if (outfit?.pieces?.length) {
        setPieces(outfit.pieces)
      } else {
        // Migrate legacy single garment into outfit session once.
        const legacy = await readFittingRoomAsset(userId, 'garment')
        if (legacy?.dataUrl) {
          const migrated: FittingRoomOutfitPiece[] = [
            {
              id: newOutfitPieceId(),
              category: legacy.garmentCategory || 'auto',
              dataUrl: legacy.dataUrl,
              mimeType: legacy.mimeType,
              updatedAt: legacy.updatedAt,
            },
          ]
          if (!cancelled) await persistOutfit(migrated)
        }
      }
      if (!cancelled) setSaved(savedRows)
      const planted = consumeFittingRoomPlantedNotice()
      if (!cancelled && planted) {
        const label = planted.title?.trim() || 'this look'
        showNotice(
          `Ready to try on “${label}”. Add your photo, then tap Try on.`,
          'info',
        )
      }
      try {
        const pf = await fetchFittingRoomPreflight()
        if (!cancelled) setPreflight(pf)
      } catch (err) {
        if (!cancelled) {
          const status = err instanceof ApiError ? err.status : 0
          // 403 from nginx allowlist / gate vs true server disabled (200 + enabled:false).
          setErrorMsg(
            status === 403
              ? 'Fitting Room API is blocked by the edge allowlist. Ask an operator to open /ai/fitting-room/*.'
              : status === 401
                ? 'Sign in again to use Fitting Room.'
                : 'Could not reach Fitting Room preflight. Check connection and retry.',
          )
          setPreflight({
            enabled: false,
            live_http: false,
            consent_version: '',
            notice_text: '',
            prompt_version: '',
            supported_categories: DEFAULT_CATEGORIES,
            preview_disclaimer:
              'Concept preview only — not a fit guarantee. Results may differ from real garments.',
            ai_gate: false,
            stars_cost: 20,
            stars_cost_note: '20 Stars per successful Fitting Room preview (flat rate).',
            max_outfit_pieces: 4,
            conflicting_category_sets: [],
          })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [userId, persistOutfit, showNotice])

  const starsCost = preflight?.stars_cost ?? costs.fitting_room ?? 20
  const maxPieces = preflight?.max_outfit_pieces ?? 4
  const categories = preflight?.supported_categories?.length
    ? preflight.supported_categories
    : DEFAULT_CATEGORIES
  const warning = useMemo(
    () => comboWarning(
      pieces.map((p) => p.category),
      preflight?.conflicting_category_sets ?? [],
    ),
    [pieces, preflight?.conflicting_category_sets],
  )

  const resetFileInput = (el: HTMLInputElement | null) => {
    if (el) el.value = ''
  }

  const onPickPerson = async (file: File | null) => {
    if (!file) return
    try {
      const { dataUrl, mimeType } = await fileToFittingRoomDataUrl(file)
      await writeFittingRoomAsset({
        userId,
        kind: 'person',
        dataUrl,
        mimeType,
        updatedAt: new Date().toISOString(),
      })
      setPersonUrl(dataUrl)
      setErrorMsg(null)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Could not save your photo.')
    } finally {
      resetFileInput(personRef.current)
      resetFileInput(personCameraRef.current)
    }
  }

  const onPickGarment = async (file: File | null) => {
    if (!file) return
    try {
      const { dataUrl, mimeType } = await fileToFittingRoomDataUrl(file)
      const replaceId = replacePieceId.current
      replacePieceId.current = null
      let next: FittingRoomOutfitPiece[]
      if (replaceId) {
        next = pieces.map((p) =>
          p.id === replaceId
            ? {
                ...p,
                dataUrl,
                mimeType,
                category: draftCategory,
                updatedAt: new Date().toISOString(),
              }
            : p,
        )
      } else {
        if (pieces.length >= maxPieces) {
          setErrorMsg(`Outfit supports up to ${maxPieces} clothing pieces. Replace one instead.`)
          return
        }
        next = [
          ...pieces,
          {
            id: newOutfitPieceId(),
            category: draftCategory,
            dataUrl,
            mimeType,
            updatedAt: new Date().toISOString(),
          },
        ]
      }
      await persistOutfit(next)
      // Keep legacy single garment mirror for older paths.
      await writeFittingRoomAsset({
        userId,
        kind: 'garment',
        dataUrl: next[next.length - 1].dataUrl,
        mimeType: next[next.length - 1].mimeType,
        updatedAt: new Date().toISOString(),
        garmentCategory: next[next.length - 1].category,
      })
      setErrorMsg(null)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Could not save clothing image.')
    } finally {
      resetFileInput(garmentRef.current)
      resetFileInput(garmentCameraRef.current)
    }
  }

  const clearPerson = async () => {
    await deleteFittingRoomAsset(userId, 'person')
    setPersonUrl(null)
  }

  const removePiece = async (id: string) => {
    const next = pieces.filter((p) => p.id !== id)
    await persistOutfit(next)
    if (!next.length) {
      await deleteFittingRoomAsset(userId, 'garment')
    }
  }

  const clearOutfit = async () => {
    await clearOutfitSession(userId)
    await deleteFittingRoomAsset(userId, 'garment')
    setPieces([])
  }

  useEffect(() => {
    if (phase !== 'running') {
      setWaitTick(0)
      return
    }
    const id = window.setInterval(() => setWaitTick((n) => n + 1), 3800)
    return () => window.clearInterval(id)
  }, [phase])

  useEffect(() => {
    if (phase !== 'running' && !previewModalOpen && !resultsOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [phase, previewModalOpen, resultsOpen])

  const persistResult = useCallback(
    async (jobId: string, categories: string[]) => {
      const blob = await fetchJobImageBlob(jobId)
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result || ''))
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(blob)
      })
      const record: FittingRoomSavedResult = {
        id: `frsave_${jobId}`,
        userId,
        jobId,
        dataUrl,
        label: `Outfit ${new Date().toLocaleString()}`,
        outfitCategories: categories,
        createdAt: new Date().toISOString(),
      }
      await saveFittingResult(record)
      const rows = await listSavedResults(userId)
      setSaved(rows)
      return rows
    },
    [userId],
  )

  const runTryOn = async () => {
    if (!personUrl || !pieces.length || !preflight?.enabled || !consent) return
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setPhase('running')
    setPreviewModalOpen(true)
    setStatusMsg('Creating your Fitting Room preview…')
    setErrorMsg(null)
    if (resultBlobUrl) {
      URL.revokeObjectURL(resultBlobUrl)
      setResultBlobUrl(null)
    }
    setResultJobId(null)
    try {
      // Phone PNGs + look plates can exceed nginx body limits (~25MB seen live) —
      // re-encode under budget right before enqueue (covers older IndexedDB assets).
      const personCompressed = await compressFittingRoomDataUrl(personUrl)
      const garmentCompressed = await Promise.all(
        pieces.map(async (p) => {
          const img = await compressFittingRoomDataUrl(p.dataUrl)
          return {
            imageBase64: img.dataUrl,
            category: p.category,
            ...(p.source ? { source: p.source } : {}),
          }
        }),
      )
      const idem = `fitting_room:${userId.slice(0, 8)}:${Date.now().toString(36)}`
      const job = await enqueueFittingRoomTryOn({
        personImageBase64: personCompressed.dataUrl,
        garmentPieces: garmentCompressed,
        idempotencyKey: idem,
        consentAcknowledged: true,
        consentVersion: preflight.consent_version,
        signal: ac.signal,
      })
      const settled = await pollAiJobUntilSettled({ jobId: job.id, signal: ac.signal })
      if (settled.status !== 'completed') {
        setPhase('failed')
        setPreviewModalOpen(false)
        setErrorMsg(ownerSafeFittingRoomError(settled.error_message))
        setStatusMsg(null)
        return
      }
      const blob = await fetchJobImageBlob(settled.id, ac.signal)
      const url = URL.createObjectURL(blob)
      setResultJobId(settled.id)
      setResultBlobUrl(url)
      setPhase('done')
      setStatusMsg('Preview ready — saved to your Fitting Room results.')
      try {
        await persistResult(
          settled.id,
          pieces.map((p) => p.category),
        )
        showNotice('Saved to Fitting Room results ✓', 'ok')
      } catch {
        showNotice('Preview ready, but auto-save failed — use Save.', 'info')
      }
    } catch (err) {
      if (ac.signal.aborted) return
      setPhase('failed')
      setPreviewModalOpen(false)
      setStatusMsg(null)
      if (err instanceof ApiError) {
        setErrorMsg(ownerSafeFittingRoomError(err.message || 'Fitting Room request failed. No Stars were charged.'))
      } else {
        setErrorMsg(
          ownerSafeFittingRoomError(
            err instanceof Error
              ? err.message
              : 'Fitting Room request failed. No Stars were charged.',
          ),
        )
      }
    }
  }

  const onDownload = async () => {
    if (!resultJobId || downloadBusy) return
    setDownloadBusy(true)
    try {
      const blob = await fetchJobImageBlob(resultJobId)
      const { saveOrDownloadBlob } = await import('@/lib/exportCanvas')
      const method = await saveOrDownloadBlob(blob, `fashionrise-fitting-${resultJobId.slice(0, 8)}.png`)
      showNotice(downloadSuccessCopy(method), method === 'share' ? 'info' : 'ok')
    } catch {
      showNotice('Download failed. Try again.', 'error')
    } finally {
      setDownloadBusy(false)
    }
  }

  const onShare = async () => {
    if (!resultBlobUrl) return
    try {
      const outcome = await requestShare({
        kind: 'look',
        title: 'FashionRise Fitting Room',
        imageUrl: resultBlobUrl,
        imageFileName: 'fashionrise-fitting-preview.png',
      })
      if (outcome === 'shared') showNotice('Share sheet opened.', 'info')
      else if (outcome === 'needs-fallback') {
        showNotice('Sharing is not available — use Download instead.', 'info')
      }
    } catch {
      showNotice('Share failed. Try download instead.', 'error')
    }
  }

  const onSavePrivate = async () => {
    if (!resultJobId) return
    try {
      await persistResult(
        resultJobId,
        pieces.map((p) => p.category),
      )
      showNotice('Saved to Fitting Room results ✓', 'ok')
    } catch {
      showNotice('Could not save this preview.', 'error')
    }
  }

  const cancelRunning = () => {
    abortRef.current?.abort()
    setPhase('idle')
    setPreviewModalOpen(false)
    setStatusMsg(null)
  }

  const closePreviewModal = () => {
    setPreviewModalOpen(false)
  }

  const onDownloadSaved = async (row: FittingRoomSavedResult) => {
    if (downloadBusy) return
    setDownloadBusy(true)
    try {
      let blob: Blob | null = null
      if (row.jobId) {
        try {
          blob = await fetchJobImageBlob(row.jobId)
        } catch {
          blob = null
        }
      }
      if (!blob) {
        const res = await fetch(row.dataUrl)
        blob = await res.blob()
      }
      const { saveOrDownloadBlob } = await import('@/lib/exportCanvas')
      const slug = (row.jobId || row.id).slice(0, 8)
      const method = await saveOrDownloadBlob(blob, `fashionrise-fitting-${slug}.png`)
      showNotice(downloadSuccessCopy(method), method === 'share' ? 'info' : 'ok')
    } catch {
      showNotice('Download failed. Try again.', 'error')
    } finally {
      setDownloadBusy(false)
    }
  }

  const onShareSaved = async (row: FittingRoomSavedResult) => {
    try {
      const outcome = await requestShare({
        kind: 'look',
        title: 'FashionRise Fitting Room',
        imageUrl: row.dataUrl,
        imageFileName: 'fashionrise-fitting-preview.png',
      })
      if (outcome === 'shared') showNotice('Share sheet opened.', 'info')
      else if (outcome === 'needs-fallback') {
        showNotice('Sharing is not available — use Download instead.', 'info')
      }
    } catch {
      showNotice('Share failed. Try download instead.', 'error')
    }
  }

  const onDeleteSaved = async (id: string) => {
    await deleteSavedResult(id)
    const rows = await listSavedResults(userId)
    setSaved(rows)
  }

  if (!isFittingRoomUiEnabled()) {
    return (
      <section className={styles.gateOff} aria-labelledby="fr-off-title">
        <h1 id="fr-off-title">Fitting Room</h1>
        <p>This experience is not enabled in this build.</p>
        <button type="button" className={styles.btn} onClick={onBackToStudio}>
          Back to Studio
        </button>
      </section>
    )
  }

  const serverOff = preflight != null && !preflight.enabled
  const canTry =
    Boolean(personUrl && pieces.length && consent && preflight?.enabled && phase !== 'running')

  return (
    <section className={styles.screen} aria-labelledby="fitting-room-brand" data-testid="fitting-room-screen">
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <p className={styles.eyebrow}>FashionRise</p>
          <h1 className={styles.brand} id="fitting-room-brand">
            Fitting Room
          </h1>
          <p className={styles.lead}>
            Upload your photo and clothing pieces for a private AI try-on preview.
          </p>
        </div>
        <div className={styles.headActions}>
          <button
            type="button"
            className={styles.btnGhost}
            data-testid="fitting-room-results-open"
            onClick={() => setResultsOpen(true)}
          >
            Results{saved.length ? ` (${saved.length})` : ''}
          </button>
          <button type="button" className={styles.btnGhost} onClick={onBackToStudio}>
            Back to Studio
          </button>
        </div>
      </header>

      {serverOff ? (
        <p className={`${styles.status} ${styles.statusError}`} role="status">
          Fitting Room is disabled on this server. Ask an operator to enable it for testing.
        </p>
      ) : null}

      <div className={styles.steps}>
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>1 · My Photo</h2>
          <p className={styles.panelHint}>
            Full-body photo works best. Use your gallery or camera. Saved privately on this device
            until you run try-on.
          </p>
          <div className={styles.preview}>
            {personUrl ? (
              <img className={styles.previewImg} src={personUrl} alt="Your saved Fitting Room photo" />
            ) : (
              <p className={styles.previewEmpty}>No photo yet</p>
            )}
          </div>
          <input
            ref={personRef}
            id={personInputId}
            className={styles.fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => void onPickPerson(e.target.files?.[0] ?? null)}
          />
          <input
            ref={personCameraRef}
            id={personCameraInputId}
            className={styles.fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            data-testid="fitting-room-person-camera"
            onChange={(e) => void onPickPerson(e.target.files?.[0] ?? null)}
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.btn}
              data-testid="fitting-room-person-gallery"
              onClick={() => openNativePicker(personRef.current, { camera: false })}
            >
              {personUrl ? 'Replace from gallery' : 'Choose photo'}
            </button>
            <button
              type="button"
              className={styles.btn}
              data-testid="fitting-room-person-take"
              onClick={() => openNativePicker(personCameraRef.current, { camera: true })}
            >
              {personUrl ? 'Retake photo' : 'Take photo'}
            </button>
            {personUrl ? (
              <button type="button" className={styles.btnGhost} onClick={() => void clearPerson()}>
                Delete
              </button>
            ) : null}
          </div>
        </div>

        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>2 · Build Outfit</h2>
          <p className={styles.panelHint}>
            Add or replace clothing from your gallery or camera. Previous pieces stay until you
            remove them.
          </p>
          <div className={styles.outfitGrid}>
            {pieces.length === 0 ? (
              <p className={styles.previewEmpty}>No clothing pieces yet</p>
            ) : (
              pieces.map((piece) => (
                <div key={piece.id} className={styles.outfitCard}>
                  <img src={piece.dataUrl} alt={`${piece.category} piece`} />
                  <span className={styles.outfitCat}>{piece.category}</span>
                  <div className={styles.actions}>
                    <button
                      type="button"
                      className={styles.btnGhost}
                      onClick={() => {
                        setDraftCategory(piece.category)
                        openGarmentPicker('gallery', piece.id)
                      }}
                    >
                      Replace
                    </button>
                    <button
                      type="button"
                      className={styles.btnGhost}
                      onClick={() => {
                        setDraftCategory(piece.category)
                        openGarmentPicker('camera', piece.id)
                      }}
                    >
                      Camera
                    </button>
                    <button
                      type="button"
                      className={styles.btnGhost}
                      onClick={() => void removePiece(piece.id)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
          {warning ? (
            <p className={`${styles.status} ${styles.statusError}`} role="status">
              {warning}
            </p>
          ) : null}
          <div className={styles.categoryRow} role="group" aria-label="Garment category for next piece">
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                className={c === draftCategory ? `${styles.chip} ${styles.chipActive}` : styles.chip}
                aria-pressed={c === draftCategory}
                onClick={() => setDraftCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <input
            ref={garmentRef}
            id={garmentInputId}
            className={styles.fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => void onPickGarment(e.target.files?.[0] ?? null)}
          />
          <input
            ref={garmentCameraRef}
            id={garmentCameraInputId}
            className={styles.fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            data-testid="fitting-room-garment-camera"
            onChange={(e) => void onPickGarment(e.target.files?.[0] ?? null)}
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.btn}
              disabled={pieces.length >= maxPieces}
              data-testid="fitting-room-garment-gallery"
              onClick={() => openGarmentPicker('gallery', null)}
            >
              Add clothing
            </button>
            <button
              type="button"
              className={styles.btn}
              disabled={pieces.length >= maxPieces}
              data-testid="fitting-room-garment-take"
              onClick={() => openGarmentPicker('camera', null)}
            >
              Take clothing photo
            </button>
            {pieces.length ? (
              <button type="button" className={styles.btnGhost} onClick={() => void clearOutfit()}>
                Clear outfit
              </button>
            ) : null}
          </div>
        </div>

        <div className={styles.panel} style={{ gridColumn: '1 / -1' }}>
          <h2 className={styles.panelTitle}>3 · AI Try-On</h2>
          <div className={styles.consent}>
            <input
              id="fr-consent"
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              disabled={!preflight?.enabled}
            />
            <label htmlFor="fr-consent">
              {preflight?.notice_text ||
                'I understand this is a visual concept preview only — not an accurate size or fit guarantee. Your photo and clothing image stay private.'}
            </label>
          </div>
          <div className={styles.tryRow}>
            <button
              type="button"
              className={styles.btnPrimary}
              disabled={!canTry}
              onClick={() => setSpendOpen(true)}
              data-testid="fitting-room-try-on"
            >
              {phase === 'failed' ? 'Retry' : 'Try on'}
            </button>
            <button
              type="button"
              className={styles.btnGhost}
              data-testid="fitting-room-results-open-inline"
              onClick={() => setResultsOpen(true)}
            >
              Open results
            </button>
          </div>
          {errorMsg ? (
            <p className={`${styles.status} ${styles.statusError}`} role="alert">
              {errorMsg}
            </p>
          ) : null}
          {phase === 'done' && resultBlobUrl ? (
            <>
              <p className={styles.status} role="status">
                {statusMsg}
              </p>
              <div className={styles.resultStage}>
                <img
                  className={styles.resultImg}
                  src={resultBlobUrl}
                  alt="AI Fitting Room concept preview"
                />
              </div>
              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.btn}
                  disabled={downloadBusy}
                  onClick={() => void onDownload()}
                >
                  {downloadBusy ? 'Saving…' : 'Download'}
                </button>
                <button type="button" className={styles.btn} onClick={() => void onShare()}>
                  Share
                </button>
                <button type="button" className={styles.btnPrimary} onClick={() => void onSavePrivate()}>
                  Save again
                </button>
                <button
                  type="button"
                  className={styles.btnGhost}
                  onClick={() => setResultsOpen(true)}
                >
                  View all results
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {downloadBusy || notice ? (
        <p
          className={`${styles.toast} ${
            noticeTone === 'error'
              ? styles.toastError
              : noticeTone === 'info'
                ? styles.toastInfo
                : styles.toastOk
          }`}
          role="status"
          data-testid="fitting-room-download-notice"
        >
          {downloadBusy ? 'Saving image…' : notice}
        </p>
      ) : null}

      <AiSpendConfirmDialog
        open={spendOpen}
        feature="fitting_room"
        cost={starsCost}
        balance={balance}
        unlimited={unlimited}
        busy={phase === 'running'}
        description="Fitting Room creates a private concept preview on your photo. Stars are charged only when the preview succeeds."
        onCancel={() => setSpendOpen(false)}
        onApproved={() => {
          setSpendOpen(false)
          void runTryOn()
        }}
        onOpenShop={() => setShopOpen(true)}
      />
      <StarsShopModal open={shopOpen} onClose={() => setShopOpen(false)} />

      {(phase === 'running' ||
        (previewModalOpen && phase === 'done' && resultBlobUrl)) &&
      typeof document !== 'undefined'
        ? createPortal(
            <div
              className={styles.waitOverlay}
              role="dialog"
              aria-modal="true"
              aria-labelledby={phase === 'running' ? 'fr-wait-title' : 'fr-preview-title'}
              data-testid={
                phase === 'running'
                  ? 'fitting-room-wait-modal'
                  : 'fitting-room-preview-modal'
              }
            >
              {phase === 'running' ? (
                <div className={styles.waitCard}>
                  <div className={styles.generatingVisual} aria-hidden>
                    <span className={styles.pulseRing} />
                    <span className={styles.pulseRingDelayed} />
                    <div className={styles.spinner} />
                  </div>
                  <strong id="fr-wait-title">
                    {waitMessages[waitTick % waitMessages.length]}
                  </strong>
                  <span className={styles.waitPill}>Rendering</span>
                  <p className={styles.waitHint}>
                    Hang tight — same Magic-style wait. Your result auto-saves when ready.
                  </p>
                  <button type="button" className={styles.btnGhost} onClick={cancelRunning}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div className={styles.previewCard} data-testid="fitting-room-preview-card">
                  <header className={styles.previewHead}>
                    <h2 id="fr-preview-title">Your try-on</h2>
                    <button
                      type="button"
                      className={styles.btnGhost}
                      data-testid="fitting-room-preview-close"
                      onClick={closePreviewModal}
                    >
                      Close
                    </button>
                  </header>
                  <div className={styles.previewResultStage}>
                    <img
                      className={styles.previewResultImg}
                      src={resultBlobUrl || undefined}
                      alt="AI Fitting Room concept preview"
                    />
                  </div>
                  <p className={styles.waitHint}>
                    {statusMsg || 'Preview ready — saved to your Fitting Room results.'}
                  </p>
                  <div className={styles.previewActions}>
                    <button
                      type="button"
                      className={styles.btn}
                      disabled={downloadBusy}
                      onClick={() => void onDownload()}
                    >
                      {downloadBusy ? 'Saving…' : 'Download'}
                    </button>
                    <button type="button" className={styles.btn} onClick={() => void onShare()}>
                      Share
                    </button>
                    <button
                      type="button"
                      className={styles.btnPrimary}
                      onClick={() => {
                        closePreviewModal()
                        setResultsOpen(true)
                      }}
                    >
                      View all results
                    </button>
                  </div>
                </div>
              )}
            </div>,
            document.body,
          )
        : null}

      {resultsOpen && typeof document !== 'undefined'
        ? createPortal(
            <div
              className={styles.resultsOverlay}
              role="dialog"
              aria-modal="true"
              aria-labelledby="fr-results-title"
              data-testid="fitting-room-results-modal"
              onClick={(e) => {
                if (e.target === e.currentTarget) setResultsOpen(false)
              }}
            >
              <div className={styles.resultsSheet}>
                <header className={styles.resultsHead}>
                  <h2 id="fr-results-title">Fitting Room results</h2>
                  <button
                    type="button"
                    className={styles.btnGhost}
                    data-testid="fitting-room-results-close"
                    onClick={() => setResultsOpen(false)}
                  >
                    Close
                  </button>
                </header>
                <p className={styles.panelHint}>
                  Saved on this device. Scroll to browse, download, share, or delete.
                </p>
                <div className={styles.resultsScroll}>
                  {saved.length === 0 ? (
                    <p className={styles.previewEmpty}>No saved previews yet — try on to create one.</p>
                  ) : (
                    <div className={styles.savedGrid}>
                      {saved.map((row) => (
                        <div key={row.id} className={styles.savedCard}>
                          <img src={row.dataUrl} alt={row.label} />
                          <span className={styles.outfitCat}>{row.label}</span>
                          <div className={styles.actions}>
                            <button
                              type="button"
                              className={styles.btnGhost}
                              disabled={downloadBusy}
                              onClick={() => void onDownloadSaved(row)}
                            >
                              Download
                            </button>
                            <button
                              type="button"
                              className={styles.btnGhost}
                              onClick={() => void onShareSaved(row)}
                            >
                              Share
                            </button>
                            <button
                              type="button"
                              className={styles.btnGhost}
                              onClick={() => void onDeleteSaved(row.id)}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </section>
  )
}
