import { apiRequest } from '@/services/api/client'

export type AccountClassification =
  | 'CUSTOMER'
  | 'OWNER'
  | 'ADMIN'
  | 'INTERNAL_TESTER'
  | 'QA_AUTOMATION'
  | 'DEMO_ACCOUNT'
  | 'UNCLASSIFIED'

export type AdminAudience =
  | 'all'
  | 'customers'
  | 'internal'
  | 'unclassified'
  | AccountClassification

export type AdminRangeKey =
  | 'today'
  | 'yesterday'
  | 'last_7d'
  | 'last_30d'
  | 'last_90d'
  | 'this_month'
  | 'last_month'
  | 'all_time'

export type AdminOverview = {
  generated_at: string
  timezone_reporting?: string
  range?: { key: string; start: string | null; end: string; label_note?: string }
  audience?: string
  audience_default?: string
  classification_counts?: Record<string, number>
  users: {
    registered?: number
    enabled?: number
    total: number
    active: number
    new_7d: number
    new_30d: number
    new_in_range?: number
    confirmed_customers?: number
    unclassified?: number
    internal?: number
    paying_customers?: number
    period?: Record<string, string>
  }
  content: {
    designs_saved: number
    designs_saved_in_range?: number
    designs_published: number
    looks_published: number
    gallery_public: number
    models_created: number
    models_ready: number
    ai_fabrics_created: number
    uploaded_fabrics: number
    likes: number
    comments: number
    follows: number
    period?: Record<string, string>
  }
  engagement?: {
    likes_by_audience?: number
    likes_on_audience_content?: number
    comments_by_audience?: number
    comments_on_audience_content?: number
    follows_by_audience?: number
    followed_audience?: number
    dau?: { kind: string; detail?: string }
    wau?: { kind: string; detail?: string }
  }
  ai_usage: {
    fitting_room_completed: number
    fitting_room_7d: number
    fitting_room_in_range?: number
    magic_completed: number
    magic_in_range?: number
    try_on_completed: number
    try_on_completed_in_range?: number
    croquis_completed_in_range?: number
    techpack_completed_in_range?: number
    jobs_last_24h: number
    jobs_pending?: number
    jobs_failed?: number
    jobs_scope_label?: string
    status_semantics?: string
    completion_timestamp_note?: string
    note?: string
  }
  operations_global?: {
    scope_label?: string
    jobs_last_24h?: number
    jobs_pending?: number
    jobs_failed_lifetime?: number
    reports_open?: number
    reports_total?: number
  }
  stars: {
    starting_grant_per_user?: number
    starting_balance_config?: number
    free_grants_issued?: number | { kind: string; detail?: string }
    free_stars_consumed_est?: number | null
    paid_stars_consumed_est?: number | null
    stars_spent_total_est?: number | null
    spent_by_feature_est?: Record<string, number>
    stars_purchased_net: number
    stars_clawed_back: number
    wallet_balance_sum: number
    unlimited_wallets?: number
    costs: Record<string, number>
    free_vs_paid_attribution?: { kind: string; detail?: string }
    stars_spent_total?: { kind: string; detail?: string }
    admin_grants?: { kind: string; detail: string }
  }
  revenue: {
    currency: string
    gross_list_price_usd: number
    refunds_list_price_usd?: number
    net_list_price_usd?: number
    purchases_counted: number
    refunds_counted?: number
    sandbox_purchases_excluded?: number
    unknown_environment_excluded?: number
    kind?: string
    period?: string
    note: string
    product_catalog: Array<{
      product_id: string
      stars: number
      list_price_usd: number
    }>
  }
  moderation: {
    scope_label?: string
    reports_open: number
    reports_total: number
  }
  charts?: {
    registrations_trend?: {
      kind: string
      timezone?: string
      grouping?: string
      all_time_chart_capped_to_90_days?: boolean
      cap_note?: string | null
      points?: Array<{ date: string; count: number }>
      empty?: boolean
      detail?: string
    }
    revenue_trend?: { kind: string; detail?: string }
    ai_cost_trend?: { kind: string; detail?: string }
  }
  needs_attention?: Array<{
    id: string
    severity: string
    title: string
    detail: string
    section: string
    scope?: string
  }>
  unavailable?: string[]
  recent_signups: Array<{
    id: string
    username: string
    email?: string
    created_at: string | null
    ai_stars?: number
    classification?: string
    suggestion?: { suggested: string; confidence: string; evidence: string[] }
  }>
}

export type AdminReport = {
  id: string
  status: string
  reason: string
  details: string | null
  created_at: string | null
  updated_at: string | null
  reporter: { id: string; username: string | null }
  reported_user: { id: string; username: string | null }
  gallery_item: {
    id: string
    title: string | null
    image_url: string | null
    moderation_status: string | null
  }
}

