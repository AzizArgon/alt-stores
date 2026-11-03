"""Consistent gzip copy of the SQLite database (safe while the site runs) into <ALT_LOCAL_DIR>/backups.

In Docker: docker compose exec -T backend python scripts/backup_db.py [label] [keep]
Daily copies keep the last 14, copies before a deploy - the last 5 (docs/deploy.md).
"""

import gzip
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import LOCAL_DIR, settings  # noqa: E402


def backup(label: str = "daily", keep: int = 14, backups: Path | None = None) -> Path:
    db_path = settings.database_url.removeprefix("sqlite:///")
    folder = backups or LOCAL_DIR / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{datetime.now():%Y-%m-%d_%H%M}_{label}.db"
    src, dst = sqlite3.connect(db_path), sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    with open(target, "rb") as f_in, gzip.open(f"{target}.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    target.unlink()
    for old in sorted(folder.glob(f"*_{label}.db.gz"), reverse=True)[keep:]:
        old.unlink()
    return Path(f"{target}.gz")


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "daily"
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    print(f"backup: {backup(label, keep)}")
