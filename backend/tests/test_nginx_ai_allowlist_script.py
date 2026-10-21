"""Offline check for the isolated Nginx AI allowlist verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_ai_allowlist.py"


def test_verify_nginx_ai_allowlist_script_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_NGINX_AI_ALLOWLIST_OK" in proc.stdout
    assert "matrix_ok GET /api/v1/ai/jobs/" in proc.stdout
    assert "matrix_ok POST /api/v1/ai/sketch/polish" in proc.stdout
    # Proposed activation snippet must not use ^~ catch-all for /api/v1/ai/.
    doc = (Path(__file__).resolve().parents[2] / "docs/deploy/PROPOSED-NGINX-AI-ALLOWLIST.md").read_text()
    activation = doc.split("## Smallest FashionRise-only change")[1].split("## Pre-activation")[0]
    assert "location ^~ /api/v1/ai/" not in activation
    assert "location /api/v1/ai/ { return 403; }" in activation
    assert "location ~ ^/api/v1/ai/jobs/" in activation
