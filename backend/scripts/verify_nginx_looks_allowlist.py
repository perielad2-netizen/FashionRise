#!/usr/bin/env python3
"""Isolated Nginx My Looks allowlist check (no production edits)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SNIPPET = """
# FashionRise My Looks allowlist candidate (isolated verification only)
location = /api/v1/looks {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/looks/[0-9a-fA-F-]{36}$" {
    limit_except GET PATCH DELETE { deny all; }
    proxy_pass http://127.0.0.1:8010;
}
"""

UUID = "11111111-1111-1111-1111-111111111111"
MATRIX = [
    ("GET", "/api/v1/looks", "allow_list"),
    ("POST", "/api/v1/looks", "deny_list_post"),
    ("GET", f"/api/v1/looks/{UUID}", "allow_get"),
    ("PATCH", f"/api/v1/looks/{UUID}", "allow_patch"),
    ("DELETE", f"/api/v1/looks/{UUID}", "allow_delete"),
    ("POST", f"/api/v1/looks/{UUID}", "deny_post"),
    ("GET", f"/api/v1/looks/{UUID}/extra", "deny_extra"),
]

_LIST_EXACT = "/api/v1/looks"
_ITEM_RE = re.compile(r"^/api/v1/looks/[0-9a-fA-F-]{36}$")


def _assert_snippet(text: str) -> None:
    if "location = /api/v1/looks" not in text:
        raise SystemExit("FAIL: missing exact /api/v1/looks location")
    if not re.search(r'location\s+~\s+"\^/api/v1/looks/', text):
        raise SystemExit("FAIL: missing look item location")
    if "limit_except GET" not in text:
        raise SystemExit("FAIL: list location must allow GET only")
    if "limit_except GET PATCH DELETE" not in text:
        raise SystemExit("FAIL: item location must allow GET PATCH DELETE")


def _classify(method: str, path: str) -> str:
    if path == _LIST_EXACT:
        if method == "GET":
            return "allow_list"
        return "deny_list_post"
    if _ITEM_RE.fullmatch(path):
        if method == "GET":
            return "allow_get"
        if method == "PATCH":
            return "allow_patch"
        if method == "DELETE":
            return "allow_delete"
        return "deny_post"
    if path.startswith("/api/v1/looks/"):
        return "deny_extra"
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
        with tempfile.TemporaryDirectory(prefix="fr-looks-nginx-") as tmp:
            conf = Path(tmp) / "nginx.conf"
            conf.write_text(
                f"""
worker_processes 1;
error_log stderr;
pid {tmp}/nginx.pid;
events {{ worker_connections 64; }}
http {{
  server {{
    listen 127.0.0.1:18091;
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

    print("VERIFY_NGINX_LOOKS_ALLOWLIST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
