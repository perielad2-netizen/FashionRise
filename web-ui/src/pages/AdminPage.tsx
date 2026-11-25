import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { GrantStarsModal } from '@/components/admin/GrantStarsModal'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { useAuth } from '@/services/auth/AuthProvider'
import {
  fetchAdminCustomer,
  fetchAdminCustomers,
  fetchAdminOverview,
  fetchAdminReports,
  fetchAdminStarsGrantsOverview,
  fetchClassificationDryRun,
  fetchMetricDictionary,
  patchAdminClassification,
  type AccountClassification,
  type AdminCustomer,
  type AdminCustomerDetail,
  type AdminOverview,
  type AdminRangeKey,
  type AdminReport,
  type AdminStarsGrantsOverview,
  type MetricDefinition,
} from '@/services/adminApi'
import { isNativeShell } from '@/services/native/platform'
import styles from './AdminPage.module.css'

const ADMIN_USERNAMES = new Set(['shilatperi', 'perishilat', 'yanivprbk'])

type Section =
  | 'overview'
  | 'customers'
  | 'revenue'
  | 'grants'
  | 'ai'
  | 'community'
  | 'dictionary'
  | 'reports'

const SECTIONS: Array<{ id: Section; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'customers', label: 'Customers' },
  { id: 'revenue', label: 'Revenue & Stars' },
  { id: 'grants', label: 'Stars Grants' },
  { id: 'ai', label: 'AI & Costs' },
  { id: 'community', label: 'Community' },
  { id: 'reports', label: 'Reports' },
  { id: 'dictionary', label: 'Metric dictionary' },
]

const RANGES: Array<{ id: AdminRangeKey; label: string }> = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'last_7d', label: '7d' },
  { id: 'last_30d', label: '30d' },
  { id: 'last_90d', label: '90d' },
  { id: 'this_month', label: 'This month' },
  { id: 'last_month', label: 'Last month' },
  { id: 'all_time', label: 'All time' },
]

const AUDIENCES: Array<{ id: string; label: string }> = [
  { id: 'customers', label: 'Confirmed customers' },
  { id: 'all', label: 'All accounts' },
  { id: 'internal', label: 'Internal / test' },
  { id: 'unclassified', label: 'Unclassified' },
]

const CLASS_OPTIONS: AccountClassification[] = [
  'CUSTOMER',
  'OWNER',
  'ADMIN',
  'INTERNAL_TESTER',
  'QA_AUTOMATION',
  'DEMO_ACCOUNT',
  'UNCLASSIFIED',
]

const PAGE_SIZE = 25

function isAdminUser(username: string | undefined, isAdminFlag: boolean | undefined): boolean {
  if (isAdminFlag) return true
  return ADMIN_USERNAMES.has((username || '').trim().toLowerCase())
}

function fmt(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US').format(n)
}

function fmtMoney(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(n)
}

function kindBadge(kind?: string): string {
  if (kind === 'exact') return styles.kindExact
  if (kind === 'estimated') return styles.kindEst
  if (kind === 'unavailable') return styles.kindUnavailable
  return ''
}

function PeriodTag({ label }: { label: string }) {
  return <span className={styles.periodTag}>{label}</span>
}

