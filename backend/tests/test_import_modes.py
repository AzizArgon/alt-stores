"""Phase B3: "full price list" / "addition" and the "what will change" summary before publishing."""

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import Currency, ImportStatus, Offer, OfferEvent, PriceImport
from app.db.seed import seed_categories
from app.services.importer import plan_import, publish_import
from tests.test_publish import _row, _store


@pytest.fixture
def db():
    # One connection for all threads: API endpoints run in a thread pool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        seed_categories(session)
        yield session


def _imp(db, store, source="file", mode="full"):
    imp = PriceImport(store_id=store.id, filename="p.xlsx", source=source, mode=mode, currency=Currency.USD,
                      status=ImportStatus.ready)
    db.add(imp)
    db.commit()
    return imp


FIRST = [_row(1, "Lexar DDR4 8GB 3200MHz", 58), _row(2, "Kingston DDR5 32GB 6000MHz", 120),
         _row(3, "Patriot DDR4 16GB 3200MHz", 40), _row(4, "Crucial DDR5 16GB 5600MHz", 70)]


def test_append_mode_does_not_take_goods_off_sale(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    stats = publish_import(db, _imp(db, store, mode="append"), store, [_row(1, "Lexar DDR4 8GB 3200MHz", 55)])
    assert stats["out_of_stock"] == 0
    assert all(o.is_in_stock for o in db.scalars(select(Offer)))


def test_full_mode_takes_missing_goods_off_sale_and_logs_it(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    stats = publish_import(db, _imp(db, store), store, FIRST[:3])
    assert stats["out_of_stock"] == 1
    crucial = db.scalar(select(Offer).where(Offer.raw_name.like("Crucial%")))
    assert not crucial.is_in_stock
    assert [(e.field, e.value, e.source) for e in crucial.events] == [("stock", "0", "import")]


def test_mode_of_text_is_always_append(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    imp = _imp(db, store, source="text", mode="full")
    assert plan_import(db, imp, store, [FIRST[0]], "full")["mode"] == "append"
    assert publish_import(db, imp, store, [FIRST[0]], "full")["out_of_stock"] == 0


def test_summary_counts_each_group(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    db.scalar(select(Offer).where(Offer.raw_name.like("Patriot%"))).is_in_stock = False
    db.commit()
    rows = [
        _row(1, "Lexar DDR4 8GB 3200MHz", 60),       # price up
        _row(2, "Kingston DDR5 32GB 6000MHz", 110),  # price down
        _row(3, "Patriot DDR4 16GB 3200MHz", 40),    # back on sale
        _row(5, "Goodram DDR4 8GB 2666MHz", 25),     # new
    ]
    plan = plan_import(db, _imp(db, store), store, rows)
    assert [i["raw_name"] for i in plan["price_up"]] == ["Lexar DDR4 8GB 3200MHz"]
    assert plan["price_up"][0]["old_price"] == 58 and plan["price_up"][0]["price"] == 60
    assert [i["raw_name"] for i in plan["price_down"]] == ["Kingston DDR5 32GB 6000MHz"]
    assert [i["raw_name"] for i in plan["back_in_stock"]] == ["Patriot DDR4 16GB 3200MHz"]
    assert [i["raw_name"] for i in plan["new"]] == ["Goodram DDR4 8GB 2666MHz"]
    assert [i["raw_name"] for i in plan["out_of_stock"]] == ["Crucial DDR5 16GB 5600MHz"]
    assert plan["unchanged"] == 0 and plan["on_sale"] == 3
    # Nothing is written by the summary
    assert db.scalar(select(Offer).where(Offer.raw_name.like("Lexar%"))).price == 58

    same = plan_import(db, _imp(db, store, mode="append"), store, [_row(1, "Lexar DDR4 8GB 3200MHz", 58)])
    assert same["unchanged"] == 1 and same["out_of_stock"] == [] and not same["large_drop"]


def test_large_drop_only_in_full_mode_over_30_percent(db):
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    assert not plan_import(db, _imp(db, store), store, FIRST[:3])["large_drop"]  # 1 of 4 = 25%
    assert plan_import(db, _imp(db, store), store, FIRST[:2])["large_drop"]  # 2 of 4 = 50%
    assert not plan_import(db, _imp(db, store), store, FIRST[:2], "append")["large_drop"]


def test_publish_endpoint_asks_to_confirm_a_large_drop(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.db.database import get_db
    from app.db.models import UserRole
    from main import app

    store = _store(db, "a@example.com")
    store.owner.role = UserRole.seller
    publish_import(db, _imp(db, store), store, FIRST)
    imp = _imp(db, store)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: store.owner
    try:
        client = TestClient(app)
        body = {"rows": [{**FIRST[0], "brand": None}]}
        res = client.post(f"/api/imports/{imp.id}/publish", json=body)
        assert res.status_code == 409 and res.json()["detail"]["code"] == "large_drop"
        res = client.post(f"/api/imports/{imp.id}/publish", json={**body, "confirm_drop": True})
        assert res.status_code == 200 and res.json()["out_of_stock"] == 3
    finally:
        app.dependency_overrides.clear()
    assert db.scalar(select(OfferEvent.id)) is not None
