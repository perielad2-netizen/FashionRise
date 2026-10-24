# P1 #54 — Magic image-edit failure investigation

**Issue:** [#54](https://github.com/perielad2-netizen/FashionRise/issues/54)  
**Investigation branch:** `cursor/magic-edit-failure-54-77c6`  
**Scope:** Read-only forensic triage + proposed observability hotfix (not deployed).  
**Paid OpenAI / live Magic retries this run:** **0**

## Safety restrictions observed

- No production DB writes, restarts, Nginx/Cloudflare changes, or deploys.
- No live OpenAI calls; no paid test jobs; operator failed sketches not retried.
- PR #41 Magic pose-fidelity **not** deployed as part of this work.
- Open docs PR [#53](https://github.com/perielad2-netizen/FashionRise/pull/53) and Front/Back architecture PR [#50](https://github.com/perielad2-netizen/FashionRise/pull/50) left untouched (not merged, not overwritten).
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
| Models (names only) | `OPENAI_MODEL=gpt-6-luna`, `OPENAI_IMAGE_MODEL=gpt-image-1` | `.env` key names/values for model ids only |
| Edit size (observed) | `1024x1536`, `input_fidelity=high` | worker journal |

**Confirmed:** GitHub tip with merged PR #41 pose-fidelity source is **not** what production BE/worker runs.

## 2. Three failed jobs (operator account only)

Window: operator screenshots ~01:34–01:36 Asia/Jerusalem on 2026-10-25 → **2026-10-24 22:33–22:37 UTC**.

| Redacted job id | created_at (UTC) | journal failure (UTC) | type | status | error_message | result_data |
|-----------------|------------------|------------------------|------|--------|---------------|-------------|
| `ad2379e2` | 22:33:45 | 22:33:53 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |
| `22b60b16` | 22:34:16 | 22:34:24 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |
| `17bc3bb7` | 22:36:51 | 22:36:57 | `sketch_polish` | `failed` | `sketch image edit failed` | JSON `null` |

Notes:

- Schema has `updated_at` (near create time on claim) — **not** a reliable completion timestamp. Journal times above are the failure times.
- No `error_category` column exists on deployed schema.
- Original sketches remained saved in Studio (operator report + no look image written).

### Per-attempt pipeline

| Check | Job 1 | Job 2 | Job 3 |
|-------|-------|-------|-------|
| Text/vision (`chat/completions`) | HTTP **200** | HTTP **200** | HTTP **200** |
| `images.edit` attempted | Yes (`gpt-image-1`, 1024×1536, `input_fidelity=high`) | Yes | Yes |
| `images/edits` HTTP | **400** | **400** | **400** |
| Logged exception class | `BadRequestError` | `BadRequestError` | `BadRequestError` |
| Image bytes returned | No | No | No |
| Look image saved | No | No | No |
| Provider `code` / `request_id` persisted | **No** (deployed sanitizer logs class only) | No | No |

Same error class for all three. October worker journal count of `image edit failed type=BadRequestError`: **3** (these only).

## 3. Failure category — verified vs unknown

### Verified

1. Failures occur **after** successful vision/chat completion, on the single `images.edit` call (`max_retries=0`).
2. Provider returns **HTTP 400 Bad Request**; SDK surfaces `BadRequestError`.
3. Deployed code maps any missing edit bytes / edit exception to `SketchCompletionError("sketch image edit failed")`, so the UI string alone cannot distinguish causes.
4. Not a global Magic outage: same operator had multiple **completed** `sketch_polish` jobs with `image_provenance=images.edit` on **2026-10-23** (models `gpt-6-luna`).
5. Operator 45-day status counts (same account): **12 completed / 3 failed** — the three failures are exactly this incident cluster.
6. Swimwear / orange outfit clothing category is **not** evidence of content-policy refusal by itself.

### Not verified (missing evidence)

- Exact provider `error.code` / `param` / refusal reason (raw bodies intentionally not logged on `2cbc1ad0`).
- Whether 400 was `content_policy_violation`, `invalid_image*`, unsupported parameter, or another bad-request class.
- Auth / quota / billing as the cause: no 401/403/429 strings in the failure window; no usage API pull performed.
- Any contribution from undeployed PR #41 (not running in prod).

### Ruled out as primary class (for these three)

- Rate limit (would typically be 429).
- Missing sketch decode before edit (edit was attempted with the configured model).
- Empty successful edit response (exception path, not empty-bytes path).

## 4. Billing assessment

| Stage | Reached? | Billable? |
|-------|----------|-----------|
| Chat Completions (vision) | Yes (HTTP 200, all three) | **Likely yes** — request completed successfully; exact usage cents **not** pulled |
| `images.edit` | Attempted; HTTP 400 | **Unknown** — failed requests may or may not appear on the provider invoice |
| Stored look image | No | N/A |

No refunds, usage API mutations, or extra paid calls were initiated.

## 5. Product requirements (compliant handling)

FashionRise must support legitimate apparel including bikinis, two-piece and one-piece swimwear, swim shorts, beachwear, sportswear. Investigation **must not** treat garment type as proof of policy rejection, and **must not** attempt to circumvent genuine provider safety systems.

Recommended product behavior when a true provider safety refusal is later proven via allowlisted `provider_code`:

- Keep the original sketch intact (already true today).
- Show a clear, non-blaming message that the edit could not proceed under provider safety rules.
- Offer retry / redesign guidance without implying FashionRise bans swimwear.

For technical 400s (invalid image/params/etc.), show a distinct technical failure message once `provider_code` / category is known.

## 6. Proposed observability hotfix (in this PR — **do not deploy yet**)

Focused code change (mock-tested; 0 paid AI):

- Extract allowlisted fields from provider exceptions: exception class, HTTP status, approved short `provider_code`, `request_id`, pipeline stage, edit attempted / bytes returned.
- Log those fields; never log/persist raw bodies, prompts, images, or credentials.
- Attach `safe_meta` on `SketchCompletionError`; worker stores only allowlisted keys under `result_data.error` on failure.
- Map known codes (e.g. `content_policy_violation`, rate limit, quota) to clearer user-facing `error_message` strings; keep historical `sketch image edit failed` for unclassified edit failures.

**Deploy caution:** GitHub `main` also contains undeployed PR #41 pose-fidelity edits in `sketch_openai.py`. Any production BE/worker rollout of this hotfix must be **cherry-picked onto `2cbc1ad0`** (or otherwise exclude #41) unless Technical PM separately authorizes pose-fidelity deploy.

## 7. Exact next Technical PM decision

1. Accept this investigation report.
2. Authorize (or reject) a **BE/worker-only** deploy of the observability hotfix **without** PR #41.
3. After observability is live, decide whether one **new** controlled Magic attempt (not a silent retry of the failed blobs) is warranted to capture `provider_code`.
4. Keep PRs [#50](https://github.com/perielad2-netizen/FashionRise/pull/50) and [#53](https://github.com/perielad2-netizen/FashionRise/pull/53) on their own tracks — do not merge them via this incident PR.
