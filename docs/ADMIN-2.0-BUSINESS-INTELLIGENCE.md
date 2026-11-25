# FashionRise Admin 2.0 — Business Intelligence & Operations Control Center

**Status:** Draft foundation (Phase A + Phase B) — **PM corrections applied; not approved for merge/deploy**  
**Baseline main:** `f3967dbf`  
**Inspected SHA (pre-correction):** `27fa5361`  
**Audience:** Technical PM / owner  
**Timezone for reporting:** Asia/Jerusalem calendar days (stored events remain UTC)

---

## 1. Existing admin architecture (pre–Admin 2.0)

| Layer | Location | Notes |
| --- | --- | --- |
| Auth gate | `backend/app/auth/admin.py` | Username allowlist + `User.is_admin`; inactive rejected |
| Routes | `backend/app/api/v1/routes/admin.py` | Overview, customers, classification, reports, dictionary |
| Aggregates | `backend/app/services/admin_analytics.py` | Audience-scoped SQL joins; honest unavailable markers |
| UI | `web-ui/src/pages/AdminPage.tsx` | Sidebar + mobile drawer; audience/range; classification confirm |
| Client API | `web-ui/src/services/adminApi.ts` | Typed fetch helpers |

Production tip at foundation start: FE `e0ee7bed`, BE tree historically `f34bd48` (verify at deploy time).

---

## 2. Root causes addressed (PM review on `27fa5361`)

| Observation | Root cause | Correction |
| --- | --- | --- |
| Audience only filtered user counts | Metrics queried global tables | `_apply_audience_fk` SQL subqueries on every customer-attributable metric |
| Date range ignored | Counts used lifetime/`created_at` only | Event metrics use range; snapshots/lifetime/global labeled |
| Sandbox excluded but unknown env included | Only sandbox denylist | Require `environment=Production` (case-insensitive); unknown counted separately |
| Free vs paid Stars inferred | Aggregate grants − spend | Marked **unavailable**; no invented attribution |
| `is_active` shown as engagement | Misnamed KPI | Renamed **Enabled accounts**; DAU/WAU unavailable |
| Customers capped at 50 with no pager | FE hardcoded limit | Pagination + search + sort + classification filter |
| Classification one-click select | No confirm/reason | Proposed → reason → optional note → confirm → submit; 409 on concurrent conflict |
| Username allowlist risk | Mutable username | Reserved names blocked at register; profile cannot rename username; prefer `is_admin` for durable auth |

---

## 3. Audience scope (authoritative)

Modes: `all` · `customers` (default business view) · `internal` · `unclassified` · individual classification enum.

Invalid audience/range → **HTTP 400** (no silent fallback to all accounts).

| Metric family | Scope | Period |
| --- | --- | --- |
| Registered / enabled accounts | Audience | Snapshot |
| New signups in range | Audience | Range (Jerusalem) |
| Designs / models / fabrics | Owner FK | Lifetime + in-range where noted |
| AI Magic / Fitting / Try-On / Croquis | Actor `AIJob.user_id` | Lifetime completed + in-range (`updated_at` completion proxy) |
| Techpack PDF runs | `TechpackAIRun.user_id` | In-range completed |
| Likes/comments/follows by audience | Actor FK | Lifetime |
| Likes/comments on audience content | Content owner FK | Lifetime |
| Production revenue / Stars purchased | Buyer FK + Production env | Range |
| Wallet balance sum | Audience finite wallets | Snapshot |
| Queue depth / open reports | **Global / All Accounts** | Rolling / snapshot — labeled |

Social UI distinguishes **actions by audience** vs **engagement received by audience content**.

---

## 4. Revenue & Stars honesty

- Gross / refunds / net = **estimated catalog list-price USD** for Production verified purchases only.  
- **Gross** includes every credited Production sale (`active` / `refunded` / `revoked` / `refund_reversed` with `stars_credited > 0`) so refunds are subtracted **once** (no double-subtraction).  
- **Refunds** = catalog price of rows currently `refunded` or `revoked`. **Net** = gross − refunds (floored at 0).  
- `blocked` (ASN before credit) is excluded from gross and refunds.  
- Reporting basis: **current lifecycle state grouped by original purchase `created_at`** — not refund cash-flow timing (authoritative historical refund timestamps unavailable).  
- Not labeled as actual money received / store proceeds (those fields = unavailable).  
- Sandbox + unknown environments excluded and counted separately.  
- Customer lifetime revenue sums **all** eligible Production rows (independent of 50-row purchase display).  
- Administrative Stars grants: **unavailable / separate PR #504** — never revenue.  
- Free vs paid consumption: **unavailable** (no historical debit amounts).  
- Starting balance shown = **today’s config**, not historical grants issued.  
- Unlimited wallets remain in AI usage even when Stars = 0.  
- Registration trend: PostgreSQL `timezone('Asia/Jerusalem', created_at)` calendar-day buckets (not UTC days relabeled). All Time chart capped to last 90 Jerusalem days and labeled.

