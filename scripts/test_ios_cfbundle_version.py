#!/usr/bin/env python3
"""Unit tests for scripts/ios_cfbundle_version.py (no Codemagic required)."""

from __future__ import annotations

import unittest

from ios_cfbundle_version import OffsetTooLowError, select_cfbundle_version


class SelectCfBundleVersionTests(unittest.TestCase):
    def test_uses_project_build_plus_offset(self) -> None:
        d = select_cfbundle_version(project_build_number=15, offset=100, asc_latest=0)
        self.assertEqual(d["base"], 115)
        self.assertEqual(d["selected"], 115)

    def test_requires_positive_project_build_number(self) -> None:
        with self.assertRaises(ValueError):
            select_cfbundle_version(project_build_number=0, offset=100, asc_latest=0)
        with self.assertRaises(ValueError):
            select_cfbundle_version(project_build_number=-3, offset=100, asc_latest=0)

    def test_requires_positive_offset(self) -> None:
        with self.assertRaises(ValueError):
            select_cfbundle_version(project_build_number=5, offset=0, asc_latest=0)

    def test_monotonic_across_sequential_project_builds(self) -> None:
        prev = 0
        for pbn in range(12, 20):
            selected = select_cfbundle_version(
                project_build_number=pbn, offset=100, asc_latest=20
            )["selected"]
            self.assertEqual(selected, pbn + 100)
            self.assertGreater(selected, prev)
            prev = selected

    def test_asc_below_base_is_ok(self) -> None:
        d = select_cfbundle_version(project_build_number=12, offset=100, asc_latest=20)
        self.assertEqual(d["selected"], 112)

    def test_asc_equal_to_base_fails_closed(self) -> None:
        with self.assertRaises(OffsetTooLowError) as ctx:
            select_cfbundle_version(project_build_number=15, offset=100, asc_latest=115)
        msg = str(ctx.exception)
        self.assertIn("Raise IOS_BUILD_NUMBER_OFFSET", msg)
        self.assertIn("at least 101", msg)

    def test_asc_ahead_of_base_fails_closed_instead_of_asc_plus_one(self) -> None:
        # Stale ASC+1 would risk repeats on the next Codemagic build; refuse.
        with self.assertRaises(OffsetTooLowError) as ctx:
            select_cfbundle_version(project_build_number=10, offset=100, asc_latest=200)
        msg = str(ctx.exception)
        self.assertIn("200", msg)
        self.assertIn("110", msg)
        self.assertIn("at least 191", msg)
        self.assertIn("might repeat", msg)

    def test_stale_asc_plus_one_would_have_collided_across_builds(self) -> None:
        """Document why we fail-closed when ASC is ahead of the offset scheme.

        If build A stamped ASC_latest+1=201 while base was 110, and build B saw a
        stale ASC_latest=200 again, max(base, 201) would reuse 201. Fail-closed
        forces an offset raise so every stamp stays on the PBN+offset rail.
        """
        with self.assertRaises(OffsetTooLowError):
            select_cfbundle_version(project_build_number=10, offset=100, asc_latest=200)
        # After operator raises offset so base clears ASC:
        d = select_cfbundle_version(project_build_number=10, offset=191, asc_latest=200)
        self.assertEqual(d["selected"], 201)
        d2 = select_cfbundle_version(project_build_number=11, offset=191, asc_latest=200)
        self.assertEqual(d2["selected"], 202)
        self.assertGreater(d2["selected"], d["selected"])


if __name__ == "__main__":
    unittest.main()
