# FashionRise — Trust boundary notes (Stage C security amendment)

**Status:** design / verification evidence only. **No production changes applied.**  
**Verdict context:** Stage C → **BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION**

## 1. Verified topology (read-only, 2026-10-20)

```text
Browser
  → Cloudflare Access (edge policy / login)
  → Cloudflare proxy (adds CF-Connecting-IP, etc.)
  → TLS to origin with Authenticated Origin Pull client cert
  → Nginx fashionrise.app (ssl_verify_client on)
  → proxy_pass → 127.0.0.1:8010 (fashionrise-api / Uvicorn)
```

| Layer | Observed |
|---|---|
| Public hostname | `fashionrise.app` — unauthenticated document → Access **302** |
| Nginx AOP | `ssl_client_certificate /etc/fashionrise/aop/ca.crt`; `ssl_verify_client on` |
| Direct origin without client cert | **400** “No required SSL certificate was sent” |
| `$remote_addr` in access log | Cloudflare edge (e.g. `172.70.x.x`), not visitor |
| Current upstream headers | `X-Real-IP $remote_addr`; `X-Forwarded-For $proxy_add_x_forwarded_for` |
| `TRUST_PROXY_HEADERS` | unset → false |
| Other VPS sites | AOP only on `fashionrise.app` (and backup copy). PickWise / CureCompass / kehilabapark unchanged |
| `ngx_http_realip_module` | **Present** (`nginx -V` includes `--with-http_realip_module`; dry `nginx -t -c` with `set_real_ip_from` / `real_ip_header` **OK**) |

### AOP certificate type (no secrets / no private keys)

| Item | Public metadata |
|---|---|
| Trusted CA on origin | Subject/Issuer `CN = FashionRise Private AOP CA` (self-signed private CA) |
| CA validity | NotBefore 2026-10-19 · NotAfter 2031-10-18 |
| CA SHA-256 fingerprint | `53:61:C6:45:14:26:9E:E5:81:D2:9C:20:F9:4C:4E:A3:85:DB:19:C2:CE:6E:39:3E:55:33:D8:F2:71:CA:BF:CA` |
| Client cert (uploaded to Cloudflare for pulls) | Subject `CN = FashionRise Cloudflare AOP Client`, issued by the private CA above |
| Client validity | ~1 year from 2026-10-19 |
| Client SHA-256 fingerprint | `83:81:C8:91:E9:EA:7D:B1:1D:96:DB:F4:D4:6C:A6:8A:86:F1:6D:DE:51:0A:70:10:D7:AC:16:60:26:78:02:FD` |

**Classification:** This is **not** Cloudflare’s **global** shared AOP certificate. It is a **FashionRise-private CA + client certificate** (zone-level or per-hostname custom AOP pattern). Origin trusts only certs signed by this private CA.

**Implication:** Global-AOP “any Cloudflare account” weakness does **not** apply to the mTLS layer as configured. Possession of FashionRise’s AOP **client private key** (or a CF config that presents that client cert) would still be required to satisfy origin mTLS.

**Dashboard confirmation (PENDING):** Operator must confirm in Cloudflare SSL/TLS → Origin Server / Authenticated Origin Pulls that the **active** zone-level or per-hostname client certificate matches fingerprint `83:81:C8:91:…:02:FD` (FashionRise Cloudflare AOP Client). Document rotation: replace client cert before NotAfter 2027-10-19; revoke old cert in CF; keep origin CA trust aligned. **Do not** paste private keys into tickets.

**Still insufficient alone for Access policy binding:** AOP proves “Cloudflare pulled with FashionRise’s AOP client.” It does **not** validate that the HTTP request carried a valid **Cloudflare Access JWT** for this application’s AUD. Edge Access 302 for anonymous browsers is necessary but not origin-enforced Access. **Edge-only residual risk is not approved.** Design: `docs/deploy/WEB-V3B-ORIGIN-ACCESS-JWT-DESIGN.md`.

## 2. Decision Gate 0 (revised) — prefer Option B

**Preferred:** Nginx `real_ip` with **explicit** Cloudflare IPv4/IPv6 CIDRs, then overwrite upstream headers from normalized `$remote_addr`.

