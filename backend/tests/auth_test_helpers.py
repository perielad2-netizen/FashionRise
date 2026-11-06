"""Shared helpers for invite-gated registration in API tests."""

from __future__ import annotations

from app.services import invitation_service


def register_with_invite(
    client,
    db_session,
    email: str,
    username: str,
    password: str = "StrongPass123!",
    *,
    display_name: str | None = None,
) -> dict:
    created = invitation_service.create_invitation(db_session, email=email, expires_in_hours=72)
    payload = {
        "email": email,
        "username": username,
        "password": password,
        "display_name": display_name if display_name is not None else username,
        "invitation_code": created.plaintext_token,
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 200, r.text
    return r.json()
