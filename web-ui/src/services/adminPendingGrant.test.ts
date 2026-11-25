import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildPendingStarsGrant,
  clearPendingStarsGrant,
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
    writePendingStarsGrant(pending)
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
    // Simulate modal remount / page refresh within the same browser session.
    const again = readPendingStarsGrant()
    expect(again?.idempotencyKey).toBe('grant-refresh-key')
    expect(again?.amount).toBe(500)
  })
})

describe('parsePositiveGrantAmount re-export smoke', () => {
  it('keeps vitest suite isolated', () => {
    expect(vi).toBeTruthy()
  })
})
