"""
Dev / admin: reset a user's bcrypt password by email.

Usage (from backend/, venv active):
  python scripts/set_user_password.py perielad@gmail.com "NewSecurePass123"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root: backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Set FashionRise user password by email.")
    parser.add_argument("email", help="User email (case-insensitive)")
    parser.add_argument("new_password", help="New password (min 8 chars recommended)")
    args = parser.parse_args()

    email_norm = args.email.strip().lower()
    pwd = args.new_password.strip()
    if len(pwd) < 8:
        print("Warning: password is shorter than 8 characters (API register requires 8+).", file=sys.stderr)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(func.lower(User.email) == email_norm))
        if not user:
            print(f"No user with email {email_norm!r}", file=sys.stderr)
            sys.exit(1)
        user.hashed_password = hash_password(pwd)
        db.add(user)
        db.commit()
        print(f"Password updated for {user.email} (id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
