"""Secure invitation code delivery — no DB, no plaintext on stdout by default."""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "manage_invitations.py"

SECRET = "super-secret-invitation-token-value"


def _load_script():
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    # Unique module name per load so monkeypatches do not leak across tests.
    name = f"manage_invitations_under_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _created():
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="ops@example.com",
        expires_at=SimpleNamespace(isoformat=lambda: "2026-10-21T00:00:00+00:00"),
        plaintext_token=SECRET,
    )


def test_write_code_file_is_owner_only_new_file(tmp_path, monkeypatch, capsys):
    mi = _load_script()
    created = _created()
    monkeypatch.setattr(mi.invitation_service, "create_invitation", lambda *a, **k: created)
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))

    out_file = tmp_path / "invite.code"
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage_invitations.py", "create", "ops@example.com", "--code-file", str(out_file)],
    )

    mi.main()
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert "invitation_code_file=" in captured.out
    assert out_file.read_text(encoding="utf-8").strip() == SECRET
    assert stat.S_IMODE(out_file.stat().st_mode) == 0o600


def test_create_refuses_without_delivery_flag(monkeypatch, capsys):
    mi = _load_script()
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(sys, "argv", ["manage_invitations.py", "create", "ops@example.com"])
    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 2
    assert "--code-file" in capsys.readouterr().err


def test_refuses_existing_file_without_creating_invitation(tmp_path, monkeypatch, capsys):
    mi = _load_script()
    existing = tmp_path / "invite.code"
    existing.write_text("old-secret\n", encoding="utf-8")

    created_calls: list[object] = []

    def create_should_not_run(*a, **k):  # noqa: ANN001
        created_calls.append(1)
        raise AssertionError("must not create invitation when code file exists")

    monkeypatch.setattr(mi.invitation_service, "create_invitation", create_should_not_run)
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage_invitations.py", "create", "ops@example.com", "--code-file", str(existing)],
    )

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 2
    assert created_calls == []
    assert existing.read_text(encoding="utf-8") == "old-secret\n"
    err = capsys.readouterr().err
    assert "already exists" in err
    assert SECRET not in err
    assert "old-secret" not in err


def test_refuses_symlink_destination(tmp_path, monkeypatch, capsys):
    mi = _load_script()
    target = tmp_path / "real.code"
    target.write_text("other\n", encoding="utf-8")
    link = tmp_path / "invite.code"
    link.symlink_to(target)

    created_calls: list[object] = []

    def create_should_not_run(*a, **k):  # noqa: ANN001
        created_calls.append(1)
        raise AssertionError("must not create invitation for symlink code-file")

    monkeypatch.setattr(mi.invitation_service, "create_invitation", create_should_not_run)
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage_invitations.py", "create", "ops@example.com", "--code-file", str(link)],
    )

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 2
    assert created_calls == []
    assert target.read_text(encoding="utf-8") == "other\n"
    err = capsys.readouterr().err
    assert "symlink" in err.lower() or "already exists" in err
    assert SECRET not in err


def test_write_failure_revokes_invitation_and_hides_secret(tmp_path, monkeypatch, capsys):
    mi = _load_script()
    created = _created()
    revoked: list[uuid.UUID] = []

    monkeypatch.setattr(mi.invitation_service, "create_invitation", lambda *a, **k: created)

    def revoke(db, invitation_id):  # noqa: ANN001
        revoked.append(invitation_id)
        return SimpleNamespace(id=invitation_id)

    monkeypatch.setattr(mi.invitation_service, "revoke_invitation", revoke)
    monkeypatch.setattr(mi, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))

    out_file = tmp_path / "invite.code"

    def boom_open(*a, **k):  # noqa: ANN001
        raise OSError("disk full")

    monkeypatch.setattr(mi.os, "open", boom_open)
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage_invitations.py", "create", "ops@example.com", "--code-file", str(out_file)],
    )

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 1
    assert revoked == [created.id]
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert "invitation_revoked_after_delivery_failure=yes" in captured.err
    assert "invitation_code_delivery_failed" in captured.err
    assert not out_file.exists()


def test_assert_helpers_reject_symlink_parent(tmp_path):
    mi = _load_script()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link_dir = tmp_path / "linkdir"
    link_dir.symlink_to(real_dir)
    with pytest.raises(mi.InvitationCodeDeliveryError, match="symlink"):
        mi._assert_code_file_destination_safe(link_dir / "invite.code")
