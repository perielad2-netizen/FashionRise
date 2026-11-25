import { useId, useState } from 'react'
import {
  parsePositiveGrantAmount,
  postAdminStarsGrant,
  type AdminCustomerDetail,
  type AdminStarsGrantReason,
  type AdminStarsGrantRecord,
} from '@/services/adminApi'
import styles from './GrantStarsModal.module.css'

const PRESETS = [10, 25, 50, 100, 150, 500] as const
const MAX_CLIENT = 10_000
const LARGE_THRESHOLD = 500

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
  onClose: () => void
  onGranted: (grant: AdminStarsGrantRecord) => void
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `grant-${crypto.randomUUID()}`
  }
  return `grant-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function GrantStarsModal({ customer, onClose, onGranted }: Props) {
  const titleId = useId()
  const unlimited = Boolean(customer.wallet.ai_stars_unlimited)
  const debt = Number(customer.wallet.ai_stars_iap_debt || 0)
  const blocked = unlimited || debt > 0
  const current = Number(customer.wallet.ai_stars || 0)

  const [step, setStep] = useState<Step>('form')
  const [amountRaw, setAmountRaw] = useState('')
  const [reason, setReason] = useState<AdminStarsGrantReason>('CUSTOMER_APPRECIATION')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [idempotencyKey] = useState(newIdempotencyKey)
  const [result, setResult] = useState<AdminStarsGrantRecord | null>(null)

  const amount = parsePositiveGrantAmount(amountRaw)
  const previewAfter = amount != null ? current + amount : null
  const reasonLabel = REASONS.find((r) => r.id === reason)?.label ?? reason

  function setPreset(n: number) {
    setAmountRaw(String(n))
    setError(null)
  }

  function validateForm(): string | null {
    if (blocked) {
      if (unlimited) return 'Manual grants are disabled for unlimited-wallet accounts.'
      return 'Cannot grant while outstanding IAP Stars debt exists.'
    }
    if (amount == null) return 'Enter a positive whole number of Stars.'
    if (amount > MAX_CLIENT) return `Maximum ${MAX_CLIENT.toLocaleString()} Stars per grant.`
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

  async function confirmGrant() {
    if (submitting) return
    const err = validateForm()
    if (err || amount == null) {
      setError(err ?? 'Invalid amount')
      setStep('form')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const grant = await postAdminStarsGrant(customer.id, {
        amount,
        reason,
        note: note.trim() || null,
        idempotency_key: idempotencyKey,
        confirm_large: amount >= LARGE_THRESHOLD,
      })
      setResult(grant)
      setStep('success')
      onGranted(grant)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Grant failed')
      setStep('form')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.scrim} role="presentation" onClick={onClose}>
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
          <button type="button" className={styles.close} onClick={onClose} disabled={submitting}>
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
                  >
                    +{n}
                  </button>
                ))}
              </div>
            </div>

            <label className={styles.field}>
              Custom amount (positive integer)
              <input
                inputMode="numeric"
                pattern="[1-9][0-9]*"
                value={amountRaw}
                onChange={(e) => {
                  setAmountRaw(e.target.value)
                  setError(null)
                }}
                placeholder="e.g. 75"
                autoComplete="off"
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
              />
            </label>

            <p className={styles.hint}>
              This credits Stars only. It never deducts, resets, or sets a target balance. Notes are
              not shown to the customer. No email or push is sent.
            </p>

            <div className={styles.actions}>
              <button type="button" className={styles.secondary} onClick={onClose}>
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
                Stars to add: <strong className={styles.positive}>+{amount.toLocaleString()} Stars</strong>
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
              the authoritative balance atomically.
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.secondary}
                onClick={() => setStep('form')}
                disabled={submitting}
              >
                Cancel
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
