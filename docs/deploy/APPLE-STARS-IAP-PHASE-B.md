# Apple Stars IAP — Phase B requirements (refunds / enablement)

Phase A landed cryptographic StoreKit 2 JWS verification and idempotent credit.
**Both** activation gates stay **false** until this phase completes:

| Gate | Env | Meaning |
|---|---|---|
| New purchases | `IAP_APPLE_PURCHASING_ENABLED` | Native shop may *start* StoreKit buys |
| Credit / recovery | `IAP_APPLE_CREDIT_ENABLED` | Server accepts confirm/reconcile of completed Apple JWS (incl. unfinished-txn recovery) |

Do **not** enable credit alone as a “production bypass” without ASN/refunds. Do **not** enable purchasing without the shop UI + `appAccountToken` wiring.

## Must ship before enabling gates

1. **App Store Server Notifications V2** webhook (signed payload verify via same library).
2. Handle at least: `REFUND`, `REVOKE`, `REFUND_REVERSED` (policy TBD) — debit or freeze Stars tied to the original `transactionId` / `originalTransactionId`.
3. Persist notification UUIDs for idempotent ASN processing.
4. Nginx allowlist for the ASN path + `GET /api/v1/shop/iap/app-account-token` if not already live.
5. Native Stars shop UI: Capgo purchase with `appAccountToken` from `GET /shop/iap/app-account-token` → confirm with JWS; unfinished-txn recovery via `getPurchases()` → same confirm path (`IAP_APPLE_CREDIT_ENABLED`).
6. Sandbox matrix for buy / kill-app mid-confirm / refund → balance.
7. Enable order (prod): ASN live → `IAP_APPLE_CREDIT_ENABLED=true` → shop UI → `IAP_APPLE_PURCHASING_ENABLED=true`. Never `IAP_ALLOW_UNVERIFIED_SANDBOX`.

## Explicitly out of Phase B unless PM expands scope

- Google Play Billing verification
- Web card checkout
- Codemagic / App Store submit automation