function AdminShell() {
  const { user } = useAuth()
  const [section, setSection] = useState<Section>('overview')
  const [range, setRange] = useState<AdminRangeKey>('last_30d')
  const [audience, setAudience] = useState('customers')
  const [menuOpen, setMenuOpen] = useState(false)
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [reports, setReports] = useState<AdminReport[]>([])
  const [reportFilter, setReportFilter] = useState('open')
  const [customers, setCustomers] = useState<AdminCustomer[]>([])
  const [customerTotal, setCustomerTotal] = useState(0)
  const [customerQ, setCustomerQ] = useState('')
  const [customerQDraft, setCustomerQDraft] = useState('')
  const [customerClassFilter, setCustomerClassFilter] = useState('')
  const [customerSort, setCustomerSort] = useState('created_at_desc')
  const [customerOffset, setCustomerOffset] = useState(0)
  const [selectedCustomer, setSelectedCustomer] = useState<AdminCustomerDetail | null>(null)
  const [grantTarget, setGrantTarget] = useState<AdminCustomerDetail | null>(null)
  const [grantsOverview, setGrantsOverview] = useState<AdminStarsGrantsOverview | null>(null)
  const [classDraft, setClassDraft] = useState('')
  const [classReason, setClassReason] = useState('')
  const [classNote, setClassNote] = useState('')
  const [classConfirm, setClassConfirm] = useState(false)
  const [classSaving, setClassSaving] = useState(false)
  const [dictionary, setDictionary] = useState<MetricDefinition[]>([])
  const [dryRunNote, setDryRunNote] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const allowed = Boolean(user && isAdminUser(user.username, user.is_admin))
  const native = isNativeShell()
  const loadGen = useRef(0)

  const load = useCallback(async () => {
    if (native || !allowed) return
    const gen = ++loadGen.current
    setLoading(true)
    setError(null)
    try {
      if (section === 'overview' || section === 'revenue' || section === 'ai') {
        const ov = await fetchAdminOverview({ range, audience })
        if (gen !== loadGen.current) return
        setOverview(ov)
      } else if (section === 'grants') {
        const [ov, grants] = await Promise.all([
          fetchAdminOverview({ range, audience }),
          fetchAdminStarsGrantsOverview({ range, audience }),
        ])
        if (gen !== loadGen.current) return
        setOverview(ov)
        setGrantsOverview(grants)
      } else if (section === 'reports' || section === 'community') {
        const [ov, res] = await Promise.all([
          fetchAdminOverview({ range, audience }),
          fetchAdminReports(reportFilter === 'all' ? undefined : reportFilter),
        ])
        if (gen !== loadGen.current) return
        setOverview(ov)
        setReports(res.items)
      } else if (section === 'customers') {
        const [ov, res] = await Promise.all([
          fetchAdminOverview({ range, audience }),
          fetchAdminCustomers({
            q: customerQ || undefined,
            audience: customerClassFilter ? 'all' : 'all',
            classification: customerClassFilter || undefined,
            limit: PAGE_SIZE,
            offset: customerOffset,
            sort: customerSort,
          }),
        ])
        if (gen !== loadGen.current) return
        setOverview(ov)
        setCustomers(res.items)
        setCustomerTotal(res.total)
      } else if (section === 'dictionary') {
        const res = await fetchMetricDictionary()
        if (gen !== loadGen.current) return
        setDictionary(res.items)
      }
    } catch (err) {
      if (gen !== loadGen.current) return
      const msg = err instanceof Error ? err.message : 'Failed to load admin data'
      setError(msg)
    } finally {
      if (gen === loadGen.current) setLoading(false)
    }
  }, [
    section,
    reportFilter,
    allowed,
    native,
    range,
    audience,
    customerQ,
    customerClassFilter,
    customerOffset,
    customerSort,
  ])

  useEffect(() => {
    void load()
  }, [load])

  const generated = useMemo(() => {
    if (!overview?.generated_at) return null
    try {
      return new Date(overview.generated_at).toLocaleString('en-IL', {
        timeZone: 'Asia/Jerusalem',
      })
    } catch {
      return overview.generated_at
    }
  }, [overview])

  const rangeLabel = overview?.range?.key ?? range

  async function openCustomer(id: string) {
    try {
      const detail = await fetchAdminCustomer(id)
      setSelectedCustomer(detail)
      setClassDraft(detail.classification)
      setClassReason('')
      setClassNote('')
      setClassConfirm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customer')
    }
  }

  async function openGrantFor(id: string) {
    try {
      const detail = await fetchAdminCustomer(id)
      setGrantTarget(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open grant form')
    }
  }

  async function submitClassification() {
    if (!selectedCustomer || !classConfirm) return
    if (classReason.trim().length < 3) {
      setError('A meaningful reason (min 3 characters) is required.')
      return
    }
    setClassSaving(true)
    setError(null)
    try {
      const updated = await patchAdminClassification(selectedCustomer.id, {
        classification: classDraft,
        reason: classReason.trim(),
        note: classNote.trim() || undefined,
        expected_classification: selectedCustomer.classification,
        expected_updated_at: selectedCustomer.classification_updated_at ?? undefined,
      })
      setSelectedCustomer(updated)
      setClassDraft(updated.classification)
      setClassConfirm(false)
      setClassReason('')
      setClassNote('')
      void load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Classification update failed')
    } finally {
      setClassSaving(false)
    }
  }

  async function runDryRun() {
    try {
      const res = await fetchClassificationDryRun(200)
      setDryRunNote(
        `${res.note} Scanned ${res.scanned}; ${res.actionable_suggestions} suggestions (not applied).`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dry-run failed')
    }
  }

  function clearCustomerFilters() {
    setCustomerQ('')
    setCustomerQDraft('')
    setCustomerClassFilter('')
    setCustomerSort('created_at_desc')
    setCustomerOffset(0)
  }

  if (native) {
    return <Navigate to="/studio/home" replace />
  }

  if (!user || !allowed) {
    return (
      <div className={styles.denied}>
        <div>
          <h1>Admin access only</h1>
          <p>Sign in with an admin FashionRise account to open this console.</p>
          <Link className={styles.backLink} to="/studio/home">
            Back to Studio
          </Link>
        </div>
      </div>
    )
  }

  const unclassified = overview?.users.unclassified ?? overview?.classification_counts?.UNCLASSIFIED
  const registered = overview?.users.registered ?? overview?.users.total
  const enabled = overview?.users.enabled ?? overview?.users.active
  const page = Math.floor(customerOffset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(customerTotal / PAGE_SIZE))
  const trendPoints = overview?.charts?.registrations_trend?.points ?? []
  const classCounts = overview?.classification_counts ?? {}

  return (
    <div className={styles.page}>
      {menuOpen ? (
        <button
          type="button"
          className={styles.navScrim}
          aria-label="Dismiss navigation overlay"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}
      <aside className={`${styles.side} ${menuOpen ? styles.sideOpen : ''}`}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>FashionRise</span>
          <span className={styles.brandTitle}>Admin 2.0</span>
        </div>
        <nav className={styles.nav} aria-label="Admin">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`${styles.navBtn} ${section === s.id ? styles.navBtnActive : ''}`}
              aria-current={section === s.id ? 'page' : undefined}
              onClick={() => {
                setSection(s.id)
                setMenuOpen(false)
              }}
            >
              {s.label}
              {s.id === 'reports' && overview && overview.moderation.reports_open > 0
                ? ` (${overview.moderation.reports_open})`
                : ''}
            </button>
          ))}
        </nav>
        <div className={styles.sideFoot}>
          <div>
            Signed in as <strong>@{user.username}</strong>
          </div>
          <Link to="/studio/home">← Back to app</Link>
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <div className={styles.headerTop}>
            <button
              type="button"
              className={styles.menuToggle}
              aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              Menu
            </button>
            <div>
              <h1>{SECTIONS.find((s) => s.id === section)?.label ?? 'Admin'}</h1>
              <p>
                Business intelligence · Asia/Jerusalem · {rangeLabel} · Updated {generated ?? '—'}
              </p>
            </div>
            <button type="button" className={styles.refresh} onClick={() => void load()}>
              Refresh
            </button>
          </div>

          <div className={styles.globalFilters} aria-label="Global filters">
            <div className={styles.filterGroup}>
              <span className={styles.filterLabel}>Audience</span>
              <div className={styles.chipRow}>
                {AUDIENCES.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    className={`${styles.chip} ${audience === a.id ? styles.chipActive : ''}`}
                    onClick={() => setAudience(a.id)}
                  >
                    {a.label}
                    {a.id === 'unclassified' && unclassified != null ? ` (${fmt(unclassified)})` : ''}
                  </button>
                ))}
              </div>
            </div>
            <div className={styles.filterGroup}>
              <span className={styles.filterLabel}>Range</span>
              <div className={styles.chipRow}>
                {RANGES.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className={`${styles.chip} ${range === r.id ? styles.chipActive : ''}`}
                    onClick={() => setRange(r.id)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </header>

        {unclassified != null && unclassified > 0 && audience === 'customers' ? (
          <div className={styles.banner} role="status">
            Default business view = confirmed customers. {fmt(unclassified)} unclassified accounts
            remain — switch Audience to review them.
          </div>
        ) : null}

        {error ? <div className={styles.error}>{error}</div> : null}
        {loading && !error ? <div className={styles.loading}>Loading…</div> : null}

        {!loading && !error && overview && (section === 'overview' || section === 'revenue' || section === 'ai') ? (
          <>
            {section === 'overview' ? (
              <>
                <section className={styles.kpiRow} aria-label="Executive KPIs">
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Confirmed customers <PeriodTag label="snapshot" />
                    </div>
                    <div className={styles.kpiValue}>{fmt(overview.users.confirmed_customers)}</div>
                    <div className={styles.kpiHint}>
                      Audience filter: {audience} · registered in filter {fmt(registered)} · enabled{' '}
                      {fmt(enabled)}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Joined in range <PeriodTag label={rangeLabel} />
                    </div>
                    <div className={styles.kpiValue}>{fmt(overview.users.new_in_range)}</div>
                    <div className={styles.kpiHint}>
                      +{fmt(overview.users.new_7d)} / 7d · unclassified {fmt(unclassified)}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Magic in range <PeriodTag label={rangeLabel} />
                    </div>
                    <div className={styles.kpiValue}>{fmt(overview.ai_usage.magic_in_range)}</div>
                    <div className={styles.kpiHint}>
                      Lifetime completed {fmt(overview.ai_usage.magic_completed)} · status=completed
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Paying customers <PeriodTag label="lifetime" />
                    </div>
                    <div className={styles.kpiValue}>{fmt(overview.users.paying_customers)}</div>
                    <div className={styles.kpiHint}>
                      Production IAP · list-price rev {fmtMoney(overview.revenue.net_list_price_usd ?? overview.revenue.gross_list_price_usd)}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      AI ops (Fitting Room) <PeriodTag label={rangeLabel} />
                    </div>
                    <div className={styles.kpiValue}>
                      {fmt(overview.ai_usage.fitting_room_in_range)}
                    </div>
                    <div className={styles.kpiHint}>
                      Provider cash cost: unavailable · queue{' '}
                      {fmt(overview.operations_global?.jobs_pending ?? overview.ai_usage.jobs_pending)}{' '}
                      <em>(Global)</em>
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Needs attention <PeriodTag label="Global" />
                    </div>
                    <div className={styles.kpiValue}>
                      {fmt(overview.needs_attention?.length ?? 0)}
                    </div>
                    <div className={styles.kpiHint}>
                      Open reports {fmt(overview.moderation.reports_open)} · unclassified{' '}
                      {fmt(unclassified)}
                    </div>
                  </div>
                </section>

                {overview.needs_attention && overview.needs_attention.length > 0 ? (
                  <section className={styles.card} aria-label="Needs attention">
                    <h2>Needs attention</h2>
                    <ul className={styles.alertList}>
                      {overview.needs_attention.map((a) => (
                        <li key={a.id} className={styles.alertItem}>
                          <span className={styles.alertSev}>{a.severity}</span>
                          <div>
                            <strong>{a.title}</strong>
                            <div className={styles.kpiHint}>
                              {a.detail}
                              {a.scope ? ` · ${a.scope}` : ''}
                            </div>
                            <button
                              type="button"
                              className={styles.linkBtn}
                              onClick={() =>
                                setSection(
                                  a.section === 'system'
                                    ? 'ai'
                                    : a.section === 'community'
                                      ? 'community'
                                      : a.section === 'customers'
                                        ? 'customers'
                                        : 'overview',
                                )
                              }
                            >
                              Open {a.section}
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                <section className={styles.grid}>
                  <article className={styles.card}>
                    <h2>Registrations trend</h2>
                    <p className={styles.kpiHint}>
                      Asia/Jerusalem calendar days
                      {overview?.charts?.registrations_trend?.all_time_chart_capped_to_90_days
                        ? ' · All Time chart capped to last 90 days'
                        : ''}
                    </p>
                    {overview?.charts?.registrations_trend?.cap_note ? (
                      <p className={styles.note}>
                        {overview.charts.registrations_trend.cap_note}
                      </p>
                    ) : null}
                    {trendPoints.length === 0 ? (
                      <p className={styles.empty}>No registrations in this audience/range.</p>
                    ) : (
                      <ul className={styles.trendList}>
                        {trendPoints.slice(-14).map((p) => (
                          <li key={p.date}>
                            <span>{p.date}</span>
                            <span>{fmt(p.count)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                  <article className={styles.card}>
                    <h2>Classification distribution</h2>
                    <div className={styles.statList}>
                      {CLASS_OPTIONS.map((c) => (
                        <div className={styles.statRow} key={c}>
                          <span>{c}</span>
                          <span>{fmt(classCounts[c] ?? 0)}</span>
                        </div>
                      ))}
                    </div>
                    <p className={styles.note}>Global inventory — not filtered by Audience chips.</p>
                  </article>
                  <article className={styles.card}>
                    <h2>Feature usage (audience)</h2>
                    <div className={styles.statList}>
                      <div className={styles.statRow}>
                        <span>Designs saved (lifetime)</span>
                        <span>{fmt(overview.content.designs_saved)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Designs in range</span>
                        <span>{fmt(overview.content.designs_saved_in_range)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Looks published</span>
                        <span>{fmt(overview.content.looks_published)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Models ready</span>
                        <span>{fmt(overview.content.models_ready)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>AI fabrics</span>
                        <span>{fmt(overview.content.ai_fabrics_created)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Try-On in range</span>
                        <span>{fmt(overview.ai_usage.try_on_completed)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Techpack in range</span>
                        <span>{fmt(overview.ai_usage.techpack_completed_in_range)}</span>
                      </div>
                    </div>
                  </article>
                  <article className={styles.card}>
                    <h2>Recent customer activity</h2>
                    {overview.recent_signups.length === 0 ? (
                      <p className={styles.empty}>No recent signups in this audience.</p>
                    ) : (
                      <ul className={styles.plainList}>
                        {overview.recent_signups.map((s) => (
                          <li key={s.id}>
                            <button
                              type="button"
                              className={styles.linkBtn}
                              onClick={() => {
                                setSection('customers')
                                void openCustomer(s.id)
                              }}
                            >
                              @{s.username}
                            </button>{' '}
                            · {s.classification ?? '—'}
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                  <article className={styles.card}>
                    <h2>Unavailable / not instrumented</h2>
                    <ul className={styles.plainList}>
                      {(overview.unavailable || []).map((u) => (
                        <li key={u}>{u}</li>
                      ))}
                    </ul>
                    <p className={styles.note}>
                      Shown as unavailable — never substituted with invented zeros. DAU/WAU require a
                      meaningful-activity store.
                    </p>
                  </article>
                </section>
              </>
            ) : null}

            {section === 'revenue' ? (
              <section className={styles.grid}>
                <article className={styles.card}>
                  <h2>
                    Revenue (production) <PeriodTag label={rangeLabel} />
                  </h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Gross list-price USD (est.)</span>
                      <span>{fmtMoney(overview.revenue.gross_list_price_usd)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Refunds list-price USD (est.)</span>
                      <span>{fmtMoney(overview.revenue.refunds_list_price_usd)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Net list-price USD (est.)</span>
                      <span>
                        {fmtMoney(overview.revenue.net_list_price_usd ?? overview.revenue.gross_list_price_usd)}
                      </span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Production purchases</span>
                      <span>{fmt(overview.revenue.purchases_counted)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Sandbox excluded</span>
                      <span>{fmt(overview.revenue.sandbox_purchases_excluded)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Unknown env excluded</span>
                      <span>{fmt(overview.revenue.unknown_environment_excluded)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Stars purchased (net)</span>
                      <span>{fmt(overview.stars.stars_purchased_net)}</span>
                    </div>
                  </div>
                  <p className={styles.note}>{overview.revenue.note}</p>
                </article>
                <article className={styles.card}>
                  <h2>Stars economy</h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Starting balance (config today)</span>
                      <span>{fmt(overview.stars.starting_balance_config ?? overview.stars.starting_grant_per_user)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Free vs paid attribution</span>
                      <span className={`${styles.kind} ${styles.kindUnavailable}`}>unavailable</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Historical spend (actual)</span>
                      <span className={`${styles.kind} ${styles.kindUnavailable}`}>unavailable</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Finite wallets sum</span>
                      <span>
                        {fmt(overview.stars.wallet_balance_sum)} <PeriodTag label="snapshot" />
                      </span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Unlimited wallets</span>
                      <span>{fmt(overview.stars.unlimited_wallets)}</span>
                    </div>
                  </div>
                  {overview.stars.admin_grants ? (
                    <p className={styles.note}>
                      Admin grants: {overview.stars.admin_grants.kind} —{' '}
                      {overview.stars.admin_grants.detail}
                    </p>
                  ) : null}
                  <p className={styles.note}>
                    {overview.stars.free_vs_paid_attribution?.detail ||
                      'Do not infer paid Stars consumption from aggregate grants.'}
                  </p>
                  <h3 className={styles.subHead}>Cost catalog (current config — not historical)</h3>
                  <div className={styles.statList}>
                    {Object.entries(overview.stars.costs || {}).map(([k, v]) => (
                      <div className={styles.statRow} key={k}>
                        <span>{k}</span>
                        <span>{fmt(v)}</span>
                      </div>
                    ))}
                  </div>
                </article>
              </section>
            ) : null}

            {section === 'ai' ? (
              <section className={styles.grid}>
                <article className={styles.card}>
                  <h2>
                    AI operations <PeriodTag label="audience + range" />
                  </h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Magic completed (lifetime)</span>
                      <span>{fmt(overview.ai_usage.magic_completed)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Magic in range</span>
                      <span>{fmt(overview.ai_usage.magic_in_range)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Fitting Room in range</span>
                      <span>{fmt(overview.ai_usage.fitting_room_in_range)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Try-On in range</span>
                      <span>{fmt(overview.ai_usage.try_on_completed)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Croquis in range</span>
                      <span>{fmt(overview.ai_usage.croquis_completed_in_range)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Techpack PDF in range</span>
                      <span>{fmt(overview.ai_usage.techpack_completed_in_range)}</span>
                    </div>
                  </div>
                  <p className={styles.note}>{overview.ai_usage.note}</p>
                  <p className={styles.note}>{overview.ai_usage.completion_timestamp_note}</p>
                </article>
                <article className={styles.card}>
                  <h2>
                    Operations queue <PeriodTag label="Global / All Accounts" />
                  </h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Jobs (24h)</span>
                      <span>{fmt(overview.ai_usage.jobs_last_24h)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Pending</span>
                      <span>{fmt(overview.ai_usage.jobs_pending)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Failed (lifetime)</span>
                      <span>{fmt(overview.ai_usage.jobs_failed)}</span>
                    </div>
                  </div>
                  <p className={styles.note}>
                    Provider cash costs: unavailable until authoritative billing import (Phase D).
                    Unlimited wallets remain in AI usage even when they consume no Stars.
                  </p>
                </article>
              </section>
            ) : null}
          </>
        ) : null}

        {!loading && !error && section === 'customers' ? (
          <>
            <div className={styles.toolbar}>
              <input
                className={styles.search}
                placeholder="Search username or email"
                value={customerQDraft}
                onChange={(e) => setCustomerQDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setCustomerOffset(0)
                    setCustomerQ(customerQDraft.trim())
                  }
                }}
                aria-label="Search customers"
              />
              <select
                className={styles.select}
                value={customerClassFilter}
                onChange={(e) => {
                  setCustomerOffset(0)
                  setCustomerClassFilter(e.target.value)
                }}
                aria-label="Classification filter"
              >
                <option value="">All classifications</option>
                {CLASS_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                className={styles.select}
                value={customerSort}
                onChange={(e) => {
                  setCustomerOffset(0)
                  setCustomerSort(e.target.value)
                }}
                aria-label="Sort customers"
              >
                <option value="created_at_desc">Newest</option>
                <option value="username_asc">Username</option>
                <option value="stars_desc">Stars</option>
              </select>
              <button
                type="button"
                className={styles.refresh}
                onClick={() => {
                  setCustomerOffset(0)
                  setCustomerQ(customerQDraft.trim())
                }}
              >
                Search
              </button>
              <button type="button" className={styles.secondaryBtn} onClick={clearCustomerFilters}>
                Clear
              </button>
              <button type="button" className={styles.secondaryBtn} onClick={() => void runDryRun()}>
                Dry-run
              </button>
            </div>
            {dryRunNote ? <div className={styles.banner}>{dryRunNote}</div> : null}
            <p className={styles.kpiHint}>
              {fmt(customerTotal)} accounts · page {page} of {pageCount}
            </p>
            <div className={styles.customerList}>
              {customers.map((c) => (
                <div key={c.id} className={styles.customerCard}>
                  <button
                    type="button"
                    className={styles.customerCardMain}
                    onClick={() => void openCustomer(c.id)}
                  >
                    <div className={styles.customerMain}>
                      <strong>@{c.username}</strong>
                      <span className={styles.emailClip}>{c.email}</span>
                    </div>
                    <div className={styles.customerMeta}>
                      <span className={styles.classBadge}>{c.classification}</span>
                      <span>{c.ai_stars_unlimited ? '∞' : fmt(c.ai_stars)} Stars</span>
                      <span>{c.is_active ? 'Enabled' : 'Disabled'}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    className={styles.grantBtn}
                    disabled={c.ai_stars_unlimited}
                    title={
                      c.ai_stars_unlimited
                        ? 'Unlimited wallets cannot receive manual grants'
                        : `Grant Stars to @${c.username}`
                    }
                    onClick={() => void openGrantFor(c.id)}
                  >
                    + Grant Stars
                  </button>
                </div>
              ))}
              {customers.length === 0 ? (
                <div className={styles.empty}>No accounts match this search or filter.</div>
              ) : null}
            </div>
            <div className={styles.pager}>
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={customerOffset <= 0}
                onClick={() => setCustomerOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </button>
              <span className={styles.kpiHint}>
                {customerOffset + 1}–{Math.min(customerOffset + PAGE_SIZE, customerTotal)} of{' '}
                {fmt(customerTotal)}
              </span>
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={customerOffset + PAGE_SIZE >= customerTotal}
                onClick={() => setCustomerOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </>
        ) : null}

        {!loading && !error && section === 'grants' && grantsOverview ? (
          <>
            <section className={styles.kpiRow} aria-label="Stars grants KPIs">
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>
                  Stars granted{' '}
                  <span className={`${styles.kind} ${styles.kindExact}`}>exact</span>
                </div>
                <div className={styles.kpiValue}>{fmt(grantsOverview.total_stars_granted)}</div>
                <div className={styles.kpiHint}>Not purchase revenue · audience + range</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Grants</div>
                <div className={styles.kpiValue}>{fmt(grantsOverview.grant_count)}</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Recipients</div>
                <div className={styles.kpiValue}>{fmt(grantsOverview.recipient_count)}</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Max / txn</div>
                <div className={styles.kpiValue}>{fmt(grantsOverview.max_per_transaction)}</div>
                <div className={styles.kpiHint}>
                  Ceiling {fmt(grantsOverview.absolute_ceiling)} · confirm ≥{' '}
                  {fmt(grantsOverview.large_confirm_threshold)}
                </div>
              </div>
            </section>
            <p className={styles.note}>{grantsOverview.note}</p>
            <section className={styles.grid}>
              <article className={styles.card}>
                <h2>By reason</h2>
                {Object.keys(grantsOverview.by_reason).length === 0 ? (
                  <p className={styles.kpiHint}>No grants in this range.</p>
                ) : (
                  <ul className={styles.plainList}>
                    {Object.entries(grantsOverview.by_reason).map(([reason, row]) => (
                      <li key={reason}>
                        {reason} · {fmt(row.count)} grants · {fmt(row.stars)} Stars
                      </li>
                    ))}
                  </ul>
                )}
              </article>
              <article className={styles.card}>
                <h2>By administrator</h2>
                {grantsOverview.by_administrator.length === 0 ? (
                  <p className={styles.kpiHint}>No administrators in this range.</p>
                ) : (
                  <ul className={styles.plainList}>
                    {grantsOverview.by_administrator.map((a) => (
                      <li key={a.actor_id ?? a.username ?? 'anon'}>
                        @{a.username || (a.actor_id ? a.actor_id.slice(0, 8) : 'anonymized')} ·{' '}
                        {fmt(a.count)} · {fmt(a.stars)} Stars
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            </section>
            <section className={styles.card}>
              <h2>Recent grant activity</h2>
              {grantsOverview.recent.length === 0 ? (
                <p className={styles.kpiHint}>No grants yet.</p>
              ) : (
                <div className={styles.tableWrap}>
                  <table>
                    <thead>
                      <tr>
                        <th>When</th>
                        <th>Amount</th>
                        <th>Reason</th>
                        <th>Recipient</th>
                        <th>Balance</th>
                        <th>Ref</th>
                      </tr>
                    </thead>
                    <tbody>
                      {grantsOverview.recent.map((g) => (
                        <tr key={g.grant_id}>
                          <td>
                            {g.created_at
                              ? new Date(g.created_at).toLocaleString('en-IL', {
                                  timeZone: 'Asia/Jerusalem',
                                })
                              : '—'}
                          </td>
                          <td>+{fmt(g.amount)}</td>
                          <td>{g.reason}</td>
                          <td>
                            {g.recipient_id ? (
                              <button
                                type="button"
                                className={styles.linkish}
                                onClick={() => void openCustomer(g.recipient_id!)}
                              >
                                {g.recipient_id.slice(0, 8)}…
                              </button>
                            ) : (
                              <span>anonymized</span>
                            )}
                          </td>
                          <td>
                            {fmt(g.balance_before)} → {fmt(g.balance_after)}
                          </td>
                          <td>{g.grant_id.slice(0, 8)}…</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        ) : null}

        {!loading && !error && (section === 'reports' || section === 'community') ? (
          <>
            <div className={styles.filters}>
              {['open', 'reviewed', 'actioned', 'dismissed', 'all'].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`${styles.filterBtn} ${
                    reportFilter === f ? styles.filterBtnActive : ''
                  }`}
                  onClick={() => setReportFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            {section === 'community' && overview ? (
              <section className={styles.kpiRow} aria-label="Community KPIs">
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>
                    Likes by audience <PeriodTag label="lifetime" />
                  </div>
                  <div className={styles.kpiValue}>
                    {fmt(overview.engagement?.likes_by_audience ?? overview.content.likes)}
                  </div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>Likes on audience content</div>
                  <div className={styles.kpiValue}>
                    {fmt(overview.engagement?.likes_on_audience_content)}
                  </div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>Comments by audience</div>
                  <div className={styles.kpiValue}>
                    {fmt(overview.engagement?.comments_by_audience ?? overview.content.comments)}
                  </div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>
                    Open reports <PeriodTag label="Global" />
                  </div>
                  <div className={styles.kpiValue}>{fmt(overview.moderation.reports_open)}</div>
                </div>
              </section>
            ) : null}
            {reports.length === 0 ? (
              <div className={styles.empty}>No reports in this filter.</div>
            ) : (
              <div className={styles.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Reason</th>
                      <th>Look</th>
                      <th>Reporter</th>
                      <th>Reported</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <span
                            className={`${styles.badge} ${
                              r.status === 'open'
                                ? styles.badgeOpen
                                : r.status === 'dismissed' || r.status === 'actioned'
                                  ? styles.badgeDone
                                  : ''
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td>
                          {r.reason}
                          {r.details ? <div className={styles.kpiHint}>{r.details}</div> : null}
                        </td>
                        <td>{r.gallery_item.title || r.gallery_item.id.slice(0, 8)}</td>
                        <td>@{r.reporter.username || '—'}</td>
                        <td>@{r.reported_user.username || '—'}</td>
                        <td>
                          {r.created_at
                            ? new Date(r.created_at).toLocaleString('en-IL', {
                                timeZone: 'Asia/Jerusalem',
                              })
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}

        {!loading && !error && section === 'dictionary' ? (
          <section className={styles.card}>
            <h2>Metric dictionary</h2>
            <div className={styles.dictList}>
              {dictionary.map((m) => (
                <article key={m.id} className={styles.dictItem}>
                  <header>
                    <strong>{m.name}</strong>
                    <span className={`${styles.kind} ${kindBadge(m.kind)}`}>{m.kind}</span>
                  </header>
                  <code className={styles.metricId}>{m.id}</code>
                  <p>{m.definition}</p>
                  {m.source ? <p className={styles.kpiHint}>Source: {m.source}</p> : null}
                  {m.coverage_note ? <p className={styles.kpiHint}>{m.coverage_note}</p> : null}
                  {m.limitations ? <p className={styles.note}>{m.limitations}</p> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </main>

      {selectedCustomer ? (
        <div className={styles.drawerScrim} role="presentation" onClick={() => setSelectedCustomer(null)}>
          <aside
            className={styles.drawer}
            role="dialog"
            aria-label="Customer detail"
            onClick={(e) => e.stopPropagation()}
          >
            <header className={styles.drawerHead}>
              <div>
                <h2>@{selectedCustomer.username}</h2>
                <p className={styles.emailClip}>{selectedCustomer.email}</p>
              </div>
              <button type="button" className={styles.refresh} onClick={() => setSelectedCustomer(null)}>
                Close
              </button>
            </header>
            <div className={styles.drawerBody}>
              <button
                type="button"
                className={styles.grantBtnWide}
                disabled={selectedCustomer.wallet.ai_stars_unlimited}
                onClick={() => setGrantTarget(selectedCustomer)}
              >
                + Grant Stars
              </button>
              <div className={styles.classConfirmBox}>
                <p className={styles.kpiHint}>
                  Current: <strong>{selectedCustomer.classification}</strong>
                  {classDraft !== selectedCustomer.classification
                    ? ` → Proposed: ${classDraft}`
                    : ''}
                </p>
                <label className={styles.field}>
                  Proposed classification
                  <select
                    value={classDraft}
                    onChange={(e) => {
                      setClassDraft(e.target.value)
                      setClassConfirm(false)
                    }}
                  >
                    {CLASS_OPTIONS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.field}>
                  Reason (required)
                  <input
                    value={classReason}
                    onChange={(e) => setClassReason(e.target.value)}
                    placeholder="Why this classification?"
                    maxLength={500}
                  />
                </label>
                <label className={styles.field}>
                  Internal note (optional)
                  <input
                    value={classNote}
                    onChange={(e) => setClassNote(e.target.value)}
                    placeholder="Optional operator note"
                    maxLength={2000}
                  />
                </label>
                <label className={styles.checkRow}>
                  <input
                    type="checkbox"
                    checked={classConfirm}
                    onChange={(e) => setClassConfirm(e.target.checked)}
                  />
                  I confirm changing {selectedCustomer.classification} → {classDraft}
                </label>
                <button
                  type="button"
                  className={styles.refresh}
                  disabled={
                    classSaving ||
                    !classConfirm ||
                    classDraft === selectedCustomer.classification ||
                    classReason.trim().length < 3
                  }
                  onClick={() => void submitClassification()}
                >
                  {classSaving ? 'Saving…' : 'Submit classification'}
                </button>
                <p className={styles.kpiHint}>
                  Classification never grants admin permissions. Suggestion:{' '}
                  {selectedCustomer.suggestion?.suggested ?? '—'} (
                  {selectedCustomer.suggestion?.confidence ?? 'none'})
                </p>
              </div>
              <div className={styles.statList}>
                <div className={styles.statRow}>
                  <span>Account status</span>
                  <span>{selectedCustomer.is_active ? 'Enabled' : 'Disabled'}</span>
                </div>
                <div className={styles.statRow}>
                  <span>Wallet</span>
                  <span>
                    {selectedCustomer.wallet.ai_stars_unlimited
                      ? '∞'
                      : fmt(selectedCustomer.wallet.ai_stars)}
                  </span>
                </div>
                <div className={styles.statRow}>
                  <span>Designs</span>
                  <span>{fmt(selectedCustomer.activity.designs_saved)}</span>
                </div>
                <div className={styles.statRow}>
                  <span>Magic completed</span>
                  <span>{fmt(selectedCustomer.activity.magic_completed)}</span>
                </div>
                <div className={styles.statRow}>
                  <span>Fitting Room</span>
                  <span>{fmt(selectedCustomer.activity.fitting_room_completed)}</span>
                </div>
                <div className={styles.statRow}>
                  <span>Lifetime list revenue (est.)</span>
                  <span>{fmtMoney(selectedCustomer.purchases.lifetime_list_price_usd)}</span>
                </div>
              </div>
              <h3 className={styles.subHead}>Purchases (display page)</h3>
              {selectedCustomer.purchases.items.length === 0 ? (
                <p className={styles.kpiHint}>No IAP rows. Balance changes may be grants or starting Stars.</p>
              ) : (
                <ul className={styles.plainList}>
                  {selectedCustomer.purchases.items.map((p, i) => (
                    <li key={`${p.product_id}-${i}`}>
                      {p.product_id} · {p.stars_credited} Stars · {p.environment}
                      {p.sandbox ? ' (sandbox)' : ''} · {fmtMoney(p.list_price_usd)}
                    </li>
                  ))}
                </ul>
              )}
              <h3 className={styles.subHead}>Admin Stars grants</h3>
              {(selectedCustomer.admin_stars_grants?.items || []).length === 0 ? (
                <p className={styles.kpiHint}>No administrative grants for this account.</p>
              ) : (
                <ul className={styles.plainList}>
                  {(selectedCustomer.admin_stars_grants?.items || []).map((g) => (
                    <li key={g.grant_id}>
                      +{fmt(g.amount)} · {g.reason} · {fmt(g.balance_before)}→
                      {fmt(g.balance_after)}
                      {g.created_at
                        ? ` · ${new Date(g.created_at).toLocaleString('en-IL', {
                            timeZone: 'Asia/Jerusalem',
                          })}`
                        : ''}
                    </li>
                  ))}
                </ul>
              )}
              <h3 className={styles.subHead}>Classification history</h3>
              {selectedCustomer.classification_history.length === 0 ? (
                <p className={styles.kpiHint}>No classification events yet.</p>
              ) : (
                <ul className={styles.plainList}>
                  {selectedCustomer.classification_history.map((h) => (
                    <li key={h.id}>
                      {h.from} → {h.to}
                      {h.actor_username ? ` by @${h.actor_username}` : ''}
                      {h.reason ? ` · ${h.reason}` : ''}
                      {h.created_at
                        ? ` · ${new Date(h.created_at).toLocaleString('en-IL', {
                            timeZone: 'Asia/Jerusalem',
                          })}`
                        : ''}
                    </li>
                  ))}
                </ul>
              )}
              {(selectedCustomer.unavailable || []).length > 0 ? (
                <p className={styles.note}>
                  Unavailable for this account: {selectedCustomer.unavailable?.join(', ')}
                </p>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}

      {grantTarget && user ? (
        <GrantStarsModal
          customer={grantTarget}
          adminId={user.id}
          onClose={() => setGrantTarget(null)}
          onGranted={(grant) => {
            setSelectedCustomer((prev) =>
              prev && prev.id === grant.recipient_id
                ? {
                    ...prev,
                    wallet: {
                      ...prev.wallet,
                      ai_stars: grant.balance_after,
                    },
                    admin_stars_grants: {
                      kind: 'exact',
                      counts_toward_revenue: false,
                      editable: false,
                      deletable: false,
                      items: [grant, ...(prev.admin_stars_grants?.items || [])],
                    },
                  }
                : prev,
            )
            setGrantTarget(null)
            void load()
          }}
        />
      ) : null}
    </div>
  )
}

export function AdminPage() {
  return (
    <ProtectedRoute>
      <AdminShell />
    </ProtectedRoute>
  )
}
