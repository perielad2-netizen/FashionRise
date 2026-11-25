import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { useAuth } from '@/services/auth/AuthProvider'
import {
  fetchAdminCustomer,
  fetchAdminCustomers,
  fetchAdminOverview,
  fetchAdminReports,
  fetchClassificationDryRun,
  fetchMetricDictionary,
  patchAdminClassification,
  type AccountClassification,
  type AdminCustomer,
  type AdminCustomerDetail,
  type AdminOverview,
  type AdminRangeKey,
  type AdminReport,
  type MetricDefinition,
} from '@/services/adminApi'
import { isNativeShell } from '@/services/native/platform'
import styles from './AdminPage.module.css'

const ADMIN_USERNAMES = new Set(['shilatperi', 'perishilat', 'yanivprbk'])

type Section =
  | 'overview'
  | 'customers'
  | 'revenue'
  | 'ai'
  | 'community'
  | 'dictionary'
  | 'reports'

const SECTIONS: Array<{ id: Section; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'customers', label: 'Customers' },
  { id: 'revenue', label: 'Revenue & Stars' },
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
  { id: 'all', label: 'All accounts' },
  { id: 'customers', label: 'Confirmed customers' },
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

function AdminShell() {
  const { user } = useAuth()
  const [section, setSection] = useState<Section>('overview')
  const [range, setRange] = useState<AdminRangeKey>('last_30d')
  const [audience, setAudience] = useState('all')
  const [menuOpen, setMenuOpen] = useState(false)
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [reports, setReports] = useState<AdminReport[]>([])
  const [reportFilter, setReportFilter] = useState('open')
  const [customers, setCustomers] = useState<AdminCustomer[]>([])
  const [customerTotal, setCustomerTotal] = useState(0)
  const [customerQ, setCustomerQ] = useState('')
  const [selectedCustomer, setSelectedCustomer] = useState<AdminCustomerDetail | null>(null)
  const [dictionary, setDictionary] = useState<MetricDefinition[]>([])
  const [dryRunNote, setDryRunNote] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const allowed = Boolean(user && isAdminUser(user.username, user.is_admin))
  const native = isNativeShell()

  const load = useCallback(async () => {
    if (native || !allowed) return
    setLoading(true)
    setError(null)
    try {
      if (section === 'overview' || section === 'revenue' || section === 'ai') {
        setOverview(await fetchAdminOverview({ range, audience }))
      } else if (section === 'reports' || section === 'community') {
        const [ov, res] = await Promise.all([
          fetchAdminOverview({ range, audience }),
          fetchAdminReports(reportFilter === 'all' ? undefined : reportFilter),
        ])
        setOverview(ov)
        setReports(res.items)
      } else if (section === 'customers') {
        const [ov, res] = await Promise.all([
          fetchAdminOverview({ range, audience }),
          fetchAdminCustomers({ q: customerQ || undefined, audience, limit: 50 }),
        ])
        setOverview(ov)
        setCustomers(res.items)
        setCustomerTotal(res.total)
      } else if (section === 'dictionary') {
        const res = await fetchMetricDictionary()
        setDictionary(res.items)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load admin data'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [section, reportFilter, allowed, native, range, audience, customerQ])

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

  async function openCustomer(id: string) {
    try {
      setSelectedCustomer(await fetchAdminCustomer(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customer')
    }
  }

  async function saveClassification(next: string) {
    if (!selectedCustomer) return
    try {
      const updated = await patchAdminClassification(selectedCustomer.id, {
        classification: next,
        reason: 'admin_console',
      })
      setSelectedCustomer(updated)
      void load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Classification update failed')
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

  return (
    <div className={styles.page}>
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
                Business intelligence · Asia/Jerusalem · Updated {generated ?? '—'}
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
            Business view is filtered to confirmed customers. {fmt(unclassified)} unclassified
            accounts remain — switch Audience to review them.
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
                    <div className={styles.kpiLabel}>Accounts</div>
                    <div className={styles.kpiValue}>{fmt(overview.users.total)}</div>
                    <div className={styles.kpiHint}>
                      +{fmt(overview.users.new_7d)} / 7d · customers{' '}
                      {fmt(overview.users.confirmed_customers)} · unclassified{' '}
                      {fmt(overview.users.unclassified)}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>
                      Production revenue{' '}
                      <span className={`${styles.kind} ${kindBadge(overview.revenue.kind || 'estimated')}`}>
                        est.
                      </span>
                    </div>
                    <div className={styles.kpiValue}>
                      {fmtMoney(overview.revenue.gross_list_price_usd)}
                    </div>
                    <div className={styles.kpiHint}>
                      List price · {fmt(overview.revenue.purchases_counted)} packs
                      {overview.revenue.sandbox_purchases_excluded
                        ? ` · ${fmt(overview.revenue.sandbox_purchases_excluded)} sandbox excluded`
                        : ''}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>Magic completed</div>
                    <div className={styles.kpiValue}>{fmt(overview.ai_usage.magic_completed)}</div>
                    <div className={styles.kpiHint}>
                      status=completed · in range {fmt(overview.ai_usage.magic_in_range)}
                    </div>
                  </div>
                  <div className={styles.kpi}>
                    <div className={styles.kpiLabel}>Fitting Room</div>
                    <div className={styles.kpiValue}>
                      {fmt(overview.ai_usage.fitting_room_completed)}
                    </div>
                    <div className={styles.kpiHint}>
                      7d {fmt(overview.ai_usage.fitting_room_7d)} · open reports{' '}
                      {fmt(overview.moderation.reports_open)}
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
                            <div className={styles.kpiHint}>{a.detail}</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                <section className={styles.grid}>
                  <article className={styles.card}>
                    <h2>Creation & publishing</h2>
                    <div className={styles.statList}>
                      <div className={styles.statRow}>
                        <span>Designs saved</span>
                        <span>{fmt(overview.content.designs_saved)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Designs published</span>
                        <span>{fmt(overview.content.designs_published)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Looks published</span>
                        <span>{fmt(overview.content.looks_published)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Models created</span>
                        <span>{fmt(overview.content.models_created)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>AI fabrics</span>
                        <span>{fmt(overview.content.ai_fabrics_created)}</span>
                      </div>
                      <div className={styles.statRow}>
                        <span>Try-On completed</span>
                        <span>{fmt(overview.ai_usage.try_on_completed)}</span>
                      </div>
                    </div>
                  </article>
                  <article className={styles.card}>
                    <h2>Unavailable / not yet instrumented</h2>
                    <ul className={styles.plainList}>
                      {(overview.unavailable || []).map((u) => (
                        <li key={u}>{u}</li>
                      ))}
                    </ul>
                    <p className={styles.note}>
                      These are shown as unavailable — never substituted with invented zeros.
                    </p>
                  </article>
                </section>
              </>
            ) : null}

            {section === 'revenue' ? (
              <section className={styles.grid}>
                <article className={styles.card}>
                  <h2>Revenue (production)</h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Gross list-price USD</span>
                      <span>{fmtMoney(overview.revenue.gross_list_price_usd)}</span>
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
                      <span>Starting grants issued</span>
                      <span>{fmt(overview.stars.free_grants_issued)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Stars spent (est.)</span>
                      <span>{fmt(overview.stars.stars_spent_total_est)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Finite wallets sum</span>
                      <span>{fmt(overview.stars.wallet_balance_sum)}</span>
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
                  <h3 className={styles.subHead}>Spend by feature (est.)</h3>
                  <div className={styles.statList}>
                    {Object.entries(overview.stars.spent_by_feature_est).map(([k, v]) => (
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
                  <h2>AI operations</h2>
                  <div className={styles.statList}>
                    <div className={styles.statRow}>
                      <span>Magic completed</span>
                      <span>{fmt(overview.ai_usage.magic_completed)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Fitting Room completed</span>
                      <span>{fmt(overview.ai_usage.fitting_room_completed)}</span>
                    </div>
                    <div className={styles.statRow}>
                      <span>Try-On completed</span>
                      <span>{fmt(overview.ai_usage.try_on_completed)}</span>
                    </div>
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
                  <p className={styles.note}>{overview.ai_usage.note}</p>
                </article>
                <article className={styles.card}>
                  <h2>Cost catalog (Stars)</h2>
                  <div className={styles.statList}>
                    {Object.entries(overview.stars.costs).map(([k, v]) => (
                      <div className={styles.statRow} key={k}>
                        <span>{k}</span>
                        <span>{fmt(v)}</span>
                      </div>
                    ))}
                  </div>
                  <p className={styles.note}>
                    Provider cash costs: unavailable until authoritative billing import (Phase D).
                    Unlimited wallets may incur provider cost without Stars debit.
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
                value={customerQ}
                onChange={(e) => setCustomerQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void load()
                }}
              />
              <button type="button" className={styles.refresh} onClick={() => void load()}>
                Search
              </button>
              <button type="button" className={styles.secondaryBtn} onClick={() => void runDryRun()}>
                Classification dry-run
              </button>
            </div>
            {dryRunNote ? <div className={styles.banner}>{dryRunNote}</div> : null}
            <p className={styles.kpiHint}>{fmt(customerTotal)} accounts in filter</p>
            <div className={styles.customerList}>
              {customers.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={styles.customerCard}
                  onClick={() => void openCustomer(c.id)}
                >
                  <div className={styles.customerMain}>
                    <strong>@{c.username}</strong>
                    <span className={styles.emailClip}>{c.email}</span>
                  </div>
                  <div className={styles.customerMeta}>
                    <span className={styles.classBadge}>{c.classification}</span>
                    <span>{c.ai_stars_unlimited ? '∞' : fmt(c.ai_stars)} Stars</span>
                  </div>
                </button>
              ))}
              {customers.length === 0 ? <div className={styles.empty}>No accounts match.</div> : null}
            </div>
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
                  <div className={styles.kpiLabel}>Likes</div>
                  <div className={styles.kpiValue}>{fmt(overview.content.likes)}</div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>Comments</div>
                  <div className={styles.kpiValue}>{fmt(overview.content.comments)}</div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>Follows</div>
                  <div className={styles.kpiValue}>{fmt(overview.content.follows)}</div>
                </div>
                <div className={styles.kpi}>
                  <div className={styles.kpiLabel}>Open reports</div>
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
              <label className={styles.field}>
                Classification
                <select
                  value={selectedCustomer.classification}
                  onChange={(e) => void saveClassification(e.target.value)}
                >
                  {CLASS_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <p className={styles.kpiHint}>
                Changing classification never grants admin permissions. Suggestion:{' '}
                {selectedCustomer.suggestion?.suggested ?? '—'} (
                {selectedCustomer.suggestion?.confidence ?? 'none'})
              </p>
              <div className={styles.statList}>
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
              <h3 className={styles.subHead}>Purchases</h3>
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
              {(selectedCustomer.unavailable || []).length > 0 ? (
                <p className={styles.note}>
                  Unavailable for this account: {selectedCustomer.unavailable?.join(', ')}
                </p>
              ) : null}
            </div>
          </aside>
        </div>
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
