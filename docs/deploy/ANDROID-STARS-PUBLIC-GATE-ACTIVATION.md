# FashionRise Android — fail-closed public Stars Play Billing activation (PM checklist)

**Purpose:** Bounded procedure so public Play customers can buy Stars and receive **verified** credits after license-tester sandbox validation.  
**This document does not flip gates.** Activation requires explicit PM authorization after the checklist is green.

## Live status (2026-11-27 Asia/Jerusalem)

| Gate | Value |
|---|---|
| `IAP_GOOGLE_PURCHASING_ENABLED` | **false** (public OFF) |
| `IAP_GOOGLE_CREDIT_ENABLED` | **false** (public OFF) |
| `IAP_GOOGLE_LICENSE_TESTER_EMAILS` | 4 FashionRise logins (license-tester bypass only) |
| `IAP_GOOGLE_RTDN_VERIFY_OIDC` | **true** |
| Products | `stars_50` / `stars_150` / `stars_500` **ACTIVE** |
| Device shell | Internal AAB **VC 156** owner-validated (layout, FCM, camera, login, deep links) |
| Alpha closed track | **VC 114** + **15** testers — **preserve**; do not recreate |

Sandbox / license-test purchases must map to `iap_purchases.environment=Sandbox` and stay **excluded** from admin Production revenue (`admin_analytics` require `environment=Production`).

---

## Invariants (never bypass)

1. Play Developer API `purchases.products.get` — purchaseState=Purchased before credit.
2. `obfuscatedExternalAccountId` must match FashionRise `app_account_token` for the signed-in user.
3. **Idempotent** credit on Android `purchase_token` (+ platform txn uniqueness) — never double-credit.
4. RTDN OIDC: audience + exact push SA email + `email_verified`; voided / canceled clawbacks under purchase-token advisory lock with fresh DB state after lock.
5. License testers: allowlisted emails only while public gates OFF; Production Play purchases for allowlisted emails must be **rejected** (Sandbox-only credit path).
6. **No** public gate flip without a green sandbox ledger row (purchase + refund/clawback) in production DB.

---

## A. Pre-activation (already mostly live)

| # | Check | Pass criteria |
|---|---|---|
| A1 | Internal AAB ≥ 156 | Owner device validation green (chrome, FCM, camera, auth, deep links) |
| A2 | Play products ACTIVE | `stars_50` / `stars_150` / `stars_500` |
| A3 | Play SA + RTDN | OIDC test notification `processing_state=applied` |
| A4 | Assetlinks | Live Play App Signing SHA-256 |
| A5 | R8 release | minify+shrink on; no ActionBar / edge-to-edge double inset |
| A6 | Public gates OFF | `PURCHASING=false` · `CREDIT=false` until section C |
| A7 | Alpha closed | Track **114** + 15 testers unchanged |

---

## B. License-tester sandbox ledger matrix (required before public ON)

Public gates remain **OFF**. Allowlisted FashionRise emails get purchasing+credit via `google_*_enabled_for(user)`.

| # | Case | Expect |
|---|---|---|
| B1 | Allowlisted buy `stars_50` | `POST /shop/iap/confirm` **200** · one `iap_purchases` row `platform=android` · `environment=Sandbox` · `stars_credited=50` |
| B2 | Re-confirm / restore same token | idempotent · **no** second credit |
| B3 | Refund / void in Play | RTDN or voided reconcile · `stars_clawed_back` / adjustment row · no double clawback |
| B4 | Admin revenue | Sandbox row **excluded** (`sandbox_purchases_excluded`); Production revenue unchanged |
| B5 | Non-allowlisted account | `/shop/iap/google/status` purchasing/credit **false** |
| B6 | Production purchaseType for allowlisted email | confirm **rejected** (Sandbox-only while gates OFF) |

**Verification note (2026-11-27):** After VC **156** owner shell validation, production still had **0** `platform=android` purchase rows and **no** `POST /shop/iap/confirm` hits. Complete B1–B4 and record message ids / purchase ids here before section C.

---

## C. Production gate flip (PM-authorized only)

Order: **credit before purchasing** (same as Apple).

### C1 — Enable credit only

```bash
IAP_GOOGLE_CREDIT_ENABLED=true
IAP_GOOGLE_PURCHASING_ENABLED=false
```

Restart `fashionrise-api` (+ AI workers if they share env). Confirm anonymous `/shop/iap/google/status` still shows purchasing/credit **false**.

### C2 — Enable purchasing

```bash
IAP_GOOGLE_PURCHASING_ENABLED=true
```

Restart API. Smoke one Production (non-license-test) buy on a non-allowlist account only after PM sign-off.

### C3 — Optional: shrink license-tester allowlist

After public ON, clear or reduce `IAP_GOOGLE_LICENSE_TESTER_EMAILS` so Sandbox bypass is not a standing production exception.

---

## Stop line

- Do **not** flip C1/C2 without B1–B4 ledger evidence in production.
- Do **not** publish the public production Play track as part of this checklist.
- Do **not** modify Alpha closed testing or its 15 testers.
