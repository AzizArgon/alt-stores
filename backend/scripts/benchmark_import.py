"""Phase 19.1: how long a price upload takes, stage by stage (the seller's cabinet pipeline, stopped at the preview).

  .venv/Scripts/python.exe scripts/benchmark_import.py <price.xlsx> --db <copy.db> [--store <id>] [--cold] [--no-ai]
                                                       [--out result.json]

Works ONLY on a copy of the database (--db must not be backend/database.db): the same functions as the cabinet
(file_to_markdown, clean_markdown, parse_clean_rows, flag_rows, _set, plan_import) wrapped with timers, nothing is
copied and nothing is published. --cold empties the parse cache of the copy first (a store uploading for the first
time); a second run without --cold on the same copy is the warm one. --no-ai: rows that would go to the AI are only
counted (no requests).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _args():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--db", required=True, help="a COPY of the database")
    p.add_argument("--store", type=int, help="store id (default: the real store with 'Age' in its name)")
    p.add_argument("--cold", action="store_true", help="empty the parse cache of the copy first")
    p.add_argument("--no-ai", action="store_true", help="count the AI rows, send nothing")
    p.add_argument("--out", help="write the full result as JSON")
    return p.parse_args()


ARGS = _args()
_db = Path(ARGS.db).resolve()
if _db == (BACKEND / "database.db").resolve() or not _db.exists():
    sys.exit("--db must be an existing COPY of the database, not backend/database.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"  # before the app is imported: SessionLocal -> the copy
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, func, select  # noqa: E402

from app.db.database import SessionLocal, init_db  # noqa: E402
from app.db.models import Currency, ImportStatus, ParseCache, PriceImport, Store  # noqa: E402
from app.services import ai_parser, importer  # noqa: E402
from app.services.branch_stock import known_branch_columns  # noqa: E402
from app.services.price_cleaner import clean_markdown  # noqa: E402

T = time.perf_counter
acc: Counter = Counter()  # seconds per wrapped function
calls: list[dict] = []  # every AI request
waits: list[dict] = []  # limiter waits and retry pauses
marks: dict = {}


def timed(module, name, key, by_source=False):
    """Replace module.name with the same function plus a timer (the logic is untouched)."""
    fn = getattr(module, name)
    if asyncio.iscoroutinefunction(fn):
        async def wrapper(*a, **kw):
            t = T()
            try:
                return await fn(*a, **kw)
            finally:
                acc[key] += T() - t
    else:
        def wrapper(*a, **kw):
            t = T()
            try:
                return fn(*a, **kw)
            finally:
                k = f"{key}:{a[2] if len(a) > 2 else kw.get('source')}" if by_source else key
                acc[k] += T() - t
    setattr(module, name, wrapper)


def _kind(error: Exception) -> str:
    s = str(error)
    for code, kind in (("PerDay", "quota_day"), ("503", "overloaded_503"), ("UNAVAILABLE", "overloaded_503"),
                       ("429", "rate_429"), ("RESOURCE_EXHAUSTED", "rate_429")):
        if code in s:
            return kind
    return type(error).__name__


def ai_call(provider: str, fn):
    async def wrapper(*a):
        model, text = (a[0], a[1]) if provider == "gemini" else ("groq", a[0])
        rec = {"provider": provider, "model": model, "rows": text.count("\n") + 1, "start": T() - marks["t0"]}
        t = T()
        try:
            answer, truncated = await fn(*a)
            rec["result"] = "truncated" if truncated else "ok"
            return answer, truncated
        except Exception as e:
            rec["result"] = _kind(e)
            raise
        finally:
            rec["seconds"] = round(T() - t, 2)
            calls.append(rec)
    return wrapper


def install_timers() -> None:
    timed(importer, "prepare_workbook", "read:prepare_workbook")
    timed(importer, "parse_by_rules", "rules")
    timed(importer, "_preview_row", "normalize", by_source=True)
    timed(importer, "save_cache", "save_cache")
    ai_parser._call_gemini = ai_call("gemini", ai_parser._call_gemini)
    ai_parser._call_groq = ai_call("groq", ai_parser._call_groq)

    delay = ai_parser._retry_delay  # every retry pause: asyncio.sleep(_retry_delay(...)) right after

    def retry_delay(error, attempt):
        d = delay(error, attempt)
        waits.append({"type": "retry_pause", "seconds": round(d, 1), "after": _kind(error)})
        return d
    ai_parser._retry_delay = retry_delay

    acquire = ai_parser.RateLimiter.acquire

    async def limited(self, tokens: int = 0):
        t = T()
        await acquire(self, tokens)
        if T() - t > 0.05:
            waits.append({"type": "rate_limit_wait", "seconds": round(T() - t, 1),
                          "provider": "groq" if self is ai_parser._groq_limiter else "gemini"})
    ai_parser.RateLimiter.acquire = limited


class _Log(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if "using Groq" in msg and "groq_switch" not in marks:
            marks["groq_switch"] = round(T() - marks["t0"], 1)


def find_store(db) -> Store:
    if ARGS.store:
        return db.get(Store, ARGS.store)
    return db.scalar(select(Store).where(Store.is_demo.is_(False), Store.name.ilike("%age%")))


def top_ai_groups(rows: list[dict]) -> list[dict]:
    """What the AI got: by category and by the section of the price (store's own headings), a few short names."""
    by = {}
    for r in rows:
        if r["source"] not in ("ai", "failed"):
            continue
        key = (r["category"], (r.get("section") or r.get("sheet") or "").strip()[:40])
        g = by.setdefault(key, {"category": key[0], "section": key[1], "rows": 0, "examples": [], "brands": Counter()})
        g["rows"] += 1
        g["brands"][r.get("brand") or "-"] += 1
        if len(g["examples"]) < 3:
            g["examples"].append(r["raw_name"][:50])
    out = sorted(by.values(), key=lambda g: -g["rows"])[:10]
    for g in out:
        g["top_brands"] = [b for b, _ in g.pop("brands").most_common(3)]
    return out


async def main() -> dict:
    logging.getLogger("app.services.ai_parser").addHandler(_Log())
    init_db()  # the copy gets today's schema, as the server does on start
    with SessionLocal() as db:
        store = find_store(db)
        if store is None:
            sys.exit("store not found")
        if ARGS.cold:
            n = db.execute(delete(ParseCache)).rowcount
            db.commit()
            print(f"cold: {n} cache entries removed from the copy")
        cache_size = db.scalar(select(func.count()).select_from(ParseCache))
        last = db.scalar(select(PriceImport).where(PriceImport.store_id == store.id).order_by(PriceImport.id.desc()))
        currency = last.currency if last else Currency.USD
        known = known_branch_columns(db, store.id)
    if ARGS.no_ai:
        async def no_ai(rows, stats):
            raise RuntimeError("benchmark --no-ai: not sent")
        importer.parse_rows = no_ai
    install_timers()
    path = Path(ARGS.file)
    data = path.read_bytes()
    st: dict = {}
    marks["t0"] = t0 = T()

    # 1. file -> markdown (the cabinet runs it in a thread)
    notices: list[str] = []
    t = T()
    md = await asyncio.to_thread(importer.file_to_markdown, data, path.name, notices)
    st["read"] = T() - t

    # 2. cleanup by code
    t = T()
    rows = clean_markdown(md, known)
    st["clean"] = T() - t

    # 3-6. cache -> rules -> AI, normalization inside (the same call as run_import)
    stats: dict = {"notices": notices} if notices else {}
    progress = []
    t = T()
    with SessionLocal() as db:
        parsed = await importer.parse_clean_rows(db, rows, stats, lambda d, n: progress.append(T()))
    t_end = T()
    gather_start = progress[0] if progress else t_end
    pre, gather = gather_start - t, t_end - gather_start
    norm_pre = acc["normalize:cache"] + acc["normalize:rule"]
    norm_ai = acc["normalize:ai"] + acc["normalize:failed"]
    st["cache"] = pre - acc["rules"] - norm_pre
    st["rules"] = acc["rules"]
    st["normalize"] = norm_pre + norm_ai
    st["ai"] = gather - norm_ai - acc["save_cache"]
    st["save_cache"] = acc["save_cache"]

    # 7. matching with the reference cards (the publish matcher, nothing written)
    t = T()
    with SessionLocal() as db:
        matcher = importer._Matcher(db)
        found = [matcher.match(r)[3] is not None for r in importer._rows_to_save(parsed)]
    st["match"] = T() - t

    # 8. Anti-Fraud (as _finish)
    t = T()
    with SessionLocal() as db:
        importer.flag_rows(db, parsed, store.id, currency)
    st["antifraud"] = T() - t
    stats["flagged"] = sum(bool(r["flags"]) for r in parsed)

    # 9. preview: rows saved into the import (_set, as _finish) + "what will change" (plan_import)
    t = T()
    with SessionLocal() as db:
        imp = PriceImport(store_id=store.id, filename=path.name, source="file", currency=currency,
                          status=ImportStatus.processing)
        db.add(imp)
        db.commit()
        imp_id = imp.id
    importer._set(imp_id, status=ImportStatus.ready, rows_json=parsed, stats_json=stats)
    with SessionLocal() as db:
        imp = db.get(PriceImport, imp_id)
        plan = importer.plan_import(db, imp, db.get(Store, store.id), imp.rows_json)
    st["preview"] = T() - t
    total = T() - t0

    src = Counter(r["source"] for r in parsed)
    counts = {"read": len(data), "clean": len(rows), "cache": stats.get("cache", 0), "rules": stats.get("rule", 0),
              "ai": stats.get("ai_rows", 0), "normalize": len(parsed), "match": len(found),
              "antifraud": stats["flagged"], "preview": len(parsed)}
    ai_wait = sum(w["seconds"] for w in waits)
    return {
        "file": path.name, "mode": "cold" if ARGS.cold else "warm/as-is", "no_ai": ARGS.no_ai,
        "cache_entries_before": cache_size, "total_seconds": round(total, 2),
        "stages": {k: {"seconds": round(v, 3), "share": round(v / total, 4), "rows": counts.get(k)}
                   for k, v in st.items()},
        "read_split": {"prepare_workbook": round(acc["read:prepare_workbook"], 2)},
        "rows": {"clean": len(rows), "preview": len(parsed), "by_source": dict(src),
                 "cache_hits": stats.get("cache", 0), "rule": stats.get("rule", 0), "ai_rows": stats.get("ai_rows", 0),
                 "skipped_not_product": len(rows) - len(parsed)},
        "ai": {"chunks": stats.get("chunks", 0), "requests": stats.get("requests", 0),
               "groq_requests": stats.get("groq_requests", 0), "splits": stats.get("splits", 0),
               "models": stats.get("models", {}), "quota_hit": bool(stats.get("quota_hit")),
               "failed_rows": stats.get("failed_rows", 0), "groq_switch_at": marks.get("groq_switch"),
               "calls": calls, "waits": waits,
               "answer_seconds": round(sum(c["seconds"] for c in calls), 1),
               "ok_answer_seconds": round(sum(c["seconds"] for c in calls if c["result"] == "ok"), 1),
               "wait_seconds": round(ai_wait, 1)},
        "match": {"rows": len(found), "existing_card": sum(found), "new_card": len(found) - sum(found),
                  "plan_new_offers": len(plan["new"]), "plan_unchanged": plan["unchanged"],
                  "plan_price_changed": len(plan["price_up"]) + len(plan["price_down"]),
                  "plan_out_of_stock": len(plan["out_of_stock"])},
        "flagged": stats["flagged"],
        "top_ai_groups": top_ai_groups(parsed),
    }


if __name__ == "__main__":
    res = asyncio.run(main())
    if ARGS.out:
        Path(ARGS.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n{res['file']} | {res['mode']} | total {res['total_seconds']} s")
    print(f"{'stage':<12}{'seconds':>10}{'share':>8}{'rows':>8}")
    for k, v in res["stages"].items():
        print(f"{k:<12}{v['seconds']:>10.2f}{v['share']:>8.1%}{v['rows'] if v['rows'] is not None else '':>8}")
    a = res["ai"]
    print(f"rows: {res['rows']['by_source']} | AI: {a['chunks']} chunks, {a['requests']} requests, "
          f"answers {a['answer_seconds']} s, waits {a['wait_seconds']} s, groq switch {a['groq_switch_at']}")
    print(f"match: {res['match']}")