**Rejected as primary design:** unconditionally forwarding `$http_cf_connecting_ip` without first proving the TCP peer is a trusted Cloudflare edge (`set_real_ip_from`).

See `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md` for the FashionRise-scoped snippet and inheritance rules.

### Cloudflare IP range maintenance

- Official lists: https://www.cloudflare.com/ips-v4 · https://www.cloudflare.com/ips-v6  
- Snapshot counts fetched 2026-10-20: **14** IPv4 prefixes, **6** IPv6 prefixes (do not hard-code forever; re-fetch before Stage D).
- Update procedure (Stage D ops): pull lists → replace FashionRise-only `set_real_ip_from` block → `nginx -t` → reload → negative tests.
- Rollback: restore previous site file from `/var/backups/fashionrise/…`.

**Never** use `set_real_ip_from 0.0.0.0/0` or trust all peers.

## 3. Access JWT / origin binding (proposed; not implemented)

| Control | Current | Gap |
|---|---|---|
| Edge Access | Enforced (302 without session) | OK for browser path |
| Custom AOP | FashionRise-private CA | Stronger than global AOP |
| Origin Access JWT validation | **Absent** (no `CF-Access-Jwt-Assertion` check in FastAPI; no AUD/team domain in `.env` keys) | Origin does not independently bind requests to this Access application |

### Least-disruptive secure options (design only)

1. **Keep custom AOP** (already present) — confirm in Cloudflare dashboard that zone-level or per-hostname AOP uses the FashionRise client cert (operator check; Cursor cannot mutate CF).
2. **Add origin Access JWT validation** (recommended defense-in-depth for Stage D or a follow-on hardening PR):
   - Validate `CF-Access-Jwt-Assertion` (or `Cf-Access-Jwt-Assertion`) against Cloudflare’s JWKS for the team domain.
   - Enforce audience (`AUD`) matching the FashionRise Access application.
   - Fail closed on missing/invalid JWT for application routes (with a documented health/exception path if any).
   - Testable: valid session JWT accepted; forged/missing/wrong-AUD rejected; direct origin without JWT rejected even if somehow TLS-authenticated.
3. **Do not** treat “anonymous 302 + AOP 400” alone as proof that another Cloudflare account cannot reach the origin application plane.

**Stage D must not claim Access-bound origin until JWT validation is implemented/verified or PM explicitly accepts edge-only Access with documented residual risk.**

## 4. Negative / isolation test plan (before TRUST_PROXY_HEADERS=true)

Execute only after approved Nginx Option B staging or carefully scoped prod change window (not Stage C).

| # | Case | Expected |
|---|---|---|
| N1 | Forged client `X-Real-IP` / `X-Forwarded-For` from trusted CF peer | Upstream key uses `real_ip`-normalized visitor; forged headers overwritten, not appended |
| N2 | Forged `CF-Connecting-IP` from **non**-Cloudflare peer | `$remote_addr` unchanged (not in `set_real_ip_from`); request should still fail AOP without FashionRise client cert |
| N3 | Missing `CF-Connecting-IP` from CF peer | **Fail closed (chosen):** do not silently rate-limit on shared edge IP. Prefer Nginx `if` / map that returns **400** for API locations when `$http_cf_connecting_ip` is empty **after** peer matched `set_real_ip_from`, **or** omit `X-Real-IP` and keep `TRUST_PROXY_HEADERS` path failing closed to a non-shared internal deny. Exact directive must be staging-tested; silent edge-bucket accept is **forbidden**. |
| N4 | Malformed IP in `CF-Connecting-IP` | real_ip leaves `$remote_addr` as edge; treat like N3 (fail closed for API) + FastAPI rejects bad `X-Real-IP` via `ipaddress` / duplicate headers |
| N5 | Direct origin attempt, no client cert | **400** AOP |
| N6 | Direct origin with stolen/wrong client cert | Fail verify (not FashionRise CA) |
| N7 | Two distinct legitimate Access clients | Distinct rate-limit buckets after Option B + `TRUST_PROXY_HEADERS=true` |
| N8 | PickWise / CureCompass / kehilabapark | Unaffected (`nginx -T` shows no FashionRise real_ip leak into other server blocks) |
| N9 | Access JWT missing/forged (once JWT gate exists) | **401/403** at origin |

