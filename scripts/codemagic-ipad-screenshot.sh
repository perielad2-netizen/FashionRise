#!/usr/bin/env bash
# Capture one native-resolution simulator PNG for a *specific* UDID.
# Prefer the generated ~/bin/fr-ipad-shot wrapper (hardwired UDID + dirs).
#
# Usage:
#   codemagic-ipad-screenshot.sh --udid UDID --out DIR [--export DIR] [label]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

UDID=""
OUT_DIR=""
EXPORT_DIR=""
LABEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --udid)
      UDID="${2:-}"
      shift 2
      ;;
    --out)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --export)
      EXPORT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 --udid UDID --out DIR [--export DIR] [label]" >&2
      exit 0
      ;;
    *)
      LABEL="$1"
      shift
      ;;
  esac
done

if [[ -z "$UDID" || -z "$OUT_DIR" ]]; then
  echo "fr-ipad-shot: FAIL — require --udid and --out (use generated ~/bin/fr-ipad-shot)" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Confirm the target device is booted (explicit UDID — never ambiguous 'booted').
if ! xcrun simctl list devices | grep "$UDID" | grep -q Booted; then
  echo "fr-ipad-shot: FAIL — simulator $UDID is not Booted" >&2
  exit 1
fi

label="$(printf '%s' "$LABEL" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-//;s/-$//')"

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
# Explicit device UDID — do not use 'booted' when multiple sims may exist.
xcrun simctl io "$UDID" screenshot "$dest"
test -s "$dest"

# Fail loud if dimensions are not an Apple-accepted 13-inch size.
python3 - <<PY
from fr_ipad_screenshot_lib import assert_accepted_ipad_13_dimensions
w, h = assert_accepted_ipad_13_dimensions("$dest")
print(f"fr-ipad-shot: ok size={w}x{h} path=$dest")
PY

if [[ -n "$EXPORT_DIR" ]]; then
  mkdir -p "$EXPORT_DIR"
  cp -f "$dest" "$EXPORT_DIR/$name"
fi

ls -la "$dest"
