import { useEffect, useId, useRef, useState } from 'react'
import {
  buildPendingStarsGrant,
  clearPendingStarsGrant,
  fetchAdminStarsGrantLimits,
  parsePositiveGrantAmount,
  pendingMatchesPayload,
  postAdminStarsGrant,
  readPendingStarsGrant,
  writePendingStarsGrant,
  type AdminCustomerDetail,
  type AdminStarsGrantReason,
  type AdminStarsGrantRecord,
} from '@/services/adminApi'
import styles from './GrantStarsModal.module.css'

const PRESETS = [10, 25, 50, 100, 150, 500] as const

const REASONS: Array<{ id: AdminStarsGrantReason; label: string }> = [
  { id: 'CUSTOMER_APPRECIATION', label: 'Customer appreciation' },
  { id: 'TECHNICAL_COMPENSATION', label: 'Technical compensation' },
  { id: 'PROMOTIONAL_GIFT', label: 'Promotional gift' },
  { id: 'WELCOME_BONUS', label: 'Welcome bonus' },
  { id: 'COMPETITION_REWARD', label: 'Competition reward (manual)' },
  { id: 'INTERNAL_TESTING', label: 'Internal testing' },
  { id: 'OTHER', label: 'Other' },
]

type Step = 'form' | 'confirm' | 'success'

