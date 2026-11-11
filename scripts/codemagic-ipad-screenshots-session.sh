#!/usr/bin/env bash
# After the simulator .app is built: pick an iPad, boot it, install+launch
# FashionRise, install the screenshot helper, then hold the VM for a bounded
# VNC session (manual screenshots from Windows).
#
# Env:
#   FR_IPAD_SCREENSHOT_HOLD_MINUTES  — default 45 (bounded; cancel early in UI)
#   BUNDLE_ID                        — default app.fashionrise.studio
#   FR_SIMULATOR_APP_PATH            — path to App.app (required)
set -euo pipefail

HOLD_MINUTES="${FR_IPAD_SCREENSHOT_HOLD_MINUTES:-45}"
BUNDLE_ID="${BUNDLE_ID:-app.fashionrise.studio}"
APP_PATH="${FR_SIMULATOR_APP_PATH:-}"
ROOT="${CM_BUILD_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SHOT_DIR="${FR_IPAD_SCREENSHOT_DIR:-$ROOT/artifacts/ipad-screenshots}"
HELPER_SRC="$ROOT/scripts/codemagic-ipad-screenshot.sh"
PICK_SRC="$ROOT/scripts/codemagic-pick-ipad-simulator.sh"

if [[ -z "$APP_PATH" || ! -d "$APP_PATH" ]]; then
  echo "codemagic-ipad-screenshots-session: FAIL — set FR_SIMULATOR_APP_PATH to App.app" >&2
  exit 1
fi
if [[ ! -f "$HELPER_SRC" || ! -f "$PICK_SRC" ]]; then
  echo "codemagic-ipad-screenshots-session: FAIL — helper scripts missing under $ROOT/scripts" >&2
  exit 1
fi

chmod +x "$HELPER_SRC" "$PICK_SRC"
mkdir -p "$SHOT_DIR"
export FR_IPAD_SCREENSHOT_DIR="$SHOT_DIR"
if [[ -n "${CM_EXPORT_DIR:-}" ]]; then
  mkdir -p "$CM_EXPORT_DIR/ipad-screenshots"
fi

# Install a short name on PATH for the VNC operator.
mkdir -p "$HOME/bin"
cp -f "$HELPER_SRC" "$HOME/bin/fr-ipad-shot"
chmod +x "$HOME/bin/fr-ipad-shot"
export PATH="$HOME/bin:$PATH"

# Desktop pointer for VNC users (no credentials).
DESKTOP="${HOME}/Desktop"
mkdir -p "$DESKTOP"
cat > "$DESKTOP/FashionRise-iPad-Screenshots-README.txt" <<EOF
FashionRise — iPad screenshot session (Codemagic remote Mac)

1. Simulator should already show FashionRise. If not, open Simulator.app.
2. Sign in with your FashionRise account (type carefully — do not paste secrets into logs).
3. Navigate to each App Store screenshot screen.
4. Capture native simulator pixels:
     fr-ipad-shot
     fr-ipad-shot studio-home
5. PNGs are written to:
     $SHOT_DIR
   and mirrored to Codemagic artifacts (ipad-screenshots/).
6. When finished, cancel the Codemagic build from the web UI (or wait for the hold timer).

This workflow does NOT publish an IPA, change ASC, or enable IAP.
EOF

echo "=== Selecting iPad simulator ==="
PICK="$("$PICK_SRC")"
UDID="${PICK%%|*}"
REST="${PICK#*|}"
SIM_NAME="${REST%%|*}"
RUNTIME="${REST##*|}"
echo "Using UDID=$UDID name=$SIM_NAME"

echo "=== Booting Simulator GUI ==="
open -a Simulator --args -CurrentDeviceUDID "$UDID" || open -a Simulator
xcrun simctl boot "$UDID" 2>/dev/null || true
# Wait until booted
for _ in $(seq 1 60); do
  if xcrun simctl list devices | grep "$UDID" | grep -q Booted; then
    break
  fi
  sleep 2
done
xcrun simctl bootstatus "$UDID" -b || true

echo "=== Installing FashionRise (.app) ==="
xcrun simctl uninstall "$UDID" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$UDID" "$APP_PATH"
xcrun simctl launch "$UDID" "$BUNDLE_ID"

# Smoke-capture proves helper + artifacts path before the human VNC session.
"$HOME/bin/fr-ipad-shot" boot-smoke || true

cat <<EOF

============================================================
FashionRise iPad Screenshots — VNC hold (${HOLD_MINUTES} minutes)
============================================================
1) In the Codemagic build page, enable / open VNC (Remote access).
2) On Windows: install RealVNC Viewer (or similar).
3) Connect using Host:Port + Username/Password shown in Codemagic.
4) On the Mac desktop, use Simulator + Terminal:
      fr-ipad-shot
      fr-ipad-shot my-label
5) Screenshots: $SHOT_DIR
6) Download them from the Codemagic build Artifacts after the build ends.
7) Cancel the build when finished to stop billing sooner.

No IPA publish · no ASC changes · no IAP gate changes.
============================================================

EOF

# Bounded hold so the VM stays up for VNC. Operator can cancel early in UI.
HOLD_SECONDS=$((HOLD_MINUTES * 60))
echo "Holding for ${HOLD_MINUTES} minutes (cancel in Codemagic UI when done)..."
sleep "$HOLD_SECONDS"
echo "Hold finished — collecting screenshot artifact mirror"
if [[ -n "${CM_EXPORT_DIR:-}" && -d "$SHOT_DIR" ]]; then
  mkdir -p "$CM_EXPORT_DIR/ipad-screenshots"
  cp -f "$SHOT_DIR"/*.png "$CM_EXPORT_DIR/ipad-screenshots/" 2>/dev/null || true
fi
ls -la "$SHOT_DIR" || true
