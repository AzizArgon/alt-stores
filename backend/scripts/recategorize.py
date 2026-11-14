"""Phase 16.1: cards to the categories of the rules (ink -> "Расходники", bags and pads out of "Прочее").

Without --apply only a report; with --apply a copy of the DB goes to <ALT_LOCAL_DIR>/backups first, then the
cards move, their specs and keys are recomputed (printers: "3 в 1" / "4 в 1"). After it: recheck_flags.py.
No AI requests. Usage (from backend/, on the server — in Docker):
  .venv/Scripts/python.exe scripts/recategorize.py [--apply] [--all]
  docker compose exec -T backend python scripts/recategorize.py [--apply]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.database import SessionLocal, init_db  # noqa: E402
from app.services import recategorize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="move the cards")
    parser.add_argument("--all", action="store_true", help="print every card that moves")
    args = parser.parse_args()
    init_db()  # new categories and columns on an old DB
    with SessionLocal() as db:
        found = recategorize.report(db)
        print(f"Cards to move: {len(found['moves'])}")
        for pair, n in found["by_pair"].items():
            print(f"  {pair}: {n}")
        for m in found["moves"] if args.all else []:
            print(f"  [{m['id']}] {m['from']} -> {m['to']}: {m['name']}")
        if not args.apply:
            print("\nCards per category now:", found["categories"])
            print("Run with --apply to move them.")
            return
        from scripts.backup_db import backup

        print(f"DB copy: {backup('before_recategorize', keep=10)}")
        result = recategorize.apply(db)
    print(f"Moved: {result['moved']}, merged with a card of the new category: {result['merged']}")
    for slug in sorted(set(result["before"]) | set(result["after"]), key=lambda s: -result["after"].get(s, 0)):
        print(f"  {slug}: {result['before'].get(slug, 0)} -> {result['after'].get(slug, 0)}")


if __name__ == "__main__":
    main()
