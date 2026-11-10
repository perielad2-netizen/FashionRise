# Apple Stars IAP — Phase B (implemented architecture)

Phase A (PR **#267**, squash-merged to `main` **`bd94f8b4`**) delivered cryptographic StoreKit 2 JWS verification and idempotent credit.

Phase B implements ASN V2 refund/revoke handling, refund liability accounting, native iOS Stars shop + recovery — **still behind default-OFF gates**.

| Gate | Env | Meaning | Default |
|---|---|---|---|
| New purchases | `IAP_APPLE_PURCHASING_ENABLED` | Native shop may *start* StoreKit buys | **false** |
| Credit / recovery | `IAP_APPLE_CREDIT_ENABLED` | Server accepts confirm/reconcile of completed Apple JWS | **false** |

Do **not** enable credit alone as a production bypass without ASN routing live. Do **not** enable purchasing without TestFlight sandbox validation.

## Architecture (as implemented)

### Notifications

- Endpoint: `POST /api/v1/shop/iap/apple/notifications` (no user session)
- Body: `{ "signedPayload": "<JWS>" }` (Apple ASN V2)
- Verification: official `app-store-server-library` `SignedDataVerifier.verify_and_decode_notification` + nested `signedTransactionInfo`
- Persistence: `iap_apple_notifications` unique on `notification_uuid`
- Handled wallet events: `REFUND`, `REVOKE`, `REFUND_REVERSED`
- Other types (e.g. `DID_RENEW`, `TEST`): acknowledged as `ignored` (no wallet mutation)
- Invalid signature → 403; transient processing → 503 (Apple retries)

### Refund / liability policy

Balance **never goes negative**. Column `users.ai_stars_iap_debt` tracks outstanding refunded Stars already spent.

On verified `REFUND` / `REVOKE` for a credited purchase:

1. Lock purchase + user rows
2. `need = stars_credited - stars_clawed_back`
3. Claw `min(balance, need)` from `ai_stars`
4. Add remainder to `ai_stars_iap_debt`
5. Record idempotent `iap_stars_adjustments` row unique on `(iap_purchase_id, adjustment_kind)` and `(platform, transaction_id, adjustment_kind)`

Example: buy 500, spend 450, refund → balance 0, debt 450. Later credits settle debt first, then increase spendable balance.

On `REFUND_REVERSED`: restore previously clawed amount only (debt first, then balance). **Never** invents a fresh purchase credit.

### Confirm path

- Still requires verified JWS + matching `appAccountToken`
- If unmatched ASN takeback exists for the transaction → create `blocked` purchase, **zero** Stars credit
- Repeat confirm after refund → idempotent `already_processed` / blocked (no re-credit)

### Native iOS shop

- `StarsShopModal` detects Capacitor iOS → StoreKit products + Buy (no Stripe/web checkout)
- Web keeps cart UX; Android shows packages unavailable for Play (staged)
- Purchase: `GET /shop/iap/app-account-token` → Capgo `purchaseProduct({ appAccountToken, autoAcknowledgePurchases: false })` → `POST /shop/iap/confirm` → `acknowledgePurchase`
- Recovery: bounded `getPurchases({ appAccountToken })` on shop open, app resume, and post-login (cooldown; credit gate required)
- Finish only after durable backend acceptance (or blocked/already_processed)

### Products

| Product ID | Stars | Planned USD (ASC) |
|---|---:|---:|
| `stars_50` | 50 | $5.99 |
| `stars_150` | 150 | $16.99 |
| `stars_500` | 500 | $49.99 |

Localized prices come from StoreKit only — never hardcode as the displayed App Store price.

## Database (Alembic **026** + **027**)

**026** revises **025**. Adds:

- `users.ai_stars_iap_debt`
- `iap_purchases`: `original_transaction_id`, `environment`, `status`, `stars_clawed_back`, `stars_restored`, `updated_at`
- `iap_apple_notifications`
- `iap_stars_adjustments`

**027** (hardening): unique adjustment per `notification_id` (allows REFUND after REFUND_REVERSED); `signed_date_ms` on notifications.

Downgrade drops Phase B structures. If production has live refund rows, prefer **backup + forward-fix** over downgrade.

## Concurrency strategy

Confirm and ASN both take PostgreSQL `pg_advisory_xact_lock(ns, crc32(iap:ios:<txn>))` **before** mutating purchases/wallets.

Lock order (deadlock-safe):

1. advisory(transaction_id)
2. `iap_purchases` `FOR UPDATE`
3. `users` `FOR UPDATE`

After any conflict, reload authoritative rows — never trust pre-lock ORM state.

## ASN retry guarantees

| State | Apple redelivery |
|---|---|
| `applied` / `ignored` | Idempotent 2xx |
| `unmatched` / `needs_reconciliation` | Re-evaluate under lock; 2xx when parked |
| `failed` / stale `processing` | Retry apply; success → 2xx; still failing → **503** |
| Receipt insert | Committed **before** apply so crashes cannot erase the UUID |

## Capgo / StoreKit recovery (plugin 7.19.3)

Verified in plugin sources:

- `purchaseProduct({ autoAcknowledgePurchases: false })` skips finish in the purchase path.
- Capgo’s `Transaction.updates` listener **still auto-finishes** verified updates before `transactionUpdated`.
- `getPurchases()` uses StoreKit `Transaction.all` (+ entitlements) and supports `appAccountToken` filter; includes `jwsRepresentation`.
- `acknowledgePurchase` finishes by transaction id; “already finished” is treated as success.

Client mitigations: session pending transaction-id hint (no raw JWS), `transactionUpdated` confirm, resume/login recovery. If history + hint both miss a charged consumable, support reconciliation via ASN / App Store Server API (gated; not enabled here).

## Nginx / Cloudflare

See `docs/deploy/PROPOSED-NGINX-SHOP-ALLOWLIST.md`.

Required new exact locations (verified missing on prod 2026-11-10):

- `GET /api/v1/shop/iap/app-account-token`
- `GET /api/v1/shop/iap/apple/status`
- `POST /api/v1/shop/iap/apple/notifications`

Existing: `confirm`, `restore`.

Cloudflare: path-exact Access/WAF bypass for ASN webhook only.

## Activation order (PM-authorized)

1. Merge + deploy BE/FE with gates **OFF**; run Alembic **026**
2. Apply nginx ASN + app-account-token allowlists; Cloudflare ASN exception
3. Configure App Store Server Notifications V2 URL → production endpoint
4. Validate webhook (Apple test notification) with gates still OFF
5. Enable `IAP_APPLE_CREDIT_ENABLED` in controlled env → sandbox confirm/recovery/refund
6. TestFlight native shop with purchasing still OFF until credit path proven
7. Enable `IAP_APPLE_PURCHASING_ENABLED` after payment integrity proven
8. Separate authorization for public App Store release

## Rollback notes

- Turning gates OFF stops new buys / new credits but does **not** undo Apple charges already made
- Keep ASN endpoint + credit recovery available for support reconciliation when customers were charged
- Never disable confirm/recovery without a support path for stranded purchases

## App Store Connect checklist (owner)

- [ ] Paid Apps Agreement + tax/banking
- [ ] Consumables `stars_50` / `stars_150` / `stars_500` with pricing
- [ ] App Store Server API key (if online checks / future history APIs)
- [ ] ASN V2 production + sandbox URLs
- [ ] Sandbox testers
- [ ] IAP review metadata / screenshots / age rating as required for first IAP version

## Explicitly out of Phase B

- Google Play Billing verification
- Web card checkout
- Codemagic / App Store submit automation
- Enabling gates in production
- Real paid purchases during implementation
