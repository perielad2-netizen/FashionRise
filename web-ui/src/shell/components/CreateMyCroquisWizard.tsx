/**
 * Create My Croquis wizard — Stage B consent/upload + Stage C AI generate/review.
 *
 * UI gate `VITE_MY_CROQUIS_UI_ENABLED` must be ON for this to mount.
 * Upload/AI backend gates remain independent and default OFF.
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
import styles from './CreateMyCroquisWizard.module.css'

export type CreateMyCroquisWizardProps = {
  open: boolean
  onClose: () => void
  onPinAccepted: (croquisId: string, version: number) => void
  onUseOfflineFixture?: (croquisId: string, version: number) => void
}

type Step =
  | 'eligibility'
  | 'local'
  | 'storage'
  | 'upload'
  | 'ai'
  | 'generating'
  | 'preview'
  | 'library'
  | 'reconciliation'
  | 'blocked'

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

  const [step, setStep] = useState<Step>(() => (noticesOk ? 'eligibility' : 'blocked'))
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [adultsChecked, setAdultsChecked] = useState(false)
  const [storageChecked, setStorageChecked] = useState(false)
  const [aiChecked, setAiChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [library, setLibrary] = useState<PersonalCroquisRead[]>([])
  const [storageConsentId, setStorageConsentId] = useState<string | null>(null)
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
    setStep('local')
  }, [])

  const runAdultsThenLocal = useCallback(async () => {
    if (!adultsChecked || !adultsNotice) {
      setError('Explicit adults-only acknowledgment is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await attestAdults({
        adults_attested: true,
        notice_version: croquisNoticeVersion('adults'),
        notice_text_hash: await sha256Hex(adultsNotice),
      })
      setStep('local')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record attestation.')
    } finally {
      setBusy(false)
    }
  }, [adultsChecked, adultsNotice])

  const runStorageConsent = useCallback(async () => {
    if (!storageChecked || !storageNotice) {
      setError('Explicit storage consent acknowledgment is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const event = await acknowledgeStorageConsent({
        acknowledged: true,
        adults_attested: true,
        notice_version: croquisNoticeVersion('storage'),
        notice_text_hash: await sha256Hex(storageNotice),
      })
      setStorageConsentId(event.id)
      setStep('upload')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record storage consent.')
    } finally {
      setBusy(false)
    }
  }, [storageChecked, storageNotice])

  const runUpload = useCallback(async () => {
    if (!localFile || !storageConsentId) {
      setError('Choose a photo and complete storage consent first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const created = await uploadPersonalCroquisPhoto(localFile, storageConsentId)
      setCroquisId(created.id)
      const ver = acceptedVersionNumber(created)
      if (ver) {
        onPinAccepted(created.id, ver)
        handleClose()
        return
      }
      // Proceed to separate AI-provider consent (Stage C). Generation stays gated OFF by default.
      setStep('ai')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }, [handleClose, localFile, onPinAccepted, storageConsentId])

  const runAiConsent = useCallback(async () => {
    if (!aiChecked || !aiNotice || !croquisId) {
      setError('Explicit AI-provider consent acknowledgment is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const event = await acknowledgeAiConsent({
        acknowledged: true,
        adults_attested: true,
        notice_version: croquisNoticeVersion('ai'),
        notice_text_hash: await sha256Hex(aiNotice),
        croquis_id: croquisId,
      })
      setAiConsentId(event.id)
      setStep('generating')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record AI consent.')
    } finally {
      setBusy(false)
    }
  }, [aiChecked, aiNotice, croquisId])

  const loadPreview = useCallback(async (assetId: string) => {
    const blob = await fetchCroquisAssetBlob(assetId)
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(blob)
    })
  }, [])

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
        // Poll durable status
        for (let i = 0; i < 40; i++) {
          await new Promise((r) => setTimeout(r, 400))
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
              'Generation failed (no croquis image was produced). You may retry with a new attempt.',
            )
            setIdempotencyKey(newIdempotencyKey())
            setStep('ai')
            return
          }
          if (ver.status === 'reconciliation_required') {
            // Do not mint a new idempotency key or return to a spend-capable AI step.
            setError(
              'Provider outcome unknown — this attempt is held for operator reconciliation. No automatic paid retry is available.',
            )
            setStep('reconciliation')
            return
          }
          if (ver.status === 'accepted' && ver.generated_asset_id) {
            onPinAccepted(croquisId, ver.version)
            handleClose()
            return
          }
        }
        setError('Still generating — open My Croquis library later, or wait and retry status.')
        setStep('library')
      } catch (err) {
        if (cancelled) return
        const msg = err instanceof ApiError ? err.message : 'Generate could not start.'
        setError(msg)
        // Gate OFF / ceiling 0 → honest disabled state, stay on AI step
        setStep('ai')
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
      setStep('ai')
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
              Create My Croquis consent collection is not authorized yet. Owner/legal-approved
              notice text must be configured before any attestation or photo upload.
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

        {step === 'eligibility' ? (
          <div className={styles.body}>
            <p className={styles.notice}>{adultsNotice}</p>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={adultsChecked}
                onChange={(e) => setAdultsChecked(e.target.checked)}
              />
              <span>I am 18 or older and acknowledge this adults-only beta notice.</span>
            </label>
            <p className={styles.hint}>Self-attestation is not independent age verification.</p>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={loadLibrary} disabled={busy}>
                My Croquis library
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!adultsChecked || busy}
                onClick={() => void runAdultsThenLocal()}
              >
                Continue
              </button>
            </div>
          </div>
        ) : null}

        {step === 'local' ? (
          <div className={styles.body}>
            <p>Choose a fully clothed photo. Preview stays on this device until you consent to upload.</p>
            {localPreviewUrl ? (
              <img src={localPreviewUrl} alt="Local photo preview" className={styles.preview} />
            ) : (
              <button type="button" className={styles.secondary} onClick={() => inputRef.current?.click()}>
                Select photo
              </button>
            )}
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
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={() => setStep('eligibility')}>
                Back
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!localFile || busy}
                onClick={() => setStep('storage')}
              >
                Continue to storage consent
              </button>
            </div>
          </div>
        ) : null}

        {step === 'storage' ? (
          <div className={styles.body}>
            <p className={styles.notice}>{storageNotice}</p>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={storageChecked}
                onChange={(e) => setStorageChecked(e.target.checked)}
              />
              <span>I explicitly consent to private storage of my photo for Create My Croquis.</span>
            </label>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={() => setStep('local')}>
                Back
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!storageChecked || busy}
                onClick={() => void runStorageConsent()}
              >
                Continue
              </button>
            </div>
          </div>
        ) : null}

        {step === 'upload' ? (
          <div className={styles.body}>
            <p>Upload stores your photo in private croquis storage (not /static/uploads).</p>
            {localPreviewUrl ? (
              <img src={localPreviewUrl} alt="Local photo preview" className={styles.preview} />
            ) : null}
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={() => setStep('storage')}>
                Back
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!localFile || !storageConsentId || busy}
                onClick={() => void runUpload()}
              >
                Upload privately
              </button>
            </div>
          </div>
        ) : null}

        {step === 'ai' ? (
          <div className={styles.body}>
            <p className={styles.notice}>
              {aiNotice ||
                'AI-provider notice text is not authorized yet. Generation stays unavailable.'}
            </p>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={aiChecked}
                onChange={(e) => setAiChecked(e.target.checked)}
                disabled={!aiNotice}
              />
              <span>
                I explicitly consent to AI-provider processing of my private photo to generate a
                fashion croquis (separate from storage consent).
              </span>
            </label>
            <p className={styles.hint}>
              Generation requires the AI gate and spend ceiling to be enabled by an operator. When
              disabled, FashionRise will not call a provider or charge spend.
            </p>
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={loadLibrary} disabled={busy}>
                My Croquis library
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={!aiChecked || !aiNotice || !croquisId || busy}
                onClick={() => void runAiConsent()}
              >
                Generate My Croquis
              </button>
            </div>
          </div>
        ) : null}

        {step === 'generating' ? (
          <div className={styles.body}>
            <p>Generating your croquis privately…</p>
            <p className={styles.hint}>
              Status: {pendingVersion?.status ?? 'queued'}. This can take a moment. Do not close
              until preview is ready.
            </p>
          </div>
        ) : null}

        {step === 'reconciliation' ? (
          <div className={styles.body}>
            <p role="alert">
              Provider outcome is unknown. This attempt is held for operator reconciliation.
              FashionRise will not start another paid generate for this photo until that review
              completes.
            </p>
            <p className={styles.hint}>
              Do not retry from this wizard. Open My Croquis library later, or contact an
              operator if this persists.
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
            <p>Preview the generated croquis. Accept pins this exact version in Studio.</p>
            {previewUrl ? (
              <img src={previewUrl} alt="Generated croquis preview" className={styles.preview} />
            ) : null}
            <div className={styles.actions}>
              <button type="button" className={styles.secondary} disabled={busy} onClick={() => void runReject()}>
                Reject
              </button>
              <button type="button" className={styles.primary} disabled={busy} onClick={() => void runAccept()}>
                Accept &amp; use in Studio
              </button>
            </div>
          </div>
        ) : null}

        {step === 'library' ? (
          <div className={styles.body}>
            <p>Select an accepted croquis version to pin in Studio (exact id + version).</p>
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
              <button type="button" className={styles.secondary} onClick={() => setStep('eligibility')}>
                Back
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  )
}
