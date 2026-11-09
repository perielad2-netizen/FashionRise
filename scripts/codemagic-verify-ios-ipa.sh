#!/usr/bin/env bash
# Verify the single FashionRise App.ipa exists, is non-empty, and embeds the
# expected CFBundleVersion. Does NOT copy the IPA elsewhere (duplicate copies
# caused Codemagic ASC publish to upload the same binary twice → 90189).
set -euo pipefail

IPA_PATH="${1:-${CM_BUILD_DIR:-}/web-ui/ios/App/build/ios/ipa/App.ipa}"
EXPECTED_FILE="${2:-/tmp/fr-ios-cfbundle-version.txt}"

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
PLIST="$(find "$TMP/Payload" -name Info.plist -print 2>/dev/null | head -n 1)"
if [ -z "$PLIST" ]; then
  echo "ERROR: Info.plist not found inside IPA"
  exit 1
fi

if [ -x /usr/libexec/PlistBuddy ]; then
  ACTUAL="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$PLIST")"
  MARKETING="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
elif command -v plutil >/dev/null 2>&1; then
  ACTUAL="$(plutil -extract CFBundleVersion raw "$PLIST")"
  MARKETING="$(plutil -extract CFBundleShortVersionString raw "$PLIST")"
else
  echo "ERROR: neither PlistBuddy nor plutil available to read IPA Info.plist"
  exit 1
fi

echo "IPA CFBundleVersion=$ACTUAL (expected=$EXPECTED)"
echo "IPA CFBundleShortVersionString=$MARKETING"
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "ERROR: IPA CFBundleVersion mismatch"
  exit 1
fi
if [ "$MARKETING" != "1.0" ]; then
  echo "ERROR: marketing version changed unexpectedly (got $MARKETING, want 1.0)"
  exit 1
fi

echo "OK: single IPA verified with CFBundleVersion=$ACTUAL marketing=$MARKETING"
