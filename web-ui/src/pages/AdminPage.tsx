import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { useAuth } from '@/services/auth/AuthProvider'
import {
  fetchAdminOverview,
  fetchAdminReports,
  type AdminOverview,
  type AdminReport,
} from '@/services/adminApi'
import { isNativeShell } from '@/services/native/platform'
import styles from './AdminPage.module.css'

const ADMIN_USERNAMES = new Set(['shilatperi', 'perishilat', 'yanivprbk'])

type Tab = 'overview' | 'reports'

function isAdminUser(username: string | undefined, isAdminFlag: boolean | undefined): boolean {
  if (isAdminFlag) return true
  return ADMIN_USERNAMES.has((username || '').trim().toLowerCase())
}

function fmt(n: number | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US').format(n)
}

function fmtMoney(n: number | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(n)
}

function AdminShell() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('overview')
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [reports, setReports] = useState<AdminReport[]>([])
  const [reportFilter, setReportFilter] = useState<string>('open')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const allowed = Boolean(user && isAdminUser(user.username, user.is_admin))
  const native = isNativeShell()

  const load = useCallback(async () => {
    if (native || !allowed) return
    setLoading(true)
    setError(null)
    try {
      if (tab === 'overview') {
        setOverview(await fetchAdminOverview())
      } else {
        const status = reportFilter === 'all' ? undefined : reportFilter
        const res = await fetchAdminReports(status)
        setReports(res.items)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load admin data'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [tab, reportFilter, allowed, native])

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

  // Web-only console — native shells stay on the product app.
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

  return (
    <div className={styles.page}>
      <aside className={styles.side}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>FashionRise</span>
          <span className={styles.brandTitle}>Admin</span>
        </div>
        <nav className={styles.nav} aria-label="Admin">
          <button
            type="button"
            className={`${styles.navBtn} ${tab === 'overview' ? styles.navBtnActive : ''}`}
            onClick={() => setTab('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            className={`${styles.navBtn} ${tab === 'reports' ? styles.navBtnActive : ''}`}
            onClick={() => setTab('reports')}
          >
            Reports
            {overview && overview.moderation.reports_open > 0
              ? ` (${overview.moderation.reports_open})`
              : ''}
          </button>
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
          <div>
            <h1>{tab === 'overview' ? 'Overview' : 'Content reports'}</h1>
            <p>
              {tab === 'overview'
                ? `Live product metrics · Updated ${generated ?? '—'}`
                : 'Social look / designer reports across FashionRise'}
            </p>
          </div>
          <button type="button" className={styles.refresh} onClick={() => void load()}>
            Refresh
          </button>
        </header>

        {error ? <div className={styles.error}>{error}</div> : null}
        {loading && !error ? <div className={styles.loading}>Loading…</div> : null}

        {!loading && !error && tab === 'overview' && overview ? (
          <>
            <section className={styles.kpiRow} aria-label="Key metrics">
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Users</div>
                <div className={styles.kpiValue}>{fmt(overview.users.total)}</div>
                <div className={styles.kpiHint}>+{fmt(overview.users.new_7d)} last 7 days</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Money earned</div>
                <div className={styles.kpiValue}>
                  {fmtMoney(overview.revenue.gross_list_price_usd)}
                </div>
                <div className={styles.kpiHint}>
                  List price · {fmt(overview.revenue.purchases_counted)} production packs
                  {overview.revenue.sandbox_purchases_excluded
                    ? ` · ${fmt(overview.revenue.sandbox_purchases_excluded)} sandbox ignored`
                    : ''}
                </div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Stars bought</div>
                <div className={styles.kpiValue}>{fmt(overview.stars.stars_purchased_net)}</div>
                <div className={styles.kpiHint}>Net of refunds / clawbacks</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Free Stars used</div>
                <div className={styles.kpiValue}>
                  {fmt(overview.stars.free_stars_consumed_est)}
                </div>
                <div className={styles.kpiHint}>
                  of {fmt(overview.stars.free_grants_issued)} starting grants
                </div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpiLabel}>Open reports</div>
                <div className={styles.kpiValue}>{fmt(overview.moderation.reports_open)}</div>
                <div className={styles.kpiHint}>
                  {fmt(overview.moderation.reports_total)} total
                </div>
              </div>
            </section>

            <section className={styles.grid}>
              <article className={styles.card}>
                <h2>Creation & publishing</h2>
                <div className={styles.statList}>
                  <div className={styles.statRow}>
                    <span>Designs published</span>
                    <span>{fmt(overview.content.designs_published)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Designs saved (studio)</span>
                    <span>{fmt(overview.content.designs_saved)}</span>
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
                    <span>AI fabrics created</span>
                    <span>{fmt(overview.content.ai_fabrics_created)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Fitting Room completed</span>
                    <span>{fmt(overview.ai_usage.fitting_room_completed)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Magic completed</span>
                    <span>{fmt(overview.ai_usage.magic_completed)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Try-on completed</span>
                    <span>{fmt(overview.ai_usage.try_on_completed)}</span>
                  </div>
                </div>
              </article>

              <article className={styles.card}>
                <h2>Stars & engagement</h2>
                <div className={styles.statList}>
                  <div className={styles.statRow}>
                    <span>Stars spent (est.)</span>
                    <span>{fmt(overview.stars.stars_spent_total_est)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Paid Stars consumed (est.)</span>
                    <span>{fmt(overview.stars.paid_stars_consumed_est)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Wallets held (finite)</span>
                    <span>{fmt(overview.stars.wallet_balance_sum)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Likes</span>
                    <span>{fmt(overview.content.likes)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Comments</span>
                    <span>{fmt(overview.content.comments)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Follows</span>
                    <span>{fmt(overview.content.follows)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>AI jobs (24h)</span>
                    <span>{fmt(overview.ai_usage.jobs_last_24h)}</span>
                  </div>
                  <div className={styles.statRow}>
                    <span>Fitting Room (7d)</span>
                    <span>{fmt(overview.ai_usage.fitting_room_7d)}</span>
                  </div>
                </div>
                <p className={styles.note}>{overview.revenue.note}</p>
              </article>
            </section>

            <section className={styles.grid}>
              <article className={styles.card}>
                <h2>Recent signups</h2>
                {overview.recent_signups.length === 0 ? (
                  <div className={styles.empty}>No users yet.</div>
                ) : (
                  <div className={styles.tableWrap}>
                    <table>
                      <thead>
                        <tr>
                          <th>User</th>
                          <th>Joined</th>
                          <th>Stars</th>
                        </tr>
                      </thead>
                      <tbody>
                        {overview.recent_signups.map((u) => (
                          <tr key={u.id}>
                            <td>
                              @{u.username}
                              <div className={styles.kpiHint}>{u.email}</div>
                            </td>
                            <td>
                              {u.created_at
                                ? new Date(u.created_at).toLocaleString('en-IL', {
                                    timeZone: 'Asia/Jerusalem',
                                  })
                                : '—'}
                            </td>
                            <td>{fmt(u.ai_stars)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </article>

              <article className={styles.card}>
                <h2>Spend by feature (est.)</h2>
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
          </>
        ) : null}

        {!loading && !error && tab === 'reports' ? (
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
                          {r.details ? (
                            <div className={styles.kpiHint}>{r.details}</div>
                          ) : null}
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
      </main>
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
