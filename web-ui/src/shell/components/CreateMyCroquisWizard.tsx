/**
 * Create Model wizard — one agreement, then Upload & Generate.
 *
 * UI gate `VITE_MY_CROQUIS_UI_ENABLED` must be ON for this to mount.
 * Upload/AI backend gates remain independent and default OFF.
 *
 * Single short checkbox + expandable full terms for private upload / AI
 * processing. Distinct backend consent events (adults / storage / AI) are
 * still recorded with versioned notice hashes and source binding — bytes
 * are not uploaded before the agreement. Upload consent never authorizes
 * public publishing.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ApiError } from '@/services/api/client'
import {
  acceptPersonalCroquisVersion,
  acceptedVersionNumber,
  acknowledgeAiConsent,
  acknowledgeCreateModelUploadConsent,
  acknowledgeStorageConsent,
  attestAdults,
  fetchCroquisAssetBlob,
  generatePersonalCroquisVersion,
  getPersonalCroquisVersion,
  rejectPersonalCroquisVersion,
  uploadPersonalCroquisPhoto,
  type CroquisSex,
  type PersonalCroquisVersionRead,
} from '@/services/personalCroquisApi'
import {
  approvedCroquisNoticeText,
  croquisNoticeVersion,
  croquisNoticesAuthorized,
  sha256Hex,
} from '@/lib/personalCroquisNotices'
import {
  CREATE_MODEL_UPLOAD_CHECKBOX_LABEL,
  CREATE_MODEL_UPLOAD_FULL_TERMS_INTRO,
  CREATE_MODEL_UPLOAD_FULL_TERMS_POINTS,
  CREATE_MODEL_UPLOAD_NOTICE_VERSION,
  formatCreateModelUploadNoticeText,
} from '@/lib/createModelUploadConsent'
import { prepareCroquisUpload } from '@/lib/prepareCroquisUpload'
import { useAiStarsWallet } from '@/hooks/useAiStarsWallet'
import { LegalConsentField } from '@/components/LegalConsentField'
import fieldStyles from '@/components/LegalConsentField.module.css'
import { AiSpendConfirmDialog } from '@/shell/components/AiSpendConfirmDialog'
import { StarsShopModal } from '@/shell/components/StarsShopModal'
import styles from './CreateMyCroquisWizard.module.css'

/** Where Create Model was opened — same wizard/API; only post-accept differs. */
export type CreateModelEntryPoint = 'my-models' | 'studio'

export type CreateMyCroquisWizardProps = {
  open: boolean
  onClose: () => void
  onPinAccepted: (croquisId: string, version: number) => void
  onUseOfflineFixture?: (croquisId: string, version: number) => void
  /** Telemetry / regression: both entry points must share this component. */
  entryPoint?: CreateModelEntryPoint
}

