"""Phase 19: how the build-post parser (phase 17.2) reads posts of different styles.

  .venv/Scripts/python.exe scripts/benchmark_builds.py            # rules only (ai=False), no AI requests
  .venv/Scripts/python.exe scripts/benchmark_builds.py --ai       # the real pipeline: cache -> rules -> one AI request

The posts (made up after real ones, no personal data) and the expected parts are in tests/benchmark/builds/posts.json.
The run works on a COPY of database.db with an empty parse cache (a cold run against the real catalog); the working
database is not touched. Per post: parts found in the right slot, parts tied to a card ("exact"), parts with values
only ("specs"), price and currency, used/not used, contacts cut out, rows sent to the AI, seconds.
Result: tests/benchmark/results/builds_<rules|ai>.json and a table on screen.
"""

import argparse
import asyncio
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
POSTS = BACKEND / "tests" / "benchmark" / "builds" / "posts.json"
RESULTS = BACKEND / "tests" / "benchmark" / "results"
CONTACT = re.compile(r"\+?\d[\d\s()\-]{7,}\d|@[a-z0-9_]{3,}", re.I)


def norm(s: str | None) -> str:
    return re.sub(r"[\s\-_]", "", (s or "").lower())


def score_post(post: dict, got: dict) -> dict:
    comps = list(got["components"])
    found = exact = specs = 0
    details = []
    for slot, token in post["parts"]:
        # the first not yet used component of this slot that mentions the token (or any of the slot without one)
        pick = next((c for c in comps if c["slot"] == slot
                     and (token is None or norm(token) in norm(c["raw_text"]))), None)
        if pick is None:
            details.append({"slot": slot, "token": token, "level": "missed"})
            continue
        comps.remove(pick)
        found += 1
        level = pick["level"]
        name = (pick.get("product") or {}).get("name")
        if level == "exact" and (token is None or norm(token) in norm(name)):
            exact += 1
        elif level == "exact":
            level = "wrong_card"
        elif pick.get("specs"):
            specs += 1
        details.append({"slot": slot, "token": token, "level": level, "card": name, "source": pick.get("source")})
    extra = [c["raw_text"] for c in comps if c["slot"] != "other"]
    kept = " ".join([got.get("name") or "", got.get("description") or ""] + [c["raw_text"] for c in got["components"]])
    used = got.get("condition") == "used"
    return {
        "parts": len(post["parts"]), "found": found, "exact": exact, "specs": specs,
        "extra": extra, "details": details,
        "price_ok": got.get("price") == post["price"] and got.get("currency") == post["currency"],
        "used_ok": used == (post["condition"] == "used"),
        "contacts_cut": not CONTACT.search(kept),
        "ai_rows": got.get("ai_pending", 0), "ai": got.get("ai"), "name": got.get("name"),
    }


async def run(ai: bool) -> dict:
    from app.core.config import settings  # noqa: F401  (loads .env for the AI keys)
    from app.services.builds import parse_build_text

    tmp = Path(tempfile.mkdtemp()) / "bench.db"
    shutil.copy(BACKEND / "database.db", tmp)
    engine = create_engine(f"sqlite:///{tmp}")
    with engine.begin() as con:
        con.execute(text("DELETE FROM parse_cache"))  # cold run: nothing was seen before
    db = sessionmaker(bind=engine)()
    out = {}
    for post in json.loads(POSTS.read_text(encoding="utf-8")):
        started = time.monotonic()
        got = await parse_build_text(db, post["text"], ai=ai)
        res = score_post(post, got)
        res["seconds"] = round(time.monotonic() - started, 1)
        res["style"] = post["style"]
        out[post["id"]] = res
    db.close()
    engine.dispose()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", action="store_true")
    args = ap.parse_args()
    out = asyncio.run(run(args.ai))
    tag = "ai" if args.ai else "rules"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"builds_{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'post':5} {'parts':>5} {'found':>5} {'exact':>5} {'specs':>5} {'price':>5} {'used':>5} {'contacts':>8}"
          f" {'ai_rows':>7} {'ai':>8} {'sec':>5}  style")
    t = {"parts": 0, "found": 0, "exact": 0, "specs": 0, "ai_rows": 0, "seconds": 0.0}
    for pid, r in out.items():
        print(f"{pid:5} {r['parts']:5} {r['found']:5} {r['exact']:5} {r['specs']:5} {str(r['price_ok']):>5}"
              f" {str(r['used_ok']):>5} {str(r['contacts_cut']):>8} {r['ai_rows']:7} {str(r['ai']):>8}"
              f" {r['seconds']:5}  {r['style']}")
        for k in t:
            t[k] += r[k]
    print("total", t, "extra parts:", {k: r["extra"] for k, r in out.items() if r["extra"]})


if __name__ == "__main__":
    main()
