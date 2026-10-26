"""Offline check for the isolated Nginx My Looks allowlist verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_looks_allowlist.py"


def test_verify_nginx_looks_allowlist_script_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_NGINX_LOOKS_ALLOWLIST_OK" in proc.stdout
    assert "matrix_ok GET /api/v1/looks" in proc.stdout
    assert "matrix_ok PATCH /api/v1/looks/" in proc.stdout
    assert "matrix_ok DELETE /api/v1/looks/" in proc.stdout
    doc = (Path(__file__).resolve().parents[2] / "docs/deploy/PROPOSED-NGINX-LOOKS-ALLOWLIST.md").read_text()
    assert "location = /api/v1/looks" in doc
    assert 'location ~ "^/api/v1/looks/[0-9a-fA-F-]{36}$"' in doc
    assert "limit_except GET PATCH DELETE" in doc
