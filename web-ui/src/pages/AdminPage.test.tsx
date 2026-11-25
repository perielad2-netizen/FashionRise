import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminPage } from '@/pages/AdminPage'

const fetchAdminOverview = vi.fn()
const fetchAdminCustomers = vi.fn()
const fetchAdminCustomer = vi.fn()
const fetchAdminReports = vi.fn()
const fetchAdminStarsGrantsOverview = vi.fn()
const fetchMetricDictionary = vi.fn()
const fetchClassificationDryRun = vi.fn()
const patchAdminClassification = vi.fn()

vi.mock('@/services/adminApi', () => ({
  fetchAdminOverview: (...args: unknown[]) => fetchAdminOverview(...args),
  fetchAdminCustomers: (...args: unknown[]) => fetchAdminCustomers(...args),
  fetchAdminCustomer: (...args: unknown[]) => fetchAdminCustomer(...args),
  fetchAdminReports: (...args: unknown[]) => fetchAdminReports(...args),
  fetchAdminStarsGrantsOverview: (...args: unknown[]) => fetchAdminStarsGrantsOverview(...args),
  fetchMetricDictionary: (...args: unknown[]) => fetchMetricDictionary(...args),
  fetchClassificationDryRun: (...args: unknown[]) => fetchClassificationDryRun(...args),
  patchAdminClassification: (...args: unknown[]) => patchAdminClassification(...args),
}))

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => false,
}))

const authState = {
  user: {
    id: 'admin-1',
    username: 'yanivprbk',
    email: 'yaniv@example.com',
    is_admin: true,
  } as {
    id: string
    username: string
    email: string
    is_admin: boolean
  } | null,
  bootstrapping: false,
  isAuthenticated: true,
}

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => authState,
}))

vi.mock('@/components/layout/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

function overviewPayload(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: '2026-11-25T12:00:00Z',
    timezone_reporting: 'Asia/Jerusalem',
    range: { key: 'last_30d', start: '2026-10-26T00:00:00Z', end: '2026-11-25T00:00:00Z' },
    audience: 'customers',
    audience_default: 'customers',
    classification_counts: {
      CUSTOMER: 12,
      UNCLASSIFIED: 4,
      OWNER: 1,
      ADMIN: 0,
      INTERNAL_TESTER: 0,
      QA_AUTOMATION: 2,
      DEMO_ACCOUNT: 0,
    },
    users: {
      registered: 12,
      enabled: 11,
      total: 12,
      active: 11,
      new_7d: 3,
      new_30d: 8,
      new_in_range: 5,
      confirmed_customers: 12,
      unclassified: 4,
      paying_customers: 2,
    },
    content: {
      designs_saved: 40,
      designs_saved_in_range: 7,
      designs_published: 10,
      looks_published: 8,
      gallery_public: 8,
      models_created: 6,
      models_ready: 5,
      ai_fabrics_created: 3,
      uploaded_fabrics: 1,
      likes: 20,
      comments: 9,
      follows: 4,
    },
    engagement: {
      likes_by_audience: 20,
      likes_on_audience_content: 15,
      comments_by_audience: 9,
      comments_on_audience_content: 6,
      follows_by_audience: 4,
      followed_audience: 2,
      dau: { kind: 'unavailable' },
      wau: { kind: 'unavailable' },
    },
    ai_usage: {
      fitting_room_completed: 14,
      fitting_room_7d: 3,
      fitting_room_in_range: 4,
      magic_completed: 30,
      magic_in_range: 6,
      try_on_completed: 5,
      croquis_completed_in_range: 2,
      techpack_completed_in_range: 1,
      jobs_last_24h: 10,
      jobs_pending: 2,
      jobs_failed: 1,
      jobs_scope_label: 'Global / All Accounts',
      status_semantics: 'completed',
      note: 'Success = completed',
    },
    operations_global: {
      scope_label: 'Global / All Accounts',
      jobs_pending: 2,
      reports_open: 1,
    },
    stars: {
      starting_grant_per_user: 10,
      starting_balance_config: 10,
      free_stars_consumed_est: null,
      paid_stars_consumed_est: null,
      stars_spent_total_est: null,
      spent_by_feature_est: {},
      stars_purchased_net: 100,
      stars_clawed_back: 0,
      wallet_balance_sum: 220,
      unlimited_wallets: 1,
      costs: { magic: 2, fitting_room: 5 },
      free_vs_paid_attribution: { kind: 'unavailable', detail: 'no ledger' },
      admin_grants: { kind: 'unavailable', detail: 'separate PR' },
    },
    revenue: {
      currency: 'USD',
      gross_list_price_usd: 11.98,
      refunds_list_price_usd: 0,
      net_list_price_usd: 11.98,
      purchases_counted: 2,
      sandbox_purchases_excluded: 1,
      unknown_environment_excluded: 0,
      kind: 'estimated',
      note: 'Estimated catalog list prices',
      product_catalog: [],
    },
    moderation: { reports_open: 1, reports_total: 3, scope_label: 'Global / All Accounts' },
    charts: {
      registrations_trend: {
        kind: 'exact',
        points: [
          { date: '2026-11-24', count: 2 },
          { date: '2026-11-25', count: 1 },
        ],
        empty: false,
      },
      revenue_trend: { kind: 'unavailable' },
      ai_cost_trend: { kind: 'unavailable' },
    },
    needs_attention: [
      {
        id: 'unclassified_accounts',
        severity: 'medium',
        title: '4 unclassified accounts',
        detail: 'Review classification',
        section: 'customers',
        scope: 'Global / All Accounts',
      },
    ],
    unavailable: ['engagement.dau', 'stars.free_vs_paid_attribution'],
    recent_signups: [
      { id: 'u1', username: 'newshopper', created_at: '2026-11-24T10:00:00Z', classification: 'CUSTOMER' },
    ],
    ...overrides,
  }
}

