# Google Play financial reconcile — operator readiness

**Persistent apply is ON** (PM-authorized 2026-11-28). Purchasing/credit stay OFF.
This document remains the activation and safety runbook for unattended recovery.

## Feature gates (production)

| Env | Live state (2026-11-28) |
| --- | --- |
| `IAP_GOOGLE_FINANCIAL_RECONCILE_ENABLED` | `true` |
| `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY` | **`true`** |
| `IAP_GOOGLE_PURCHASING_ENABLED` | **`false`** |
| `IAP_GOOGLE_CREDIT_ENABLED` | **`false`** |
| `IAP_GOOGLE_FINANCIAL_RECONCILE_LIMIT` | `50` (bounded batch) |
| `IAP_GOOGLE_FINANCIAL_RECONCILE_INTERVAL_SECONDS` | **`300`** (5 minutes) |

Emergency disable: set `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=false`
and/or `IAP_GOOGLE_FINANCIAL_RECONCILE_ENABLED=false`, then restart API + AI workers.

## Architecture

| Piece | Role |
| --- | --- |
| `google_play_reconcile.reconcile_android_purchases` | Classification + optional apply |
| `google_play_reconcile_worker.run_google_play_reconcile_tick` | Hourly tick: interval, backoff, **cluster advisory lock**, fair cursor |
| `google_rtdn._clawback_purchase` / `ai_stars.apply_iap_clawback` | Wallet mutation + debt |
| `GooglePlayReconcileRun` / `Finding` | Audit + Admin snapshot (no live Play on page load) |
| Admin `GET /api/v1/admin/iap/google/reconcile` | Read-only dry-run |

Scoped one-shot apply (validated on GPA.3329):  
`scripts/run_google_play_reconcile_once.py --order-id … --authorize-apply-stars N --apply`  
uses process-local order scope; never flip the persistent apply gate for that exercise.

## Monitoring (Admin snapshot)

`admin_reconciliation_snapshot` exposes:

- Last successful / last failed run (error **code** + truncated detail — **no tokens**)
- Consecutive failure streak (from run meta)
- Scheduler interval + batch limit
- Backlog: outstanding Stars, `recover_full` / `review` findings, wallet debt totals
- Skipped lock / backoff run counts
- Sandbox vs production finding buckets

**Alert when (recommended):** fail_streak ≥ 2; no successful tick for > 2× interval;
`findings_review` grows; `wallet_debt_stars` grows unexpectedly; `skipped_lock_runs`
spike; provider `GOOGLE_API_*` errors.

## Refund classification policy

Implemented in `classify_recovery` — do **not** auto-deduct ambiguous states.

| Provider evidence | Decision | Action when apply ON |
| --- | --- | --- |
| Full refund (`REFUNDED` + authoritative refund total) **and** entitlement canceled/404 | `recover_full` | Claw outstanding Stars |
| Full refund, entitlement still purchased | `review` | No deduct |
| Partial refund / partial events | `review` | No deduct |
| `PENDING_REFUND` / entitlement pending | `wait` | Retry later |
| Refund event without `REFUNDED` state | `review` | No deduct |
| `REFUNDED` missing refund total | `review` | No deduct |
| Order canceled before process (no full refund) | `review` | No deduct |
| Already clawed / no outstanding | `already_recovered` | No-op |
| Identity mismatch | `skip_identity` | No deduct |
| Missing order / token / API error | `skip_*` | No deduct; backoff on API failures |
| Chargeback / void | Via RTDN void path when present; reconcile requires same full-refund+revoke bar | Never blind deduct |

Sandbox vs production: findings and Admin buckets are separated; Sandbox refunds
often lack cancel RTDN — reconcile is the fallback (proven on GPA.3393 / GPA.3329).

Duplicate RTDN + reconcile: durable `orders-reconcile:{token}` message ids +
purchase-token locks + clawback idempotency (`stars_clawed_back`).

## Wallet debt runbook

