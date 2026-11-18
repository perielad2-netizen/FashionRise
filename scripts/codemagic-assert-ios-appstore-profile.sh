#!/usr/bin/env bash
# Fail closed before archive when the App Store distribution profile is missing
# Push Notifications and/or Associated Domains (Codemagic exit 65 root cause).
#
# Usage (Codemagic, after `xcode-project use-profiles`):
#   scripts/codemagic-assert-ios-appstore-profile.sh [bundle_id]
#
# Expected entitlements (must match App/AppRelease.entitlements):
#   - aps-environment (production on App Store profiles)
#   - com.apple.developer.associated-domains
set -euo pipefail

BUNDLE_ID="${1:-${BUNDLE_ID:-app.fashionrise.studio}}"
PROFILES_DIR="${HOME}/Library/MobileDevice/Provisioning Profiles"

if [ ! -d "$PROFILES_DIR" ]; then
  echo "ERROR: no provisioning profiles directory at: $PROFILES_DIR"
  echo "Run xcode-project use-profiles first, or fetch App Store signing in Codemagic."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FOUND_ANY=0
MATCHED=0
OK_APS=0
OK_ASSOC=0
BEST_NAME=""

shopt -s nullglob
for profile in "$PROFILES_DIR"/*.mobileprovision; do
  FOUND_ANY=1
  DECODED="$TMP_DIR/$(basename "$profile").plist"
  if ! security cms -D -i "$profile" >"$DECODED" 2>/dev/null; then
    echo "WARN: could not decode $(basename "$profile")"
    continue
  fi

  NAME="$(/usr/libexec/PlistBuddy -c 'Print :Name' "$DECODED" 2>/dev/null || true)"
  APP_ID="$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:application-identifier' "$DECODED" 2>/dev/null || true)"
  # application-identifier is TEAMID.bundle.id
  case "$APP_ID" in
    *".$BUNDLE_ID") ;;
    *) continue ;;
  esac

  # Prefer App Store / Distribution profiles (skip development).
  get_task="$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:get-task-allow' "$DECODED" 2>/dev/null || echo true)"
  if [ "$get_task" = "true" ]; then
    continue
  fi

  MATCHED=1
  BEST_NAME="$NAME"
  echo "=== Profile: $NAME ==="
  echo "application-identifier: $APP_ID"

  if /usr/libexec/PlistBuddy -c 'Print :Entitlements:aps-environment' "$DECODED" >/dev/null 2>&1; then
    APS="$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:aps-environment' "$DECODED")"
    echo "aps-environment: $APS"
    OK_APS=1
  else
    echo "aps-environment: MISSING"
  fi

  if /usr/libexec/PlistBuddy -c 'Print :Entitlements:com.apple.developer.associated-domains' "$DECODED" >/dev/null 2>&1; then
    echo "associated-domains: present"
    OK_ASSOC=1
  else
    echo "associated-domains: MISSING"
  fi
done

if [ "$FOUND_ANY" -eq 0 ]; then
  echo "ERROR: no .mobileprovision files under $PROFILES_DIR"
  exit 1
fi

if [ "$MATCHED" -eq 0 ]; then
  echo "ERROR: no App Store (non-development) profile found for bundle id $BUNDLE_ID"
  echo "Codemagic → Code signing identities: fetch/upload an App Store Distribution profile."
  exit 1
fi

if [ "$OK_APS" -eq 1 ] && [ "$OK_ASSOC" -eq 1 ]; then
  echo "OK: profile '$BEST_NAME' includes Push + Associated Domains for $BUNDLE_ID"
  exit 0
fi

cat <<EOF
ERROR: App Store profile '$BEST_NAME' is missing required capabilities for archive.

xcodebuild fails with:
  Provisioning profile doesn't include the Associated Domains capability
  Provisioning profile doesn't include the Push Notifications capability
  Profile doesn't include aps-environment and com.apple.developer.associated-domains

Fix (Apple Developer + Codemagic) — then re-run fashionrise-ios-app-store:
  1. developer.apple.com → Identifiers → $BUNDLE_ID
     Enable: Push Notifications, Associated Domains → Save
  2. Profiles → App Store distribution for $BUNDLE_ID
     Edit/regenerate (or delete + create) so the profile includes those capabilities
     Name often: FashionRise_AppStore_Distribution
  3. Codemagic → Code signing identities → refresh/fetch App Store profiles
     (remove the stale cached FashionRise_AppStore_Distribution if still old)
  4. Re-run workflow fashionrise-ios-app-store on main

Repo entitlements (must stay): web-ui/ios/App/App/AppRelease.entitlements
Operator doc: docs/deploy/NATIVE-PUSH-OPERATOR.md
EOF
exit 1
