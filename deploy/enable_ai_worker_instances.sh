#!/usr/bin/env bash
# Enable N parallel FashionRise AI workers (systemd template instances).
# Safe with the existing SKIP LOCKED claimer — each instance picks different jobs.
#
# Usage (on the VPS as root):
#   bash deploy/enable_ai_worker_instances.sh           # default: 3
#   bash deploy/enable_ai_worker_instances.sh 3
#   bash deploy/enable_ai_worker_instances.sh 1          # roll back to single worker
set -euo pipefail

N="${1:-3}"
if ! [[ "$N" =~ ^[1-9][0-9]*$ ]]; then
  echo "usage: $0 <positive-integer-count>" >&2
  exit 2
fi

UNIT_SRC="$(cd "$(dirname "$0")" && pwd)/systemd/fashionrise-ai-worker@.service"
UNIT_DST=/etc/systemd/system/fashionrise-ai-worker@.service

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "missing template: $UNIT_SRC" >&2
  exit 1
fi

install -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload

# Stop legacy single-unit if present (replaced by @1..@N).
if systemctl list-unit-files fashionrise-ai-worker.service &>/dev/null; then
  systemctl disable --now fashionrise-ai-worker.service 2>/dev/null || true
fi

# Disable instances above N, enable 1..N.
for u in $(systemctl list-units --all --no-legend 'fashionrise-ai-worker@*.service' | awk '{print $1}'); do
  idx="${u#fashionrise-ai-worker@}"
  idx="${idx%.service}"
  if [[ "$idx" =~ ^[0-9]+$ ]] && (( idx > N )); then
    systemctl disable --now "fashionrise-ai-worker@${idx}.service" 2>/dev/null || true
  fi
done

INSTANCES=()
for ((i = 1; i <= N; i++)); do
  INSTANCES+=("fashionrise-ai-worker@${i}.service")
done

systemctl enable --now "${INSTANCES[@]}"
systemctl restart "${INSTANCES[@]}"

echo "AI workers active (want=${N}):"
systemctl list-units --no-legend 'fashionrise-ai-worker@*.service' || true
systemctl is-active "${INSTANCES[@]}"
