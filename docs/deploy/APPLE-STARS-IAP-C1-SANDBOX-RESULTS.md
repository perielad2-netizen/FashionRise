# Apple Stars IAP — C1 Sandbox first purchase results (read-only audit)

**When:** 2026-11-10 ~23:47 IST (21:47 UTC)  
**Account:** `perielad2@gmail.com` (sandbox allowlist + finite override)  
**Scope:** Read-only production audit. No new purchases, no gate flips, no App Review.

## Verdict

| Check | Result |
|---|---|
| Genuine Apple Sandbox signed path | **PASS** — ASN `ONE_TIME_CHARGE` + StoreKit confirm JWS accepted |
| Correct SKU | **PASS** — `stars_50` / 50 Stars |
| `appAccountToken` ownership | **PASS** — ASN token `1f14e2aa-a456-5694-b64d-7bd376d867fd` matches server token for user |
| Exactly one 50-Star credit | **PASS** — single `iap_purchases` row; one `ai_stars_credited amount=50` |
| Durable ledger | **PASS** — `iap_purchases` unique `(platform, transaction_id)`; status `active`; env `Sandbox` |
| Idempotency / recovery | **PASS** — second `POST /shop/iap/confirm` ~3s later; **no** second credit |
| Public gates | **PASS** — purchasing/credit still **OFF** globally; allowlist-only sandbox path |
| App Store submission | **NOT blocked by ledger/security** — blocked by remaining UI polish + gated launch policy |

## Ledger facts (prod)

| Field | Value |
|---|---|
| Purchase id | `7d914427-b915-49b9-8924-2fc3a57bd358` |
| Transaction id | `2000001264125176` (= original) |
| Product | `stars_50` · stars_credited **50** · clawed **0** · restored **0** |
| Environment / status | **Sandbox** / **active** |
| ASN | `ONE_TIME_CHARGE` · Sandbox · same txn · same `app_account_token` · `ignored` (non-takeback policy) |
| Adjustments | none (no refund/revoke) |
| Wallet after credit log | `ai_stars=1000039` · debt **0** · DB `ai_stars_unlimited=true` · **effective unlimited=false** (finite override) |

Confirm log (21:47:09Z): `iap_confirmed … product=stars_50 stars=50 txn_suffix=001264125176`.

## Idempotency / recovery (no mutation)

1. Unique DB constraint `uq_iap_purchases_platform_txn` — **1** row for this txn.
2. Client recovery/`confirm` replay at 21:47:12Z returned **200** with **no** second `ai_stars_credited` line.
3. Pending-txn recovery remains allowlisted for this tester; public credit gate **OFF**.

## UI issues (observed) → proposed minimal fixes

### 1. All three buttons show “Buying…”
**Cause:** `StarsShopModal` used shared `busy && flowState === 'purchasing'` for every pack button.  
**Fix (code in this PR):** track `buyingProductId`; only that button shows “Buying…”; others stay “Buy” (still disabled). Preserve StoreKit flow and gates.

### 2. Shop shows USD while Apple sheet shows ILS
**Cause (code):** Shop already renders Capgo/StoreKit `priceString` (`Product.displayPrice`) — **no hardcoded USD** in the native path. Currency mismatch is almost always **Sandbox Apple ID / storefront** vs device region, or ASC price availability — not a FE hardcode bug.  
**Fix (ops / ASC, not a FE price invent):** Confirm Sandbox tester Apple ID storefront is Israel; ensure `stars_50/150/500` have Israel/ILS price points in ASC. Optional QA: log Capgo `currencyCode` beside `priceString` in TestFlight builds only. **Do not** replace StoreKit strings with manual ILS formatting.

### 3. Placeholder app icon on Apple purchase sheet
**Cause:** Not FE shop CSS. Sheet uses the app’s marketing/binary icon. Repo has a valid **1024×1024 RGB PNG** App Icon asset; placeholder usually means ASC **App Store icon** missing/stale or the installed TestFlight build predates the icon.  
**Fix (ASC / rebuild):** Upload/verify 1024 App Store icon in App Store Connect; ship a new TestFlight build from `main` if the installed IPA is older than the icon asset. No IAP security change.

## Gates (unchanged — leave OFF for public)

| Gate | Prod value |
|---|---|
| `IAP_APPLE_PURCHASING_ENABLED` | **false** |
| `IAP_APPLE_CREDIT_ENABLED` | **false** |
| `IAP_ALLOW_UNVERIFIED_SANDBOX` | **false** |
| Sandbox allowlist | count **4** (includes `perielad2@gmail.com`) |
| Finite override | count **1** (`perielad2@gmail.com`) |

## Does anything block App Store submission?

| Item | Blocks submit? |
|---|---|
| Ledger / JWS / token / idempotency | **No** — C1 sandbox credit path validated |
| Public purchasing/credit still OFF | **Policy hold** — intentional until PM opens gates |
| “Buying…” on all packs | **Polish** — fixed in this PR; ship in next TF before submit preferred |
| USD vs ILS display | **ASC/storefront verify** — not a security blocker; confirm ILS storefront before submit |
| Placeholder purchase-sheet icon | **ASC/TF asset** — fix before App Review screenshots/submit |
| Real-money / App Review | **Do not submit** until PM authorizes gate plan + TF matrix complete |

**Stop for PM review.** No public gate enable. No App Review submit. No further sandbox purchases required for this audit.
