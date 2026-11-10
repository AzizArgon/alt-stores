import json
from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.security import verify_password
from app.db.database import Base
from app.db.models import Offer, Store, User
from app.db.seed import seed_categories
from app.services.importer import publish_import
from app.services.market import build_market
from scripts.demo_reset import real_store_data, restore_real_store
from scripts.seed_demo import real_store, seed_demo
from scripts.set_account import set_account, validate
from tests.test_publish import _import, _row, db  # noqa: F401  (db is a fixture)


def _real(db):
    store = Store(owner=User(email="seller1@example.com", password_hash="x"), name="Age Computers")
    db.add(store)
    db.commit()
    rows = [
        {**_row(1, "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", 114), "category": "cpu", "brand": "Intel"},
        {**_row(2, "Samsung 990 PRO 1TB M.2 NVMe SSD", 225), "category": "ssd", "brand": "Samsung"},
        *[_row(n, f"Kingston DDR5 {n}GB", 10 + n) for n in range(3, 40)],
    ]
    publish_import(db, _import(db, store), store, rows)
    return store


def test_set_account_changes_login_and_marks_store_real(db):
    store = _real(db)
    store.is_demo = True
    assert validate("owner@example.com", "short") is not None  # registration rules: 8+ characters
    assert validate("owner@example.com", "long enough 1") is None
    user = set_account(db, "seller1@example.com", "Owner@Example.com", "long enough 1")
    assert user.email == "owner@example.com" and verify_password("long enough 1", user.password_hash)
    assert store.is_verified and not store.is_demo
    with pytest.raises(SystemExit):
        set_account(db, "nobody@example.com", "x@example.com", "long enough 1")


def test_demo_is_built_from_the_real_store_and_does_not_touch_it(db):
    store = _real(db)
    set_account(db, "seller1@example.com", "owner@example.com", "long enough 1")
    before = [(o.raw_name, o.price, o.is_in_stock) for o in store.offers]
    seed_demo(db, 12_000)
    assert real_store(db).id == store.id
    db.refresh(store)
    assert sorted((o.raw_name, o.price, o.is_in_stock) for o in store.offers) == sorted(before)
    demo = db.scalars(select(Store).where(Store.is_demo.is_(True))).all()
    assert [s.name for s in demo] == ["Silicon Plus", "Byte Market", "PC Galaxy"]
    md = build_market(db, date.today())
    # Byte Market sells in UZS and the test DB has no CBU rate: it is not in the market at all
    assert md.demo_stores == {s.id for s in demo if s.name != "Byte Market"}


def test_real_store_survives_export_and_restore(db):
    store = _real(db)
    set_account(db, "seller1@example.com", "owner@example.com", "long enough 1")
    seed_demo(db, 12_000)
    store.offers[0].price_history[0].price = 99  # an older price of the real store
    db.commit()
    data = json.loads(json.dumps(real_store_data(db)))  # through JSON, as in the backups folder
    assert [d["user"]["email"] for d in data] == ["owner@example.com"]

    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as clean:
        seed_categories(clean)
        report = restore_real_store(clean, data[0])
        assert report["created"] == len(data[0]["offers"])
        user = clean.scalar(select(User))
        assert user.email == "owner@example.com" and verify_password("long enough 1", user.password_hash)
        restored = clean.scalar(select(Store))
        assert restored.is_verified and not restored.is_demo
        offers = clean.scalars(select(Offer).order_by(Offer.id)).all()
        assert sorted((o.raw_name, o.price) for o in offers) == sorted((o["raw_name"], o["price"])
                                                                       for o in data[0]["offers"])
        changed = next(o for o in offers if o.raw_name == store.offers[0].raw_name)
        assert [h.price for h in changed.price_history] == [99]
        seed_demo(clean, 12_000)  # the demo is rebuilt from the restored store
        assert real_store(clean).id == restored.id


def test_real_store_branches_and_stock_survive_export_and_restore(db):
    """Phase 12.1: the owner's branches (with the remembered columns) and the stock by branch come back."""
    from app.db.models import Branch
    from app.services.branches import save_branch, set_stock

    store = _real(db)
    store.address, store.hours = "ул. Навои, 12", "Пн–Сб 10–19"
    main = save_branch(db, store, {"city": "tashkent", "address": "ул. Навои, 12", "landmark": "ЦУМ",
                                   "hours": "Пн–Сб 10–19"})
    other = save_branch(db, store, {"city": "tashkent", "address": "ул. Бабура, 5", "landmark": "рынок", "name": "Б"})
    other.columns_json = ["Склад Б"]
    set_stock(store.offers[0], other.id, quantity=3)
    set_stock(store.offers[0], main.id, quantity=0)
    db.commit()
    data = json.loads(json.dumps(real_store_data(db)))
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as clean:
        seed_categories(clean)
        restore_real_store(clean, data[0])
        branches = clean.scalars(select(Branch).order_by(Branch.id)).all()
        assert [(b.address, b.is_main, b.columns_json) for b in branches] == [
            ("ул. Навои, 12", True, []), ("ул. Бабура, 5", False, ["Склад Б"])]
        restored = clean.scalar(select(Store))
        assert restored.hours == "Пн–Сб 10–19"
        offer = clean.scalar(select(Offer).where(Offer.raw_name == store.offers[0].raw_name))
        assert {s.branch_id: s.quantity for s in offer.stocks} == {branches[0].id: 0, branches[1].id: 3}
        assert offer.is_in_stock
