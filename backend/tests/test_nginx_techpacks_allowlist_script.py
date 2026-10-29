"""Offline check for the isolated Nginx techpacks allowlist verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_techpacks_allowlist.py"


def test_verify_nginx_techpacks_allowlist_script_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_NGINX_TECHPACKS_ALLOWLIST_OK" in proc.stdout
    assert "matrix_ok GET /api/v1/techpacks" in proc.stdout
    assert "matrix_ok POST /api/v1/techpacks" in proc.stdout
    assert "matrix_ok GET /api/v1/techpacks/exports/" in proc.stdout
    doc = (Path(__file__).resolve().parents[2] / "docs/deploy/PROPOSED-NGINX-TECHPACKS-ALLOWLIST.md").read_text()
    assert "location = /api/v1/techpacks" in doc
    assert "/exports/" in doc
    assert "limit_except GET POST" in doc