type Props = {
  customer: Pick<
    AdminCustomerDetail,
    'id' | 'username' | 'email' | 'classification' | 'wallet'
  >
  adminId: string
  onClose: () => void
  onGranted: (grant: AdminStarsGrantRecord) => void
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `grant-${crypto.randomUUID()}`
  }
  return `grant-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function GrantStarsModal({ customer, adminId, onClose, onGranted }: Props) {
  const titleId = useId()
  const unlimited = Boolean(customer.wallet.ai_stars_unlimited)
  const debt = Number(customer.wallet.ai_stars_iap_debt || 0)
  const blocked = unlimited || debt > 0
  const current = Number(customer.wallet.ai_stars || 0)

  const [maxPerTxn, setMaxPerTxn] = useState(10_000)
  const [largeThreshold, setLargeThreshold] = useState(500)
  const [step, setStep] = useState<Step>('form')
  const [amountRaw, setAmountRaw] = useState('')
  const [reason, setReason] = useState<AdminStarsGrantReason>('CUSTOMER_APPRECIATION')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)
  const [result, setResult] = useState<AdminStarsGrantRecord | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const submitLock = useRef(false)

  useEffect(() => {
    void fetchAdminStarsGrantLimits()
      .then((lim) => {
        setMaxPerTxn(lim.max_per_transaction)
        setLargeThreshold(lim.large_confirm_threshold)
      })
      .catch(() => {
        /* keep defaults */
      })
  }, [])

  // Restore pending grant for this admin + recipient after refresh / reopen.
  useEffect(() => {
    const pending = readPendingStarsGrant()
    if (!pending) return
    if (pending.adminId !== adminId || pending.recipientId !== customer.id) return
    setIdempotencyKey(pending.idempotencyKey)
    setAmountRaw(String(pending.amount))
    setReason(pending.reason as AdminStarsGrantReason)
    setUncertain(true)
    setError(
      'A previous grant attempt for this customer may still be unresolved. ' +
        'Confirm to reconcile with the same idempotency key — do not change the amount.',
    )
    setStep('confirm')
  }, [adminId, customer.id])

  const amount = parsePositiveGrantAmount(amountRaw)
  const previewAfter = amount != null ? current + amount : null
  const reasonLabel = REASONS.find((r) => r.id === reason)?.label ?? reason

  function setPreset(n: number) {
    if (uncertain) return
    setAmountRaw(String(n))
    setError(null)
  }

  function validateForm(): string | null {
    if (blocked) {
      if (unlimited) return 'Manual grants are disabled for unlimited-wallet accounts.'
      return 'Cannot grant while outstanding IAP Stars debt exists.'
    }
    if (amount == null) return 'Enter a positive whole number of Stars.'
    if (amount > maxPerTxn) {
      return `Maximum ${maxPerTxn.toLocaleString()} Stars per grant.`
    }
    if (reason === 'OTHER' && !note.trim()) return 'An explanatory note is required for Other.'
    if (note.trim().length > 2000) return 'Note must be at most 2000 characters.'
    return null
  }

  function goConfirm() {
    const err = validateForm()
    if (err) {
      setError(err)
      return
    }
    setError(null)
    setStep('confirm')
  }

  function attemptClose() {
    if (submitting || submitLock.current) {
      setError('Grant is in progress — wait for confirmation before closing.')
      return
    }
    onClose()
  }

  async function confirmGrant() {
    if (submitLock.current || submitting) return
    const err = validateForm()
    if (err || amount == null) {
      setError(err ?? 'Invalid amount')
      setStep('form')
      return
    }

    const pendingExisting = readPendingStarsGrant()
    let key = idempotencyKey
    if (pendingExisting) {
      const matches = pendingMatchesPayload(pendingExisting, {
        adminId,
        recipientId: customer.id,
        amount,
        reason,
        note: note.trim(),
      })
      if (matches) {
        key = pendingExisting.idempotencyKey
        setIdempotencyKey(key)
      } else if (pendingExisting.recipientId === customer.id && pendingExisting.adminId === adminId) {
        // Same recipient, different payload while unresolved — refuse new key.
        setError(
          'A pending grant with different details exists for this customer. ' +
            'Reconcile or clear the session pending grant before submitting a new amount.',
        )
        return
      }
    }

    const pending = buildPendingStarsGrant({
      adminId,
      recipientId: customer.id,
      amount,
      reason,
      note: note.trim(),
      idempotencyKey: key,
    })
    writePendingStarsGrant(pending)

    submitLock.current = true
    setSubmitting(true)
    setError(null)
    setUncertain(false)
    try {
      const grant = await postAdminStarsGrant(customer.id, {
        amount,
        reason,
        note: note.trim() || null,
        idempotency_key: key,
        confirm_large: amount >= largeThreshold,
      })
      clearPendingStarsGrant(key)
      setResult(grant)
      setStep('success')
      onGranted(grant)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Grant failed'
      // Keep pending key for retry / refresh recovery on uncertain network outcomes.
      setUncertain(true)
      setError(
        `${msg}. If the network dropped after submit, reopen this grant and confirm again — ` +
          'the same idempotency key will be reused.',
      )
      setStep('confirm')
    } finally {
      submitLock.current = false
      setSubmitting(false)
    }
  }

  return (
    <div
      className={styles.scrim}
      role="presentation"
      onClick={() => {
        if (!submitting) attemptClose()
      }}
    >
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.head}>
          <div>
            <p className={styles.eyebrow}>Grant Stars · ADD ONLY</p>
            <h2 id={titleId}>+ Grant Stars</h2>
          </div>
          <button
            type="button"
            className={styles.close}
            onClick={attemptClose}
            disabled={submitting}
          >
            Close
          </button>
        </header>

        <div className={styles.recipient} aria-label="Grant recipient">
          <div className={styles.recipientMark}>Recipient</div>
          <strong>@{customer.username}</strong>
          <span className={styles.meta}>{customer.email}</span>
          <span className={styles.meta}>
            {customer.classification} ·{' '}
            {unlimited ? 'Unlimited Stars' : `${current.toLocaleString()} Stars`}
            {debt > 0 ? ` · Debt ${debt}` : ''}
          </span>
        </div>

        {blocked ? (
          <div className={styles.banner} role="status">
            {unlimited
              ? 'This account has unlimited Stars. Manual grants are disabled.'
              : `This account has ${debt} Stars of outstanding IAP debt. Grants are blocked until debt is resolved through the refund accounting path.`}
          </div>
        ) : null}

        {uncertain ? (
          <div className={styles.banner} role="status">
            Pending grant recovery active — idempotency key reused for this administrator +
            recipient + payload.
          </div>
        ) : null}

        {error ? <div className={styles.error}>{error}</div> : null}

        {step === 'form' && !blocked ? (
          <div className={styles.body}>
            <div>
              <div className={styles.label}>Quick amounts</div>
              <div className={styles.presets}>
                {PRESETS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={`${styles.preset} ${amount === n ? styles.presetActive : ''}`}
                    onClick={() => setPreset(n)}
                    disabled={uncertain}
                  >
                    +{n}
                  </button>
                ))}
              </div>
            </div>

            <label className={styles.field}>
              Custom amount (positive integer, max {maxPerTxn.toLocaleString()})
              <input
                inputMode="numeric"
                pattern="[1-9][0-9]*"
                value={amountRaw}
                onChange={(e) => {
                  if (uncertain) return
                  setAmountRaw(e.target.value)
                  setError(null)
                }}
                placeholder="e.g. 75"
                autoComplete="off"
                readOnly={uncertain}
              />
            </label>

            <div className={styles.preview}>
              <div>
                <span>Current</span>
                <strong>{current.toLocaleString()}</strong>
              </div>
              <div>
                <span>To add</span>
                <strong className={styles.positive}>
                  {amount != null ? `+${amount.toLocaleString()}` : '—'}
                </strong>
              </div>
              <div>
                <span>After grant</span>
                <strong>
                  {previewAfter != null ? previewAfter.toLocaleString() : '—'}
                </strong>
              </div>
            </div>

            <label className={styles.field}>
              Reason
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value as AdminStarsGrantReason)}
                disabled={uncertain}
              >
                {REASONS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.field}>
              Internal note{reason === 'OTHER' ? ' (required)' : ' (optional)'}
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={2000}
                rows={3}
                placeholder="Visible only to administrators"
                readOnly={uncertain}
              />
            </label>

            <p className={styles.hint}>
              This credits Stars only. It never deducts, resets, or sets a target balance. Notes are
              not shown to the customer. No email or push is sent. Grants of{' '}
              {largeThreshold.toLocaleString()}+ Stars require an extra confirmation.
            </p>

            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={attemptClose}>
                Cancel
              </button>
              <button type="button" className={styles.primary} onClick={goConfirm}>
                Review grant
              </button>
            </div>
          </div>
        ) : null}

        {step === 'confirm' && amount != null ? (
          <div className={styles.body}>
            <p className={styles.confirmLead}>
              You are about to grant <strong>{amount.toLocaleString()} Stars</strong> to{' '}
              <strong>@{customer.username}</strong>.
            </p>
            <ul className={styles.confirmList}>
              <li>
                Current balance: <strong>{current.toLocaleString()} Stars</strong>
              </li>
              <li>
                Stars to add:{' '}
                <strong className={styles.positive}>+{amount.toLocaleString()} Stars</strong>
              </li>
              <li>
                Expected new balance:{' '}
                <strong>{(previewAfter ?? 0).toLocaleString()} Stars</strong>
              </li>
              <li>
                Reason: <strong>{reasonLabel}</strong>
              </li>
            </ul>
            <p className={styles.warn}>
              This operation cannot be undone from the administration panel. The backend calculates
              the authoritative balance atomically. Rapid double-clicks are ignored.
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.secondary}
                onClick={() => {
                  if (!submitting) setStep('form')
                }}
                disabled={submitting}
              >
                Back
              </button>
              <button
                type="button"
                className={styles.primary}
                onClick={() => void confirmGrant()}
                disabled={submitting}
              >
                {submitting
                  ? 'Granting…'
                  : `Confirm & Grant ${amount.toLocaleString()} Stars`}
              </button>
            </div>
          </div>
        ) : null}

        {step === 'success' && result ? (
          <div className={styles.body}>
            <div className={styles.success} role="status">
              Stars granted successfully
              {result.idempotent_replay ? ' (idempotent replay)' : ''}
            </div>
            <ul className={styles.confirmList}>
              <li>
                Amount added:{' '}
                <strong className={styles.positive}>+{result.amount.toLocaleString()}</strong>
              </li>
              <li>
                New balance: <strong>{result.balance_after.toLocaleString()} Stars</strong>
              </li>
              <li>
                Grant reference: <code>{result.grant_id}</code>
              </li>
            </ul>
            <div className={styles.actions}>
              <button type="button" className={styles.primary} onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
