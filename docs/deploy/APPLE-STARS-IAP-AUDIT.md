# Apple Stars IAP — App Store readiness audit (2026-11-10)

**Status:** Audit approved (PR **#266** squash-merged 2026-11-10).  
**Follow-on:** Phase A (**#267**) merged to `main` `bd94f8b4` (gates OFF, not deployed). Phase B implementation: `APPLE-STARS-IAP-PHASE-B.md` + branch `cursor/apple-iap-phase-b-complete-77c6` (PM review; gates OFF).

## Verdict (audit-time — historical)

At audit time FashionRise was **not** ready to credit Stars from Apple IAP in production. Phase A/B closed the code gaps behind default-OFF gates; production enablement still requires deploy, nginx/ASN, ASC config, and PM-authorized gate activation.

## Verified findings

### What exists

| Piece | Finding |
|---|---|
| Client adapter | `web-ui/src/services/native/iap.ts` — `@capgo/native-purchases` ^7.19.3, `PURCHASE_TYPE.INAPP`, products `stars_50` / `stars_150` / `stars_500` |
| Confirm API | `POST /api/v1/shop/iap/confirm` (`shop.py` → `iap_service.confirm_purchase`) — auth required, rate-limited |
| Persist | `iap_purchases` (Alembic 024) with `UNIQUE (platform, transaction_id)`; prod DB has the table (alembic **025**) |
| Wallet | `ai_stars.credit_stars` uses `SELECT … FOR UPDATE` on the user row |
| Catalog | `stars_shop.STAR_PACKAGES` SKUs/prices match IAP IDs ($5.99 / $16.99 / $49.99) |
| Nginx | Live allowlist for `/api/v1/shop/iap/confirm` and `/iap/restore` |
| Docs | `docs/STORE-DEPLOY.md` documents staged verification |
| Tests | Confirm fail-closed without credentials; unknown product rejected |

### Gaps (blockers for App Store Stars)

1. **No real Apple verification** — `_verify_with_store` for iOS raises `ServiceUnavailableError` (“staged”) even when `IAP_APPLE_SHARED_SECRET` is set. Unverified sandbox credit only when `IAP_ALLOW_UNVERIFIED_SANDBOX` and `environment != production`.
2. **Prod credentials absent** — `/opt/fashionrise/src/backend/.env` has no `IAP_APPLE_*` / Google IAP keys (confirm stays 503). Prefer **App Store Server API v2 + JWS** (`jwsRepresentation` from Capgo) over legacy shared-secret `verifyReceipt`.
3. **Client `product_id` trusted for Stars amount** — after a future verify stub is replaced, Stars must be taken from the **verified** Apple product id, not the request body alone.
4. **Shop UI not wired** — `StarsShopModal` uses cart/checkout only (`available=False` / checkout disabled). It never calls `purchaseStarsPack` / `listStarsIapProducts`.
5. **Interrupted confirm** — Apple can charge while `/iap/confirm` fails; no startup/`getPurchases()` re-confirm queue. `/iap/restore` is a placeholder (`restored: 0`).
6. **Refunds** — no App Store Server Notifications (ASN) endpoint; no debit/revoke of Stars on refund.
7. **Concurrency UX** — unique constraint prevents double credit on commit, but `IntegrityError` is not mapped to the idempotent `already_processed` response.
8. **`appAccountToken`** — Capgo supports UUID account tokens for fraud/user linking; not passed today.
9. **ASC configuration** — products must exist as **Consumable** IAPs with those exact IDs; Paid Apps Agreement, banking/tax, privacy URL, and sandbox testers still required outside the repo.
10. **Tests thin** — no happy-path credit with mocked Apple JWS, no idempotent reconfirm, no cross-user conflict, no refund debit, no FE native shop tests.

## Recommended implementation plan (after PM approval)

### P0 — Server trust boundary

1. Implement Apple verify using **App Store Server API v2**: decode/verify JWS (or fetch transaction by id with API key); reject missing/invalid JWS in production.
2. Map **verified** `productId` → Stars via `STARS_PRODUCTS`; ignore client stars; reject product mismatch vs body if body is kept for logging only.
3. Persist verified fields as needed (e.g. original transaction id, environment sandbox/prod) without storing secrets.
4. Catch unique-violation on insert → return same-user idempotent payload.
5. Force-disable `IAP_ALLOW_UNVERIFIED_SANDBOX` when `ENVIRONMENT=production` in settings validators.
6. Add ASN webhook (REFUND / REVOKE) → debit or mark purchase revoked; never leave refunded Stars spendable.

### P0 — Client / UX

1. In native shell, `StarsShopModal` (or dedicated sheet): `listStarsIapProducts` + `purchaseStarsPack`; hide web cart checkout on iOS.
2. After purchase, always confirm with server; on confirm failure, retry and on next launch run `getPurchases()` → confirm each uncredited txn.
3. Pass `appAccountToken` (UUID derived from FashionRise user id).
4. Copy: Stars are consumable digital goods; restore does not re-grant spent Stars (Apple consumable rules).

### P1 — Config / ops

1. App Store Connect: create/approve Consumable IAPs `stars_50` / `stars_150` / `stars_500` at launch prices.
2. Create App Store Server API key; store key id / issuer / private key on server (not in git). Shared secret optional only if keeping legacy receipt path.
3. Confirm nginx ASN path allowlist when webhook is added.
4. Sandbox TestFlight purchase matrix; then production credentials.

### Tests

- BE: mocked valid/invalid JWS; product mismatch; idempotent reconfirm; cross-user conflict; refund debit; production rejects unverified sandbox flag.
- FE: native shop buy path mocked Capgo; confirm retry / getPurchases recovery.
- Manual: sandbox buy each SKU; kill app between Apple sheet and confirm; refund in sandbox + ASN.

### Deployment (only when PM asks)

1. Merge verification + UI PRs → migrate if schema extends → set Apple API secrets on VPS → restart API.
2. New TestFlight build (manual Codemagic) with IAP capability / products visible.
3. Do **not** enable unverified sandbox in production.

## Security checklist (must hold)

- Never credit Stars without valid server-side Apple verification in production.
- Never treat client `product_id` / `transaction_id` as proof of payment.
- Never expose Apple API keys or shared secrets in logs, clients, or git.
- Preserve existing non-IAP Stars/wallet behavior for web beta.
