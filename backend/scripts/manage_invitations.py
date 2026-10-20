"""
Operator CLI: create / inspect / revoke invite-only beta invitations.

Usage (from backend/, venv active):

  python scripts/manage_invitations.py create user@example.com --hours 72
  python scripts/manage_invitations.py status --email user@example.com
  python scripts/manage_invitations.py status --id <uuid>
  python scripts/manage_invitations.py revoke --id <uuid>

The plaintext invitation code is printed ONLY on create. Store it out-of-band;
never commit it, paste it into tickets, or leave it in shell history on shared hosts.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services import invitation_service  # noqa: E402


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
    # Never print token_hash in operator-facing status (still a secret amenity).
    print("token=REDACTED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage FashionRise beta registration invitations.")
    sub = parser.add_subparsers(dest="command", required=True)

    create_p = sub.add_parser("create", help="Create a single-use invitation for one email")
    create_p.add_argument("email", help="Invited email address")
    create_p.add_argument("--hours", type=int, default=72, help="Expiry in hours (default 72)")
    create_p.add_argument("--note", default=None, help="Optional operator note (not a secret)")

    status_p = sub.add_parser("status", help="Inspect invitation status (never prints the token)")
    status_p.add_argument("--id", dest="invitation_id", default=None, help="Invitation UUID")
    status_p.add_argument("--email", default=None, help="List invitations for this email")

    revoke_p = sub.add_parser("revoke", help="Revoke an unused invitation")
    revoke_p.add_argument("--id", dest="invitation_id", required=True, help="Invitation UUID")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "create":
            created = invitation_service.create_invitation(
                db,
                email=args.email,
                expires_in_hours=args.hours,
                note=args.note,
            )
            print(f"id={created.id}")
            print(f"email={created.email}")
            print(f"expires_at={created.expires_at.isoformat()}")
            print(f"invitation_code={created.plaintext_token}")
            print("Deliver the invitation_code out-of-band. It will not be shown again.")
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
