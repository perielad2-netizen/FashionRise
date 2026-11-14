import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { isFittingRoomUiEnabled } from '@/config/fittingRoomUi'
import {
  deleteFittingRoomAsset,
  fileToFittingRoomDataUrl,
  readFittingRoomAsset,
  writeFittingRoomAsset,
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

export function FittingRoomScreen({ userId, onBackToStudio }: Props) {
  const personInputId = useId()
  const garmentInputId = useId()
  const personRef = useRef<HTMLInputElement>(null)
  const garmentRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const noticeTimer = useRef<number | null>(null)

  const [personUrl, setPersonUrl] = useState<string | null>(null)
  const [garmentUrl, setGarmentUrl] = useState<string | null>(null)
  const [category, setCategory] = useState('auto')
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

  const showNotice = useCallback((text: string, tone: 'ok' | 'info' | 'error') => {
    setNotice(text)
    setNoticeTone(tone)
    if (noticeTimer.current != null) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => {
      setNotice(null)
      noticeTimer.current = null
    }, 4200)
  }, [])

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
      const [person, garment] = await Promise.all([
        readFittingRoomAsset(userId, 'person'),
        readFittingRoomAsset(userId, 'garment'),
      ])
      if (cancelled) return
      if (person?.dataUrl) setPersonUrl(person.dataUrl)
      if (garment?.dataUrl) {
        setGarmentUrl(garment.dataUrl)
        if (garment.garmentCategory) setCategory(garment.garmentCategory)
      }
      try {
        const pf = await fetchFittingRoomPreflight()
        if (!cancelled) setPreflight(pf)
      } catch {
        if (!cancelled) {
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
          })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [userId])

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
    }
  }

  const onPickGarment = async (file: File | null) => {
    if (!file) return
    try {
      const { dataUrl, mimeType } = await fileToFittingRoomDataUrl(file)
      await writeFittingRoomAsset({
        userId,
        kind: 'garment',
        dataUrl,
        mimeType,
        updatedAt: new Date().toISOString(),
        garmentCategory: category,
      })
      setGarmentUrl(dataUrl)
      setErrorMsg(null)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Could not save clothing image.')
    }
  }

  const clearPerson = async () => {
    await deleteFittingRoomAsset(userId, 'person')
    setPersonUrl(null)
  }

  const clearGarment = async () => {
    await deleteFittingRoomAsset(userId, 'garment')
    setGarmentUrl(null)
  }

  const runTryOn = async () => {
    if (!personUrl || !garmentUrl || !preflight?.enabled || !consent) return
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setPhase('running')
    setStatusMsg('Creating your Fitting Room preview…')
    setErrorMsg(null)
    if (resultBlobUrl) {
      URL.revokeObjectURL(resultBlobUrl)
      setResultBlobUrl(null)
    }
    setResultJobId(null)
    try {
      const idem = `fitting_room:${userId.slice(0, 8)}:${Date.now().toString(36)}`
      const job = await enqueueFittingRoomTryOn({
        personImageBase64: personUrl,
        garmentImageBase64: garmentUrl,
        idempotencyKey: idem,
        consentAcknowledged: true,
        consentVersion: preflight.consent_version,
        garmentCategory: category,
        signal: ac.signal,
      })
      const settled = await pollAiJobUntilSettled({ jobId: job.id, signal: ac.signal })
      if (settled.status !== 'completed') {
        setPhase('failed')
        setErrorMsg(
          settled.error_message?.trim() ||
            'Fitting Room could not finish this preview. No Stars were charged.',
        )
        setStatusMsg(null)
        return
      }
      const blob = await fetchJobImageBlob(settled.id, ac.signal)
      const url = URL.createObjectURL(blob)
      setResultJobId(settled.id)
      setResultBlobUrl(url)
      setPhase('done')
      setStatusMsg('Preview ready — concept only, not a fit guarantee.')
    } catch (err) {
      if (ac.signal.aborted) return
      setPhase('failed')
      setStatusMsg(null)
      if (err instanceof ApiError) {
        setErrorMsg(err.message || 'Fitting Room request failed. No Stars were charged.')
      } else {
        setErrorMsg(
          err instanceof Error
            ? err.message
            : 'Fitting Room request failed. No Stars were charged.',
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
      if (outcome === 'shared') {
        showNotice('Share sheet opened.', 'info')
      } else if (outcome === 'needs-fallback') {
        showNotice('Sharing is not available — use Download instead.', 'info')
      }
    } catch {
      showNotice('Share failed. Try download instead.', 'error')
    }
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

  const categories = preflight?.supported_categories?.length
    ? preflight.supported_categories
    : DEFAULT_CATEGORIES
  const serverOff = preflight != null && !preflight.enabled
  const canTry =
    Boolean(personUrl && garmentUrl && consent && preflight?.enabled && phase !== 'running')

  return (
    <section className={styles.screen} aria-labelledby="fitting-room-brand" data-testid="fitting-room-screen">
      <header className={styles.header}>
        <p className={styles.brand} id="fitting-room-brand">
          Fashion<span>Rise</span> Fitting Room
        </p>
        <p className={styles.lead}>
          Upload your photo and a clothing image for a private AI try-on preview.
        </p>
      </header>

      <p className={styles.disclaimer} role="note">
        {preflight?.preview_disclaimer ||
          'Concept preview only — not a fit guarantee. Results may differ from real garments.'}
      </p>

      {serverOff ? (
        <p className={`${styles.status} ${styles.statusError}`} role="status">
          Fitting Room is disabled on this server. Ask an operator to enable it for testing.
        </p>
      ) : null}

      <div className={styles.steps}>
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>1 · My Photo</h2>
          <p className={styles.panelHint}>
            Full-body photo works best. Saved privately on this device until you run try-on.
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
            accept="image/*"
            capture="environment"
            onChange={(e) => void onPickPerson(e.target.files?.[0] ?? null)}
          />
          <div className={styles.actions}>
            <button type="button" className={styles.btn} onClick={() => personRef.current?.click()}>
              {personUrl ? 'Replace photo' : 'Upload photo'}
            </button>
            {personUrl ? (
              <button type="button" className={styles.btnGhost} onClick={() => void clearPerson()}>
                Delete
              </button>
            ) : null}
          </div>
        </div>

        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>2 · Choose Clothing</h2>
          <p className={styles.panelHint}>
            Product shot or store screenshot. Category is a soft hint for the AI.
          </p>
          <div className={styles.preview}>
            {garmentUrl ? (
              <img className={styles.previewImg} src={garmentUrl} alt="Selected clothing" />
            ) : (
              <p className={styles.previewEmpty}>No clothing selected</p>
            )}
          </div>
          <div className={styles.categoryRow} role="group" aria-label="Garment category">
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                className={c === category ? `${styles.chip} ${styles.chipActive}` : styles.chip}
                aria-pressed={c === category}
                onClick={() => setCategory(c)}
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
            accept="image/*"
            onChange={(e) => void onPickGarment(e.target.files?.[0] ?? null)}
          />
          <div className={styles.actions}>
            <button type="button" className={styles.btn} onClick={() => garmentRef.current?.click()}>
              {garmentUrl ? 'Replace clothing' : 'Upload clothing'}
            </button>
            {garmentUrl ? (
              <button type="button" className={styles.btnGhost} onClick={() => void clearGarment()}>
                Remove
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
                'I understand this is a visual concept preview only — not an accurate size or fit guarantee.'}
            </label>
          </div>
          <div className={styles.tryRow}>
            <button
              type="button"
              className={styles.btnPrimary}
              disabled={!canTry}
              onClick={() => void runTryOn()}
              data-testid="fitting-room-try-on"
            >
              {phase === 'running' ? 'Working…' : phase === 'failed' ? 'Retry try-on' : 'Try on'}
            </button>
            <button type="button" className={styles.btnGhost} onClick={onBackToStudio}>
              Back to Studio
            </button>
          </div>
          {phase === 'running' ? (
            <p className={`${styles.status} ${styles.loadingPulse}`} role="status">
              {statusMsg}
            </p>
          ) : null}
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
    </section>
  )
}
