"""Offline check for the personal-croquis Nginx allowlist verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_personal_croquis_allowlist.py"


def test_verify_nginx_personal_croquis_allowlist_script_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_NGINX_PERSONAL_CROQUIS_ALLOWLIST_OK" in proc.stdout
    assert "matrix_ok POST /api/v1/personal-croquis/consent/upload" in proc.stdout
    doc = (
        Path(__file__).resolve().parents[2]
        / "docs/deploy/PROPOSED-NGINX-PERSONAL-CROQUIS-ALLOWLIST.md"
    ).read_text()
    assert "location = /api/v1/personal-croquis/consent/upload" in doc
    assert 'location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/publish$"' in doc
