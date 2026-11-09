#!/usr/bin/env bash
# Bump Codemagic MIN_IOS_BUILD_NUMBER by 1 (ASC CFBundleVersion floor).
# Usage: ./scripts/bump-min-ios-build-number.sh
# Optional: ./scripts/bump-min-ios-build-number.sh --to N
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
YAML="$ROOT/codemagic.yaml"
STATUS="$ROOT/docs/00-PROJECT-STATUS.md"
STORE="$ROOT/docs/STORE-DEPLOY.md"

if [[ ! -f "$YAML" ]]; then
  echo "error: missing $YAML" >&2
  exit 1
fi

current="$(
  sed -nE 's/^[[:space:]]*MIN_IOS_BUILD_NUMBER:[[:space:]]*"([0-9]+)".*/\1/p' "$YAML" | head -n1
)"
if [[ -z "${current}" ]]; then
  echo "error: could not parse MIN_IOS_BUILD_NUMBER from codemagic.yaml" >&2
  exit 1
fi

if [[ "${1:-}" == "--to" ]]; then
  next="${2:?usage: $0 --to N}"
  if ! [[ "$next" =~ ^[0-9]+$ ]]; then
    echo "error: --to requires an integer" >&2
    exit 1
  fi
else
  next=$((current + 1))
fi

python3 - "$YAML" "$current" "$next" <<'PY'
import pathlib, re, sys

path = pathlib.Path(sys.argv[1])
old, new = sys.argv[2], sys.argv[3]
text = path.read_text()
text2, n1 = re.subn(
    r'(MIN_IOS_BUILD_NUMBER:\s*")' + re.escape(old) + r'(")',
    r"\g<1>" + new + r"\g<2>",
    text,
    count=1,
)
text3, n2 = re.subn(
    r'(FLOOR="\$\{MIN_IOS_BUILD_NUMBER:-)' + re.escape(old) + r'(\}")',
    r"\g<1>" + new + r"\g<2>",
    text2,
    count=1,
)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"expected one vars bump and one fallback bump; got vars={n1} fallback={n2}")
path.write_text(text3)
print(f"codemagic.yaml: MIN_IOS_BUILD_NUMBER {old} → {new}")
PY

python3 - "$STATUS" "$STORE" "$current" "$next" <<'PY'
import pathlib, re, sys

status_path = pathlib.Path(sys.argv[1])
store_path = pathlib.Path(sys.argv[2])
old, new = sys.argv[3], sys.argv[4]

def patch(path: pathlib.Path) -> None:
    if not path.exists():
        return
    text = path.read_text()
    text2 = text
    text2 = re.sub(
        rf"(MIN_IOS_BUILD_NUMBER=){re.escape(old)}\b",
        rf"\g<1>{new}",
        text2,
    )
    text2 = re.sub(
        rf"(max\(BUILD_NUMBER,\s*){re.escape(old)}(\))",
        rf"\g<1>{new}\g<2>",
        text2,
    )
    if text2 != text:
        path.write_text(text2)
        print(f"{path}: updated quotes {old} → {new}")
    else:
        print(f"{path}: no floor quotes to update")

patch(status_path)
patch(store_path)
PY

echo "OK: MIN_IOS_BUILD_NUMBER is now $next"