type Step = 'compose' | 'generating' | 'preview' | 'reconciliation' | 'blocked'

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `croquis-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function CreateMyCroquisWizard({
  open,
  onClose,
  onPinAccepted,
  onUseOfflineFixture,
  entryPoint = 'my-models',
}: CreateMyCroquisWizardProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const noticesOk = useMemo(() => croquisNoticesAuthorized(), [])
  const adultsNotice = useMemo(() => approvedCroquisNoticeText('adults'), [])
  const storageNotice = useMemo(() => approvedCroquisNoticeText('storage'), [])
  const aiNotice = useMemo(() => approvedCroquisNoticeText('ai'), [])

  const [step, setStep] = useState<Step>(() => (noticesOk ? 'compose' : 'blocked'))
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [modelSex, setModelSex] = useState<CroquisSex | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aiConsentId, setAiConsentId] = useState<string | null>(null)
  const [croquisId, setCroquisId] = useState<string | null>(null)
  const [pendingVersion, setPendingVersion] = useState<PersonalCroquisVersionRead | null>(null)
  const pendingVersionRef = useRef<PersonalCroquisVersionRead | null>(null)
  const croquisIdRef = useRef<string | null>(null)
  const stepRef = useRef<Step>('compose')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)
  const [spendOpen, setSpendOpen] = useState(false)
  const [shopOpen, setShopOpen] = useState(false)
  const { balance, unlimited, costs } = useAiStarsWallet()
  const croquisCost = costs.croquis

  useEffect(() => {
    pendingVersionRef.current = pendingVersion
  }, [pendingVersion])
  useEffect(() => {
    croquisIdRef.current = croquisId
  }, [croquisId])
  useEffect(() => {
    stepRef.current = step
  }, [step])

  // Keep the dialog above Android/Samsung/Chrome bottom toolbars via visualViewport.
  // Mirror ConfirmDialog — required when portaled to document.body from My Models
  // (parent modelsRise transform otherwise traps position:fixed).
  useEffect(() => {
    if (!open) return
    const vv = window.visualViewport
    const sync = () => {
      const layoutH = window.innerHeight || 0
      const visibleH = vv?.height ?? layoutH
      const offsetTop = vv?.offsetTop ?? 0
      const chromeBottom = Math.max(0, Math.round(layoutH - visibleH - offsetTop))
      const target = document.querySelector(
        '[data-testid="create-model-wizard-backdrop"]',
      ) as HTMLElement | null
      target?.style.setProperty('--fr-browser-chrome-bottom', `${chromeBottom}px`)
      target?.style.setProperty('--fr-visible-height', `${Math.round(visibleH)}px`)
    }
    sync()
    // Re-sync after portal paint.
    const raf = window.requestAnimationFrame(sync)
    vv?.addEventListener('resize', sync)
    vv?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
    return () => {
      window.cancelAnimationFrame(raf)
      vv?.removeEventListener('resize', sync)
      vv?.removeEventListener('scroll', sync)
      window.removeEventListener('resize', sync)
    }
  }, [open])

  // Lock background scroll while the portaled sheet is open (both entry points).
  useEffect(() => {
    if (!open) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [open])

  const cancelInFlightGenerate = useCallback(() => {
    // Only abandon mid-generation. Preview close/accept must not re-reject.
    if (stepRef.current !== 'generating') return
    const id = croquisIdRef.current
    const ver = pendingVersionRef.current
    if (!id || !ver) return
    void rejectPersonalCroquisVersion(id, ver.version).catch(() => undefined)
  }, [])

  const handleClose = useCallback(() => {
    cancelInFlightGenerate()
    setLocalPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    onClose()
  }, [cancelInFlightGenerate, onClose])

  // Escape closes cleanly without leaving an invisible overlay.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy && !spendOpen) handleClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, spendOpen, handleClose])

  const onPickLocal = useCallback((file: File) => {
    setError(null)
    setLocalFile(file)
    setLocalPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
  }, [])

  const loadPreview = useCallback(async (assetId: string) => {
    const blob = await fetchCroquisAssetBlob(assetId)
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(blob)
    })
  }, [])

  const runUploadAndGenerate = useCallback(async () => {
    if (!localFile) {
      setError('Select a photo first.')
      return
    }
    if (modelSex !== 'male' && modelSex !== 'female') {
      setError('Select male or female for this model.')
      return
    }
    if (!agreed) {
      setError('Confirm the agreement before uploading.')
      return
    }
    if (!adultsNotice || !storageNotice || !aiNotice) {
      setError('Consent notices are not authorized yet.')
      return
    }
    setBusy(true)
    setBusyLabel('Preparing photo…')
    setError(null)
    try {
      // Phone JPEGs often exceed nginx 12m / backend 10 MB → silent 413 without this.
      const uploadFile = await prepareCroquisUpload(localFile)
      setBusyLabel('Uploading…')
      // Distinct auditable backend records from one UI agreement. Order matters:
      // adults → storage → create_model_upload (short+7-point) → upload bytes →
      // AI consent bound to croquis → generate.
      await attestAdults({
        adults_attested: true,
        notice_version: croquisNoticeVersion('adults'),
        notice_text_hash: await sha256Hex(adultsNotice),
      })
      const storageEvent = await acknowledgeStorageConsent({
        acknowledged: true,
        adults_attested: true,
        notice_version: croquisNoticeVersion('storage'),
        notice_text_hash: await sha256Hex(storageNotice),
      })
      await acknowledgeCreateModelUploadConsent({
        acknowledged: true,
        adults_attested: true,
        notice_version: CREATE_MODEL_UPLOAD_NOTICE_VERSION,
        notice_text_hash: await sha256Hex(formatCreateModelUploadNoticeText()),
      })
      const created = await uploadPersonalCroquisPhoto(uploadFile, storageEvent.id, {
        sex: modelSex,
      })
      setCroquisId(created.id)
      const ver = acceptedVersionNumber(created)
      if (ver) {
        onPinAccepted(created.id, ver)
        handleClose()
        return
      }
      setBusyLabel('Starting generate…')
      const aiEvent = await acknowledgeAiConsent({
        acknowledged: true,
        adults_attested: true,
        notice_version: croquisNoticeVersion('ai'),
        notice_text_hash: await sha256Hex(aiNotice),
        croquis_id: created.id,
      })
      setAiConsentId(aiEvent.id)
      setStep('generating')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload & Generate could not start.')
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }, [
    adultsNotice,
    agreed,
    aiNotice,
    handleClose,
    localFile,
    modelSex,
    onPinAccepted,
    storageNotice,
  ])

  // Poll generating → awaiting_review / failed / reconciliation
  useEffect(() => {
    if (step !== 'generating' || !croquisId || !aiConsentId) return
    let cancelled = false
    const ac = new AbortController()
    ;(async () => {
      setBusy(true)
      setError(null)
      try {
        const enqueued = await generatePersonalCroquisVersion(
          croquisId,
          { ai_consent_id: aiConsentId, idempotency_key: idempotencyKey },
          ac.signal,
        )
        if (cancelled) {
          void rejectPersonalCroquisVersion(croquisId, enqueued.version).catch(() => undefined)
          return
        }
        setPendingVersion(enqueued)
        // Image generation can take 1–3 minutes. Poll durable status for up to
        // ~4 minutes without launching a new provider request.
        const pollMs = import.meta.env.MODE === 'test' ? 20 : 2000
        const maxPolls = import.meta.env.MODE === 'test' ? 50 : 120
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, pollMs))
          if (cancelled) {
            void rejectPersonalCroquisVersion(croquisId, enqueued.version).catch(() => undefined)
            return
          }
          const ver = await getPersonalCroquisVersion(croquisId, enqueued.version, ac.signal)
          setPendingVersion(ver)
          if (ver.status === 'awaiting_review' && ver.generated_asset_id) {
            await loadPreview(ver.generated_asset_id)
            if (!cancelled) setStep('preview')
            return
          }
          if (ver.status === 'failed') {
            setError(
              ver.failure_message?.trim() ||
                'Generation failed (no model image was produced). You may try again with Upload & Generate.',
            )
            setIdempotencyKey(newIdempotencyKey())
            setStep('compose')
            return
          }
          if (ver.status === 'reconciliation_required') {
            setError(
              ver.failure_message?.trim() ||
                'This attempt needs a short review before it can finish. No automatic retry was started.',
            )
            setStep('reconciliation')
            return
          }
          if (ver.status === 'accepted' && ver.generated_asset_id) {
            onPinAccepted(croquisId, ver.version)
            handleClose()
            return
          }
          if (ver.status === 'generating' || ver.status === 'queued') {
            // Keep waiting — do not treat slow generation as failure.
            continue
          }
        }
        setError(
          'Still generating on the server. Keep this page open a bit longer, or check My Models later — no new paid attempt was started.',
        )
        setStep('compose')
      } catch (err) {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Generate could not start.')
        setStep('compose')
      } finally {
        if (!cancelled) setBusy(false)
      }
    })()
    return () => {
      cancelled = true
      ac.abort()
    }
  }, [step, croquisId, aiConsentId, idempotencyKey, handleClose, loadPreview, onPinAccepted])

  const runAccept = useCallback(async () => {
    if (!croquisId || !pendingVersion) return
    setBusy(true)
    setError(null)
    try {
      const accepted = await acceptPersonalCroquisVersion(croquisId, pendingVersion.version)
      onPinAccepted(croquisId, accepted.version)
      handleClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not accept model.')
    } finally {
      setBusy(false)
    }
  }, [croquisId, handleClose, onPinAccepted, pendingVersion])

  const runReject = useCallback(async () => {
    if (!croquisId || !pendingVersion) return
    setBusy(true)
    setError(null)
    try {
      await rejectPersonalCroquisVersion(croquisId, pendingVersion.version)
      setPendingVersion(null)
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
      setIdempotencyKey(newIdempotencyKey())
      setAiConsentId(null)
      setStep('compose')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reject model.')
    } finally {
      setBusy(false)
    }
  }, [croquisId, pendingVersion])

  if (!open) return null

  // Portal to document.body so position:fixed is not trapped by My Models
  // modelsRise transform (Android modal jump after picker / on X close).
  const overlay = (
    <>
    <div
      className={`fr-keyboard-overlay ${styles.backdrop}`}
      role="presentation"
      data-portal="document-body"
      data-testid="create-model-wizard-backdrop"
      data-entry-point={entryPoint}
      onClick={handleClose}
    >
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-my-croquis-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <div className={styles.titleBlock}>
            <p className={styles.eyebrow}>FashionRise</p>
            <h2 id="create-my-croquis-title">Create Model</h2>
          </div>
          <button type="button" className={styles.close} onClick={handleClose} aria-label="Close">
            ×
          </button>
        </header>

        {step === 'blocked' ? (
          <div className={styles.body}>
            <p>
              Create Model is not ready yet — consent notices must be configured before photo
              upload.
            </p>
            {onUseOfflineFixture ? (
              <button
                type="button"
                className={styles.secondary}
                onClick={() => {
                  onUseOfflineFixture('00000000-0000-4000-8000-0000000000b1', 1)
                  handleClose()
                }}
              >
                Use offline test fixture (dev/test only)
              </button>
            ) : null}
          </div>
        ) : null}

        {step === 'compose' ? (
          <>
            <div className={styles.body}>
              <p className={styles.lead}>
                Select a fully clothed fashion pose photo, agree once, then upload and generate your
                model.
              </p>
              <p className={styles.hint}>
                Use a camera photo of the person — not an app screenshot. Kidswear uses Studio
                templates — no child photos.
              </p>

              {/*
                Preview lives in a DIV frame (not a <button>). Android WebView often fails to
                clip overflow on buttons, so tall screenshots spilled over Change photo.
                Pattern: Mobbin-style portrait card + separate change action.
              */}
              <div className={styles.photoCard} data-testid="create-model-photo-card">
                <div
                  className={localPreviewUrl ? styles.photoFrame : styles.photoFrameEmpty}
                  data-testid="create-model-photo-frame"
                >
                  {localPreviewUrl ? (
                    <img
                      src={localPreviewUrl}
                      alt="Selected pose photo preview"
                      className={styles.preview}
                      draggable={false}
                    />
                  ) : (
                    <button
                      type="button"
                      className={styles.photoEmptyHit}
                      onClick={() => inputRef.current?.click()}
                      disabled={busy}
                      aria-label="Select photo"
                    >
                      <span className={styles.photoEmpty}>
                        Tap to select a fully clothed pose photo
                      </span>
                    </button>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.changePhoto}
                  onClick={() => inputRef.current?.click()}
                  disabled={busy}
                  data-testid="create-model-change-photo"
                >
                  {localFile ? 'Change photo' : 'Select photo'}
                </button>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className={styles.file}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) onPickLocal(file)
                  e.target.value = ''
                }}
              />

              <fieldset className={styles.sexFieldset} disabled={busy || !localFile}>
                <legend className={styles.sexLegend}>Model is</legend>
                <div className={styles.sexRow} role="radiogroup" aria-label="Model sex">
                  <button
                    type="button"
                    className={modelSex === 'male' ? styles.sexOptionActive : styles.sexOption}
                    aria-pressed={modelSex === 'male'}
                    data-testid="create-model-sex-male"
                    onClick={() => setModelSex('male')}
                  >
                    Male
                  </button>
                  <button
                    type="button"
                    className={modelSex === 'female' ? styles.sexOptionActive : styles.sexOption}
                    aria-pressed={modelSex === 'female'}
                    data-testid="create-model-sex-female"
                    onClick={() => setModelSex('female')}
                  >
                    Female
                  </button>
                </div>
                <p className={styles.hint}>
                  Saved for Try On Person so pants and skirts are not confused.
                </p>
              </fieldset>

              <LegalConsentField
                checked={agreed}
                onCheckedChange={setAgreed}
                disabled={busy || !localFile}
                shortLabel={CREATE_MODEL_UPLOAD_CHECKBOX_LABEL}
                intro={CREATE_MODEL_UPLOAD_FULL_TERMS_INTRO}
                points={CREATE_MODEL_UPLOAD_FULL_TERMS_POINTS}
                checkboxTestId="create-model-upload-consent"
                termsTestId="create-model-upload-terms"
                expandedExtra={
                  <>
                    <a
                      className={fieldStyles.privacyLink}
                      href="/privacy"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Privacy Policy
                    </a>
                    <div className={fieldStyles.approvedNotices}>
                      <h3>Approved notices on record</h3>
                      <p>
                        <strong>Adults:</strong> {adultsNotice}
                      </p>
                      <p>
                        <strong>Private storage:</strong> {storageNotice}
                      </p>
                      <p>
                        <strong>AI processing:</strong> {aiNotice}
                      </p>
                    </div>
                  </>
                }
              />

              {error ? (
                <p className={styles.errorInline} role="alert">
                  {error}
                </p>
              ) : null}
              {busy && busyLabel ? <p className={styles.busyHint}>{busyLabel}</p> : null}
            </div>

            <div className={styles.footer}>
              <button
                type="button"
                className={styles.primary}
                disabled={!localFile || !modelSex || !agreed || busy || !aiNotice}
                onClick={() => setSpendOpen(true)}
              >
                {busy ? (
                  busyLabel || 'Working…'
                ) : (
                  <>
                    Upload &amp; Generate
                    {!unlimited ? <span className={styles.costBadge}>−{croquisCost}</span> : null}
                  </>
                )}
              </button>
            </div>
          </>
        ) : null}

        {step === 'generating' ? (
          <div className={styles.body}>
            <p>Generating your model…</p>
            <p className={styles.hint}>
              Status: {pendingVersion?.status ?? 'queued'}. Fashion illustration can take up to a
              few minutes — please keep this window open.
            </p>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={handleClose}>
                Cancel
              </button>
            </div>
          </div>
        ) : null}

        {step === 'reconciliation' ? (
          <div className={styles.body}>
            <p role="alert">
              This attempt needs a short review before it can finish. FashionRise will not start
              another paid generate for this photo until that review completes.
            </p>
            <div className={styles.actions}>
              <button type="button" className={styles.primary} onClick={handleClose}>
                Close
              </button>
            </div>
          </div>
        ) : null}

        {step === 'preview' ? (
          <div className={styles.body}>
            <p>Preview your model. Accept pins it in Studio, or delete and try again.</p>
            {previewUrl ? (
              <img src={previewUrl} alt="Generated model preview" className={styles.preview} />
            ) : null}
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} disabled={busy} onClick={() => void runReject()}>
                Delete
              </button>
              <button type="button" className={styles.primary} disabled={busy} onClick={() => void runAccept()}>
                Accept &amp; use in Studio
              </button>
            </div>
          </div>
        ) : null}

        {error && step !== 'compose' ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>

    <AiSpendConfirmDialog
      open={spendOpen}
      feature="croquis"
      cost={croquisCost}
      balance={balance}
      unlimited={unlimited}
      busy={busy}
      description="Creates a private fashion model from your photo for Studio try-on and Magic."
      onCancel={() => setSpendOpen(false)}
      onApproved={() => {
        setSpendOpen(false)
        void runUploadAndGenerate()
      }}
      onOpenShop={() => setShopOpen(true)}
    />
    <StarsShopModal open={shopOpen} onClose={() => setShopOpen(false)} />
    </>
  )

  if (typeof document === 'undefined') return overlay
  return createPortal(overlay, document.body)
}
