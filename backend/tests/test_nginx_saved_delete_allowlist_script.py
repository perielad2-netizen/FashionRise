"""Offline check for the isolated Nginx saved-delete allowlist verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_saved_delete_allowlist.py"
DOC = Path(__file__).resolve().parents[2] / "docs/deploy/PROPOSED-NGINX-SAVED-DELETE-ALLOWLIST.md"


def test_verify_nginx_saved_delete_allowlist_script_passes():
    proc = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_NGINX_SAVED_DELETE_ALLOWLIST_OK" in proc.stdout
    assert "matrix_ok DELETE /api/v1/designs/saved/" in proc.stdout
    assert "matrix_ok DELETE /api/v1/designs/11111111" in proc.stdout

    doc = DOC.read_text(encoding="utf-8")
    assert "designs/saved/" in doc
    assert "limit_except DELETE" in doc
    assert "limit_except GET POST PUT" in doc
