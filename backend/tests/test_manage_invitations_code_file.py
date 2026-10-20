"""Secure invitation code delivery — no DB, no plaintext on stdout by default."""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "manage_invitations.py"


def _load_script():
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    spec = importlib.util.spec_from_file_location("manage_invitations_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_write_code_file_is_owner_only(tmp_path, monkeypatch, capsys):
    mi = _load_script()

    created = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="ops@example.com",
        expires_at=SimpleNamespace(isoformat=lambda: "2026-10-21T00:00:00+00:00"),
        plaintext_token="super-secret-invitation-token-value",
    )

    monkeypatch.setattr(
        mi.invitation_service,
        "create_invitation",
        lambda *a, **k: created,
    )
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))

    out_file = tmp_path / "invite.code"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage_invitations.py",
            "create",
            "ops@example.com",
            "--code-file",
            str(out_file),
        ],
    )

    mi.main()
    captured = capsys.readouterr()
    assert "super-secret-invitation-token-value" not in captured.out
    assert "super-secret-invitation-token-value" not in captured.err
    assert "invitation_code_file=" in captured.out
    assert out_file.read_text(encoding="utf-8").strip() == "super-secret-invitation-token-value"
    mode = stat.S_IMODE(out_file.stat().st_mode)
    assert mode == 0o600


def test_create_refuses_without_delivery_flag(monkeypatch, capsys):
    mi = _load_script()
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage_invitations.py", "create", "ops@example.com"],
    )
    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--code-file" in err
