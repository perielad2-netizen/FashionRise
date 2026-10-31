/**
 * Create My Croquis Stage B wizard — consent-first, local preview, gated upload.
 *
 * UI gate `VITE_MY_CROQUIS_UI_ENABLED` must be ON for this to mount.
 * Upload/AI backend gates remain independent and default OFF.
 * Empty/draft notice text → fail closed (no affirmative consent recorded).
 * Stage B does not call providers; offline/tests use synthetic fixtures only.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '@/services/api/client'
import {
  acknowledgeStorageConsent,
  attestAdults,
  listPersonalCroquis,
  uploadPersonalCroquisPhoto,
  type PersonalCroquisRead,
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
  /** Pin exact accepted (croquisId, version) into Studio. */
  onPinAccepted: (croquisId: string, version: number) => void
  /** Offline Stage B: inject a deterministic accepted pin without upload/provider. */
  onUseOfflineFixture?: (croquisId: string, version: number) => void
}

type Step =
  | 'eligibility'
  | 'local'
  | 'storage'
  | 'upload'
  | 'library'
  | 'blocked'

export function CreateMyCroquisWizard({
  open,
  onClose,
  onPinAccepted,
  onUseOfflineFixture,
}: CreateMyCroquisWizardProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>('eligibility')
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [adultsChecked, setAdultsChecked] = useState(false)
  const [storageChecked, setStorageChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [library, setLibrary] = useState<PersonalCroquisRead[]>([])
  const [storageConsentId, setStorageConsentId] = useState<string | null>(null)

  const noticesOk = useMemo(() => croquisNoticesAuthorized(), [])
  const adultsNotice = useMemo(() => approvedCroquisNoticeText('adults'), [])
  const storageNotice = useMemo(() => approvedCroquisNoticeText('storage'), [])

  const reset = useCallback(() => {
    setStep(noticesOk ? 'eligibility' : 'blocked')
    setAdultsChecked(false)
    setStorageChecked(false)
    setBusy(false)
    setError(null)
    setStorageConsentId(null)
    setLocalFile(null)
    setLocalPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
  }, [noticesOk])

  useEffect(() => {
    if (open) reset()
  }, [open, reset])

  const handleClose = useCallback(() => {
    reset()
    onClose()
  }, [onClose, reset])

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
      const latest = created.latest_accepted
      if (latest?.version) {
        onPinAccepted(created.id, latest.version)
        handleClose()
        return
      }
      // Upload succeeded but no accepted generated version yet (Stage B: AI gate OFF).
      setError(
        'Photo stored privately. Generation is not enabled in this environment — your source is retained under Stage A rules.',
      )
      setStep('library')
      const rows = await listPersonalCroquis()
      setLibrary(rows)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }, [handleClose, localFile, onPinAccepted, storageConsentId])

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
            <p className={styles.hint}>
              Self-attestation is not independent age verification.
            </p>
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
              {localPreviewUrl ? (
                <button
                  type="button"
                  className={styles.secondary}
                  onClick={() => inputRef.current?.click()}
                >
                  Replace
                </button>
              ) : null}
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

        {step === 'library' ? (
          <div className={styles.body}>
            <p>Select an accepted croquis version to pin in Studio (exact id + version).</p>
            {library.length === 0 ? <p className={styles.hint}>No croquis yet.</p> : null}
            <ul className={styles.list}>
              {library.map((row) => {
                const ver = row.latest_accepted?.version
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
                      {row.display_name || 'Untitled'} · v{ver ?? '—'}
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
