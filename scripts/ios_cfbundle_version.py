#!/usr/bin/env python3
"""Select a unique iOS CFBundleVersion for Codemagic / App Store Connect.

Primary stamp (monotonic across Codemagic project builds):
  CFBundleVersion = PROJECT_BUILD_NUMBER + IOS_BUILD_NUMBER_OFFSET

ASC/TestFlight latest is a fail-closed guard only:
  if ASC already has a build >= that planned stamp, refuse and ask for a
  higher offset. Never stamp ASC_latest+1 alone — a stale ASC API reply
  can make two sequential Codemagic builds pick the same number.

Marketing version (CFBundleShortVersionString) is out of scope — stays 1.0.
"""

from __future__ import annotations

import argparse
import json
import sys


DEFAULT_OFFSET = 100


class OffsetTooLowError(ValueError):
    """ASC is ahead of PROJECT_BUILD_NUMBER + offset; raise the offset."""


def select_cfbundle_version(
    *,
    project_build_number: int,
    offset: int = DEFAULT_OFFSET,
    asc_latest: int = 0,
) -> dict[str, int]:
    if not isinstance(project_build_number, int) or isinstance(project_build_number, bool):
        raise ValueError("project_build_number must be a positive integer")
    if project_build_number < 1:
        raise ValueError(
            "project_build_number must be a positive integer "
            "(require Codemagic PROJECT_BUILD_NUMBER; never fall back to 0)"
        )
    if offset < 1:
        raise ValueError("offset must be a positive integer")
    if asc_latest < 0:
        raise ValueError("asc_latest must be >= 0")

    base = project_build_number + offset
    # If ASC already consumed this stamp (or anything higher), do not guess
    # ASC_latest+1 — that collides under stale API between sequential builds.
    if asc_latest >= base:
        need_offset = asc_latest - project_build_number + 1
        raise OffsetTooLowError(
            "ASC/TestFlight latest build "
            f"{asc_latest} is >= planned CFBundleVersion {base} "
            f"(PROJECT_BUILD_NUMBER={project_build_number} + offset={offset}). "
            f"Raise IOS_BUILD_NUMBER_OFFSET to at least {need_offset} "
            "so the next Codemagic stamp clears App Store Connect, then rebuild. "
            "Refusing to assign a number that might repeat."
        )

    return {
        "project_build_number": project_build_number,
        "offset": offset,
        "base": base,
        "asc_latest": asc_latest,
        "selected": base,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-build-number", type=int, required=True)
    parser.add_argument("--offset", type=int, default=DEFAULT_OFFSET)
    parser.add_argument("--asc-latest", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Print full JSON decision")
    args = parser.parse_args(argv)

    try:
        decision = select_cfbundle_version(
            project_build_number=args.project_build_number,
            offset=args.offset,
            asc_latest=args.asc_latest,
        )
    except OffsetTooLowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(decision, sort_keys=True))
    else:
        print(decision["selected"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
