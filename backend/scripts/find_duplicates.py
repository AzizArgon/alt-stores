"""Phase 16.1: finds cards of one product ("one product — one card") and merges them.

Without --apply only a report: groups of cards with the same key (merged by --apply) and possible duplicates
(the same brand + model in two categories: sent to the admin, "Исправления карточек"). With --apply a copy of
the DB goes to <ALT_LOCAL_DIR>/backups first. No AI requests. Usage (from backend/, on the server — in Docker):
  .venv/Scripts/python.exe scripts/find_duplicates.py [--apply] [--limit 30]
  docker compose exec -T backend python scripts/find_duplicates.py [--apply]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.database import SessionLocal, init_db  # noqa: E402
from app.services import duplicates  # noqa: E402


def _print_groups(title: str, groups: list, limit: int) -> None:
    print(f"\n{title}: {len(groups)}")
    for group in groups[:limit]:
        keeper, *others = group
        print(f"  [{keeper['id']}] {keeper['name']} ({keeper['category']}, offers {keeper['offers']})")
        for p in others:
            print(f"     <- [{p['id']}] {p['name']} ({p['category']}, offers {p['offers']})")
    if len(groups) > limit:
        print(f"  ... and {len(groups) - limit} more")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="merge sure duplicates, send doubtful ones to the admin")
    parser.add_argument("--limit", type=int, default=30, help="groups to print")
    args = parser.parse_args()
    init_db()  # new columns (products.merged_into, product_fixes.kind) on an old DB
    with SessionLocal() as db:
        if args.apply:
            from scripts.backup_db import backup

            print(f"DB copy: {backup('before_find_duplicates', keep=10)}")
            result = duplicates.apply(db)
        else:
            result = duplicates.report(db)
    _print_groups("Same key (one card)", result["sure"], args.limit)
    _print_groups("Possible duplicates (another category)", result["doubtful"], args.limit)
    if args.apply:
        print(f"\nMerged cards: {result['merged']}, sent to the admin: {result['sent_to_admin']}")
    else:
        print(f"\nWould merge {result['merge_cards']} cards. Run with --apply to do it.")


if __name__ == "__main__":
    main()
