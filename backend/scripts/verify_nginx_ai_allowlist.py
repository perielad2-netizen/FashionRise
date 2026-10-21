#!/usr/bin/env python3
"""Isolated Nginx AI allowlist precedence check (no production edits).

Writes a temporary FashionRise-only server snippet that mirrors
docs/deploy/PROPOSED-NGINX-AI-ALLOWLIST.md, runs `nginx -t` when nginx is
available, and asserts location precedence rules that keep job GET routes
reachable while sibling AI routes stay denied.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SNIPPET = """
# FashionRise AI allowlist candidate (isolated verification only)
location = /static/uploads { return 403; }
location ^~ /static/uploads/ { return 403; }

location = /api/v1/ai { return 403; }

location = /api/v1/ai/sketch/polish {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ ^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$ {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

# Plain prefix deny — must NOT use ^~ or regex jobs never match.
location /api/v1/ai/ { return 403; }
"""

MATRIX = [
    ("POST", "/api/v1/ai/sketch/polish", "allow_exact_polish"),
    ("GET", "/api/v1/ai/sketch/polish", "deny_method_polish"),
    ("GET", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111", "allow_regex_job"),
    ("GET", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111/image", "allow_regex_image"),
    ("POST", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111", "deny_method_job"),
    ("POST", "/api/v1/ai/sketch/clean", "deny_prefix_sibling"),
    ("GET", "/api/v1/ai/jobs", "deny_prefix_list"),
    ("GET", "/static/uploads/ai/x.png", "deny_static_uploads"),
]

_JOB_RE = re.compile(r"^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$")


def _assert_snippet_precedence(text: str) -> None:
    if "location ^~ /api/v1/ai/" in text:
        raise SystemExit("FAIL: catch-all must not use ^~ (blocks regex job routes)")
    if not re.search(r"location\s+/api/v1/ai/\s*\{\s*return 403;", text):
        raise SystemExit("FAIL: missing plain prefix deny for /api/v1/ai/")
    if not re.search(
        r"location\s+~\s+\^/api/v1/ai/jobs/\[0-9a-fA-F-\]\{36\}\(/image\)\?\$",
        text,
    ):
        raise SystemExit("FAIL: missing regex jobs allowlist")
    if "location = /api/v1/ai/sketch/polish" not in text:
        raise SystemExit("FAIL: missing exact polish allowlist")
    regex_at = text.find("location ~ ^/api/v1/ai/jobs/")
    prefix_at = text.find("location /api/v1/ai/ {")
    if regex_at < 0 or prefix_at < 0 or regex_at > prefix_at:
        raise SystemExit("FAIL: regex jobs rule must be declared before plain prefix deny")


def _classify(method: str, path: str) -> str:
    """Model intended allowlist outcome for the candidate snippet."""
    if path == "/static/uploads" or path.startswith("/static/uploads/"):
        return "deny_static_uploads"
    if path == "/api/v1/ai/sketch/polish":
        return "allow_exact_polish" if method == "POST" else "deny_method_polish"
    job = _JOB_RE.fullmatch(path)
    if job:
        if method != "GET":
            return "deny_method_job"
        return "allow_regex_image" if path.endswith("/image") else "allow_regex_job"
    if path == "/api/v1/ai/jobs":
        return "deny_prefix_list"
    if path.startswith("/api/v1/ai/"):
        return "deny_prefix_sibling"
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
        with tempfile.TemporaryDirectory(prefix="fr-ai-nginx-") as tmp:
            conf = Path(tmp) / "nginx.conf"
            conf.write_text(
                f"""
worker_processes 1;
error_log stderr;
pid {tmp}/nginx.pid;
events {{ worker_connections 64; }}
http {{
  server {{
    listen 127.0.0.1:18089;
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

    print("VERIFY_NGINX_AI_ALLOWLIST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
