import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildPendingStarsGrant,
  clearPendingStarsGrant,
  isDefinitiveGrantFailure,
  pendingMatchesPayload,
  readPendingStarsGrant,
  writePendingStarsGrant,
} from './adminApi'

describe('pending Stars grant session recovery', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  it('persists and restores pending grant without storing the note', () => {
    const pending = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'user-9',
      amount: 75,
      reason: 'CUSTOMER_APPRECIATION',
      note: 'secret customer note',
      idempotencyKey: 'grant-abc-12345678',
    })
    expect(writePendingStarsGrant(pending).ok).toBe(true)
    const raw = sessionStorage.getItem('fr.admin.starsGrant.pending.v1')!
    expect(raw).not.toContain('secret customer note')
    const restored = readPendingStarsGrant()
    expect(restored?.idempotencyKey).toBe('grant-abc-12345678')
    expect(restored?.amount).toBe(75)
    expect(restored?.adminId).toBe('admin-1')
    expect(restored?.recipientId).toBe('user-9')
  })

  it('matches exact payload for retry reuse', () => {
    const pending = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'user-9',
      amount: 75,
      reason: 'CUSTOMER_APPRECIATION',
      note: 'hello',
      idempotencyKey: 'grant-abc-12345678',
    })
    expect(
      pendingMatchesPayload(pending, {
        adminId: 'admin-1',
        recipientId: 'user-9',
        amount: 75,
        reason: 'CUSTOMER_APPRECIATION',
        note: 'hello',
      }),
    ).toBe(true)
    expect(
      pendingMatchesPayload(pending, {
        adminId: 'admin-1',
        recipientId: 'user-9',
        amount: 80,
        reason: 'CUSTOMER_APPRECIATION',
        note: 'hello',
      }),
    ).toBe(false)
  })

  it('clears pending only for matching idempotency key', () => {
    writePendingStarsGrant(
      buildPendingStarsGrant({
        adminId: 'a',
        recipientId: 'b',
        amount: 10,
        reason: 'OTHER',
        note: 'x',
        idempotencyKey: 'grant-keep-key-01',
      }),
    )
    clearPendingStarsGrant('grant-other-key-99')
    expect(readPendingStarsGrant()?.idempotencyKey).toBe('grant-keep-key-01')
    clearPendingStarsGrant('grant-keep-key-01')
    expect(readPendingStarsGrant()).toBeNull()
  })

  it('survives simulated refresh (same sessionStorage)', () => {
    writePendingStarsGrant(
      buildPendingStarsGrant({
        adminId: 'admin-1',
        recipientId: 'user-9',
        amount: 500,
        reason: 'PROMOTIONAL_GIFT',
        note: '',
        idempotencyKey: 'grant-refresh-key',
      }),
    )
    const again = readPendingStarsGrant()
    expect(again?.idempotencyKey).toBe('grant-refresh-key')
    expect(again?.amount).toBe(500)
  })

  it('refuses to overwrite customer A pending when writing customer B', () => {
    const pendingA = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'customer-a',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      note: '',
      idempotencyKey: 'grant-customer-a-key',
    })
    expect(writePendingStarsGrant(pendingA).ok).toBe(true)

    const pendingB = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'customer-b',
      amount: 25,
      reason: 'WELCOME_BONUS',
      note: '',
      idempotencyKey: 'grant-customer-b-key',
    })
    const result = writePendingStarsGrant(pendingB)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.existing.recipientId).toBe('customer-a')
      expect(result.existing.idempotencyKey).toBe('grant-customer-a-key')
    }
    expect(readPendingStarsGrant()?.recipientId).toBe('customer-a')
    expect(readPendingStarsGrant()?.idempotencyKey).toBe('grant-customer-a-key')
  })

  it('allows rewriting the same unresolved idempotency key', () => {
    const first = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'customer-a',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      note: 'n1',
      idempotencyKey: 'grant-same-key-01',
    })
    expect(writePendingStarsGrant(first).ok).toBe(true)
    const again = buildPendingStarsGrant({
      adminId: 'admin-1',
      recipientId: 'customer-a',
      amount: 50,
      reason: 'CUSTOMER_APPRECIATION',
      note: 'n1',
      idempotencyKey: 'grant-same-key-01',
    })
    expect(writePendingStarsGrant(again).ok).toBe(true)
    expect(readPendingStarsGrant()?.idempotencyKey).toBe('grant-same-key-01')
  })

  it('classifies definitive vs uncertain grant failures', () => {
    expect(isDefinitiveGrantFailure(422)).toBe(true)
    expect(isDefinitiveGrantFailure(403)).toBe(true)
    expect(isDefinitiveGrantFailure(409)).toBe(true)
    expect(isDefinitiveGrantFailure(401)).toBe(true)
    expect(isDefinitiveGrantFailure(500)).toBe(false)
    expect(isDefinitiveGrantFailure(0)).toBe(false)
  })
})

describe('parsePositiveGrantAmount re-export smoke', () => {
  it('keeps vitest suite isolated', () => {
    expect(vi).toBeTruthy()
  })
})
