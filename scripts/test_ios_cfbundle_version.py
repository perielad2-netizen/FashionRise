#!/usr/bin/env python3
"""Unit tests for scripts/ios_cfbundle_version.py (no Codemagic required)."""

from __future__ import annotations

import unittest

from ios_cfbundle_version import select_cfbundle_version


class SelectCfBundleVersionTests(unittest.TestCase):
    def test_uses_project_build_plus_offset(self) -> None:
        d = select_cfbundle_version(project_build_number=15, offset=100, asc_latest=0)
        self.assertEqual(d["base"], 115)
        self.assertEqual(d["selected"], 115)
        self.assertEqual(d["asc_next"], 0)

    def test_raises_to_asc_latest_plus_one_when_higher(self) -> None:
        d = select_cfbundle_version(project_build_number=10, offset=100, asc_latest=200)
        self.assertEqual(d["base"], 110)
        self.assertEqual(d["asc_next"], 201)
        self.assertEqual(d["selected"], 201)

    def test_never_reuses_same_base_when_asc_equals_base_minus_one(self) -> None:
        # ASC already has 114 → next must be >= 115; base is also 115.
        d = select_cfbundle_version(project_build_number=15, offset=100, asc_latest=114)
        self.assertEqual(d["selected"], 115)

    def test_asc_collision_path_advances_past_known_upload(self) -> None:
        # Simulate ASC already having build 20 while Codemagic counter is still low.
        d = select_cfbundle_version(project_build_number=12, offset=100, asc_latest=20)
        self.assertEqual(d["base"], 112)
        self.assertEqual(d["selected"], 112)

    def test_monotonic_project_builds_differ(self) -> None:
        a = select_cfbundle_version(project_build_number=12, offset=100, asc_latest=20)["selected"]
        b = select_cfbundle_version(project_build_number=13, offset=100, asc_latest=20)["selected"]
        self.assertGreater(b, a)

    def test_rejects_negatives(self) -> None:
        with self.assertRaises(ValueError):
            select_cfbundle_version(project_build_number=-1, offset=100, asc_latest=0)


if __name__ == "__main__":
    unittest.main()
