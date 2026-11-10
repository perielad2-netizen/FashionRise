#!/usr/bin/env bash
# Verify the single FashionRise App.ipa exists, is non-empty, and embeds the
# expected CFBundleVersion / marketing version / bundle id from the app plist.
# Does NOT copy the IPA elsewhere (duplicate copies caused Codemagic ASC
# publish to upload the same binary twice → 90189).
set -euo pipefail

IPA_PATH="${1:-${CM_BUILD_DIR:-}/web-ui/ios/App/build/ios/ipa/App.ipa}"
EXPECTED_FILE="${2:-/tmp/fr-ios-cfbundle-version.txt}"
EXPECTED_BUNDLE_ID="${EXPECTED_IOS_BUNDLE_ID:-app.fashionrise.studio}"
EXPECTED_MARKETING="${EXPECTED_IOS_MARKETING_VERSION:-1.0}"

if [ ! -f "$IPA_PATH" ]; then
  echo "ERROR: App.ipa missing after build-ipa"
  echo "expected=$IPA_PATH"
  ls -la "$(dirname "$IPA_PATH")" 2>/dev/null || true
  find "${CM_BUILD_DIR:-.}/web-ui/ios/App" -name '*.ipa' 2>/dev/null || true
  exit 1
fi

SIZE="$(stat -f%z "$IPA_PATH" 2>/dev/null || stat -c%s "$IPA_PATH")"
if [ -z "$SIZE" ] || [ "$SIZE" -le 0 ]; then
  echo "ERROR: App.ipa is empty (size=${SIZE:-unknown}) at $IPA_PATH"
  exit 1
fi

echo "OK: App.ipa ready"
echo "IPA_PATH=$IPA_PATH"
echo "IPA_SIZE_BYTES=$SIZE"
ls -lh "$IPA_PATH"

# Count .ipa files under the clone that publishing might pick up (default **/*.ipa).
CLONE="${CM_BUILD_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
IPA_LIST_FILE="$(mktemp)"
find "$CLONE" -type f -name '*.ipa' 2>/dev/null | sort >"$IPA_LIST_FILE"
IPA_COUNT="$(wc -l <"$IPA_LIST_FILE" | tr -d ' ')"
echo "IPA_COUNT_IN_CLONE=$IPA_COUNT"
while IFS= read -r found; do
  echo "IPA_FOUND=$found"
done <"$IPA_LIST_FILE"
if [ "$IPA_COUNT" != "1" ]; then
  echo "ERROR: expected exactly one .ipa under clone for ASC publish; found $IPA_COUNT"
  echo "Duplicate IPA paths make app-store-connect publish upload the same build twice (90189)."
  rm -f "$IPA_LIST_FILE"
  exit 1
fi
FOUND_IPA="$(head -n 1 "$IPA_LIST_FILE")"
rm -f "$IPA_LIST_FILE"
if [ "$FOUND_IPA" != "$IPA_PATH" ]; then
  echo "ERROR: sole IPA path mismatch"
  echo "expected=$IPA_PATH"
  echo "found=$FOUND_IPA"
  exit 1
fi

if [ ! -f "$EXPECTED_FILE" ]; then
  echo "ERROR: missing expected CFBundleVersion file at $EXPECTED_FILE"
  exit 1
fi
EXPECTED="$(tr -cd '0-9' <"$EXPECTED_FILE")"
if ! [[ "$EXPECTED" =~ ^[0-9]+$ ]]; then
  echo "ERROR: invalid expected CFBundleVersion in $EXPECTED_FILE"
  exit 1
fi

TMP="$(mktemp -d)"
# shellcheck disable=SC2064
trap "rm -rf '$TMP'" EXIT
unzip -q "$IPA_PATH" -d "$TMP"

# Resolve exactly one app Info.plist: Payload/<Name>.app/Info.plist
# (depth 2). Nested framework plists are deeper and must not be selected.
PLIST_LIST_FILE="$(mktemp)"
find "$TMP/Payload" -mindepth 2 -maxdepth 2 -name Info.plist 2>/dev/null | sort >"$PLIST_LIST_FILE"
PLIST_COUNT="$(wc -l <"$PLIST_LIST_FILE" | tr -d ' ')"
echo "APP_INFO_PLIST_COUNT=$PLIST_COUNT"
while IFS= read -r found_plist; do
  echo "APP_INFO_PLIST_CANDIDATE=$found_plist"
