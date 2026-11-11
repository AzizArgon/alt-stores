"""Creates an admin, or makes an existing account an admin (phase 13). There is no admin registration on the site.

The password is typed in this terminal only (hidden, twice): never a file, the command line or the chat.
An account with a store is refused (a seller would lose the cabinet) — use another email.
Usage (from backend/):
  .venv/Scripts/python.exe scripts/create_admin.py EMAIL
On the server (Docker, phase 20):
  ssh -t <server> "cd /opt/alt-stores && docker compose exec backend python scripts/create_admin.py EMAIL"
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import User, UserRole  # noqa: E402
from scripts.set_account import validate  # noqa: E402


def create_admin(db: Session, email: str, password: str) -> tuple[User, bool]:
    """(the admin, True if the account is new). Unblocks it: an admin is never blocked."""
    email = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    created = user is None
    if created:
        user = User(email=email, password_hash=hash_password(password), role=UserRole.admin)
        db.add(user)
    else:
        if user.stores:
            raise SystemExit(f"{email} has a store ({user.stores[0].name}): use another email for the admin")
        user.role, user.password_hash = UserRole.admin, hash_password(password)
        user.blocked_at = user.block_reason = None
    db.commit()
    return user, created


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    args = parser.parse_args()

    from app.db.database import SessionLocal, init_db

    init_db()
    while True:
        password = getpass.getpass("Admin password: ")
        if (error := validate(args.email, password)) is not None:
            print(error)
        elif getpass.getpass("Again: ") != password:
            print("passwords differ")
        else:
            break
    with SessionLocal() as db:
        user, created = create_admin(db, args.email, password)
        print(f"{'created' if created else 'made admin'}: {user.email} — log in at /admin/login")
