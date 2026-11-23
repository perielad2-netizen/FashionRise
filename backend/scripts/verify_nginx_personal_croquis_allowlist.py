#!/usr/bin/env python3
"""Offline structural check for personal-croquis nginx allowlist docs.

Asserts docs/deploy/PROPOSED-NGINX-PERSONAL-CROQUIS-ALLOWLIST.md still lists
the Create Model consent/upload route and My Models publish path so a future
edge deny cannot silently regress without failing CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/deploy/PROPOSED-NGINX-PERSONAL-CROQUIS-ALLOWLIST.md"

REQUIRED_SNIPPETS = (
    'location = /api/v1/personal-croquis/consent/upload',
    'location = /api/v1/personal-croquis/consent/storage',
    'location = /api/v1/personal-croquis/consent/ai',
    'location = /api/v1/personal-croquis/photos',
    'location = /api/v1/personal-croquis/attestations/adults',
    'location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/publish$"',
    'location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/sex$"',
    'location ~ "^/api/v1/personal-croquis/[0-9a-fA-F-]{36}/versions/generate$"',
    'location /api/v1/personal-croquis/ { return 403; }',
    'client_max_body_size 25m',
)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SNIPPETS if s not in text]
    if missing:
        for item in missing:
            print(f"missing: {item}")
        print("VERIFY_NGINX_PERSONAL_CROQUIS_ALLOWLIST_FAIL", file=sys.stderr)
        return 1
    print("matrix_ok POST /api/v1/personal-croquis/consent/upload")
    print("matrix_ok POST /api/v1/personal-croquis/photos")
    print("matrix_ok POST|DELETE /api/v1/personal-croquis/{uuid}/publish")
    print("matrix_ok PATCH /api/v1/personal-croquis/{uuid}/sex")
    print("VERIFY_NGINX_PERSONAL_CROQUIS_ALLOWLIST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
