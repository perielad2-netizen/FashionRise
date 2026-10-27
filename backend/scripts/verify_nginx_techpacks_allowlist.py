#!/usr/bin/env python3
"""Isolated Nginx Create Real Design (techpacks) allowlist check — V2 AI routes."""

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

location = /api/v1/techpacks/ai/status {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/ai/runs/[0-9a-fA-F-]{36}$" {
    limit_except GET { deny all; }
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

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/confirm$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate-professional$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/latest-run$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/techpacks/artifacts/[0-9a-fA-F-]{36}/image$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}
"""

UUID = "11111111-1111-1111-1111-111111111111"
MATRIX = [
    ("GET", "/api/v1/techpacks", "allow_list"),
    ("POST", "/api/v1/techpacks", "allow_create"),
    ("DELETE", "/api/v1/techpacks", "deny_list_delete"),
    ("GET", "/api/v1/techpacks/ai/status", "allow_ai_status"),
    ("GET", f"/api/v1/techpacks/ai/runs/{UUID}", "allow_ai_run"),
    ("GET", f"/api/v1/techpacks/{UUID}", "allow_get"),
    ("PATCH", f"/api/v1/techpacks/{UUID}", "allow_patch"),
    ("DELETE", f"/api/v1/techpacks/{UUID}", "deny_delete"),
    ("POST", f"/api/v1/techpacks/{UUID}/export", "allow_export"),
    ("GET", f"/api/v1/techpacks/{UUID}/exports", "allow_exports"),
    ("POST", f"/api/v1/techpacks/{UUID}/ai/confirm", "allow_ai_confirm"),
    ("POST", f"/api/v1/techpacks/{UUID}/ai/generate", "allow_ai_generate"),
    ("POST", f"/api/v1/techpacks/{UUID}/ai/generate-professional", "allow_ai_generate_professional"),
    ("GET", f"/api/v1/techpacks/{UUID}/ai/latest-run", "allow_ai_latest_run"),
    ("GET", f"/api/v1/techpacks/exports/{UUID}/pdf", "allow_pdf"),
    ("GET", f"/api/v1/techpacks/artifacts/{UUID}/image", "allow_artifact"),
    ("POST", f"/api/v1/techpacks/{UUID}/ai-draft", "deny_ai_legacy"),
    ("GET", f"/api/v1/techpacks/{UUID}/extra", "deny_extra"),
]

_LIST_EXACT = "/api/v1/techpacks"
_AI_STATUS = "/api/v1/techpacks/ai/status"
_AI_RUN_RE = re.compile(r"^/api/v1/techpacks/ai/runs/[0-9a-fA-F-]{36}$")
_ITEM_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}$")
_EXPORT_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/export$")
_EXPORTS_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/exports$")
_AI_CONFIRM_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/confirm$")
_AI_GENERATE_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate$")
_AI_GENERATE_PROFESSIONAL_RE = re.compile(
    r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/generate-professional$"
)
_AI_LATEST_RUN_RE = re.compile(r"^/api/v1/techpacks/[0-9a-fA-F-]{36}/ai/latest-run$")
_PDF_RE = re.compile(r"^/api/v1/techpacks/exports/[0-9a-fA-F-]{36}/pdf$")
_ARTIFACT_RE = re.compile(r"^/api/v1/techpacks/artifacts/[0-9a-fA-F-]{36}/image$")


def _assert_snippet(text: str) -> None:
    if "location = /api/v1/techpacks" not in text:
        raise SystemExit("FAIL: missing exact /api/v1/techpacks location")
    if "location = /api/v1/techpacks/ai/status" not in text:
        raise SystemExit("FAIL: missing ai/status location")
    if "/ai/confirm$" not in text:
        raise SystemExit("FAIL: missing ai/confirm location")
    if "/ai/generate$" not in text:
        raise SystemExit("FAIL: missing ai/generate location")
    if "/ai/generate-professional$" not in text:
        raise SystemExit("FAIL: missing ai/generate-professional location")
    if "/ai/latest-run$" not in text:
        raise SystemExit("FAIL: missing ai/latest-run location")
    if "/pdf$" not in text:
        raise SystemExit("FAIL: missing pdf location")
    if "/image$" not in text:
        raise SystemExit("FAIL: missing artifacts image location")


def _classify(method: str, path: str) -> str:
    if path == _LIST_EXACT:
        if method == "GET":
            return "allow_list"
        if method == "POST":
            return "allow_create"
        return "deny_list_delete"
    if path == _AI_STATUS:
        return "allow_ai_status" if method == "GET" else "deny_extra"
    if _AI_RUN_RE.fullmatch(path):
        return "allow_ai_run" if method == "GET" else "deny_extra"
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
    if _AI_CONFIRM_RE.fullmatch(path):
        return "allow_ai_confirm" if method == "POST" else "deny_extra"
    if _AI_GENERATE_PROFESSIONAL_RE.fullmatch(path):
        return "allow_ai_generate_professional" if method == "POST" else "deny_extra"
    if _AI_GENERATE_RE.fullmatch(path):
        return "allow_ai_generate" if method == "POST" else "deny_extra"
    if _AI_LATEST_RUN_RE.fullmatch(path):
        return "allow_ai_latest_run" if method == "GET" else "deny_extra"
    if _PDF_RE.fullmatch(path):
        return "allow_pdf" if method == "GET" else "deny_extra"
    if _ARTIFACT_RE.fullmatch(path):
        return "allow_artifact" if method == "GET" else "deny_extra"
    if path.startswith("/api/v1/techpacks/"):
        return "deny_ai_legacy" if path.endswith("/ai-draft") else "deny_extra"
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
