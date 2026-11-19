import { apiRequest } from '@/services/api/client'

export type AdminOverview = {
  generated_at: string
  users: {
    total: number
    active: number
    new_7d: number
    new_30d: number
  }
  content: {
    designs_saved: number
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
  }
  ai_usage: {
    fitting_room_completed: number
    fitting_room_7d: number
    magic_completed: number
    try_on_completed: number
    jobs_last_24h: number
  }
  stars: {
    starting_grant_per_user: number
    free_grants_issued: number
    free_stars_consumed_est: number
    paid_stars_consumed_est: number
    stars_spent_total_est: number
    spent_by_feature_est: Record<string, number>
    stars_purchased_net: number
    stars_clawed_back: number
    wallet_balance_sum: number
    costs: Record<string, number>
  }
  revenue: {
    currency: string
    gross_list_price_usd: number
    purchases_counted: number
    note: string
    product_catalog: Array<{
      product_id: string
      stars: number
      list_price_usd: number
    }>
  }
  moderation: {
    reports_open: number
    reports_total: number
  }
  recent_signups: Array<{
    id: string
    username: string
    email: string
    created_at: string | null
    ai_stars: number
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

export async function fetchAdminOverview(): Promise<AdminOverview> {
  return apiRequest<AdminOverview>('/admin/overview')
}

export async function fetchAdminReports(status?: string): Promise<{
  items: AdminReport[]
  count: number
}> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiRequest(`/admin/reports${q}`)
}
