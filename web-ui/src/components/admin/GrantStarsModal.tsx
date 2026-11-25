import { useEffect, useId, useRef, useState } from 'react'
import { ApiError } from '@/services/api/client'
import {
  buildPendingStarsGrant,
  clearPendingStarsGrant,
  fetchAdminStarsGrantByIdempotency,
  fetchAdminStarsGrantLimits,
  isDefinitiveGrantFailure,
  noteFingerprint,
  parsePositiveGrantAmount,
  pendingMatchesPayload,
  postAdminStarsGrant,
  readPendingStarsGrant,
  writePendingStarsGrant,
  type AdminCustomerDetail,
  type AdminStarsGrantReason,
  type AdminStarsGrantRecord,
  type GrantWalletSnapshot,
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

type Step = 'form' | 'confirm' | 'success' | 'blocked'

type Props = {
  customer: Pick<
    AdminCustomerDetail,
    'id' | 'username' | 'email' | 'classification' | 'wallet'
  >
  adminId: string
  onClose: () => void
  /** Second arg is authoritative current wallet when known (may differ from grant.balance_after). */
  onGranted: (grant: AdminStarsGrantRecord, currentWallet?: GrantWalletSnapshot) => void
  /** Optional wallet refresh when reconcile returns a newer balance. */
  onWalletRefresh?: (wallet: {
    ai_stars: number
    ai_stars_unlimited: boolean
    ai_stars_iap_debt: number
  }) => void
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `grant-${crypto.randomUUID()}`
  }
  return `grant-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function GrantStarsModal({
  customer,
  adminId,
  onClose,
  onGranted,
  onWalletRefresh,
}: Props) {
  const titleId = useId()
  const [walletStars, setWalletStars] = useState(Number(customer.wallet.ai_stars || 0))
  const unlimited = Boolean(customer.wallet.ai_stars_unlimited)
  const debt = Number(customer.wallet.ai_stars_iap_debt || 0)
  const blocked = unlimited || debt > 0
  const current = walletStars

  const [maxPerTxn, setMaxPerTxn] = useState(10_000)
  const [largeThreshold, setLargeThreshold] = useState(500)
  const [step, setStep] = useState<Step>('form')
  const [amountRaw, setAmountRaw] = useState('')
  const [reason, setReason] = useState<AdminStarsGrantReason>('CUSTOMER_APPRECIATION')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey)
  const [result, setResult] = useState<AdminStarsGrantRecord | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [noteRequiredForRecovery, setNoteRequiredForRecovery] = useState(false)
  const [blockingPending, setBlockingPending] = useState<{
    recipientId: string
    idempotencyKey: string
  } | null>(null)
  const [walletChangedNote, setWalletChangedNote] = useState<string | null>(null)
  const submitLock = useRef(false)
  const reconcileOnce = useRef(false)

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

  // Restore pending grant / block other-customer unresolved grants.
  useEffect(() => {
    if (reconcileOnce.current) return
    reconcileOnce.current = true
    const pending = readPendingStarsGrant()
    if (!pending) return
    if (pending.adminId !== adminId) return

    if (pending.recipientId !== customer.id) {
      setBlockingPending({
        recipientId: pending.recipientId,
        idempotencyKey: pending.idempotencyKey,
      })
      setStep('blocked')
      setError(
        'An unresolved Stars grant for another customer is still pending recovery. ' +
          'Reconcile that grant before starting a new one — the pending record was not overwritten.',
      )
      return
    }

    setIdempotencyKey(pending.idempotencyKey)
    setAmountRaw(String(pending.amount))
    setReason(pending.reason as AdminStarsGrantReason)
    setUncertain(true)
    setNoteRequiredForRecovery(pending.noteFingerprint !== noteFingerprint(''))
    setNote('')
    setStep('confirm')
    setReconciling(true)
    setError('Checking whether this grant already completed…')

    void fetchAdminStarsGrantByIdempotency(pending.idempotencyKey)
      .then((rec) => {
        if (rec.outcome === 'recorded' && rec.grant) {
          clearPendingStarsGrant(pending.idempotencyKey)
          setResult(rec.grant)
          setUncertain(false)
          setNoteRequiredForRecovery(false)
          if (rec.wallet) {
            setWalletStars(rec.wallet.ai_stars)
            onWalletRefresh?.({
              ai_stars: rec.wallet.ai_stars,
              ai_stars_unlimited: rec.wallet.ai_stars_unlimited,
              ai_stars_iap_debt: rec.wallet.ai_stars_iap_debt,
            })
            if (rec.wallet.ai_stars !== rec.grant.balance_after) {
              setWalletChangedNote(
                `Wallet has changed since the grant completed (current balance ${rec.wallet.ai_stars.toLocaleString()} Stars; grant recorded balance after ${rec.grant.balance_after.toLocaleString()}).`,
              )
            }
          }
          setError(null)
          setStep('success')
          onGranted(
            rec.grant,
            rec.wallet
              ? {
                  ai_stars: rec.wallet.ai_stars,
                  ai_stars_unlimited: rec.wallet.ai_stars_unlimited,
                  ai_stars_iap_debt: rec.wallet.ai_stars_iap_debt,
                }
              : { ai_stars: rec.grant.balance_after },
          )
          return
        }
        if (rec.outcome === 'unavailable') {
          setError(
            rec.message ||
              'Grant reconciliation is unavailable for this administrator. Do not submit a new key.',
          )
          setStep('blocked')
          return
        }
        // not_found — preserve key; require exact payload (incl. note) before retry.
        setError(
          'No completed grant was found for this idempotency key yet. ' +
            'A concurrent request may still commit. Re-enter the exact original note (if any), ' +
            'then confirm to retry with the same key — do not change the amount.',
        )
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : 'Reconciliation failed'
        setError(
          `${msg}. Pending grant kept. Re-enter the original note if needed, then confirm — ` +
            'the same idempotency key will be reused. Not-found / network errors are not proof of failure.',
        )
      })
      .finally(() => {
        setReconciling(false)
      })
  }, [adminId, customer.id, onGranted, onWalletRefresh])

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
    if (uncertain) {
      const pending = readPendingStarsGrant()
      if (
        pending &&
        !pendingMatchesPayload(pending, {
          adminId,
          recipientId: customer.id,
          amount,
          reason,
          note: note.trim(),
        })
      ) {
        if (noteRequiredForRecovery && !note.trim()) {
          return 'Re-enter the original internal note before retrying this pending grant.'
        }
        return (
          'Reconstructed payload must match the pending grant (amount, reason, and note). ' +
          'Do not change the amount or start a new idempotency key.'
        )
      }
    }
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
    if (submitting || submitLock.current || reconciling) {
      setError('Grant is in progress — wait for confirmation before closing.')
      return
    }
    onClose()
  }

  async function confirmGrant() {
    if (submitLock.current || submitting || reconciling) return
    const err = validateForm()
    if (err || amount == null) {
      setError(err ?? 'Invalid amount')
      setStep('form')
      return
    }

    // Snapshot recovery state before any async work. A 4xx on retry does NOT
    // prove the earlier uncertain request failed — keep the original key.
    const recoveringUncertain = uncertain
    const pendingExisting = readPendingStarsGrant()
    let key = idempotencyKey
    if (pendingExisting) {
      if (pendingExisting.adminId === adminId && pendingExisting.recipientId !== customer.id) {
        setError(
          'An unresolved grant for another customer must be reconciled before submitting a new grant.',
        )
        setBlockingPending({
          recipientId: pendingExisting.recipientId,
          idempotencyKey: pendingExisting.idempotencyKey,
        })
        setStep('blocked')
        return
      }
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
        setError(
          'A pending grant with different details exists for this customer. ' +
            'Re-enter the exact original note and amount, or reconcile via the server before a new grant.',
        )
        return
      }
    }

    // Sync lock before any async reconcile or POST (double-click / concurrent safe).
    submitLock.current = true
    setSubmitting(true)
    setError(null)
    try {
      // Prefer read-only reconcile before another POST when recovering.
      if (recoveringUncertain) {
        try {
          const rec = await fetchAdminStarsGrantByIdempotency(key)
          if (rec.outcome === 'recorded' && rec.grant) {
            clearPendingStarsGrant(key)
            setResult(rec.grant)
            setUncertain(false)
            setNoteRequiredForRecovery(false)
            const walletSnap: GrantWalletSnapshot = rec.wallet
              ? {
                  ai_stars: rec.wallet.ai_stars,
                  ai_stars_unlimited: rec.wallet.ai_stars_unlimited,
                  ai_stars_iap_debt: rec.wallet.ai_stars_iap_debt,
                }
              : { ai_stars: rec.grant.balance_after }
            setWalletStars(walletSnap.ai_stars)
            if (rec.wallet) {
              onWalletRefresh?.({
                ai_stars: rec.wallet.ai_stars,
                ai_stars_unlimited: rec.wallet.ai_stars_unlimited,
                ai_stars_iap_debt: rec.wallet.ai_stars_iap_debt,
              })
              if (rec.wallet.ai_stars !== rec.grant.balance_after) {
                setWalletChangedNote(
                  `Wallet has changed since the grant completed (current balance ${rec.wallet.ai_stars.toLocaleString()} Stars).`,
                )
              }
            }
            setStep('success')
            onGranted(rec.grant, walletSnap)
            return
          }
          if (rec.outcome === 'unavailable') {
            setError(rec.message)
            setStep('blocked')
            return
          }
        } catch {
          // Fall through to POST — uncertain network; keep same key.
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
      const writeResult = writePendingStarsGrant(pending)
      if (!writeResult.ok) {
        setError(
          'An unresolved pending grant already exists and was not overwritten. ' +
            `Reconcile recipient ${writeResult.existing.recipientId} first.`,
        )
        setBlockingPending({
          recipientId: writeResult.existing.recipientId,
          idempotencyKey: writeResult.existing.idempotencyKey,
        })
        setStep('blocked')
        return
      }

      const grant = await postAdminStarsGrant(customer.id, {
        amount,
        reason,
        note: note.trim() || null,
        idempotency_key: key,
        confirm_large: amount >= largeThreshold,
      })
      clearPendingStarsGrant(key)
      setUncertain(false)
      setNoteRequiredForRecovery(false)
      setResult(grant)
      setWalletStars(grant.balance_after)
      setStep('success')
      onGranted(grant, { ai_stars: grant.balance_after })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Grant failed'
      const status = e instanceof ApiError ? e.status : 0
      if (recoveringUncertain) {
        // Retry 4xx / network while recovering: keep original pending key until
        // authoritative reconcile proves recorded or a human resolves it.
        setUncertain(true)
        setNoteRequiredForRecovery(noteFingerprint(note.trim()) !== noteFingerprint(''))
        setError(
          `${msg}. Outcome still uncertain for the original idempotency key — ` +
            'pending recovery was preserved. Reconcile or retry with the same key; ' +
            'do not start a new key. A 4xx on retry does not prove the earlier request failed.',
        )
        setStep('confirm')
      } else if (status && isDefinitiveGrantFailure(status)) {
        // First-attempt definitive validation/auth rejection — safe to clear.
        clearPendingStarsGrant(key)
        setUncertain(false)
        setNoteRequiredForRecovery(false)
        setIdempotencyKey(newIdempotencyKey())
        setError(`${msg}. This rejection is definitive — pending recovery was cleared.`)
        setStep('form')
      } else {
        setUncertain(true)
        setNoteRequiredForRecovery(noteFingerprint(note.trim()) !== noteFingerprint(''))
        setError(
          `${msg}. Outcome uncertain. Reopen or confirm again with the same idempotency key ` +
            'after re-entering the original note — do not start a new key.',
        )
        setStep('confirm')
      }
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
        if (!submitting && !reconciling) attemptClose()
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
            disabled={submitting || reconciling}
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
            Pending grant recovery active — idempotency key preserved. Reconcile via the server
            before posting again. Notes are not stored in the browser; re-enter the original note
            if one was supplied.
          </div>
        ) : null}

        {error ? <div className={styles.error}>{error}</div> : null}

        {step === 'blocked' ? (
          <div className={styles.body}>
            <p className={styles.confirmLead}>
              Grant submission is blocked until the unresolved pending operation is reconciled.
            </p>
            {blockingPending ? (
              <ul className={styles.confirmList}>
                <li>
                  Pending recipient id: <code>{blockingPending.recipientId}</code>
                </li>
                <li>
                  Idempotency key: <code>{blockingPending.idempotencyKey}</code>
                </li>
              </ul>
            ) : null}
            <div className={styles.actions}>
              <button type="button" className={styles.primary} onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        ) : null}

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
              Internal note
              {reason === 'OTHER' || noteRequiredForRecovery
                ? ' (required)'
                : ' (optional)'}
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={2000}
                rows={3}
                placeholder={
                  noteRequiredForRecovery
                    ? 'Re-enter the exact original internal note'
                    : 'Visible only to administrators'
                }
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
            {uncertain ? (
              <label className={styles.field}>
                Internal note
                {noteRequiredForRecovery || reason === 'OTHER' ? ' (required for retry)' : ''}
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder="Re-enter the exact original internal note (not stored in the browser)"
                />
              </label>
            ) : null}
            <p className={styles.warn}>
              This operation cannot be undone from the administration panel. The backend calculates
              the authoritative balance atomically. Rapid double-clicks are ignored.
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.secondary}
                onClick={() => {
                  if (!submitting && !reconciling) setStep('form')
                }}
                disabled={submitting || reconciling}
              >
                Back
              </button>
              <button
                type="button"
                className={styles.primary}
                onClick={() => void confirmGrant()}
                disabled={submitting || reconciling}
              >
                {submitting || reconciling
                  ? 'Working…'
                  : uncertain
                    ? `Reconcile / Confirm ${amount.toLocaleString()} Stars`
                    : `Confirm & Grant ${amount.toLocaleString()} Stars`}
              </button>
            </div>
          </div>
        ) : null}

        {step === 'success' && result ? (
          <div className={styles.body}>
            <div className={styles.success} role="status">
              Stars granted successfully
              {result.idempotent_replay ? ' (idempotent replay / reconciled)' : ''}
            </div>
            <ul className={styles.confirmList}>
              <li>
                Amount added:{' '}
                <strong className={styles.positive}>+{result.amount.toLocaleString()}</strong>
              </li>
              <li>
                Balance after grant:{' '}
                <strong>{result.balance_after.toLocaleString()} Stars</strong>
              </li>
              <li>
                Current wallet: <strong>{current.toLocaleString()} Stars</strong>
              </li>
              <li>
                Grant reference: <code>{result.grant_id}</code>
              </li>
            </ul>
            {walletChangedNote ? (
              <p className={styles.warn} role="status">
                {walletChangedNote}
              </p>
            ) : null}
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
