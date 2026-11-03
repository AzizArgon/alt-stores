from sqlalchemy import func, select

from app.db.models import Build, FraudFlag, Offer, PriceHistory, Store, User
from app.services.importer import publish_import
from scripts.seed_demo import seed_demo
from tests.test_publish import _import, _row, db  # noqa: F401  (db is a fixture)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_demo_stores_share_cards_flag_cheap_items_and_rerun_without_duplicates(db):
    user = User(email="seller1@example.com", password_hash="x")
    age = Store(owner=user, name="Age Computers")
    db.add(age)
    db.commit()
    rows = [
        {**_row(1, "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", 114), "category": "cpu", "brand": "Intel"},
        {**_row(2, "Samsung 990 PRO 1TB M.2 NVMe SSD", 225), "category": "ssd", "brand": "Samsung"},
        *[_row(n, f"Kingston DDR5 {n}GB", 10 + n) for n in range(3, 40)],
    ]
    publish_import(db, _import(db, age), age, rows)

    report = seed_demo(db, 12_000)
    assert [r["store"] for r in report[:3]] == ["Silicon Plus", "Byte Market", "PC Galaxy"]
    # Demo history: 7 past points per demo offer, marked so that one query deletes it
    demo = db.scalar(select(func.count()).where(PriceHistory.is_demo.is_(True)))
    assert demo == report[3]["demo_history_points"] == 7 * sum(r["created"] for r in report[:3])
    i5 = db.scalars(select(Offer).where(Offer.raw_name.like("%i5-12400F%"))).all()
    assert len({o.product_id for o in i5}) == 1 and len(i5) == 4  # Age + 3 demo stores, one card
    byte_market = next(o for o in i5 if o.store.name == "Byte Market")
    assert byte_market.currency.value == "UZS" and byte_market.price > 1_000_000

    # PC Galaxy sells the SSD at half price: flagged, the showcase CPU is not
    cheap = db.scalars(select(FraudFlag).where(FraudFlag.type == "price_below_market")).all()
    assert [f.offer.store.name for f in cheap] == ["PC Galaxy"]
    assert "990 PRO" in cheap[0].offer.raw_name

    # Demo builds are marked and recreated; the real store gets none
    assert all(b.is_demo and b.store.is_demo for b in db.scalars(select(Build)))
    counts = [_count(db, m) for m in (User, Store, Offer, PriceHistory, FraudFlag, Build)]
    seed_demo(db, 12_000)
    assert [_count(db, m) for m in (User, Store, Offer, PriceHistory, FraudFlag, Build)] == counts


def test_builds_only_keeps_offers_history_and_passwords(db):
    from scripts.seed_demo import refresh_stores_and_builds

    user = User(email="seller1@example.com", password_hash="x")
    age = Store(owner=user, name="Age Computers")
    db.add(age)
    db.commit()
    rows = [
        {**_row(1, "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", 114), "category": "cpu", "brand": "Intel"},
        *[_row(n, f"Kingston DDR5 {n}GB", 10 + n) for n in range(2, 30)],
    ]
    publish_import(db, _import(db, age), age, rows)
    seed_demo(db, 12_000)
    # The server has its own demo passwords and an old city
    demo1 = db.scalar(select(User).where(User.email == "demo1@example.com"))
    demo1.password_hash = "server-own"
    demo1_store = db.scalar(select(Store).where(Store.user_id == demo1.id))
    demo1_store.city = "andijan"
    db.commit()
    counts = [_count(db, m) for m in (User, Store, Offer, PriceHistory)]

    report = refresh_stores_and_builds(db, 12_000)

    assert [_count(db, m) for m in (User, Store, Offer, PriceHistory)] == counts
    assert demo1.password_hash == "server-own" and demo1_store.city == "tashkent"
    assert report[0]["demo_builds"] == _count(db, Build)
    assert db.get(Store, age.id).is_demo is False
