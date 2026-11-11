# FashionRise iPad Screenshots via Codemagic (Windows-friendly)

**Purpose:** Capture App Store–ready iPad screenshots on a real iPadOS Simulator using Codemagic’s remote Mac + VNC — without owning a Mac or iPad.

**Workflow name in Codemagic:** `FashionRise iPad Screenshots`  
**Workflow id:** `fashionrise-ipad-screenshots`  
**Manual only** (no git trigger). **Does not** publish an IPA, change App Store Connect, enable IAP gates, or create purchases.

Device family stays **iPhone + iPad** (`TARGETED_DEVICE_FAMILY = "1,2"`).

---

## What the workflow does

1. Builds the Capacitor native web bundle from `.env.native` (production API `https://fashionrise.app/api/v1`).
2. Builds an **unsigned simulator `.app`** (not an App Store IPA).
3. Dynamically picks an available iPad simulator (prefers **13-inch iPad Pro**, then **13-inch iPad Air**, then 12.9-inch Pro).
4. Boots Simulator, installs FashionRise, launches it.
5. Installs helper command `fr-ipad-shot` and holds the Mac for a bounded VNC session (default **45 minutes**).
6. Collects PNGs into Codemagic **Artifacts** under `ipad-screenshots/`.

---

## Windows operator steps

### A. Start the workflow

1. Open the FashionRise app in [Codemagic](https://codemagic.io).
2. Click **Start new build**.
3. Select branch (usually `main` after merge) and workflow **FashionRise iPad Screenshots**.
4. **Check Enable SSH/VNC access** before starting (required every build).
5. Start the build. Wait until scripts reach **Boot iPad, launch FashionRise, hold for VNC screenshots**.

### B. Connect with VNC from Windows

1. Install [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/) (or another VNC client).
2. In the Codemagic build page, expand **Explore build machine via SSH or VNC/RDP client**.
3. Copy **Host**, **Port**, **Username**, **Password** (one-time; expire when the build ends).
4. In VNC Viewer, connect to `HOST:PORT` (example: `192.159.66.83:16543`).
5. Enter Username + Password when prompted. Continue past the certificate warning if shown.

You should see the remote Mac desktop with **Simulator** running FashionRise.

### C. Operate FashionRise on the simulated iPad

1. Use the mouse/keyboard in VNC to sign in with your FashionRise account.
2. Navigate the Create / Studio / Stars / Looks screens needed for App Store metadata.
3. Do **not** paste passwords into Codemagic build logs or commit them.
4. Public IAP gates remain OFF — Sandbox/allowlist behavior matches production config; do not flip env gates.

### D. Capture screenshots

On the remote Mac, open **Terminal** (or use the Desktop README) and run:

```bash
fr-ipad-shot
fr-ipad-shot studio-home
fr-ipad-shot stars-shop
```

Each call writes a sequential native-resolution PNG:

- `…/artifacts/ipad-screenshots/shot-001.png`
- `…/artifacts/ipad-screenshots/shot-002-studio-home.png`
- …

`xcrun simctl io booted screenshot` captures the **simulator display**, not a scaled desktop grab.

### E. End the session and download

1. When finished, **Cancel** the Codemagic build (stops the hold early) **or** wait for the hold timer.
2. After the build finishes, open the build’s **Artifacts**.
3. Download the `ipad-screenshots` PNGs (also mirrored under Codemagic’s export ZIP when present).

---

## Safety invariants

| Must | Must not |
|---|---|
| Manual start only | Auto-trigger on push |
| Simulator `.app` only | Build/publish App Store IPA in this workflow |
| Production API from `.env.native` | Print tokens / passwords |
| Keep `TARGETED_DEVICE_FAMILY = "1,2"` | Drop iPhone or iPad support |
| Bounded VNC hold | Leave the VM running indefinitely |
| Artifacts = screenshots | ASC upload / IAP gate changes |

---

## Related scripts

| Script | Role |
|---|---|
| `scripts/codemagic-pick-ipad-simulator.sh` | Choose best available iPad UDID |
| `scripts/codemagic-ipad-screenshot.sh` | Native simulator PNG (`fr-ipad-shot`) |
| `scripts/codemagic-ipad-screenshots-session.sh` | Boot / install / launch / hold |

Offline picker test: `python3 scripts/test_codemagic_pick_ipad_simulator.py`
