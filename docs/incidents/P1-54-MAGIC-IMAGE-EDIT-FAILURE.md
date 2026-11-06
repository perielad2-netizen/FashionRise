# P1 #54 — Magic image-edit failure investigation

**Issue:** [#54](https://github.com/perielad2-netizen/FashionRise/issues/54)  
**Observability draft PR:** [#55](https://github.com/perielad2-netizen/FashionRise/pull/55) (`cursor/magic-edit-failure-54-77c6`)  
**Model migration:** separate draft PR (not mixed into #55)  
**Paid OpenAI / live Magic retries this run:** **0**

## Leading root-cause explanation (PM-confirmed docs)

Official OpenAI documentation states **`gpt-image-1` was shut down on October 23, 2026**:

- https://developers.openai.com/api/docs/deprecations (October 23, 2026 shutdown table; replacement: `gpt-image-2.5-sunburst` or `gpt-image-2.5-flare`)
- https://developers.openai.com/api/docs/models/gpt-image-1 (status: Shut down)
- https://developers.openai.com/api/reference/python/resources/images/methods/edit

**Production AI worker is still configured with `OPENAI_IMAGE_MODEL=gpt-image-1`.**

Three operator Magic failures on **2026-10-24 22:33–22:37 UTC** (Oct 25 Asia/Jerusalem local) match: chat/completions **200** → images/edits **400** `BadRequestError`. Earlier same-day/prior successes on Oct 23 fit the shutdown timeline.

**Model retirement is the leading, high-confidence operational explanation.** Historical per-request provider `error.code` values were **not recorded** on deployed `2cbc1ad0`, so exact per-request attribution remains unavailable. **Do not claim proven per-job codes. Do not run another paid probe against the retired model.**

Swimwear / garment category has **not** been established as a content-policy refusal.

## Safety restrictions observed

- No production DB writes, restarts, Nginx/Cloudflare changes, or deploys.
- No live OpenAI calls; no paid test jobs; operator failed sketches not retried.
- PR #41 Magic pose-fidelity **not** deployed as part of this work.
- Open docs PR [#53](https://github.com/perielad2-netizen/FashionRise/pull/53) and Front/Back architecture PR [#50](https://github.com/perielad2-netizen/FashionRise/pull/50) left untouched (not merged, not overwritten).
- Issue [#51](https://github.com/perielad2-netizen/FashionRise/issues/51) remains closed / operator-accepted **5/5**.
- Reports use redacted job id prefixes only; no images, base64, prompts, tokens, PII, or raw provider bodies.

## 1. Production versions verified (read-only)

| Layer | Verified value | Evidence |
|-------|----------------|----------|
| Frontend Nginx root | `/var/www/fashionrise/releases/c6fc1eb8` | `sites-enabled/fashionrise.app` |
| Frontend revision | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` | release dir + SHA256SUMS present |
| Backend `/opt/fashionrise/src` | `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9` | `git rev-parse HEAD` as app user |
| AI worker | same SHA; PID **35740** since `2026-10-24 06:36:33 UTC` | systemd |
| API | PID **35739** since `2026-10-24 06:36:33 UTC` | systemd |
| Alembic | **005** | `alembic current` + `alembic_version` |
| Models (names only) | `OPENAI_MODEL=gpt-6-luna`, `OPENAI_IMAGE_MODEL=gpt-image-1` (**retired**) | `.env` model ids only |
| Edit size (observed) | `1024x1536`, `input_fidelity=high` | worker journal |

**Confirmed:** GitHub tip with merged PR #41 pose-fidelity source is **not** what production BE/worker runs. Deploying entire `main` BE/worker for this incident is **not** authorized.

## 2. Three failed jobs (operator account only)

| Redacted job id | created_at (UTC) | journal failure (UTC) | type | status | error_message | result_data |
|-----------------|------------------|------------------------|------|--------|---------------|-------------|
| `ad2379e2` | 22:33:45 | 22:33:53 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |
| `22b60b16` | 22:34:16 | 22:34:24 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |
| `17bc3bb7` | 22:36:51 | 22:36:57 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |

All three: vision/chat **200** → `images.edit` attempted with retired `gpt-image-1` → HTTP **400** / `BadRequestError` → no image bytes → no look saved. Provider `code` / `request_id` **not** persisted on deployed sanitizer.

## 3. Failure category — verified vs unknown

### Verified

1. Failures after successful vision/chat, on single `images.edit` (`max_retries=0`).
2. HTTP 400 + `BadRequestError` for all three.
3. Production still points at shut-down `gpt-image-1` (official retirement 2026-10-23).
4. Not a global Magic outage before shutdown window (prior completed `images.edit` jobs).
5. Swimwear is a legitimate FashionRise product requirement — not proven as policy refusal.

### Not verified

- Exact historical provider `error.code` per job (unavailable).
- Whether any individual 400 also carried an unrelated invalid-parameter code.
- Edit-call billing for HTTP 400 responses.

## 4. Billing assessment

| Stage | Reached? | Billable? |
|-------|----------|-----------|
| Chat Completions | Yes (200) | Likely yes — cents not pulled |
| `images.edit` | Attempted; 400 | Unknown |
| Stored look | No | N/A |

## 5. PR #55 observability scope (this PR only)

Hardening (not deployed):

- Strict allowlists for `error_category`, `stage`, `error_type`, `provider_code`.
- Recognized safety codes include `moderation_blocked` and `content_policy_violation`.
- Ordinary HTTP 400 **without** a confirmed safety code → `provider_bad_request` (never content-policy).
- Model-unavailable (`model_not_found`) distinguished from policy / quota / rate-limit / auth.
- Validated `request_id`; never persist raw bodies, moderation_details, prompts, images, credentials.
- API `AIJobRead` re-normalizes `result_data.error` through the same allowlists; owner-only job access preserved.
- Mock tests cover moderation refusal, plain 400, unknown codes, quota, model_not_found, API leakage, sensitive redaction.

**PR #55 does not change the production image model.** Model migration is a separate draft PR.

## 6. Proposed supported replacement (separate PR)

Preferred: **`gpt-image-2.5-sunburst`** (precision editing). Alternative for later eval: `gpt-image-2.5-flare`.  
See the migration PR for capability table, parameter choices (`input_fidelity` omitted for Sunburst), cost estimate, and production isolation plan off `2cbc1ad0`.

## 7. Exact next Technical PM decision

1. Re-review amended PR #55 (observability only) — still **no merge/deploy** until authorized.
2. Review separate Sunburst migration draft PR + offline maintenance isolation branch based on `2cbc1ad0`.
3. Later authorize a bounded maintenance release (observability + model migration only; **exclude** undeployed PR #41) and optionally one budget-bounded production Magic validation on the supported model.

**STOP** — no production changes from this documentation/code track alone.
