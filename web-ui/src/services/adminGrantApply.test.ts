import { describe, expect, it } from 'vitest'
import {
  applyStarsGrantToCustomerDetail,
  type AdminCustomerDetail,
  type AdminStarsGrantRecord,
} from './adminApi'

const baseCustomer = {
  id: 'user-1',
  email: 'a@example.com',
  username: 'shopper',
  is_active: true,
  is_admin: false,
  classification: 'CUSTOMER',
  classification_updated_at: null,
  created_at: null,
  ai_stars: 10,
  ai_stars_unlimited: false,
  wallet: {
    ai_stars: 10,
    ai_stars_unlimited: false,
    ai_stars_iap_debt: 0,
  },
  activity: {
    designs_saved: 0,
    models_created: 0,
    magic_completed: 0,
    fitting_room_completed: 0,
  },
  purchases: {
    items: [],
    lifetime_list_price_usd: 0,
    kind: 'exact',
  },
  classification_history: [],
  admin_stars_grants: {
    kind: 'exact',
    items: [] as AdminStarsGrantRecord[],
    counts_toward_revenue: false,
    editable: false,
    deletable: false,
  },
} as AdminCustomerDetail

const grant: AdminStarsGrantRecord = {
  grant_id: 'g1',
  recipient_id: 'user-1',
  actor_id: 'admin-1',
  amount: 50,
  balance_before: 10,
  balance_after: 60,
  reason: 'CUSTOMER_APPRECIATION',
  note: null,
  source: 'ADMIN_GRANT',
  status: 'completed',
  idempotency_key: 'k1',
  created_at: null,
  idempotent_replay: true,
}

describe('applyStarsGrantToCustomerDetail', () => {
  it('uses authoritative current wallet instead of historical balance_after', () => {
    const next = applyStarsGrantToCustomerDetail(baseCustomer, grant, { ai_stars: 42 })
    expect(next.wallet.ai_stars).toBe(42)
    expect(next.admin_stars_grants?.items[0]?.balance_after).toBe(60)
  })

  it('falls back to grant.balance_after when no current wallet provided', () => {
    const next = applyStarsGrantToCustomerDetail(baseCustomer, grant)
    expect(next.wallet.ai_stars).toBe(60)
  })

  it('does not duplicate an existing grant during reconciliation', () => {
    const withGrant = applyStarsGrantToCustomerDetail(baseCustomer, grant, { ai_stars: 60 })
    const again = applyStarsGrantToCustomerDetail(withGrant, grant, { ai_stars: 30 })
    expect(again.admin_stars_grants?.items).toHaveLength(1)
    expect(again.wallet.ai_stars).toBe(30)
  })

  it('leaves unrelated customers unchanged', () => {
    const other = { ...baseCustomer, id: 'user-other' }
    const next = applyStarsGrantToCustomerDetail(other, grant, { ai_stars: 99 })
    expect(next).toBe(other)
  })
})