describe('AdminPage', () => {
  beforeEach(() => {
    authState.user = {
      id: 'admin-1',
      username: 'yanivprbk',
      email: 'yaniv@example.com',
      is_admin: true,
    }
    fetchAdminOverview.mockReset()
    fetchAdminCustomers.mockReset()
    fetchAdminCustomer.mockReset()
    fetchAdminReports.mockReset()
    fetchMetricDictionary.mockReset()
    fetchClassificationDryRun.mockReset()
    patchAdminClassification.mockReset()

    fetchAdminOverview.mockResolvedValue(overviewPayload())
    fetchAdminCustomers.mockResolvedValue({
      items: [
        {
          id: 'c1',
          username: 'alice',
          email: 'alice@example.com',
          is_active: true,
          is_admin: false,
          classification: 'CUSTOMER',
          ai_stars: 8,
          ai_stars_unlimited: false,
          created_at: '2026-11-01T00:00:00Z',
        },
      ],
      total: 40,
      limit: 25,
      offset: 0,
      has_more: true,
    })
    fetchAdminReports.mockResolvedValue({ items: [], count: 0 })
    fetchMetricDictionary.mockResolvedValue({
      items: [
        {
          id: 'users.enabled',
          name: 'Enabled accounts',
          definition: 'is_active=true',
          source: 'users',
          kind: 'exact',
        },
      ],
    })
  })

  it('loads overview KPIs for confirmed customers by default', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(fetchAdminOverview).toHaveBeenCalled())
    expect(fetchAdminOverview).toHaveBeenCalledWith(
      expect.objectContaining({ audience: 'customers', range: 'last_30d' }),
    )
    expect(
      await screen.findByRole('heading', { name: 'Overview' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Audience filter: customers/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Needs attention' })).toBeInTheDocument()
  })

  it('switches audience and reloads overview', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })

    fetchAdminOverview.mockResolvedValueOnce(
      overviewPayload({
        audience: 'all',
        users: {
          ...overviewPayload().users,
          registered: 99,
          total: 99,
          confirmed_customers: 12,
        },
      }),
    )
    fireEvent.click(screen.getByRole('button', { name: /All accounts/i }))
    await waitFor(() =>
      expect(fetchAdminOverview).toHaveBeenCalledWith(
        expect.objectContaining({ audience: 'all' }),
      ),
    )
  })

  it('switches date range', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })
    fireEvent.click(screen.getByRole('button', { name: /^7d$/i }))
    await waitFor(() =>
      expect(fetchAdminOverview).toHaveBeenCalledWith(
        expect.objectContaining({ range: 'last_7d' }),
      ),
    )
  })

  it('shows loading then error state', async () => {
    fetchAdminOverview.mockRejectedValueOnce(new Error('boom'))
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('boom')).toBeInTheDocument()
  })

  it('paginates customers directory', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })
    fireEvent.click(screen.getByRole('button', { name: /^Customers$/i }))
    await waitFor(() => expect(fetchAdminCustomers).toHaveBeenCalled())
    expect(await screen.findByText('@alice')).toBeInTheDocument()
    expect(screen.getByText(/page 1 of/i)).toBeInTheDocument()

    fetchAdminCustomers.mockResolvedValueOnce({
      items: [
        {
          id: 'c2',
          username: 'bob',
          email: 'bob@example.com',
          is_active: true,
          is_admin: false,
          classification: 'CUSTOMER',
          ai_stars: 3,
          ai_stars_unlimited: false,
          created_at: null,
        },
      ],
      total: 40,
      limit: 25,
      offset: 25,
      has_more: true,
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await waitFor(() =>
      expect(fetchAdminCustomers).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 25 }),
      ),
    )
  })

  it('requires confirmation before classification submit', async () => {
    fetchAdminCustomer.mockResolvedValue({
      id: 'c1',
      username: 'alice',
      email: 'alice@example.com',
      is_active: true,
      is_admin: false,
      classification: 'UNCLASSIFIED',
      classification_updated_at: null,
      ai_stars: 8,
      ai_stars_unlimited: false,
      created_at: null,
      wallet: { ai_stars: 8, ai_stars_iap_debt: 0, ai_stars_unlimited: false },
      activity: {
        designs_saved: 1,
        models_created: 0,
        magic_completed: 0,
        fitting_room_completed: 0,
      },
      purchases: { items: [], lifetime_list_price_usd: 0, kind: 'estimated' },
      classification_history: [],
      suggestion: { suggested: 'CUSTOMER', confidence: 'none', evidence: [] },
    })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })
    fireEvent.click(screen.getByRole('button', { name: /^Customers$/i }))
    await screen.findByText('@alice')
    fireEvent.click(screen.getByText('@alice'))

    const dialog = await screen.findByRole('dialog', { name: /Customer detail/i })
    fireEvent.change(within(dialog).getByDisplayValue('UNCLASSIFIED'), {
      target: { value: 'CUSTOMER' },
    })
    fireEvent.change(within(dialog).getByPlaceholderText(/Why this classification/i), {
      target: { value: 'manual review confirmed' },
    })
    const submit = within(dialog).getByRole('button', { name: /Submit classification/i })
    expect(submit).toBeDisabled()
    fireEvent.click(within(dialog).getByRole('checkbox'))
    expect(submit).not.toBeDisabled()
    patchAdminClassification.mockResolvedValue({
      id: 'c1',
      username: 'alice',
      email: 'alice@example.com',
      is_active: true,
      is_admin: false,
      classification: 'CUSTOMER',
      classification_updated_at: '2026-11-25T12:01:00Z',
      ai_stars: 8,
      ai_stars_unlimited: false,
      created_at: null,
      wallet: { ai_stars: 8, ai_stars_iap_debt: 0, ai_stars_unlimited: false },
      activity: {
        designs_saved: 1,
        models_created: 0,
        magic_completed: 0,
        fitting_room_completed: 0,
      },
      purchases: { items: [], lifetime_list_price_usd: 0, kind: 'estimated' },
      classification_history: [
        {
          id: 'h1',
          from: 'UNCLASSIFIED',
          to: 'CUSTOMER',
          reason: 'manual review confirmed',
          note: null,
          actor_id: 'admin-1',
          actor_username: 'yanivprbk',
          created_at: '2026-11-25T12:01:00Z',
        },
      ],
      suggestion: { suggested: 'CUSTOMER', confidence: 'none', evidence: [] },
    })
    fireEvent.click(submit)
    await waitFor(() =>
      expect(patchAdminClassification).toHaveBeenCalledWith(
        'c1',
        expect.objectContaining({
          classification: 'CUSTOMER',
          reason: 'manual review confirmed',
          expected_classification: 'UNCLASSIFIED',
        }),
      ),
    )
  })

  it('opens mobile navigation drawer', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })
    // Desktop CSS hides the toggle from the a11y tree; still present in DOM for mobile.
    const menu = screen.getByLabelText(/Open navigation/i, { hidden: true })
    fireEvent.click(menu)
    expect(screen.getByLabelText(/Close navigation/i, { hidden: true })).toBeInTheDocument()
  })

  it('denies non-admin users', async () => {
    authState.user = {
      id: 'u2',
      username: 'regular',
      email: 'r@example.com',
      is_admin: false,
    }
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Admin access only/i)).toBeInTheDocument()
    expect(fetchAdminOverview).not.toHaveBeenCalled()
  })

  it('preserves Reports section', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: 'Overview' })
    fireEvent.click(screen.getByRole('button', { name: /^Reports/i }))
    await waitFor(() => expect(fetchAdminReports).toHaveBeenCalled())
    expect(await screen.findByText(/No reports in this filter/i)).toBeInTheDocument()
  })
})
