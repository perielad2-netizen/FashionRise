#!/usr/bin/env python3
"""Isolated Nginx saved-delete allowlist check (no production edits).

Mirrors docs/deploy/PROPOSED-NGINX-SAVED-DELETE-ALLOWLIST.md: allow DELETE only on
/api/v1/designs/saved/{uuid}, and deny DELETE on the general designs location.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SNIPPET = """
# FashionRise saved-delete allowlist candidate (isolated verification only)
location ~ "^/api/v1/designs/saved/[0-9a-fA-F-]{36}$" {
    limit_except DELETE { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ ^/api/v1/designs(?:/.*)?$ {
    limit_except GET POST PUT { deny all; }
    proxy_pass http://127.0.0.1:8010;
}
"""

UUID = "11111111-1111-1111-1111-111111111111"
MATRIX = [
    ("DELETE", f"/api/v1/designs/saved/{UUID}", "allow_saved_delete"),
    ("GET", f"/api/v1/designs/saved/{UUID}", "deny_saved_get"),
    ("POST", f"/api/v1/designs/saved/{UUID}", "deny_saved_post"),
    ("DELETE", f"/api/v1/designs/{UUID}", "deny_generic_delete"),
    ("GET", f"/api/v1/designs/{UUID}", "allow_generic_get"),
    ("PUT", f"/api/v1/designs/{UUID}", "allow_generic_put"),
    ("POST", "/api/v1/designs", "allow_create"),
    ("GET", "/api/v1/designs/my", "allow_list_my"),
]

_SAVED_RE = re.compile(r"^/api/v1/designs/saved/[0-9a-fA-F-]{36}$")
_DESIGNS_RE = re.compile(r"^/api/v1/designs(?:/.*)?$")


def _assert_snippet_precedence(text: str) -> None:
    if not re.search(r'location\s+~\s+"\^/api/v1/designs/saved/', text):
        raise SystemExit("FAIL: missing saved-delete location")
    if "limit_except DELETE" not in text:
        raise SystemExit("FAIL: saved location must allow DELETE only")
    if "limit_except GET POST PUT" not in text:
        raise SystemExit("FAIL: general designs location must deny DELETE")
    saved_at = text.find("designs/saved/")
    general_at = text.find("designs(?:/.*)?")
    if saved_at < 0 or general_at < 0 or saved_at > general_at:
        raise SystemExit("FAIL: saved-delete location must be declared before general designs")


def _classify(method: str, path: str) -> str:
    if _SAVED_RE.fullmatch(path):
        if method == "DELETE":
            return "allow_saved_delete"
        if method == "GET":
            return "deny_saved_get"
        return "deny_saved_post"
    if _DESIGNS_RE.fullmatch(path):
        if method == "DELETE":
            return "deny_generic_delete"
        if method == "GET" and path.endswith("/my"):
            return "allow_list_my"
        if method == "GET":
            return "allow_generic_get"
        if method == "PUT":
            return "allow_generic_put"
        if method == "POST":
            return "allow_create"
        return "deny_generic_other"
    raise SystemExit(f"FAIL: unmapped matrix path {method} {path}")


def main() -> int:
    _assert_snippet_precedence(SNIPPET)
    for method, path, label in MATRIX:
        got = _classify(method, path)
        if got != label:
            raise SystemExit(f"FAIL matrix {method} {path}: expected {label}, got={got}")
        print(f"matrix_ok {method} {path} -> {label}")

    nginx = shutil.which("nginx")
    if nginx:
        with tempfile.TemporaryDirectory(prefix="fr-saved-del-nginx-") as tmp:
            conf = Path(tmp) / "nginx.conf"
            conf.write_text(
                f"""
worker_processes 1;
error_log stderr;
pid {tmp}/nginx.pid;
events {{ worker_connections 64; }}
http {{
  server {{
    listen 127.0.0.1:18090;
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

    print("VERIFY_NGINX_SAVED_DELETE_ALLOWLIST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
