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
  unavailable?: string[]
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
