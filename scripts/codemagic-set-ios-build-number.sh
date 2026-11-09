#!/usr/bin/env bash
# Stamp a unique CFBundleVersion for FashionRise iOS (Codemagic).
# Marketing version (MARKETING_VERSION / 1.0) is left unchanged.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="${CM_BUILD_DIR:-$ROOT}/web-ui/ios/App"
cd "$APP_DIR"

OFFSET="${IOS_BUILD_NUMBER_OFFSET:-100}"
APP_ID="${APP_STORE_APPLE_ID:?APP_STORE_APPLE_ID is required}"
MARKETING_VERSION_STRING="${IOS_MARKETING_VERSION:-1.0}"

# Fail closed: require Codemagic's project-wide counter. Do not fall back to 0
# or BUILD_NUMBER (workflow-local) — that breaks uniqueness / monotonicity.
if [ -z "${PROJECT_BUILD_NUMBER:-}" ]; then
  echo "ERROR: PROJECT_BUILD_NUMBER is unset. Codemagic must export a positive project build number."
  exit 1
fi
if ! [[ "${PROJECT_BUILD_NUMBER}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PROJECT_BUILD_NUMBER must be a positive integer (got '${PROJECT_BUILD_NUMBER}')"
  exit 1
fi
if ! [[ "${OFFSET}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: IOS_BUILD_NUMBER_OFFSET must be a positive integer (got '${OFFSET}')"
  exit 1
fi

PROJECT_BN="${PROJECT_BUILD_NUMBER}"

latest_or_0() {
  local line token
  line="$("$@" 2>/dev/null | tail -n 1 || true)"
  token="$(printf '%s\n' "$line" | awk '{print $NF}')"
  if [[ "${token}" =~ ^[0-9]+$ ]]; then
    echo "${token}"
  else
    echo 0
  fi
}

max_num() {
  local a="$1" b="$2"
  if [ "$a" -gt "$b" ]; then echo "$a"; else echo "$b"; fi
}

TF="$(latest_or_0 app-store-connect get-latest-testflight-build-number "$APP_ID" --platform IOS --version-string "$MARKETING_VERSION_STRING")"
TF_ALL="$(latest_or_0 app-store-connect get-latest-testflight-build-number "$APP_ID" --platform IOS)"
AS="$(latest_or_0 app-store-connect get-latest-app-store-build-number "$APP_ID" --platform IOS --version-string "$MARKETING_VERSION_STRING")"
AS_ALL="$(latest_or_0 app-store-connect get-latest-app-store-build-number "$APP_ID" --platform IOS)"
GB="$(latest_or_0 app-store-connect get-latest-build-number "$APP_ID" --platform IOS --all-versions)"

ASC_LATEST=0
for n in "$TF" "$TF_ALL" "$AS" "$AS_ALL" "$GB"; do
  ASC_LATEST="$(max_num "$ASC_LATEST" "$n")"
done

set +e
DECISION_JSON="$(
  python3 "$ROOT/scripts/ios_cfbundle_version.py" \
    --project-build-number "$PROJECT_BN" \
    --offset "$OFFSET" \
    --asc-latest "$ASC_LATEST" \
    --json 2>/tmp/fr-ios-cfbundle-version.err
)"
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ]; then
  echo "ERROR: refused to assign CFBundleVersion (exit=$STATUS)"
  cat /tmp/fr-ios-cfbundle-version.err >&2 || true
  echo "CFBundleVersion inputs: PROJECT_BUILD_NUMBER=$PROJECT_BN BUILD_NUMBER=${BUILD_NUMBER:-unset} offset=$OFFSET asc_latest=$ASC_LATEST tf=$TF/$TF_ALL appstore=$AS/$AS_ALL combined=$GB marketing=$MARKETING_VERSION_STRING"
  exit "$STATUS"
fi

CANDIDATE="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["selected"])' <<<"$DECISION_JSON")"

echo "CFBundleVersion decision: $DECISION_JSON"
echo "CFBundleVersion inputs: PROJECT_BUILD_NUMBER=$PROJECT_BN BUILD_NUMBER=${BUILD_NUMBER:-unset} offset=$OFFSET asc_latest=$ASC_LATEST tf=$TF/$TF_ALL appstore=$AS/$AS_ALL combined=$GB marketing=$MARKETING_VERSION_STRING"
echo "CFBundleVersion selected=$CANDIDATE"
echo "CM_COMMIT=${CM_COMMIT:-unset}"

agvtool new-version -all "$CANDIDATE"
echo "$CANDIDATE" > /tmp/fr-ios-cfbundle-version.txt
echo "Wrote expected CFBundleVersion to /tmp/fr-ios-cfbundle-version.txt"
