import gzip
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backup_db  # noqa: E402


def test_backup_is_a_full_copy_and_old_ones_go(tmp_path, monkeypatch):
    db = tmp_path / "database.db"
    with sqlite3.connect(db) as con:
        con.execute("create table t (x)")
        con.execute("insert into t values (42)")
    monkeypatch.setattr(backup_db.settings, "database_url", f"sqlite:///{db}")
    folder = tmp_path / "backups"
    folder.mkdir()
    for day in ("2026-01-01", "2026-01-02", "2026-01-03"):
        (folder / f"{day}_0330_daily.db.gz").write_bytes(b"")
    (folder / "2026-01-01_0100_before_deploy.db.gz").write_bytes(b"")

    made = backup_db.backup("daily", 2, folder)

    restored = tmp_path / "restored.db"
    restored.write_bytes(gzip.decompress(made.read_bytes()))
    with sqlite3.connect(restored) as con:
        assert con.execute("select x from t").fetchone() == (42,)
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["2026-01-01_0100_before_deploy.db.gz", "2026-01-03_0330_daily.db.gz", made.name]
