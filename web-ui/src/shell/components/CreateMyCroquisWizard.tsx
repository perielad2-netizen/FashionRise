/**
 * Create My Croquis wizard — one agreement, then Upload & Generate.
 *
 * UI gate `VITE_MY_CROQUIS_UI_ENABLED` must be ON for this to mount.
 * Upload/AI backend gates remain independent and default OFF.
 *
 * Single visible checkbox covers photo rights, private storage, and AI
 * processing. Distinct backend consent events (adults / storage / AI) are
 * still recorded with versioned notice hashes and source binding — bytes
 * are not uploaded before the agreement.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '@/services/api/client'
import {
  acceptPersonalCroquisVersion,
  acceptedVersionNumber,
  acknowledgeAiConsent,
  acknowledgeStorageConsent,
  attestAdults,
  fetchCroquisAssetBlob,
  generatePersonalCroquisVersion,
  getPersonalCroquisVersion,
  listPersonalCroquis,
  rejectPersonalCroquisVersion,
  uploadPersonalCroquisPhoto,
  type PersonalCroquisRead,
  type PersonalCroquisVersionRead,
} from '@/services/personalCroquisApi'
import {
  approvedCroquisNoticeText,
  croquisNoticeVersion,
  croquisNoticesAuthorized,
  sha256Hex,
} from '@/lib/personalCroquisNotices'
import { prepareCroquisUpload } from '@/lib/prepareCroquisUpload'
import styles from './CreateMyCroquisWizard.module.css'

export type CreateMyCroquisWizardProps = {
  open: boolean
  onClose: () => void
  onPinAccepted: (croquisId: string, version: number) => void
  onUseOfflineFixture?: (croquisId: string, version: number) => void
}

type Step = 'compose' | 'generating' | 'preview' | 'library' | 'reconciliation' | 'blocked'

const COMBINED_AGREEMENT_LABEL =
  'I have permission to use this photo and agree to private storage and AI processing to create my croquis.'

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `croquis-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function CreateMyCroquisWizard({
  open,
  onClose,
  onPinAccepted,
  onUseOfflineFixture,
}: CreateMyCroquisWizardProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const noticesOk = useMemo(() => croquisNoticesAuthorized(), [])
  const adultsNotice = useMemo(() => approvedCroquisNoticeText('adults'), [])
  const storageNotice = useMemo(() => approvedCroquisNoticeText('storage'), [])
  const aiNotice = useMemo(() => approvedCroquisNoticeText('ai'), [])

  const [step, setStep] = useState<Step>(() => (noticesOk ? 'compose' : 'blocked'))
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [library, setLibrary] = useState<PersonalCroquisRead[]>([])
  const [aiConsentId, setAiConsentId] = useState<string | null>(null)
  const [croquisId, setCroquisId] = useState<string | null>(null)
  const [pendingVersion, setPendingVersion] = useState<PersonalCroquisVersionRead | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)

  const handleClose = useCallback(() => {
    setLocalPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    onClose()
  }, [onClose])

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
      // adults → storage → upload (bytes) → AI consent bound to croquis → generate.
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
      const created = await uploadPersonalCroquisPhoto(uploadFile, storageEvent.id)
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
  }, [adultsNotice, agreed, aiNotice, handleClose, localFile, onPinAccepted, storageNotice])

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
        if (cancelled) return
        setPendingVersion(enqueued)
        // Image generation can take 1–3 minutes. Poll durable status for up to
        // ~4 minutes without launching a new provider request.
        const pollMs = import.meta.env.MODE === 'test' ? 20 : 2000
        const maxPolls = import.meta.env.MODE === 'test' ? 50 : 120
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, pollMs))
          if (cancelled) return
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
                'Generation failed (no croquis image was produced). You may try again with Upload & Generate.',
            )
            setIdempotencyKey(newIdempotencyKey())
            setStep('compose')
            return
          }
          if (ver.status === 'reconciliation_required') {
            setError(
              ver.failure_message?.trim() ||
                'Provider outcome unknown — this attempt is held for review. No automatic paid retry is available.',
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
          'Still generating on the server. Keep this page open a bit longer, or reopen Create My Croquis / library later — no new paid attempt was started.',
        )
        setStep('library')
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
      setError(err instanceof ApiError ? err.message : 'Could not accept croquis.')
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
      setError(err instanceof ApiError ? err.message : 'Could not reject croquis.')
    } finally {
      setBusy(false)
    }
  }, [croquisId, pendingVersion])

  const loadLibrary = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const rows = await listPersonalCroquis()
      setLibrary(rows)
      setStep('library')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load My Croquis.')
    } finally {
      setBusy(false)
    }
  }, [])

  if (!open) return null

  return (
    <div className={styles.backdrop} role="presentation" onClick={handleClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-my-croquis-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 id="create-my-croquis-title">Create My Croquis</h2>
          <button type="button" className={styles.close} onClick={handleClose} aria-label="Close">
            ×
          </button>
        </header>

        {step === 'blocked' ? (
          <div className={styles.body}>
            <p>
              Create My Croquis is not ready yet — consent notices must be configured before photo
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
          <div className={styles.body}>
            <p>
              Select a fully clothed fashion pose photo, agree once, then upload and generate your
              croquis.
            </p>
            <p className={styles.hint}>
              Designing children&apos;s clothing uses Studio templates and mannequins — you do not
              need to upload a child&apos;s photograph.
            </p>

            {localPreviewUrl ? (
              <img src={localPreviewUrl} alt="Local photo preview" className={styles.preview} />
            ) : null}
            <button
              type="button"
              className={styles.secondary}
              onClick={() => inputRef.current?.click()}
              disabled={busy}
            >
              {localFile ? 'Change photo' : 'Select photo'}
            </button>
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

            <label className={styles.check}>
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                disabled={busy || !localFile}
              />
              <span>{COMBINED_AGREEMENT_LABEL}</span>
            </label>

            <button
              type="button"
              className={styles.detailsToggle}
              onClick={() => setShowDetails((v) => !v)}
            >
              {showDetails ? 'Hide details' : 'Show details'}
            </button>
            {showDetails ? (
              <div className={styles.notice}>
                <p>{adultsNotice}</p>
                <p>{storageNotice}</p>
                <p>{aiNotice}</p>
              </div>
            ) : null}

            <p className={styles.hint}>
              Upload &amp; Generate sends your photo to the AI provider and may incur usage cost
              under your account limits. Preview stays on this device until you agree. Large phone
              photos are compressed on this device before upload.
            </p>

            {error ? (
              <p className={styles.errorInline} role="alert">
                {error}
              </p>
            ) : null}
            {busy && busyLabel ? <p className={styles.busyHint}>{busyLabel}</p> : null}

            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={loadLibrary} disabled={busy}>
                My Croquis library
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!localFile || !agreed || busy || !aiNotice}
                onClick={() => void runUploadAndGenerate()}
              >
                {busy ? busyLabel || 'Working…' : 'Upload & Generate'}
              </button>
            </div>
          </div>
        ) : null}

        {step === 'generating' ? (
          <div className={styles.body}>
            <p>Generating your croquis…</p>
            <p className={styles.hint}>
              Status: {pendingVersion?.status ?? 'queued'}. Fashion illustration can take up to a
              few minutes — please keep this window open.
            </p>
          </div>
        ) : null}

        {step === 'reconciliation' ? (
          <div className={styles.body}>
            <p role="alert">
              Provider outcome is unknown. This attempt is held for review. FashionRise will not
              start another paid generate for this photo until that review completes.
            </p>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={loadLibrary} disabled={busy}>
                My Croquis library
              </button>
              <button type="button" className={styles.primary} onClick={handleClose}>
                Close
              </button>
            </div>
          </div>
        ) : null}

        {step === 'preview' ? (
          <div className={styles.body}>
            <p>Preview your croquis. Accept pins it in Studio, or delete and try again.</p>
            {previewUrl ? (
              <img src={previewUrl} alt="Generated croquis preview" className={styles.preview} />
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

        {step === 'library' ? (
          <div className={styles.body}>
            <p>Select an accepted croquis to use in Studio.</p>
            {library.length === 0 ? <p className={styles.hint}>No croquis yet.</p> : null}
            <ul className={styles.list}>
              {library.map((row) => {
                const ver = acceptedVersionNumber(row)
                const label = row.display_name || 'Untitled'
                const statusBits = [
                  ver ? `v${ver}` : 'no accepted version',
                  row.archived ? 'archived' : null,
                  row.erased ? 'erased' : null,
                ]
                  .filter(Boolean)
                  .join(' · ')
                return (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={styles.secondary}
                      disabled={!ver}
                      onClick={() => {
                        if (!ver) return
                        onPinAccepted(row.id, ver)
                        handleClose()
                      }}
                    >
                      {label} · {statusBits}
                    </button>
                  </li>
                )
              })}
            </ul>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={() => setStep('compose')}>
                Back
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
  )
}
