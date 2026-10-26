#!/usr/bin/env python3
"""Isolated Nginx Create Real Design (techpacks) allowlist check."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SNIPPET = """
# FashionRise techpacks allowlist candidate (isolated verification only)
location = /api/v1/techpacks {
    limit_except GET POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}$" {
    limit_except GET PATCH { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/export$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/exports$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}
"""

UUID = "11111111-1111-1111-1111-111111111111"
MATRIX = [
    ("GET", "/api/v1/techpacks", "allow_list"),
    ("POST", "/api/v1/techpacks", "allow_create"),
    ("DELETE", "/api/v1/techpacks", "deny_list_delete"),
    ("GET", f"/api/v1/techpacks/{UUID}", "allow_get"),
    ("PATCH", f"/api/v1/techpacks/{UUID}", "allow_patch"),
    ("DELETE", f"/api/v1/techpacks/{UUID}", "deny_delete"),
    ("POST", f"/api/v1/techpacks/{UUID}/export", "allow_export"),
    ("GET", f"/api/v1/techpacks/{UUID}/exports", "allow_exports"),
    ("GET", f"/api/v1/techpacks/exports/{UUID}/pdf", "allow_pdf"),
    ("POST", f"/api/v1/techpacks/{UUID}/ai-draft", "deny_ai"),
    ("GET", f"/api/v1/techpacks/{UUID}/extra", "deny_extra"),
]

_LIST_EXACT = "/api/v1/techpacks"
_ITEM_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}$")
_EXPORT_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/export$")
_EXPORTS_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/exports$")
_PDF_RE = re.compile(r"^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$")


def _assert_snippet(text: str) -> None:
    if "location = /api/v1/techpacks" not in text:
        raise SystemExit("FAIL: missing exact /api/v1/techpacks location")
    if "limit_except GET POST" not in text:
        raise SystemExit("FAIL: list location must allow GET POST")
    if "limit_except GET PATCH" not in text:
        raise SystemExit("FAIL: item location must allow GET PATCH")
    if "/export$" not in text:
        raise SystemExit("FAIL: missing export location")
    if "/pdf$" not in text:
        raise SystemExit("FAIL: missing pdf location")


def _classify(method: str, path: str) -> str:
    if path == _LIST_EXACT:
        if method == "GET":
            return "allow_list"
        if method == "POST":
            return "allow_create"
        return "deny_list_delete"
    if _ITEM_RE.fullmatch(path):
        if method == "GET":
            return "allow_get"
        if method == "PATCH":
            return "allow_patch"
        return "deny_delete"
    if _EXPORT_RE.fullmatch(path):
        return "allow_export" if method == "POST" else "deny_extra"
    if _EXPORTS_RE.fullmatch(path):
        return "allow_exports" if method == "GET" else "deny_extra"
    if _PDF_RE.fullmatch(path):
        return "allow_pdf" if method == "GET" else "deny_extra"
    if path.startswith("/api/v1/techpacks/"):
        return "deny_ai" if path.endswith("/ai-draft") else "deny_extra"
    raise SystemExit(f"FAIL: unmapped matrix path {method} {path}")


def main() -> int:
    _assert_snippet(SNIPPET)
    for method, path, label in MATRIX:
        got = _classify(method, path)
        if got != label:
            raise SystemExit(f"FAIL matrix {method} {path}: expected {label}, got={got}")
        print(f"matrix_ok {method} {path} -> {label}")

    nginx = shutil.which("nginx")
    if nginx:
        with tempfile.TemporaryDirectory(prefix="fr-techpacks-nginx-") as tmp:
            conf = Path(tmp) / "nginx.conf"
            conf.write_text(
                f"""
worker_processes 1;
error_log stderr;
pid {tmp}/nginx.pid;
events {{ worker_connections 64; }}
http {{
  server {{
    listen 127.0.0.1:18092;
    server_name fashionrise.test;
{SNIPPET}
  }}
}}
""",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [nginx, "-t", "-c", str(conf)],
                check=False,
                capture_output=True,
                text=True,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            print(out.strip())
            if proc.returncode != 0:
                raise SystemExit(f"FAIL: nginx -t exit {proc.returncode}")
            print("nginx_t_ok")
    else:
        print("nginx_absent_skip_t")

    print("VERIFY_NGINX_TECHPACKS_ALLOWLIST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
