"""Gives an existing account a new email and password and marks its store real (not demo, verified).

For the owner of the real store: the password is typed in this terminal (hidden, twice), it never goes to a file,
the command line or the chat. The rules are the same as at registration (scripts/demo_reset.py keeps the account).
Usage (from backend/):
  .venv/Scripts/python.exe scripts/set_account.py OLD_EMAIL [NEW_EMAIL]
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import User  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402


def validate(email: str, password: str) -> str | None:
    """The registration rules; returns the error text or None."""
    try:
        RegisterRequest(email=email, password=password)
    except ValidationError as e:
        return "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
    return None


def set_account(db: Session, old_email: str, new_email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == old_email.lower()))
    if user is None:
        raise SystemExit(f"not found: {old_email}")
    new_email = new_email.lower()
    if new_email != user.email and db.scalar(select(User).where(User.email == new_email)):
        raise SystemExit(f"already registered: {new_email}")
    user.email = new_email
    user.password_hash = hash_password(password)
    for store in user.stores:
        store.is_demo = False
        store.is_verified = True
    db.commit()
    return user


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("old_email")
    parser.add_argument("new_email", nargs="?", help="leave out to keep the email")
    args = parser.parse_args()
    new_email = args.new_email or args.old_email

    from app.db.database import SessionLocal, init_db

    init_db()  # an older DB gets the is_demo column
    while True:
        password = getpass.getpass("New password: ")
        if (error := validate(new_email, password)) is not None:
            print(error)
        elif getpass.getpass("Again: ") != password:
            print("passwords differ")
        else:
            break
    with SessionLocal() as db:
        user = set_account(db, args.old_email, new_email, password)
        print(f"done: {user.email}, stores real and verified: {[s.name for s in user.stores]}")