Policy (unchanged — document only):

- `ai_stars` never goes negative.
- Clawback takes `min(balance, need)` from balance; remainder → `ai_stars_iap_debt`.
- Future credits (`credit_stars`) settle debt **before** increasing spendable balance.
- Multiple refunds accumulate debt independently under purchase-token serialization.
- Concurrent reconcile/RTDN: advisory xact lock per purchase token + `FOR UPDATE`.

### Scenarios

| Scenario | Expected |
| --- | --- |
| User still holds all purchased Stars | Full claw from balance; debt += 0 |
| Spent some | Partial balance + debt for remainder |
| Spent all | Balance 0; debt += full outstanding |
| Existing debt + new refund | Debt increases further |
| Future purchase/credit while debt > 0 | Credit settles debt first |
| Duplicate reconcile on recovered order | `already_recovered` / nothing_to_claw |
| Concurrent ticks | One cluster lock holder; others skip |

**Customer-facing debt messaging:** do not change without PM review. Operators see
debt on Admin customer rows (`ai_stars_iap_debt`).

## Historical backlog (2026-11-28 Asia/Jerusalem — read-only)

Android `iap_purchases` inventory (no additional mutations during assessment):

| Metric | Value |
| --- | --- |
| Notable recoverable | **`GPA.3363-8286-3414-93081`** Sandbox `stars_50` · `REFUNDED` + entitlement canceled · dry-run **`recover_full` would 50** · wallet still **999397** · RTDN **absent** (Sandbox) · blocked solely by apply gate OFF |
| Prior recovered | GPA.3393 + GPA.3329 clawed exactly once each |
| Other outstanding | Active non-refund rows may still show Stars (e.g. prior `GPA.3387…`) — **not** recoverable without refund+revoke |
| Wallet debt users / Stars | 0 / 0 |
| Production purchases | 0 |

Do **not** apply against active non-refunded orders. GPA.3363 is ready for the **first scheduled apply tick** after PM enablement — no manual wallet edit.

## Scheduler safety

- Same service as scoped apply validation.
- Cluster `pg_try_advisory_lock` on dedicated connection (survives internal commits).
- Batch limit capped (default 50, max 200).
- Fair cursor wraps so outstanding rows are not stranded outside lookback.
- Google API failures → `failed` run + exponential backoff (15m … 6h).
- Partial provider errors → run status `partial`.
- Disable immediately via gates above.
- Audit: every tick records `GooglePlayReconcileRun`; applies write notifications + clawback adjustments.

## Activation plan (PM approval required — NOT executed)

### Preconditions

1. Monitoring alerts wired (fail streak, stale success, review backlog, debt).
2. This classification + debt runbook reviewed by PM.
3. Backlog re-checked same day (expect recoverable ≈ 0 unless new refunds).
4. Purchasing/credit remain OFF unless separately authorized.
5. Dual-sign / recorded PM approval for `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true`.

### Exact config change

```bash
# On VPS env only — after approval
IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true
# Keep:
IAP_GOOGLE_FINANCIAL_RECONCILE_ENABLED=true
IAP_GOOGLE_PURCHASING_ENABLED=false
IAP_GOOGLE_CREDIT_ENABLED=false
# restart fashionrise-api + ai-worker@{1..3}
```

### Expected first hour

- Dry-run ticks become apply ticks for `recover_full` only.
- Maximum expected outstanding recovery: **re-read backlog same day** (was 0 recoverable refund Stars on 2026-11-27 after GPA.3329).
- `GPA.3387` active 50 Stars must **not** claw without refund+revoke evidence.

### Verification after first scheduled apply tick

1. Latest `GooglePlayReconcileRun`: `dry_run=false`, status success/partial.
2. No unexpected wallet moves; compare Admin snapshot backlog.
3. `findings_review` unchanged or reviewed.
4. Gates for purchasing/credit still false.

### Rollback

Set `IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=false`, restart workers, confirm next tick `dry_run=true`.