done <"$PLIST_LIST_FILE"
if [ "$PLIST_COUNT" = "0" ]; then
  echo "ERROR: missing Payload/*.app/Info.plist inside IPA"
  find "$TMP/Payload" -name Info.plist 2>/dev/null | sed 's/^/FOUND_NESTED_PLIST=/' || true
  rm -f "$PLIST_LIST_FILE"
  exit 1
fi
if [ "$PLIST_COUNT" != "1" ]; then
  echo "ERROR: ambiguous Payload/*.app/Info.plist count=$PLIST_COUNT (expected exactly one app bundle)"
  rm -f "$PLIST_LIST_FILE"
  exit 1
fi
PLIST="$(head -n 1 "$PLIST_LIST_FILE")"
rm -f "$PLIST_LIST_FILE"
case "$PLIST" in
  */Payload/*.app/Info.plist) ;;
  *)
    echo "ERROR: resolved Info.plist is not Payload/*.app/Info.plist: $PLIST"
    exit 1
    ;;
esac
echo "APP_INFO_PLIST=$PLIST"

read_plist_key() {
  local key="$1"
  if [ -x /usr/libexec/PlistBuddy ]; then
    /usr/libexec/PlistBuddy -c "Print :${key}" "$PLIST"
  elif command -v plutil >/dev/null 2>&1; then
    plutil -extract "$key" raw "$PLIST"
  else
    echo "ERROR: neither PlistBuddy nor plutil available to read IPA Info.plist" >&2
    return 1
  fi
}

ACTUAL="$(read_plist_key CFBundleVersion)"
MARKETING="$(read_plist_key CFBundleShortVersionString)"
BUNDLE_ID="$(read_plist_key CFBundleIdentifier)"

echo "IPA CFBundleVersion=$ACTUAL (expected=$EXPECTED)"
echo "IPA CFBundleShortVersionString=$MARKETING (expected=$EXPECTED_MARKETING)"
echo "IPA CFBundleIdentifier=$BUNDLE_ID (expected=$EXPECTED_BUNDLE_ID)"

if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "ERROR: IPA CFBundleVersion mismatch"
  exit 1
fi
if [ "$MARKETING" != "$EXPECTED_MARKETING" ]; then
  echo "ERROR: marketing version mismatch (got $MARKETING, want $EXPECTED_MARKETING)"
  exit 1
fi
if [ "$BUNDLE_ID" != "$EXPECTED_BUNDLE_ID" ]; then
  echo "ERROR: bundle identifier mismatch (got $BUNDLE_ID, want $EXPECTED_BUNDLE_ID)"
  exit 1
fi

# App icon must be compiled into the bundle. Modern Xcode stores it in Assets.car;
# older layouts may also emit AppIcon*.png beside the binary.
APP_DIR="$(dirname "$PLIST")"
ASSETS_CAR="$APP_DIR/Assets.car"
ICON_PNG_COUNT="$(find "$APP_DIR" -maxdepth 1 -type f \( -name 'AppIcon*.png' -o -name 'AppIcon*.PNG' \) 2>/dev/null | wc -l | tr -d ' ')"
echo "APP_DIR=$APP_DIR"
echo "ASSETS_CAR_EXISTS=$([ -f "$ASSETS_CAR" ] && echo yes || echo no)"
echo "APPICON_PNG_COUNT=$ICON_PNG_COUNT"
if [ -f "$ASSETS_CAR" ]; then
  ASSETS_SIZE="$(stat -f%z "$ASSETS_CAR" 2>/dev/null || stat -c%s "$ASSETS_CAR")"
  echo "ASSETS_CAR_BYTES=$ASSETS_SIZE"
  # A real FashionRise icon catalog is tens of KB+; a stub/empty car is suspicious.
  if [ -z "$ASSETS_SIZE" ] || [ "$ASSETS_SIZE" -lt 8192 ]; then
    echo "ERROR: Assets.car is missing or suspiciously small (${ASSETS_SIZE:-0} bytes)"
    exit 1
  fi
elif [ "$ICON_PNG_COUNT" = "0" ]; then
  echo "ERROR: IPA app bundle has neither Assets.car nor AppIcon*.png — purchase sheet will show a placeholder"
  exit 1
fi

echo "OK: single IPA verified with CFBundleVersion=$ACTUAL marketing=$MARKETING bundleId=$BUNDLE_ID"
