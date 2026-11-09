#!/usr/bin/env python3
"""Select a unique iOS CFBundleVersion for Codemagic / App Store Connect.

Primary: PROJECT_BUILD_NUMBER + fixed offset (monotonic per Codemagic project).
Raise to ASC/TestFlight latest+1 when that is higher (API can lag; never go down).

Marketing version (CFBundleShortVersionString) is out of scope — stays 1.0.
"""

from __future__ import annotations

import argparse
import json
import sys


DEFAULT_OFFSET = 100


def select_cfbundle_version(
    *,
    project_build_number: int,
    offset: int = DEFAULT_OFFSET,
    asc_latest: int = 0,
) -> dict[str, int]:
    if project_build_number < 0:
        raise ValueError("project_build_number must be >= 0")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if asc_latest < 0:
        raise ValueError("asc_latest must be >= 0")

    base = project_build_number + offset
    asc_next = asc_latest + 1 if asc_latest > 0 else 0
    selected = max(base, asc_next)
    return {
        "project_build_number": project_build_number,
        "offset": offset,
        "base": base,
        "asc_latest": asc_latest,
        "asc_next": asc_next,
        "selected": selected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-build-number", type=int, required=True)
    parser.add_argument("--offset", type=int, default=DEFAULT_OFFSET)
    parser.add_argument("--asc-latest", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Print full JSON decision")
    args = parser.parse_args(argv)

    decision = select_cfbundle_version(
        project_build_number=args.project_build_number,
        offset=args.offset,
        asc_latest=args.asc_latest,
    )
    if args.json:
        print(json.dumps(decision, sort_keys=True))
    else:
        print(decision["selected"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
