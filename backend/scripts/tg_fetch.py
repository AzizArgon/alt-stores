"""Collects new posts of the enabled Telegram channels (phase 9) and prints what came of them.

Only the posts after the last processed one, at most 50 per run for all channels (the free AI limits), a pause
between channels. The schedule on the server comes in phase 20.
Usage (from backend/):
  .venv/Scripts/python.exe scripts/tg_fetch.py [--max 50] [--channel NAME]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REASONS = {
    "no_price": "no price in the text", "image_price": "price only on a picture", "no_model": "no product model",
    "ad": "advert, no product", "sold": "already sold", "old": "older than 30 days", "no_text": "no text",
    "ai_failed": "AI failed (retried next run)", "build": "a whole PC", "bundle": "a kit, one price",
    "other_category": "not a catalog category",
}


def main() -> int:
    from sqlalchemy import select

    from app.db.database import SessionLocal, init_db
    from app.db.models import TgChannel
    from app.services import telegram

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=telegram.MAX_POSTS, help="new posts per run (all channels)")
    ap.add_argument("--channel", help="only this channel")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    init_db()
    with SessionLocal() as db:
        if args.channel:
            ch = db.scalar(select(TgChannel).where(TgChannel.username == args.channel.lstrip("@")))
            if ch is None:
                print(f"No channel @{args.channel}")
                return 1
            logs = [asyncio.run(telegram.run_channel(db, ch, args.max))]
            logs[0].expired = telegram.expire_old(db)
        else:
            logs = asyncio.run(telegram.run_all(db, max_posts=args.max))
    if not logs:
        print("No enabled channels. Add one: scripts/tg_channels.py add <channel>")
        return 0
    print(f"{'channel':<26}{'on page':>8}{'new':>6}{'ads':>6}{'offers':>8}{'sold':>6}{'gone':>6}  skipped")
    for g in logs:
        skipped = ", ".join(f"{REASONS.get(k, k)}: {v}" for k, v in sorted(g.skipped.items())) or "-"
        print(f"@{g.username:<25}{g.fetched:>8}{g.new:>6}{g.parsed:>6}{g.offers:>8}{g.sold:>6}{g.gone:>6}  {skipped}")
        if g.error:
            print(f"  error: {g.error}")
    print(f"Ads older than 30 days taken off: {logs[0].expired}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
