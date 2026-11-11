#!/usr/bin/env bash
# Pick an available 13-inch iPadOS Simulator for App Store screenshots.
# Requires iPad Pro (13-inch) or iPad Air (13-inch). Fails closed otherwise.
# Prints one line: UDID|NAME|RUNTIME
#
# Usage: codemagic-pick-ipad-simulator.sh
# Optional: FR_SIMCTL_LIST_JSON=/path/to/simctl-list.json (offline tests)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

if [[ -n "${FR_SIMCTL_LIST_JSON:-}" ]]; then
  LIST_JSON="$(cat "$FR_SIMCTL_LIST_JSON")"
else
  LIST_JSON="$(xcrun simctl list devices available -j)"
fi
export LIST_JSON

python3 - <<'PY'
import json, os, sys
from fr_ipad_screenshot_lib import pick_13_inch_ipad

data = json.loads(os.environ["LIST_JSON"])
try:
    udid, name, runtime = pick_13_inch_ipad(data)
except ValueError as exc:
    print(f"codemagic-pick-ipad-simulator: FAIL — {exc}", file=sys.stderr)
    sys.exit(1)

print(f"{udid}|{name}|{runtime}")
print(
    f"codemagic-pick-ipad-simulator: selected name={name!r} runtime={runtime!r}",
    file=sys.stderr,
)
PY
