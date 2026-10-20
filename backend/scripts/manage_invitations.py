"""
Operator CLI: create / inspect / revoke invite-only beta invitations.

Usage (from backend/, venv active):

  # Preferred under Cursor/SSH: write the one-time code to a NEW 0600 file (never stdout)
  python scripts/manage_invitations.py create user@example.com --hours 72 \\
      --code-file /var/lib/fashionrise/invites/user.code

  python scripts/manage_invitations.py status --email user@example.com
  python scripts/manage_invitations.py status --id <uuid>
  python scripts/manage_invitations.py revoke --id <uuid>

  # Local interactive only — prints the code to stdout (avoid under agent tooling):
  python scripts/manage_invitations.py create user@example.com --print-code

Plaintext invitation tokens are never stored in the database (digest only).
Do not paste production codes into tickets, PRs, or Cursor chat.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services import invitation_service  # noqa: E402


class InvitationCodeDeliveryError(RuntimeError):
    """Secure code-file delivery failed. Message must never include the plaintext code."""


def _print_row(row) -> None:
    status = invitation_service.invitation_status(row)
    print(f"id={row.id}")
    print(f"email={row.email_normalized}")
    print(f"status={status}")
    print(f"expires_at={row.expires_at.isoformat()}")
    print(f"created_at={row.created_at.isoformat() if row.created_at else ''}")
    print(f"revoked_at={row.revoked_at.isoformat() if row.revoked_at else ''}")
    print(f"redeemed_at={row.redeemed_at.isoformat() if row.redeemed_at else ''}")
    print(f"redeemed_by_user_id={row.redeemed_by_user_id or ''}")
    print(f"note={row.note or ''}")
    print("token=REDACTED")


def _assert_code_file_destination_safe(path: Path) -> Path:
    """Fail closed before creating an invitation if the destination is unsafe."""
    path = path.expanduser()
    if path.exists() or path.is_symlink():
        raise InvitationCodeDeliveryError(
            "invitation code file already exists or is a symlink; refusing to overwrite"
        )
    parent = path.parent
    if parent.exists() and parent.is_symlink():
        raise InvitationCodeDeliveryError(
            "invitation code directory is a symlink; refusing unsafe delivery path"
        )
    # Create the parent directory if needed (not a symlink race on the leaf).
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise InvitationCodeDeliveryError(
            "invitation code directory resolved to a symlink; refusing unsafe delivery path"
        )
    # Re-check leaf after mkdir in case of races / odd mounts.
    if path.exists() or path.is_symlink():
        raise InvitationCodeDeliveryError(
            "invitation code file already exists or is a symlink; refusing to overwrite"
        )
    return path


def _write_code_file(path: Path, code: str) -> Path:
    """Create a new owner-only file. Never truncate, overwrite, or follow symlinks."""
    path = _assert_code_file_destination_safe(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError as exc:
        raise InvitationCodeDeliveryError(
            "invitation code file already exists; refusing to overwrite"
        ) from exc
    except OSError as exc:
        # Do not include path details that might echo secrets; keep message generic.
        raise InvitationCodeDeliveryError(
            f"failed to create invitation code file ({type(exc).__name__})"
        ) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(code)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise InvitationCodeDeliveryError(
            f"failed to write invitation code file ({type(exc).__name__})"
        ) from exc

    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    # Final symlink/mode check on the created inode path.
    if path.is_symlink():
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise InvitationCodeDeliveryError(
            "invitation code path became a symlink after create; refusing delivery"
        )
    return path


def _revoke_undelivered(db, invitation_id: uuid.UUID) -> None:
    """Best-effort revoke so a failed delivery leaves no redeemable orphan invite."""
    invitation_service.revoke_invitation(db, invitation_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage FashionRise beta registration invitations.")
    sub = parser.add_subparsers(dest="command", required=True)

    create_p = sub.add_parser("create", help="Create a single-use invitation for one email")
    create_p.add_argument("email", help="Invited email address")
    create_p.add_argument("--hours", type=int, default=72, help="Expiry in hours (default 72)")
    create_p.add_argument("--note", default=None, help="Optional operator note (not a secret)")
    create_p.add_argument(
        "--code-file",
        type=Path,
        default=None,
        help="Write the one-time invitation code to a NEW file with mode 0600 (recommended)",
    )
    create_p.add_argument(
        "--print-code",
        action="store_true",
        help="Print invitation code to stdout (local interactive only; avoid under Cursor/SSH logs)",
    )

    status_p = sub.add_parser("status", help="Inspect invitation status (never prints the token)")
    status_p.add_argument("--id", dest="invitation_id", default=None, help="Invitation UUID")
    status_p.add_argument("--email", default=None, help="List invitations for this email")

    revoke_p = sub.add_parser("revoke", help="Revoke an unused invitation")
    revoke_p.add_argument("--id", dest="invitation_id", required=True, help="Invitation UUID")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "create":
            if not args.code_file and not args.print_code:
                print(
                    "Refusing to emit an invitation code without --code-file or --print-code. "
                    "Prefer --code-file so agent/SSH logs never capture the secret.",
                    file=sys.stderr,
                )
                sys.exit(2)

            # Validate destination before inserting so we do not create an orphan on
            # obvious path problems (existing file / symlink).
            code_path: Path | None = None
            if args.code_file:
                try:
                    code_path = _assert_code_file_destination_safe(args.code_file)
                except InvitationCodeDeliveryError as exc:
                    print(f"invitation_code_delivery_failed: {exc}", file=sys.stderr)
                    sys.exit(2)

            created = invitation_service.create_invitation(
                db,
                email=args.email,
                expires_in_hours=args.hours,
                note=args.note,
            )
            print(f"id={created.id}")
            print(f"email={created.email}")
            print(f"expires_at={created.expires_at.isoformat()}")

            if code_path is not None:
                try:
                    written = _write_code_file(code_path, created.plaintext_token)
                except InvitationCodeDeliveryError as exc:
                    # Never print the plaintext token. Revoke so the invite cannot be used.
                    try:
                        _revoke_undelivered(db, created.id)
                        print(
                            "invitation_revoked_after_delivery_failure=yes",
                            file=sys.stderr,
                        )
                    except Exception as revoke_exc:  # noqa: BLE001
                        print(
                            f"invitation_revoke_after_delivery_failure_error="
                            f"{type(revoke_exc).__name__}",
                            file=sys.stderr,
                        )
                    print(f"invitation_code_delivery_failed: {exc}", file=sys.stderr)
                    sys.exit(1)
                print(f"invitation_code_file={written}")
                print("Read the code from that file out-of-band; it is not printed here.")

            if args.print_code:
                print(f"invitation_code={created.plaintext_token}")
                print(
                    "Deliver the invitation_code out-of-band. "
                    "It will not be stored in the database."
                )
            return

        if args.command == "status":
            if args.invitation_id:
                row = invitation_service.get_invitation(db, uuid.UUID(args.invitation_id))
                if not row:
                    print("Invitation not found", file=sys.stderr)
                    sys.exit(1)
                _print_row(row)
                return
            if args.email:
                rows = invitation_service.list_invitations_for_email(db, args.email)
                if not rows:
                    print("No invitations for that email")
                    return
                for i, row in enumerate(rows):
                    if i:
                        print("---")
                    _print_row(row)
                return
            print("Provide --id or --email", file=sys.stderr)
            sys.exit(2)

        if args.command == "revoke":
            row = invitation_service.revoke_invitation(db, uuid.UUID(args.invitation_id))
            _print_row(row)
            return
    finally:
        db.close()


if __name__ == "__main__":
    main()