## 5. Invitation code-file path (principal: `fashionriseapp`)

| Bad example | Why |
|---|---|
| `/root/.fashionrise-invites/…` | API/CLI as `fashionriseapp` cannot create under `/root` |

| Approved pattern | Details |
|---|---|
| Directory | `/var/lib/fashionrise/invites/` (under home `/var/lib/fashionrise`) |
| Dir mode | `0700`, owner `fashionriseapp:fashionriseapp` |
| File | **New** file only (`O_EXCL`), mode `0600`, refuse symlinks / existing paths |
| On delivery failure | Auto-revoke invitation (existing CLI behavior) |
| Delivery | Out-of-band; never paste codes into tickets/chats/agent logs |

### Invite path readiness check (read-only, 2026-10-20)

| Check | Result |
|---|---|
| Parent `/var/lib/fashionrise` | Owner `fashionriseapp:fashionriseapp`, mode `750` (`drwxr-x---`); ancestry `/` → `var` → `lib` are root-owned normal dirs (**no symlink** in `namei -l`) |
| `/var/lib/fashionrise/invites` | **Absent** today — create in Stage D as `fashionriseapp`: `mkdir -m 700 invites` (do **not** rely on CLI `mkdir(parents=True)` alone for mode) |
| Execution user | `fashionriseapp` (systemd `User=` / nologin home) can write under home |
| Invitations created | **None** (Stage C / this amendment) |

## 6. Uvicorn peer vs SlowAPI fallback

Production: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010` (uvicorn **0.31.1**).

Default **`--proxy-headers` enabled**; trusted hosts default **`127.0.0.1`**. When Nginx on localhost sends `X-Forwarded-For`, `ProxyHeadersMiddleware` may rewrite `scope["client"]` from that header. Therefore SlowAPI’s `get_remote_address` fallback is **post-middleware** client host — **not** guaranteed to be literal `127.0.0.1`.

**Until Option B overwrites XFF with a single visitor IP**, forged or appended XFF from the browser→CF→Nginx chain can influence the ASGI peer. Mitigation path: Option B overwrite + `TRUST_PROXY_HEADERS=true` with PR #23 parser; consider `--forwarded-allow-ips=` empty or `--no-proxy-headers` only under a separate approved change if needed.

## 7. Option B verification checklist (not executed)

Before `TRUST_PROXY_HEADERS=true` in production:

1. Install FashionRise-only `set_real_ip_from` with **full current** Cloudflare IPv4 **and** IPv6 CIDRs (re-fetch https://www.cloudflare.com/ips-v4 and ips-v6).
2. `real_ip_header CF-Connecting-IP;`
3. Overwrite `X-Real-IP` / `X-Forwarded-For` with `$remote_addr` on **login, refresh, logout, me, register, designs**.
4. `nginx -T` proves other vhosts unchanged.
5. Execute N1–N9 including two-client bucket isolation and IPv6 client.
6. Deploy PR #23 parser first.
7. Only then set `TRUST_PROXY_HEADERS=true`.

## 8. Separate code / docs artifacts

| Artifact | Role |
|---|---|
| Draft PR #23 | Strict SlowAPI `ipaddress` + duplicate-header fail-closed |
| `WEB-V3B-ORIGIN-ACCESS-JWT-DESIGN.md` | Origin Access JWT/AUD design (**required** before activation) |
| Draft PR #21 | Stage B docs — **merge first** when authorized; then rebase #22 |
| Draft PR #22 | This trust-boundary pack — stay **BLOCKED**; do not merge until #21 reconciled |

## 9. Outstanding (unchanged blockers)

1. CF dashboard AOP client match confirmation + rotation notes.
2. Option B live verification + N3 fail-closed directive staging.
3. Origin Access JWT implementation after design approval.
4. PR #23 merge/deploy authorization.
5. Genuine expired Access session test (**PENDING**).
6. PR #21 merge → rebase/reconcile #22; preserve Stage B operator **6/6 PASS**.

**Verdict remains `BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION`.**
