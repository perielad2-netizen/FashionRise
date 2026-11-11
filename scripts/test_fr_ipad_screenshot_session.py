#!/usr/bin/env python3
"""Offline tests: hardwired VNC helpers, finish signal, dimensions, artifacts."""

from __future__ import annotations

import os
import pathlib
import struct
import subprocess
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts"
SHOT = ROOT / "scripts" / "codemagic-ipad-screenshot.sh"


def write_png(path: pathlib.Path, width: int, height: int, rgb=(0, 128, 255)) -> None:
    """Minimal valid RGB PNG (no Pillow)."""
    raw = b""
    row = bytes(rgb) * width
    for _ in range(height):
        raw += b"\x00" + row
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(
        b"IEND", b""
    )
    path.write_bytes(data)


def test_dimensions_lib() -> None:
    import sys

    sys.path.insert(0, str(LIB))
    from fr_ipad_screenshot_lib import (  # type: ignore
        ACCEPTED_IPAD_13_SIZES,
        assert_accepted_ipad_13_dimensions,
        pick_13_inch_ipad,
        png_dimensions,
    )

    with tempfile.TemporaryDirectory() as td:
        ok = pathlib.Path(td) / "ok.png"
        write_png(ok, 2064, 2752)
        assert png_dimensions(ok) == (2064, 2752)
        assert assert_accepted_ipad_13_dimensions(ok) == (2064, 2752)

        bad = pathlib.Path(td) / "bad.png"
        write_png(bad, 100, 100)
        try:
            assert_accepted_ipad_13_dimensions(bad)
            raise AssertionError("expected dimension failure")
        except ValueError as exc:
            assert "100x100" in str(exc)

    assert (2064, 2752) in ACCEPTED_IPAD_13_SIZES
    udid, name, _ = pick_13_inch_ipad(
        {
            "devices": {
                "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
                    {"name": "iPad Pro (13-inch) (M4)", "udid": "u1", "isAvailable": True},
                ]
            }
        }
    )
    assert udid == "u1" and "13-inch" in name


def test_generated_wrapper_hardwires_udid_and_paths() -> None:
    """Simulate session wrapper generation — fresh Terminal must not need CM_* env."""
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        shot_dir = td_path / "artifacts" / "ipad-screenshots"
        export_dir = td_path / "export" / "ipad-screenshots"
        shot_dir.mkdir(parents=True)
        export_dir.mkdir(parents=True)
        helper = SHOT
        udid = "DEADBEEF-UDID"
        wrapper = td_path / "fr-ipad-shot"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    f'exec "{helper}" --udid "{udid}" --out "{shot_dir}" --export "{export_dir}" "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        text = wrapper.read_text(encoding="utf-8")
        assert udid in text
        assert str(shot_dir) in text
        assert str(export_dir) in text
        assert "booted" not in text
        # Wrapper must not read FR_IPAD_SCREENSHOT_DIR / CM_EXPORT_DIR at runtime.
        assert "FR_IPAD_SCREENSHOT_DIR" not in text
        assert "CM_EXPORT_DIR" not in text


def test_finish_flag_and_artifact_collect() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        session = td_path / "session"
        shot_dir = td_path / "shots"
        export_dir = td_path / "export"
        session.mkdir()
        shot_dir.mkdir()
        export_dir.mkdir()
        finish = session / "FINISH.flag"
        write_png(shot_dir / "shot-001-boot-smoke.png", 2064, 2752)
        write_png(shot_dir / "shot-002-studio.png", 2064, 2752)

        finish_wrapper = td_path / "fr-ipad-finish"
        finish_wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    f'date -u +%Y-%m-%dT%H:%M:%SZ > "{finish}"',
                    'echo "fr-ipad-finish: signaled"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        finish_wrapper.chmod(0o755)
        subprocess.check_call(["bash", str(finish_wrapper)])
        assert finish.is_file()

        # Mimic session artifact collection after finish.
        for png in shot_dir.glob("shot-*.png"):
            (export_dir / png.name).write_bytes(png.read_bytes())
        exported = sorted(p.name for p in export_dir.glob("shot-*.png"))
        assert exported == ["shot-001-boot-smoke.png", "shot-002-studio.png"]


def test_screenshot_cli_requires_explicit_udid() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(LIB)
    cp = subprocess.run(
        ["bash", str(SHOT), "label-only"],
        env=env,
        text=True,
        capture_output=True,
    )
    assert cp.returncode != 0
    assert "require --udid" in (cp.stderr or "")


def main() -> int:
    test_dimensions_lib()
    test_generated_wrapper_hardwires_udid_and_paths()
    test_finish_flag_and_artifact_collect()
    test_screenshot_cli_requires_explicit_udid()
    print("test_fr_ipad_screenshot_session: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
