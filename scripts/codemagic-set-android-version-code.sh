#!/usr/bin/env bash
# FashionRise — pick a monotonic Android versionCode for Codemagic Play AABs.
#
# versionCode = PROJECT_BUILD_NUMBER + ANDROID_VERSION_CODE_OFFSET
# Optional: if GOOGLE_PLAY_PACKAGE_NAME + google-play CLI credentials exist,
# require stamp > latest Play build number (fail closed / raise offset).
#
# Writes:
#   /tmp/fr-android-version-code.txt  — numeric versionCode
#   CM_ENV FR_ANDROID_VERSION_CODE / FR_ANDROID_VERSION_NAME
set -euo pipefail

OFFSET="${ANDROID_VERSION_CODE_OFFSET:-0}"
PACKAGE_NAME="${GOOGLE_PLAY_PACKAGE_NAME:-app.fashionrise.studio}"
VERSION_NAME="${ANDROID_VERSION_NAME:-1.0}"

if [[ -z "${PROJECT_BUILD_NUMBER:-}" ]]; then
  echo "ERROR: PROJECT_BUILD_NUMBER is required (Codemagic built-in)" >&2
  exit 1
fi
if ! [[ "$PROJECT_BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PROJECT_BUILD_NUMBER must be a positive integer (got '$PROJECT_BUILD_NUMBER')" >&2
  exit 1
fi
if ! [[ "$OFFSET" =~ ^[0-9]+$ ]]; then
  echo "ERROR: ANDROID_VERSION_CODE_OFFSET must be a non-negative integer (got '$OFFSET')" >&2
  exit 1
fi

STAMP=$((PROJECT_BUILD_NUMBER + OFFSET))
if [[ "$STAMP" -lt 1 ]]; then
  echo "ERROR: computed versionCode $STAMP is < 1" >&2
  exit 1
fi

LATEST=""
if command -v google-play >/dev/null 2>&1; then
  # Best-effort: when Play API credentials are present this fails closed on stale codes.
  set +e
  LATEST=$(google-play get-latest-build-number --package-name "$PACKAGE_NAME" 2>/dev/null)
  GP_RC=$?
  set -e
  if [[ $GP_RC -eq 0 && -n "${LATEST:-}" && "$LATEST" =~ ^[0-9]+$ ]]; then
    if [[ "$STAMP" -le "$LATEST" ]]; then
      echo "ERROR: versionCode $STAMP <= Google Play latest $LATEST for $PACKAGE_NAME" >&2
      echo "Raise ANDROID_VERSION_CODE_OFFSET (currently $OFFSET) so PROJECT_BUILD_NUMBER+offset > $LATEST" >&2
      exit 1
    fi
    echo "Play latest versionCode=$LATEST; using stamp=$STAMP"
  else
    echo "Play latest versionCode unavailable (ok for first upload); using stamp=$STAMP"
  fi
else
  echo "google-play CLI not present; using stamp=$STAMP"
fi

echo "$STAMP" >/tmp/fr-android-version-code.txt
echo "$VERSION_NAME" >/tmp/fr-android-version-name.txt

if [[ -n "${CM_ENV:-}" ]]; then
  {
    echo "FR_ANDROID_VERSION_CODE=$STAMP"
    echo "FR_ANDROID_VERSION_NAME=$VERSION_NAME"
  } >>"$CM_ENV"
fi

echo "OK: Android versionCode=$STAMP versionName=$VERSION_NAME (project=$PROJECT_BUILD_NUMBER offset=$OFFSET)"