---

## 5. Account classification

Classifications (CHECK-constrained; independent of `is_admin`):

`CUSTOMER` · `OWNER` · `ADMIN` · `INTERNAL_TESTER` · `QA_AUTOMATION` · `DEMO_ACCOUNT` · `UNCLASSIFIED`

Rules:

- Default: **UNCLASSIFIED** (no production backfill in this PR)  
- Heuristics non-authoritative; unlimited Stars ≠ OWNER  
- PATCH requires meaningful reason + optimistic concurrency (`expected_classification` / `expected_updated_at`) → 409 on conflict  
- Classification **never** grants/revokes admin permissions  
- Audit history with actor username  

Migration: Alembic **043** (CHECK constraints included) — **not executed in production**.

---

## 6. Authorization security findings

| Check | Result |
| --- | --- |
| Public/invite registration claims reserved admin username | **Blocked** (case-insensitive Conflict) |
| Google OAuth auto-register claims reserved username | **Blocked** — `_unique_username` skips reserved names |
| Profile username change to allowlist | **N/A** — `ProfileUpdate` has no username field |
| Case variants bypass reservation | Covered by normalize-lower |
| Inactive/deleted admin token | `get_current_user` → 401; `require_admin` re-checks `is_active` |
| Classification → admin privilege | Explicitly prevented in `set_classification` |
| Prefer stable identity | **Finding:** durable path is `User.is_admin` (UUID). Username allowlist remains for owner-designated accounts until a bounded remediation migrates allowlist → `is_admin` flags without changing unrelated auth. Username reuse after deletion cannot transfer allowlist access to a new person if registration continues to reserve those names; existing deleted-account cleanup should retain reservation. |

Every admin endpoint covered by unauthorized regression tests.

---

## 7. AI metrics verification

| Product surface | Source | Success criterion |
| --- | --- | --- |
| Magic / Dual Magic | `AIJob` `sketch_polish` / `sketch_clean` | `status=completed` |
| Fitting Room | `fitting_room_try_on` | `completed` |
| Try-On | `personal_try_on` (+ realism step separate) | `completed` |
| Croquis generate | `personal_croquis_generate` | `completed` |
| Fabrics | `FabricAsset.source=ai` (not AIJob) | Asset exists; not double-counted as job |
| Technical PDF | `TechpackAIRun.status=completed` | Separate table |

Completion timestamp: **`updated_at`** proxy (no `completed_at` column) — documented in payload.  
Provider billing / operation duration: **unavailable**.  
No live AI calls in verification.

---

## 8. Migration & deploy (proposed order — do not execute yet)

1. Confirm Alembic head = **043** (grants/ledger is a separate stacked PR if present — avoid duplicate revision IDs).  
2. Disposable DB: `alembic upgrade head` → downgrade 042 → upgrade head.  
3. Auth smoke + wallet smoke + account deletion FK smoke.  
4. Apply nginx/CF admin allowlist (`docs/deploy/PROPOSED-NGINX-ADMIN-ALLOWLIST.md`) **before** FE tip that calls new paths.  
5. Deploy BE (API restart) → FE tip → smoke `/admin`.  
6. Classification dry-run only — **no** production classification backfill.  
7. Do **not** modify Stars balances, payment gates, or native apps.

Existing web/iOS/Android clients: no contract break (admin-only routes). Catch-all nginx must allowlist new exact paths or new admin calls 403.

---

## 9. Metric dictionary (summary)

Full list: `GET /api/v1/admin/metrics/dictionary` and Admin UI → Metric dictionary.

Kinds: **exact** · **estimated** · **unavailable**

Unavailable (honest gaps): platform/country acquisition, D7 retention, DAU/WAU, live App Store downloads, provider cash billing, free/paid Stars attribution, historical spend actuals, durable admin-grant ledger (separate feature).

---

## 10. Phase C / D (not in this PR)

**Phase C:** activation funnels, retention cohorts, acquisition charts, CSV exports, notification/system health panels, daily revenue series.  

**Phase D:** versioned analytics events, App Store Connect / Play analytics, provider billing imports, durable admin-grant ledger integration (coordinate with ADD-ONLY grants PR — no duplicate accounting).

---

## 11. Exact next action

Technical PM re-review of amended PR #503 → approve migration plan → disposable DB proof → authorize nginx allowlist → FE+BE tip deploy (separate authorize). **STOP — do not merge/deploy from this agent.**
