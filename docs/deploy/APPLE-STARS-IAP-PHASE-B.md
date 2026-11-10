# Apple Stars IAP — Phase B requirements (refunds / enablement)

Phase A landed cryptographic StoreKit 2 JWS verification and idempotent credit,
but **`IAP_APPLE_PURCHASING_ENABLED` stays false** until this phase completes.

## Must ship before enabling public purchasing

1. **App Store Server Notifications V2** webhook (signed payload verify via same library).
2. Handle at least: `REFUND`, `REVOKE`, `REFUND_REVERSED` (policy TBD) — debit or freeze Stars tied to the original `transactionId` / `originalTransactionId`.
3. Persist notification UUIDs for idempotent ASN processing.
4. Nginx allowlist for the ASN path + `GET /api/v1/shop/iap/app-account-token` if not already live.
5. Native Stars shop UI: Capgo purchase → confirm with JWS; pass `appAccountToken` from `GET /shop/iap/app-account-token`; unfinished-txn recovery via `getPurchases()`.
6. Sandbox matrix for buy / kill-app mid-confirm / refund → balance.
7. Only then set `IAP_APPLE_PURCHASING_ENABLED=true` on production (still never `IAP_ALLOW_UNVERIFIED_SANDBOX`).

## Explicitly out of Phase B unless PM expands scope

- Google Play Billing verification
- Web card checkout
- Codemagic / App Store submit automation
