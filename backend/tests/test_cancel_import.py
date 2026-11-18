"""Phase 17.6: cancelling an unpublished upload - rows dropped, offers untouched, cache kept, 7-day auto-cancel."""

import asyncio
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import ImportStatus, Offer, ParseCache, PriceHistory, PriceImport, UserRole, utcnow
from app.services import importer
from app.services.importer import cancel_import, cancel_stale_imports, publish_import
from app.services.price_cleaner import CleanRow
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row, _store


def _state(db):
    offers = [(o.id, o.price, o.is_in_stock, o.raw_name) for o in db.scalars(select(Offer).order_by(Offer.id))]
    return offers, db.scalar(select(func.count(PriceHistory.id)))


def _pending(db, store, status=ImportStatus.ready):
    imp = _imp(db, store)
    imp.status = status
    imp.rows_json = [_row(1, "Lexar DDR4 8GB 3200MHz", 99), _row(5, "Goodram DDR4 8GB 2666MHz", 25)]
    imp.columns_json = {"Склад": None}
    db.commit()
    return imp


def test_cancel_drops_rows_and_keeps_offers_prices_and_cache(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    db.add(ParseCache(key="lexar ddr4 8gb", data={"category": "ram"}, source="ai"))
    db.commit()
    before = _state(db)
    imp = _pending(db, store)

    cancel_import(db, imp)
    db.refresh(imp)
    assert imp.status == ImportStatus.cancelled and imp.rows_json == [] and imp.columns_json is None
    assert imp.filename == "p.xlsx" and imp.created_at is not None  # stays in the history
    assert _state(db) == before
    assert db.scalar(select(ParseCache).where(ParseCache.key == "lexar ddr4 8gb")) is not None


def test_auto_cancel_after_seven_days(db):
    store = _store(db, "a@example.com")
    old, fresh, failed, published = (_pending(db, store), _pending(db, store),
                                     _pending(db, store, ImportStatus.failed), _imp(db, store))
    publish_import(db, published, store, FIRST)
    for imp in (old, failed, published):
        imp.created_at = utcnow() - timedelta(days=8)
    db.commit()

    assert cancel_stale_imports(db) == 2
    for imp in (old, fresh, failed, published):
        db.refresh(imp)
    assert old.status == failed.status == ImportStatus.cancelled and old.rows_json == []
    assert fresh.status == ImportStatus.ready and fresh.rows_json
    assert published.status == ImportStatus.published


def test_background_parse_stops_and_cannot_revive_a_cancelled_import(db, monkeypatch):
    """Cancelled while parsing: no new AI requests, and the finished parse doesn't bring the rows back."""
    store = _store(db, "a@example.com")
    imp = _pending(db, store, ImportStatus.processing)
    monkeypatch.setattr(importer, "SessionLocal", lambda: _NoClose(db))
    monkeypatch.setattr(importer.settings, "parser_chunk_rows", 1)
    monkeypatch.setattr(importer.settings, "parser_concurrency", 1)
    monkeypatch.setattr(importer, "parse_by_rules", lambda name: None)
    calls = []

    async def fake_ai(chunk, stats):
        calls.append(chunk[0].row)
        cancel_import(db, db.get(PriceImport, imp.id))  # the seller cancels during the first request
        return [{"row": chunk[0].row, "category": "ram", "name": chunk[0].name, "brand": "Lexar", "specs": {}}]

    monkeypatch.setattr(importer, "parse_rows", fake_ai)
    rows = [CleanRow(row=n, sheet="", section="", name=f"Item {n}", ai_text=f"Item {n}", price=10, currency=None, is_in_stock=True)
            for n in (1, 2, 3)]
    stats: dict = {}
    parsed = asyncio.run(importer.parse_clean_rows(db, rows, stats, should_stop=importer._stopper(imp.id)))
    importer._finish(imp.id, parsed, stats)

    assert calls == [1]  # rows 2 and 3 never went to the AI
    assert db.scalar(select(ParseCache)) is not None  # the finished request is cached
    db.refresh(imp)
    assert imp.status == ImportStatus.cancelled and imp.rows_json == []


class _NoClose:
    """The test session as a `with SessionLocal() as db` block that doesn't close it."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *exc):
        return False


def _client(db, user):
    from app.api.deps import get_current_user
    from app.db.database import get_db
    from main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return app, TestClient(app)


def test_endpoint_cancels_only_own_unpublished_imports(db):
    store, other = _store(db, "a@example.com"), _store(db, "b@example.com")
    store.owner.role = other.owner.role = UserRole.seller
    published = _imp(db, store)
    publish_import(db, published, store, FIRST)
    mine, theirs = _pending(db, store), _pending(db, other)
    app, client = _client(db, store.owner)
    try:
        assert client.post(f"/api/imports/{theirs.id}/cancel").status_code == 404
        res = client.post(f"/api/imports/{published.id}/cancel")
        assert res.status_code == 409 and res.json()["detail"]["code"] == "not_cancellable"
        res = client.post(f"/api/imports/{mine.id}/cancel")
        assert res.status_code == 200 and res.json()["status"] == "cancelled"
        assert client.post(f"/api/imports/{mine.id}/cancel").status_code == 409  # already cancelled
        assert client.post(f"/api/imports/{mine.id}/publish", json={"rows": FIRST}).status_code == 409
        listed = {i["id"]: i["status"] for i in client.get("/api/imports").json()}
        assert listed[mine.id] == "cancelled" and listed[published.id] == "published"
    finally:
        app.dependency_overrides.clear()
    db.refresh(theirs)
    assert theirs.status == ImportStatus.ready and theirs.rows_json
