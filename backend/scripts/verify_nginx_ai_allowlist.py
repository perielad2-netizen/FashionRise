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

location = /api/v1/ai/sketch/polish-dual {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location = /api/v1/ai/personal-try-on {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location = /api/v1/ai/personal-try-on/preflight {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location = /api/v1/ai/personal-try-on/fashn/prepare {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location = /api/v1/ai/personal-try-on/fashn/garment-realism {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/ai/personal-try-on/fashn/garment-realism/[0-9a-fA-F-]{36}/accept$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location = /api/v1/ai/personal-try-on/fashn/garment-realism/accepted {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/ai/personal-try-on/[0-9a-fA-F-]{36}/experiment-verdict$" {
    limit_except POST { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ ^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$ {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

location ~ "^/api/v1/ai/magic-operations/[0-9a-fA-F-]{36}/jobs$" {
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:8010;
}

# Plain prefix deny — must NOT use ^~ or regex jobs never match.
location /api/v1/ai/ { return 403; }
"""

MATRIX = [
    ("POST", "/api/v1/ai/sketch/polish", "allow_exact_polish"),
    ("GET", "/api/v1/ai/sketch/polish", "deny_method_polish"),
    ("POST", "/api/v1/ai/sketch/polish-dual", "allow_exact_polish_dual"),
    ("GET", "/api/v1/ai/sketch/polish-dual", "deny_method_polish_dual"),
    (
        "GET",
        "/api/v1/ai/magic-operations/11111111-1111-1111-1111-111111111111/jobs",
        "allow_regex_magic_operations_jobs",
    ),
    (
        "POST",
        "/api/v1/ai/magic-operations/11111111-1111-1111-1111-111111111111/jobs",
        "deny_method_magic_operations_jobs",
    ),
    ("POST", "/api/v1/ai/personal-try-on", "allow_exact_try_on"),
    ("GET", "/api/v1/ai/personal-try-on", "deny_method_try_on"),
    ("GET", "/api/v1/ai/personal-try-on/preflight", "allow_exact_try_on_preflight"),
    ("POST", "/api/v1/ai/personal-try-on/preflight", "deny_method_try_on_preflight"),
    ("POST", "/api/v1/ai/personal-try-on/fashn/prepare", "allow_exact_fashn_prepare"),
    ("GET", "/api/v1/ai/personal-try-on/fashn/prepare", "deny_method_fashn_prepare"),
    ("POST", "/api/v1/ai/personal-try-on/fashn/garment-realism", "allow_exact_fashn_garment_realism"),
    ("GET", "/api/v1/ai/personal-try-on/fashn/garment-realism", "deny_method_fashn_garment_realism"),
    (
        "POST",
        "/api/v1/ai/personal-try-on/fashn/garment-realism/11111111-1111-1111-1111-111111111111/accept",
        "allow_regex_fashn_garment_realism_accept",
    ),
    (
        "GET",
        "/api/v1/ai/personal-try-on/fashn/garment-realism/11111111-1111-1111-1111-111111111111/accept",
        "deny_method_fashn_garment_realism_accept",
    ),
    (
        "GET",
        "/api/v1/ai/personal-try-on/fashn/garment-realism/accepted",
        "allow_exact_fashn_accepted_catalog",
    ),
    (
        "POST",
        "/api/v1/ai/personal-try-on/fashn/garment-realism/accepted",
        "deny_method_fashn_accepted_catalog",
    ),
    (
        "POST",
        "/api/v1/ai/personal-try-on/11111111-1111-1111-1111-111111111111/experiment-verdict",
        "allow_regex_try_on_experiment_verdict",
    ),
    (
        "GET",
        "/api/v1/ai/personal-try-on/11111111-1111-1111-1111-111111111111/experiment-verdict",
        "deny_method_try_on_experiment_verdict",
    ),
    ("GET", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111", "allow_regex_job"),
    ("GET", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111/image", "allow_regex_image"),
    ("POST", "/api/v1/ai/jobs/11111111-1111-1111-1111-111111111111", "deny_method_job"),
    ("POST", "/api/v1/ai/sketch/clean", "deny_prefix_sibling"),
    ("GET", "/api/v1/ai/jobs", "deny_prefix_list"),
    ("GET", "/static/uploads/ai/x.png", "deny_static_uploads"),
]

_JOB_RE = re.compile(r"^/api/v1/ai/jobs/[0-9a-fA-F-]{36}(/image)?$")
_MAGIC_OPS_RE = re.compile(
    r"^/api/v1/ai/magic-operations/[0-9a-fA-F-]{36}/jobs$"
)
_ACCEPT_RE = re.compile(
    r"^/api/v1/ai/personal-try-on/fashn/garment-realism/[0-9a-fA-F-]{36}/accept$"
)
_VERDICT_RE = re.compile(
    r"^/api/v1/ai/personal-try-on/[0-9a-fA-F-]{36}/experiment-verdict$"
)


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
    if "location = /api/v1/ai/sketch/polish-dual" not in text:
        raise SystemExit("FAIL: missing exact polish-dual allowlist")
    if not re.search(
        r'location\s+~\s+"?\^/api/v1/ai/magic-operations/'
        r'\[0-9a-fA-F-\]\{36\}/jobs\$"?',
        text,
    ):
        raise SystemExit("FAIL: missing regex magic-operations jobs allowlist")
    if "location = /api/v1/ai/personal-try-on" not in text:
        raise SystemExit("FAIL: missing exact personal-try-on allowlist")
    if "location = /api/v1/ai/personal-try-on/preflight" not in text:
        raise SystemExit("FAIL: missing exact personal-try-on preflight allowlist")
    if "location = /api/v1/ai/personal-try-on/fashn/prepare" not in text:
        raise SystemExit("FAIL: missing exact personal-try-on fashn prepare allowlist")
    if "location = /api/v1/ai/personal-try-on/fashn/garment-realism" not in text:
        raise SystemExit("FAIL: missing exact personal-try-on fashn garment-realism allowlist")
    if not re.search(
        r'location\s+~\s+"?\^/api/v1/ai/personal-try-on/fashn/garment-realism/'
        r'\[0-9a-fA-F-\]\{36\}/accept\$"?',
        text,
    ):
        raise SystemExit("FAIL: missing regex garment-realism accept allowlist (#170)")
    if "location = /api/v1/ai/personal-try-on/fashn/garment-realism/accepted" not in text:
        raise SystemExit("FAIL: missing exact accepted-garment catalog allowlist (#176)")
    if not re.search(
        r'location\s+~\s+"?\^/api/v1/ai/personal-try-on/'
        r'\[0-9a-fA-F-\]\{36\}/experiment-verdict\$"?',
        text,
    ):
        raise SystemExit("FAIL: missing regex experiment-verdict allowlist (#176)")
    accept_at = text.find("/api/v1/ai/personal-try-on/fashn/garment-realism/")
    # Prefer the accept location line (quoted or bare).
    accept_line = text.find("garment-realism/[0-9a-fA-F-]{36}/accept")
    verdict_line = text.find("experiment-verdict")
    regex_at = text.find("/api/v1/ai/jobs/[0-9a-fA-F-]{36}")
    prefix_at = text.find("location /api/v1/ai/ {")
    if accept_line < 0 or prefix_at < 0 or accept_line > prefix_at:
        raise SystemExit("FAIL: regex accept rule must be declared before plain prefix deny")
    if verdict_line < 0 or prefix_at < 0 or verdict_line > prefix_at:
        raise SystemExit("FAIL: experiment-verdict rule must be declared before plain prefix deny")
    if regex_at < 0 or prefix_at < 0 or regex_at > prefix_at:
        raise SystemExit("FAIL: regex jobs rule must be declared before plain prefix deny")
    _ = accept_at  # kept for readability in diffs

def _classify(method: str, path: str) -> str:
    """Model intended allowlist outcome for the candidate snippet."""
    if path == "/static/uploads" or path.startswith("/static/uploads/"):
        return "deny_static_uploads"
    if path == "/api/v1/ai/sketch/polish":
        return "allow_exact_polish" if method == "POST" else "deny_method_polish"
    if path == "/api/v1/ai/sketch/polish-dual":
        return "allow_exact_polish_dual" if method == "POST" else "deny_method_polish_dual"
    if _MAGIC_OPS_RE.match(path):
        return (
            "allow_regex_magic_operations_jobs"
            if method == "GET"
            else "deny_method_magic_operations_jobs"
        )
    if path == "/api/v1/ai/personal-try-on":
        return "allow_exact_try_on" if method == "POST" else "deny_method_try_on"
    if path == "/api/v1/ai/personal-try-on/preflight":
        return (
            "allow_exact_try_on_preflight"
            if method == "GET"
            else "deny_method_try_on_preflight"
        )
    if path == "/api/v1/ai/personal-try-on/fashn/prepare":
        return (
            "allow_exact_fashn_prepare"
            if method == "POST"
            else "deny_method_fashn_prepare"
        )
    if path == "/api/v1/ai/personal-try-on/fashn/garment-realism/accepted":
        return (
            "allow_exact_fashn_accepted_catalog"
            if method == "GET"
            else "deny_method_fashn_accepted_catalog"
        )
    if path == "/api/v1/ai/personal-try-on/fashn/garment-realism":
        return (
            "allow_exact_fashn_garment_realism"
            if method == "POST"
            else "deny_method_fashn_garment_realism"
        )
    if _ACCEPT_RE.fullmatch(path):
        return (
            "allow_regex_fashn_garment_realism_accept"
            if method == "POST"
            else "deny_method_fashn_garment_realism_accept"
        )
    if _VERDICT_RE.fullmatch(path):
        return (
            "allow_regex_try_on_experiment_verdict"
            if method == "POST"
            else "deny_method_try_on_experiment_verdict"
        )
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
