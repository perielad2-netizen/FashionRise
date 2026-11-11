"""Shared helpers for FashionRise Codemagic iPad screenshot sessions."""

from __future__ import annotations

import re
from pathlib import Path

# Apple App Store Connect — required iPad 13" display class sizes.
# https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/
ACCEPTED_IPAD_13_SIZES: frozenset[tuple[int, int]] = frozenset(
    {
        (2064, 2752),  # iPad Pro / Air 13" portrait
        (2752, 2064),  # landscape
        (2048, 2732),  # also accepted in 13" class
        (2732, 2048),
    }
)

_IPAD_13_NAME = re.compile(r"ipad (?:pro|air) \(13[- ]?inch", re.I)


def is_supported_13_inch_ipad_name(name: str) -> bool:
    return bool(_IPAD_13_NAME.search(name or ""))


def score_13_inch_ipad(name: str) -> int | None:
    """Higher is better. None = not an accepted 13-inch screenshot device."""
    n = (name or "").lower()
    if not is_supported_13_inch_ipad_name(n):
        return None
    if "ipad pro" in n:
        return 100
    if "ipad air" in n:
        return 90
    return None


def pick_13_inch_ipad(devices_json: dict) -> tuple[str, str, str]:
    """
    Return (udid, name, runtime) for the best available 13-inch iPad.
    Raises ValueError with a clear message if none are available.
    """
    devices = devices_json.get("devices") or {}
    candidates: list[tuple[int, str, str, str]] = []
    seen_unsupported: list[str] = []

    for runtime, rows in devices.items():
        if "iOS" not in runtime and "iPadOS" not in runtime:
            continue
        for d in rows or []:
            if not d.get("isAvailable", True):
                continue
            name = str(d.get("name") or "")
            if "iPad" not in name:
                continue
            udid = str(d.get("udid") or "")
            if not udid:
                continue
            score = score_13_inch_ipad(name)
            if score is None:
                seen_unsupported.append(name)
                continue
            candidates.append((score, name, udid, runtime))

    if not candidates:
        unsupported = ", ".join(sorted(set(seen_unsupported))[:8]) or "(none)"
        raise ValueError(
            "No supported 13-inch iPad simulator is available "
            f"(need iPad Pro/Air 13-inch). Found iPads: {unsupported}. "
            "Refusing to invent or upscale a different tablet size."
        )

    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    _score, name, udid, runtime = candidates[0]
    return udid, name, runtime


def png_dimensions(path: str | Path) -> tuple[int, int]:
    """Read width/height from PNG IHDR without external deps."""
    p = Path(path)
    with p.open("rb") as fh:
        sig = fh.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"not a PNG: {p}")
        _length = fh.read(4)
        ctype = fh.read(4)
        if ctype != b"IHDR":
            raise ValueError(f"missing IHDR in {p}")
        width = int.from_bytes(fh.read(4), "big")
        height = int.from_bytes(fh.read(4), "big")
        return width, height


def assert_accepted_ipad_13_dimensions(path: str | Path) -> tuple[int, int]:
    width, height = png_dimensions(path)
    if (width, height) not in ACCEPTED_IPAD_13_SIZES:
        accepted = ", ".join(f"{w}x{h}" for w, h in sorted(ACCEPTED_IPAD_13_SIZES))
        raise ValueError(
            f"screenshot {path} is {width}x{height}; "
            f"Apple 13-inch iPad class requires one of: {accepted}. "
            "Not upscaling or inventing a size."
        )
    return width, height
