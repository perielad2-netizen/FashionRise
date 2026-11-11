#!/usr/bin/env bash
# Pick an available iPadOS Simulator UDID for App Store screenshot work.
# Prefers 13-inch iPad Pro / Air (Apple-accepted tablet screenshot class), then
# 12.9-inch Pro, then any iPad Pro/Air. Prints one line: UDID|NAME|RUNTIME
#
# Usage: codemagic-pick-ipad-simulator.sh
# Optional: FR_SIMCTL_LIST_JSON=/path/to/simctl-list.json (offline tests)
set -euo pipefail

if [[ -n "${FR_SIMCTL_LIST_JSON:-}" ]]; then
  LIST_JSON="$(cat "$FR_SIMCTL_LIST_JSON")"
else
  LIST_JSON="$(xcrun simctl list devices available -j)"
fi
export LIST_JSON

python3 - <<'PY'
import json, os, re, sys

data = json.loads(os.environ["LIST_JSON"])
devices = data.get("devices") or {}

candidates = []
for runtime, rows in devices.items():
    if "iOS" not in runtime and "iPadOS" not in runtime:
        continue
    for d in rows or []:
        if not d.get("isAvailable", True):
            continue
        name = str(d.get("name") or "")
        if "iPad" not in name:
            continue
        udid = str(d.get("udid") or "")
        if not udid:
            continue
        candidates.append((name, udid, runtime))

if not candidates:
    print("codemagic-pick-ipad-simulator: FAIL — no available iPad simulators", file=sys.stderr)
    sys.exit(1)

def score(name: str) -> tuple:
    n = name.lower()
    if re.search(r"ipad pro \(13[- ]?inch", n):
        return (100, name)
    if re.search(r"ipad air \(13[- ]?inch", n):
        return (90, name)
    if re.search(r"ipad pro \(12\.9[- ]?inch", n):
        return (80, name)
    if "ipad pro" in n:
        return (50, name)
    if "ipad air" in n:
        return (40, name)
    return (10, name)

candidates.sort(key=lambda row: score(row[0]), reverse=True)
name, udid, runtime = candidates[0]
print(f"{udid}|{name}|{runtime}")
print(
    f"codemagic-pick-ipad-simulator: selected name={name!r} runtime={runtime!r}",
    file=sys.stderr,
)
PY