export type AdminCustomer = {
  id: string
  username: string
  email: string
  is_active: boolean
  is_admin: boolean
  classification: AccountClassification | string
  classification_note?: string | null
  ai_stars: number
  ai_stars_unlimited: boolean
  created_at: string | null
  suggestion?: { suggested: string; confidence: string; evidence: string[] }
}

export type AdminCustomerDetail = AdminCustomer & {
  email_verified?: boolean
  classification_updated_at?: string | null
  wallet: {
    ai_stars: number
    ai_stars_iap_debt: number
    ai_stars_unlimited: boolean
  }
  activity: {
    designs_saved: number
    models_created: number
    magic_completed: number
    fitting_room_completed: number
  }
  purchases: {
    items: Array<{
      product_id: string
      stars_credited: number
      environment: string | null
      sandbox: boolean
      status: string
      platform: string | null
      created_at: string | null
      list_price_usd: number
    }>
    lifetime_list_price_usd: number
    kind: string
  }
  classification_history: Array<{
    id: string
    from: string
    to: string
    reason: string | null
    note: string | null
    actor_id: string | null
    actor_username?: string | null
    created_at: string | null
  }>
  admin_stars_grants?: {
    kind?: string
    items: AdminStarsGrantRecord[]
    excluded_from_revenue?: boolean
    counts_toward_revenue?: boolean
    editable?: boolean
    deletable?: boolean
  }
  unavailable?: string[]
}

export type AdminStarsGrantReason =
  | 'CUSTOMER_APPRECIATION'
  | 'TECHNICAL_COMPENSATION'
  | 'PROMOTIONAL_GIFT'
  | 'WELCOME_BONUS'
  | 'COMPETITION_REWARD'
  | 'INTERNAL_TESTING'
  | 'OTHER'

export type AdminStarsGrantRecord = {
  grant_id: string
  recipient_id: string | null
  actor_id: string | null
  amount: number
  balance_before: number
  balance_after: number
  reason: string
  note: string | null
  source: string
  status: string
  idempotency_key: string
  created_at: string | null
  idempotent_replay?: boolean
}

export type AdminStarsGrantLimits = {
  max_per_transaction: number
  absolute_ceiling: number
  large_confirm_threshold: number
  reasons: string[]
}

export type AdminStarsGrantsOverview = AdminStarsGrantLimits & {
  kind: string
  source: string
  counts_toward_revenue: boolean
  creates_iap_transactions: boolean
  total_stars_granted: number
  grant_count: number
  recipient_count: number
  by_reason: Record<string, { count: number; stars: number }>
  by_administrator: Array<{
    actor_id: string | null
    username: string | null
    count: number
    stars: number
  }>
  recent: AdminStarsGrantRecord[]
  audience?: string
  note?: string
  range?: { key: string; start: string | null; end: string }
}

