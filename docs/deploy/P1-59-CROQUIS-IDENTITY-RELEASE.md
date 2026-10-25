# P1 #59 — Selected croquis identity — future release plan

**Status:** Draft code only. **Do not deploy** until Technical PM approval + operator visual acceptance on Issue [#59](https://github.com/perielad2-netizen/FashionRise/issues/59).

**Cursor paid AI this change:** **0**. No production deploy, no merge of PR #57 to `main`, no DB / Nginx / Cloudflare / Sunburst quality changes.

## Production baseline (reverified 2026-10-25)

| Layer | Revision | Notes |
|---|---|---|
| GitHub `main` | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` | Includes PR #41 pose-fidelity source (**not** on prod BE) |
| Production frontend | `c6fc1eb8` | Same as verified main tip when this plan was written |
| Production backend + AI worker | `b800e53d25dcdf2481f377470543b323798796a7` | Isolated Sunburst maint lineage (P1 #54 / deploy record PR [#58](https://github.com/perielad2-netizen/FashionRise/pull/58)) |
| Alembic | `005` | Unchanged by #59 |
| Image model | `gpt-image-2.5-sunburst` high / 1024×1536 / n=1 / png / `max_retries=0` | Do not alter for this release |

**Hard rule:** Do **not** deploy GitHub `main` indiscriminately to the backend/worker. Main carries undeployed pose-fidelity packing from PR #41 that differs from the production maint prompt lineage.

## What this patch changes

- Frontend sends `input_data.reference_model_id` with Magic polish (selected Studio croquis id snapshotted with the sketch).
- Backend validates allowlisted IDs on enqueue; missing metadata stays compatible.
- Vision + `images.edit` prompts treat validated selected-reference metadata as authoritative over conflicting vision prose.
- No migration, no stored-design rewrite, no remapping of legacy `female`/`male` IDs.

## Approved future deploy shape (when authorized)

1. **Frontend:** Deploy the #59 web-ui commit (or a cherry-pick containing only the Magic identity contract) onto production FE lineage based on `c6fc1eb8`.
2. **Backend + AI worker:** Cherry-pick / rebase the #59 backend identity modules onto the **production maint tip** `b800e53d` (or the then-current Sunburst maint tip), **excluding** undeployed PR #41 pose packing unless separately approved.
3. Restart API + worker only after the audited tip is on disk; keep Alembic `005`.
4. Do **not** merge PR #57 into `main` as part of this release.
5. Smoke: unauthenticated AI paths still Nginx-denied; authenticated polish enqueue with a known male id returns 201 and stores `reference_model_id`; **no** paid Magic in smoke unless PM authorizes a separate visual gate.

## Rollback

1. Restore previous FE release directory / symlink (pre-#59).
2. Restore previous BE/worker tree at `b800e53d` (or the pre-cherry-pick tip).
3. Restart `fashionrise-api` + `fashionrise-ai-worker`.
4. No DB rollback required (no schema change). Existing jobs without `reference_model_id` remain valid.

## Visual acceptance gate (operator)

Acceptance is **not** “Magic returns an image.” For a male library croquis (e.g. `male-straight` / `male-contrapposto`) with a grey top + blue trousers sketch:

- Result remains recognizably the selected **male** fashion-croquis family.
- Pose / stance / limb relationships remain recognizable.
- Garment colors and silhouette remain faithful.
- No silent swap to a female-presenting runway figure.

Keep Issue #59 **open** until that gate passes.
