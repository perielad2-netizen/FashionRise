# Magic capacity — parallel AI workers (A now, B when downloads grow)

**Goal:** When several designers press Magic at once, each should wait roughly the OpenAI time (~35–45s), not a long queue.

## How Magic runs today (after option A)

Jobs sit in Postgres (`ai_jobs`). Each **AI worker process** claims one job at a time (`SKIP LOCKED`) and waits on OpenAI.

| Parallel workers | If 25 people press Magic together | Last person waits about |
| --- | --- | --- |
| **1** (old) | 1 at a time | ~15–20 min |
| **3** (option A — live target) | 3 at a time | ~5–7 min |
| **8–12** (option B) | 8–12 at a time | ~2–3 min |
| **25** | all at once | ~35–45s |

OpenAI still has to allow that many image calls at once (rate limits). Workers alone cannot beat the provider cap.

---

## Option A — now (this VPS, ~$0 extra)

**What:** Run **3** systemd instances: `fashionrise-ai-worker@1` … `@3`.

**Why 3 on the current box:** Shared London VPS (~2 vCPU / 8 GB) also runs PickWise, CureCompass, Postgres, etc. Magic is mostly waiting on OpenAI (network), so 3 idle workers are cheap (~20 MB each). More than ~3–4 risks RAM/swap pressure when Magics peak together.

**Apply / change count (on VPS as root):**

```bash
cd /opt/fashionrise/src
bash deploy/enable_ai_worker_instances.sh 3
systemctl list-units 'fashionrise-ai-worker@*'
```

**Rollback to 1 worker:**

```bash
bash deploy/enable_ai_worker_instances.sh 1
```

**Restart after code deploys** (all instances):

```bash
systemctl restart 'fashionrise-ai-worker@*.service'
# or named:
systemctl restart fashionrise-ai-worker@{1,2,3}.service
```

Legacy unit `fashionrise-ai-worker.service` (no `@`) is **disabled** once the template is enabled.

---

## Option B — when downloads / concurrent Magic grow

**What:** New **dedicated** Vultr box for AI workers only (API/UI stay on current VPS or move later).

### Vultr price (8 vCPU / 16 GB) — as of late 2026

| Plan | Specs | Typical price |
| --- | --- | --- |
| **High Performance** (shared vCPU) | 8 vCPU · 16 GB · 350 GB NVMe · 8 TB | **~$96/mo** (~$0.14/hr) |
| **CPU Optimized** (dedicated vCPU) | 8 vCPU · 16 GB | **~$160–180/mo** |

London / Tel Aviv list the High Performance 8/16 at **$96/mo** (São Paulo higher). Confirm in the Vultr control panel before buying. **AI/OpenAI $ is separate.**

On that box run **8–12** worker instances (`enable_ai_worker_instances.sh 8` … `12`) pointing at the same Postgres (private network / secure DB URL).

### When to buy B (downloads + Magic pressure)

Use **downloads** as a growth signal, but trigger B on **Magic wait pain**, not vanity MAU alone:

| Signal | Stay on A (3 workers) | Do B (8+ vCPU / 16 GB worker box) |
| --- | --- | --- |
| App downloads (lifetime) | under ~**5k–10k** | past ~**10k–25k** *and* Magic queues regularly |
| Concurrent Magic presses | rare spikes of ≤5 | regular spikes of **10+** designers |
| P95 Magic wait (queue + OpenAI) | usually **&lt; ~2–3 min** | often **&gt; ~3–4 min** or designers complain |
| VPS swap / load | swap quiet during Magic peaks | swap climbing / API feels slow while Magic runs |

**Rule of thumb:**  
- **&lt; ~5k downloads / quiet Magic** → keep A.  
- **~10k+ downloads** or **10+ Magics at once** often → buy B (~$96/mo High Performance 8/16).  
- Aiming for **~25 Magics each ~40s** → B plus **~25 worker slots** and OpenAI limit headroom (may need a second worker box or larger plan later).

---

## What this does *not* fix

- OpenAI TPM/RPM / image concurrency limits  
- Stars / billing  
- Slow mobile Wi‑Fi (client network)  
- Single shared Postgres under huge write load (later: bigger DB or connection pooling)

---

## Quick owner check

1. Press Magic from 2–3 accounts at once → all should finish near ~40–90s (not one after another for many minutes).  
2. `systemctl is-active fashionrise-ai-worker@{1,2,3}` → all `active`.  
3. Journal: `journalctl -u 'fashionrise-ai-worker@*' -n 50 --no-pager`.