export type MetricDefinition = {
  id: string
  name: string
  definition: string
  source: string | null
  kind: 'exact' | 'estimated' | 'unavailable' | string
  limitations?: string
  coverage_note?: string
  audience_default?: string
  period?: string
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export async function fetchAdminOverview(opts?: {
  range?: AdminRangeKey | string
  audience?: AdminAudience | string
}): Promise<AdminOverview> {
  return apiRequest<AdminOverview>(
    `/admin/overview${qs({ range: opts?.range, audience: opts?.audience })}`,
  )
}

export async function fetchAdminReports(status?: string): Promise<{
  items: AdminReport[]
  count: number
}> {
  return apiRequest(`/admin/reports${qs({ status })}`)
}

export async function fetchAdminCustomers(opts?: {
  q?: string
  audience?: string
  classification?: string
  limit?: number
  offset?: number
  sort?: string
}): Promise<{
  items: AdminCustomer[]
  total: number
  limit: number
  offset: number
  has_more?: boolean
}> {
  return apiRequest(
    `/admin/customers${qs({
      q: opts?.q,
      audience: opts?.audience,
      classification: opts?.classification,
      limit: opts?.limit,
      offset: opts?.offset,
      sort: opts?.sort,
    })}`,
  )
}

export async function fetchAdminCustomer(id: string): Promise<AdminCustomerDetail> {
  return apiRequest(`/admin/customers/${encodeURIComponent(id)}`)
}

export async function patchAdminClassification(
  id: string,
  body: {
    classification: string
    reason: string
    note?: string
    expected_classification?: string
    expected_updated_at?: string | null
  },
): Promise<AdminCustomerDetail> {
  return apiRequest(`/admin/customers/${encodeURIComponent(id)}/classification`, {
    method: 'PATCH',
    body,
  })
}

export async function fetchMetricDictionary(): Promise<{ items: MetricDefinition[] }> {
  return apiRequest('/admin/metrics/dictionary')
}

export async function fetchClassificationDryRun(limit = 200): Promise<{
  scanned: number
  actionable_suggestions: number
  items: Array<{
    id: string
    username: string
    current: string
    suggested: string
    confidence: string
    evidence: string[]
  }>
  note: string
}> {
  return apiRequest(`/admin/classification/dry-run${qs({ limit })}`)
}

export async function fetchClassificationOptions(): Promise<{ items: string[] }> {
  return apiRequest('/admin/classification/options')
}

export function parsePositiveGrantAmount(raw: string): number | null {
  const s = (raw || '').trim()
  if (!/^[1-9][0-9]*$/.test(s)) return null
  const n = Number(s)
  if (!Number.isSafeInteger(n) || n <= 0) return null
  return n
}

export async function fetchAdminStarsGrantLimits(): Promise<AdminStarsGrantLimits> {
  return apiRequest('/admin/stars/grants/config')
}

export async function fetchAdminStarsGrantsOverview(opts?: {
  range?: AdminRangeKey | string
  audience?: string
}): Promise<AdminStarsGrantsOverview> {
  return apiRequest(
    `/admin/stars/grants${qs({ range: opts?.range, audience: opts?.audience })}`,
  )
}

export async function postAdminStarsGrant(
  userId: string,
  body: {
    amount: number
    reason: AdminStarsGrantReason | string
    note?: string | null
    idempotency_key: string
    confirm_large: boolean
  },
): Promise<AdminStarsGrantRecord> {
  return apiRequest(`/admin/users/${encodeURIComponent(userId)}/stars/grants`, {
    method: 'POST',
    body,
  })
}

export type AdminStarsGrantReconcileOutcome = 'recorded' | 'not_found' | 'unavailable'

export type AdminStarsGrantReconcileResult = {
  outcome: AdminStarsGrantReconcileOutcome
  message: string
  grant: AdminStarsGrantRecord | null
  wallet: {
    recipient_id: string
    ai_stars: number
    ai_stars_unlimited: boolean
    ai_stars_iap_debt: number
  } | null
  wallet_mutations: number
}

/** Read-only reconciliation — never credits Stars. */
export async function fetchAdminStarsGrantByIdempotency(
  idempotencyKey: string,
): Promise<AdminStarsGrantReconcileResult> {
  return apiRequest(
    `/admin/stars/grants/idempotency/${encodeURIComponent(idempotencyKey)}`,
  )
}

/** Session-scoped pending grant recovery (no notes / emails persisted). */
export type PendingStarsGrant = {
  adminId: string
  recipientId: string
  amount: number
  reason: string
  noteFingerprint: string
  idempotencyKey: string
  createdAt: string
}

const PENDING_GRANT_STORAGE_KEY = 'fr.admin.starsGrant.pending.v1'

export function noteFingerprint(note: string): string {
  // Short non-reversible fingerprint — do not store the note itself.
  let h = 0
  const s = note || ''
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) | 0
  return `${s.length}:${h}`
}

export function buildPendingStarsGrant(input: {
  adminId: string
  recipientId: string
  amount: number
  reason: string
  note: string
  idempotencyKey: string
}): PendingStarsGrant {
  return {
    adminId: input.adminId,
    recipientId: input.recipientId,
    amount: input.amount,
    reason: input.reason,
    noteFingerprint: noteFingerprint(input.note),
    idempotencyKey: input.idempotencyKey,
    createdAt: new Date().toISOString(),
  }
}

export function readPendingStarsGrant(): PendingStarsGrant | null {
  try {
    const raw = sessionStorage.getItem(PENDING_GRANT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PendingStarsGrant
    if (
      !parsed?.adminId ||
      !parsed?.recipientId ||
      !parsed?.idempotencyKey ||
      typeof parsed.amount !== 'number'
    ) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

/**
 * Write a pending grant. Never silently overwrites a different unresolved grant.
 * Same idempotency key may refresh metadata; a different key is blocked.
 */
export function writePendingStarsGrant(
  pending: PendingStarsGrant,
): { ok: true } | { ok: false; existing: PendingStarsGrant } {
  const current = readPendingStarsGrant()
  if (current && current.idempotencyKey !== pending.idempotencyKey) {
    return { ok: false, existing: current }
  }
  sessionStorage.setItem(PENDING_GRANT_STORAGE_KEY, JSON.stringify(pending))
  return { ok: true }
}

export function clearPendingStarsGrant(idempotencyKey?: string): void {
  const current = readPendingStarsGrant()
  if (idempotencyKey && current && current.idempotencyKey !== idempotencyKey) return
  sessionStorage.removeItem(PENDING_GRANT_STORAGE_KEY)
}

export function pendingMatchesPayload(
  pending: PendingStarsGrant,
  input: {
    adminId: string
    recipientId: string
    amount: number
    reason: string
    note: string
  },
): boolean {
  return (
    pending.adminId === input.adminId &&
    pending.recipientId === input.recipientId &&
    pending.amount === input.amount &&
    pending.reason === input.reason &&
    pending.noteFingerprint === noteFingerprint(input.note)
  )
}

/** Definitive client/auth/validation failures — do not keep retrying blindly. */
export function isDefinitiveGrantFailure(status: number): boolean {
  return status === 400 || status === 401 || status === 403 || status === 404 || status === 409 || status === 422
}
