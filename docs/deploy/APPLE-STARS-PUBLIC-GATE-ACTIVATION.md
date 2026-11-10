# FashionRise 1.0 — fail-closed public Stars IAP activation (PM checklist)

**Purpose:** Bounded procedure so App Review and public customers can buy Stars and receive **verified** credits.  
**This document does not flip gates.** Activation requires explicit PM authorization after the checklist is green.

## Invariants (never bypass)

1. StoreKit 2 **JWS** verification via App Store Server Library (Production + Sandbox roots).
2. **`appAccountToken`** must match the signed-in FashionRise user.
3. **Idempotent** credit on `(platform, transaction_id)` — never double-credit.
4. ASN V2 **REFUND / REVOKE / REFUND_REVERSED** handling with debt accounting.
5. **No** unverified credit · **no** fake receipts · **no** reviewer email allowlist · **no** `IAP_ALLOW_UNVERIFIED_SANDBOX` in production.

Sandbox allowlist (`IAP_APPLE_SANDBOX_TESTER_EMAILS`) is **temporary** for TestFlight matrix only. Public launch turns on the global gates and may empty the allowlist afterward.

---

## A. Pre-activation (code + ASC) — do before flipping env

| # | Check | Pass criteria |
|---|---|---|
| A1 | main tip includes Buying… polish + real AppIcon | Merged + Codemagic assert-ios-appicon green |
| A2 | App version **1.0** | `MARKETING_VERSION=1.0` |
| A3 | Consumables in ASC | `stars_50` / `stars_150` / `stars_500` · type **Consumable** · Ready to Submit / Approved with app |
| A4 | Israel / storefront pricing | Each SKU has price for Israel (ILS). Shop displays StoreKit `priceString` only |
| A5 | App Store icon | ASC App Information 1024 icon uploaded; TF IPA embeds non-blank AppIcon (`Assets.car`) |
| A6 | Privacy policy URL | Live HTTPS URL in ASC |
| A7 | Screenshots + metadata | Phone (+ iPad if listed); description mentions Stars as consumable AI credits |
| A8 | Digital Services Act (EU) | ASC DSA / trader contact fields complete for FashionRise legal entity |
| A9 | Review notes | Steps: create account → open Stars shop → buy Starter → run Magic (−10) → balance updates |
| A10 | First IAP with version | Submit **1.0 binary + three IAPs together** (first-time IAP) |
| A11 | Prod gates still OFF | `IAP_APPLE_PURCHASING_ENABLED=false` · `IAP_APPLE_CREDIT_ENABLED=false` until section C |

---

## B. TestFlight sandbox matrix (allowlist only)

Public gates remain **OFF**. Allowlisted FashionRise emails get purchasing+credit via `apple_*_enabled_for(user)`.

| # | Case | Expect |
|---|---|---|
| B1 | Allowlisted buy `stars_50` | Sandbox JWS confirm · +50 · one `iap_purchases` row |
| B2 | Re-confirm / recover same txn | `already_processed` · **no** second credit |
| B3 | Magic after buy | −10 Stars · finite wallet |
| B4 | Non-allowlisted account | status shows purchasing/credit **false** |
| B5 | Anonymous status | purchasing/credit **false** |
| B6 | Shop UI | Only tapped pack shows Buying… · `priceString` from StoreKit · real app icon on sheet |

Do **not** require a reviewer-specific email in the allowlist for launch.

---

## C. Production gate flip (PM-authorized window)

Order is intentional — **credit before purchasing** so an in-flight Apple txn can confirm if a reviewer buys after purchasing opens.

### C1 — Enable credit only

```bash
# On VPS backend .env (example) — values not committed
IAP_APPLE_CREDIT_ENABLED=true
IAP_APPLE_PURCHASING_ENABLED=false   # still off
IAP_ALLOW_UNVERIFIED_SANDBOX=false   # must stay false
```

Then: `systemctl restart fashionrise-api fashionrise-ai-worker`  
Verify: `/health` 200 · anonymous `/shop/iap/apple/status` → `credit_enabled=false` still for anon?  
Wait — status uses `apple_credit_enabled_for(user)`. For anonymous, credit should be false. For signed-in users after global credit ON, credit true.

Smoke: recovery/confirm of an **already credited** txn → already_processed. **No new paid purchase yet.**

### C2 — Enable purchasing

```bash
IAP_APPLE_PURCHASING_ENABLED=true
IAP_APPLE_CREDIT_ENABLED=true
IAP_ALLOW_UNVERIFIED_SANDBOX=false
```

Restart API (+ worker).  
Verify signed-in non-allowlist user sees both true; anonymous false for buy UX.

### C3 — Clear or shrink sandbox allowlist (optional after public ON)

Allowlist becomes redundant once globals are true. Prefer emptying after public green so policy is “everyone verified,” not “special emails.”

### C4 — Rollback (fail closed)

```bash
IAP_APPLE_PURCHASING_ENABLED=false
IAP_APPLE_CREDIT_ENABLED=false
```

Restart. Buys stop; incomplete Apple txns stay recoverable when credit is re-enabled (JWS + idempotency).

---

## D. App Review submit (after C2 green)

1. Codemagic → `main` → **FashionRise iOS (App Store IPA)** once · build **>117**.
2. ASC: attach IPA to **1.0** · include three consumables · submit for review.
3. Review notes: sandbox Apple ID instructions if Apple requests; emphasize consumable Stars; no custom checkout.
4. **Do not** add App Review emails to `IAP_APPLE_SANDBOX_TESTER_EMAILS` as the launch mechanism — public gates must be ON so reviewers buy like customers.

---

## E. Explicit non-goals

- No web/Stripe card UI for Stars in the iOS app  
- No Unity republish  
- No enabling gates in the same change that only documents this checklist  
- No unverified sandbox credit in production
