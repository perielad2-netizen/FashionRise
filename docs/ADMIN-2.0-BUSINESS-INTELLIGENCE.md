# FashionRise Admin 2.0 — Business Intelligence & Operations Control Center

**Status:** Draft foundation (Phase A + Phase B) — **not deployed**  
**Baseline main:** `f3967dbf`  
**Audience:** Technical PM / owner  
**Timezone for reporting:** Asia/Jerusalem calendar days (stored events remain UTC)

---

## 1. Existing admin architecture (pre–Admin 2.0)

| Layer | Location | Notes |
| --- | --- | --- |
| Auth gate | `backend/app/auth/admin.py` | Username allowlist + `User.is_admin`; server-side 403 |
| Routes | `backend/app/api/v1/routes/admin.py` | Was `/overview` + `/reports` only |
| Aggregates | `backend/app/services/admin_analytics.py` | Single overview payload |
| UI | `web-ui/src/pages/AdminPage.tsx` | Two tabs; mobile pill nav |
| Client API | `web-ui/src/services/adminApi.ts` | Typed fetch helpers |

Production tip at foundation start: FE `e0ee7bed`, BE tree historically `f34bd48` (verify at deploy time).

---

## 2. Root causes of metric inconsistencies (Nov 25 snapshot)

| Observation | Root cause | Fix in foundation |
| --- | --- | --- |
| Magic / Fitting Room / Try-On = 0 despite usage | Admin filtered `AIJob.status == "succeeded"`; workers persist **`completed`** | Count `completed`; document semantics |
| Stars spend est. low | Same wrong status on debited jobs | Use `completed` + `stars_debited` |
| 110 Stars with $0 production revenue | Balance ≠ purchase. Admin gift / starting grant / non-IAP credit possible; IAP ledger can be empty | Customer 360 shows purchases separately; admin-grant ledger marked **unavailable** |
| Mixed test + customers | No classification model | `account_classification` (default `UNCLASSIFIED`); no silent CUSTOMER backfill |
| Overview nav text invisible on mobile | `.navBtnActive { color:#fff }` + mobile white background without resetting text | Mobile active: dark bg + white text |
| Awkward email wrapping | Table cells without `overflow-wrap` | Card list + `emailClip` |

---

## 3. Mobbin design research

Authorized Mobbin Pro MCP used (web platform). References studied (patterns only — no proprietary assets copied):

- Amplitude / Slite / Notion analytics — KPI cards, date range, metric tooltips, empty states  
- Mixpanel / Okta — user directories & filters  
- Basedash / 7shifts / Teachable — sidebar IA, needs-attention severity, report queues  
- Google Analytics library — collections vs reports progressive disclosure  

**FashionRise direction:** light premium surface, FashionRise accent (#c2185b), desktop sidebar + mobile drawer/menu, global Audience + Range chips, customer detail drawer, exact/estimated/unavailable badges.

---

## 4. Account classification policy

Classifications (independent of `is_admin`):

`CUSTOMER` · `OWNER` · `ADMIN` · `INTERNAL_TESTER` · `QA_AUTOMATION` · `DEMO_ACCOUNT` · `UNCLASSIFIED`

Rules:

- Default for all accounts: **UNCLASSIFIED**  
- Heuristic suggestions are non-authoritative (`/admin/classification/dry-run`)  
- Operator PATCH writes classification + audit row (`account_classification_events`)  
- Classification **never** grants/revokes admin permissions  
- No automatic production backfill without approved dry-run  

Migration: Alembic **043** (not executed in production in this PR).

---

## 5. Metric dictionary (summary)

Full list: `GET /api/v1/admin/metrics/dictionary` and Admin UI → Metric dictionary.

Kinds: **exact** · **estimated** · **unavailable**

Unavailable in Phase B (honest gaps): platform, country, D7 retention, live App Store downloads, provider cash billing, durable admin-grant ledger, full activity timeline.

---

## 6. Phase B implemented surfaces

- Responsive Admin 2.0 shell (sidebar / mobile menu)  
- Global Audience + Range filters  
- Overview KPIs + Needs attention  
- Customers directory + detail drawer + classification PATCH  
- Revenue & Stars (production vs sandbox)  
- AI & Costs (corrected job status)  
- Community KPIs + existing Reports queue  
- Metric dictionary  

Not in this PR: funnels, cohorts, exports CSV, App Store Connect live API, notification deep health, system restart actions.

---

## 7. Security

- All `/admin/*` require `AdminUser` dependency  
- Classification mutation audited with actor id  
- No wallet grant/reset endpoints  
- No impersonation / user delete / payment admin  
- Customer payloads omit passwords, tokens, secrets  

---

## 8. Migration & deploy

- **043** must be reviewed and applied in a separately authorized maintenance window  
- Rollback: `alembic downgrade 042`  
- FE tip deploy only after PM merge authorization  
- Do not restart API/workers in this foundation task  

---

## 9. Phase C / D roadmap

**Phase C:** activation funnels, retention cohorts, acquisition charts, CSV exports, notification/system health panels.  

**Phase D:** versioned analytics events, App Store Connect / Play analytics integrations (after credential scope verification), provider billing imports.

---

## 10. Exact next action

Technical PM review of draft PR → approve migration plan → disposable DB upgrade/downgrade proof → classify dry-run approval → FE+BE tip deploy (separate authorize).
