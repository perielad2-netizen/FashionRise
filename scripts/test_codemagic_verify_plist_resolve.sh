#!/usr/bin/env bash
# Regression: app Info.plist resolution must use Payload/*.app/Info.plist only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/Payload/App.app/Frameworks/Foo.framework"
printf 'app' >"$TMP/Payload/App.app/Info.plist"
printf 'framework' >"$TMP/Payload/App.app/Frameworks/Foo.framework/Info.plist"

PLIST_LIST_FILE="$(mktemp)"
find "$TMP/Payload" -mindepth 2 -maxdepth 2 -name Info.plist 2>/dev/null | sort >"$PLIST_LIST_FILE"
PLIST_COUNT="$(wc -l <"$PLIST_LIST_FILE" | tr -d ' ')"
if [ "$PLIST_COUNT" != "1" ]; then
  echo "FAIL: expected exactly one depth-2 Info.plist, got $PLIST_COUNT"
  cat "$PLIST_LIST_FILE"
  exit 1
fi
PLIST="$(head -n 1 "$PLIST_LIST_FILE")"
rm -f "$PLIST_LIST_FILE"
case "$PLIST" in
  */Payload/*.app/Info.plist) ;;
  *)
    echo "FAIL: unexpected plist path $PLIST"
    exit 1
    ;;
esac
if [ "$(cat "$PLIST")" != "app" ]; then
  echo "FAIL: selected framework plist instead of app plist"
  exit 1
fi

# Ambiguous: two .app bundles
mkdir -p "$TMP/Payload/Other.app"
printf 'other' >"$TMP/Payload/Other.app/Info.plist"
COUNT="$(find "$TMP/Payload" -mindepth 2 -maxdepth 2 -name Info.plist | wc -l | tr -d ' ')"
if [ "$COUNT" != "2" ]; then
  echo "FAIL: expected ambiguous count 2, got $COUNT"
  exit 1
fi

echo "test_codemagic_verify_plist_resolve: ok"
