# FashionRise iPad Screenshots via Codemagic (Windows-friendly)

**Purpose:** Capture App Store–ready **13-inch iPad** screenshots on a real iPadOS Simulator using Codemagic’s remote Mac + VNC — without owning a Mac or iPad.

**Workflow name in Codemagic:** `FashionRise iPad Screenshots`  
**Workflow id:** `fashionrise-ipad-screenshots`  
**Manual only** (no git trigger). **Does not** publish an IPA, change App Store Connect, enable IAP gates, or create purchases.

Device family stays **iPhone + iPad** (`TARGETED_DEVICE_FAMILY = "1,2"`).

Accepted PNG sizes (Apple 13-inch class): **2064×2752**, **2752×2064**, **2048×2732**, **2732×2048**.

---

## What the workflow does

1. Builds the Capacitor native web bundle from `.env.native` (production API `https://fashionrise.app/api/v1`).
2. Builds an **unsigned simulator `.app`** (not an App Store IPA).
3. Requires an available **13-inch iPad Pro or Air** simulator (fails clearly otherwise — no invent/upscale).
4. Boots that UDID, installs FashionRise, launches it.
5. Installs hardwired helpers `fr-ipad-shot` / `fr-ipad-finish` (absolute paths + Desktop copies) so a **fresh VNC Terminal** works without Codemagic env inheritance.
6. Boot smoke screenshot **must succeed** (dimensions validated) before the VNC hold.
7. Holds until you run **`fr-ipad-finish`** (preferred) or the bounded timeout (default 45 minutes).
8. Exits **successfully** and publishes PNGs under Codemagic **Artifacts** → `ipad-screenshots/`.

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

You should see the remote Mac desktop with **Simulator** running FashionRise. A Desktop README lists the exact helper paths for this session.

### C. Operate FashionRise on the simulated iPad

1. Use the mouse/keyboard in VNC to sign in with your FashionRise account.
2. Navigate the Create / Studio / Stars / Looks screens needed for App Store metadata.
3. Do **not** paste passwords into Codemagic build logs or commit them.
4. Public IAP gates remain OFF — do not flip env gates.

### D. Capture screenshots

On the remote Mac, open **Terminal** (or double-click **Capture-Screenshot.command** on the Desktop) and run:

```bash
fr-ipad-shot
fr-ipad-shot studio-home
fr-ipad-shot stars-shop
```

If `fr-ipad-shot` is not found in a brand-new Terminal, use the absolute path from the Desktop README, for example:

```bash
~/bin/fr-ipad-shot
~/bin/fr-ipad-shot studio-home
```

or the Desktop copy:

```bash
~/Desktop/fr-ipad-shot studio-home
```

Helpers are **hardwired** to this session’s simulator UDID and artifact directory — they do not depend on Codemagic script environment variables.

Each call writes a sequential native-resolution PNG and validates Apple 13-inch dimensions:

- `…/artifacts/ipad-screenshots/shot-001.png`
- `…/artifacts/ipad-screenshots/shot-002-studio-home.png`

### E. Finish successfully and download

1. When finished capturing, run:

```bash
fr-ipad-finish
```

   (or `~/bin/fr-ipad-finish`, or double-click **Finish-Screenshot-Session.command**)

2. **Do not cancel** a successful screenshot session. `fr-ipad-finish` lets the Codemagic step complete and publish Artifacts.
3. Wait until the build status is **successful**.
4. Open the build’s **Artifacts** and download the `ipad-screenshots` PNGs.

Fallback: if you forget `fr-ipad-finish`, the hold ends after the configured minutes and still finishes successfully (as long as at least the smoke screenshot exists).

---

## Safety invariants

| Must | Must not |
|---|---|
| Manual start only | Auto-trigger on push |
| Simulator `.app` only | Build/publish App Store IPA in this workflow |
| 13-inch iPad Pro/Air only | Fall back to unsupported tablets / upscale |
| Hardwired UDID + shot dir in helpers | Rely on ambiguous `simctl io booted` |
| `fr-ipad-finish` → successful build | Cancel a successful session to “download” |
| Production API from `.env.native` | Print tokens / passwords |
| Keep `TARGETED_DEVICE_FAMILY = "1,2"` | Drop iPhone or iPad support |
| Artifacts = screenshots | ASC upload / IAP gate changes |

---

## Related scripts

| Script | Role |
|---|---|
| `scripts/fr_ipad_screenshot_lib.py` | 13-inch picker + PNG dimension rules |
| `scripts/codemagic-pick-ipad-simulator.sh` | Choose 13-inch iPad UDID (fail closed) |
| `scripts/codemagic-ipad-screenshot.sh` | Native PNG for explicit UDID |
| `scripts/codemagic-ipad-screenshots-session.sh` | Boot / install / generate helpers / hold / finish |

Offline tests:

```bash
python3 scripts/test_codemagic_pick_ipad_simulator.py
python3 scripts/test_codemagic_ipad_screenshots_yaml.py
python3 scripts/test_fr_ipad_screenshot_session.py
python3 scripts/assert-codemagic-ios-yaml.py
```
