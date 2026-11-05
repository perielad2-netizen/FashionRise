"""Typed private-croquis unlink outcomes for fail-closed retention."""

from __future__ import annotations

from enum import Enum


class CroquisUnlinkOutcome(str, Enum):
    """Distinguish successful removal from already-absent vs unsafe/failed."""

    REMOVED = "removed"
    ALREADY_ABSENT = "already_absent"
    UNSAFE = "unsafe"
    FAILED = "failed"
