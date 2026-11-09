"""Public Telegram channels whose ads are collected (phase 9; managed from the admin in phase 13).

Usage (from backend/):
  .venv/Scripts/python.exe scripts/tg_channels.py add <channel> [--title "Name"] [--city tashkent]
  .venv/Scripts/python.exe scripts/tg_channels.py list
  .venv/Scripts/python.exe scripts/tg_channels.py disable <channel>   (enable <channel> to switch back)
  .venv/Scripts/python.exe scripts/tg_channels.py remove <channel>    (its ads and collected posts go too)
<channel> is the name from t.me/<channel> (with or without @ or the link).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402


def _name(raw: str) -> str:
    return raw.strip().removeprefix("https://").removeprefix("t.me/").removeprefix("s/").lstrip("@").strip("/")


def main() -> int:
    from app.db.database import SessionLocal, init_db
    from app.db.models import Offer, Store, TgChannel, TgPost, User
    from app.db.seed import CITIES
    from app.services.telegram import add_channel

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("channel")
    add.add_argument("--title")
    add.add_argument("--city", default="tashkent", choices=sorted(CITIES))
    sub.add_parser("list")
    for cmd in ("disable", "enable", "remove"):
        sub.add_parser(cmd).add_argument("channel")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        if args.cmd == "add":
            try:
                ch = add_channel(db, args.channel, args.title, args.city)
            except ValueError as e:
                print(f"Error: {e}")
                return 1
            print(f"Added @{ch.username} ({ch.title}, {ch.city}). Collect: scripts/tg_fetch.py")
            return 0
        if args.cmd == "list":
            rows = db.scalars(select(TgChannel).order_by(TgChannel.username)).all()
            if not rows:
                print("No channels. Add one: scripts/tg_channels.py add <channel>")
            for ch in rows:
                ads = db.scalar(select(func.count(Offer.id)).where(Offer.store_id == ch.store_id,
                                                                  Offer.is_in_stock.is_(True)))
                checked = ch.checked_at.strftime("%Y-%m-%d %H:%M") if ch.checked_at else "never"
                print(f"@{ch.username:<24} {'on ' if ch.enabled else 'off'}  {ch.city:<10} last post {ch.last_post_id:<7} "
                      f"checked {checked:<16} ads {ads}  {ch.title}")
            return 0
        ch = db.scalar(select(TgChannel).where(TgChannel.username == _name(args.channel)))
        if ch is None:
            print(f"No channel @{_name(args.channel)}")
            return 1
        if args.cmd in ("disable", "enable"):
            ch.enabled = args.cmd == "enable"
            db.commit()
            print(f"@{ch.username}: {'enabled' if ch.enabled else 'disabled'}")
            return 0
        store = db.get(Store, ch.store_id)
        for offer in db.scalars(select(Offer).where(Offer.store_id == store.id)):
            db.delete(offer)  # with its price history, flags and events
        db.query(TgPost).filter(TgPost.channel_id == ch.id).delete()
        db.delete(ch)
        db.flush()
        user = db.get(User, store.user_id)
        db.delete(store)
        db.flush()
        db.delete(user)
        db.commit()
        print(f"Removed @{_name(args.channel)} with its ads")
        return 0


if __name__ == "__main__":
    sys.exit(main())
