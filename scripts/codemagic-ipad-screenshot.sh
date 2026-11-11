#!/usr/bin/env bash
# Capture the booted iOS Simulator display at native resolution.
# Sequential PNGs land in FR_IPAD_SCREENSHOT_DIR (and CM_EXPORT_DIR mirror).
#
# Usage:
#   fr-ipad-shot
#   fr-ipad-shot studio-home
#   codemagic-ipad-screenshot.sh [optional-label]
set -euo pipefail

OUT_DIR="${FR_IPAD_SCREENSHOT_DIR:-${CM_EXPORT_DIR:-$PWD}/ipad-screenshots}"
mkdir -p "$OUT_DIR"

# Require a booted device (do not invent UDIDs).
if ! xcrun simctl list devices booted | grep -q 'Booted'; then
  echo "fr-ipad-shot: FAIL — no booted simulator (open Simulator / boot first)" >&2
  exit 1
fi

label_raw="${1:-}"
label="$(printf '%s' "$label_raw" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-//;s/-$//')"

next=1
shopt -s nullglob
for f in "$OUT_DIR"/shot-*.png; do
  base="$(basename "$f")"
  num="${base#shot-}"
  num="${num%%-*}"
  num="${num%.png}"
  if [[ "$num" =~ ^[0-9]+$ ]]; then
    n=$((10#$num))
    if (( n >= next )); then next=$((n + 1)); fi
  fi
done
shopt -u nullglob

seq="$(printf '%03d' "$next")"
if [[ -n "$label" ]]; then
  name="shot-${seq}-${label}.png"
else
  name="shot-${seq}.png"
fi

dest="$OUT_DIR/$name"
# Native resolution of the simulator display (not a scaled desktop grab).
xcrun simctl io booted screenshot "$dest"
# Fail closed if the file is missing or empty.
test -s "$dest"

# Mirror into Codemagic export dir so the build ZIP always includes shots.
if [[ -n "${CM_EXPORT_DIR:-}" ]]; then
  mkdir -p "$CM_EXPORT_DIR/ipad-screenshots"
  cp -f "$dest" "$CM_EXPORT_DIR/ipad-screenshots/$name"
fi

echo "fr-ipad-shot: wrote $dest"
ls -la "$dest"
