from sqlalchemy import func, select

from app.db.models import Build, Conversation, FraudFlag, Message, Offer, PriceHistory, Store, User
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

    # Demo builds are marked and updated in place; the real store gets none
    assert all(b.is_demo and b.store.is_demo for b in db.scalars(select(Build)))
    counts = [_count(db, m) for m in (User, Store, Offer, PriceHistory, FraudFlag, Build, Conversation, Message)]
    seed_demo(db, 12_000)
    assert [_count(db, m) for m in (User, Store, Offer, PriceHistory, FraudFlag, Build, Conversation, Message)] == counts


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

    chats = [_count(db, m) for m in (Conversation, Message)]
    report = refresh_stores_and_builds(db, 12_000)

    assert [_count(db, m) for m in (User, Store, Offer, PriceHistory)] == counts
    # Demo conversations are recreated without duplicates
    assert [_count(db, m) for m in (Conversation, Message)] == chats
    assert report[1]["demo_chats"] == chats[0] - report[2]["demo_reservations"] >= 2
    assert all(c.is_demo and c.store.is_demo for c in db.scalars(select(Conversation)))
    assert demo1.password_hash == "server-own" and demo1_store.city == "tashkent"
    assert report[0]["demo_builds"] == _count(db, Build)
    assert db.get(Store, age.id).is_demo is False


def test_builds_only_twice_keeps_build_ids_and_buyer_conversations(db):
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
    builds = {b.name: b.id for b in db.scalars(select(Build))}
    assert builds
    # A buyer's own conversation about a demo build (not demo: the seed never deletes it)
    from app.db.models import TopicKind
    buyer = db.scalar(select(User).where(User.email == "buyer1@example.com"))
    build_id = max(builds.values())
    build = db.get(Build, build_id)
    own = db.scalar(select(Conversation).where(Conversation.topic_kind == TopicKind.build,
                                                Conversation.topic_id == build_id))
    if own is None:
        own = Conversation(buyer_id=buyer.id, store_id=build.store_id, topic_kind=TopicKind.build, topic_id=build_id)
        db.add(own)
    own.is_demo = False
    db.commit()

    refresh_stores_and_builds(db, 12_000)
    refresh_stores_and_builds(db, 12_000)

    assert {b.name: b.id for b in db.scalars(select(Build))} == builds
    assert db.get(Conversation, own.id).topic_id == build_id and db.get(Build, build_id) is not None


def test_demo_reservations_survive_builds_only_reruns(db):
    from app.db.models import Reservation, TopicKind
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
    first = {r.demo_key: (r.id, r.status.value, r.build_id) for r in db.scalars(select(Reservation))}
    assert first and all(r.is_demo and r.store.is_demo for r in db.scalars(select(Reservation)))
    convs = {c.topic_id: c.id for c in db.scalars(select(Conversation).where(Conversation.topic_kind == TopicKind.reservation))}
    assert set(convs) == {rid for rid, _, _ in first.values()}
    counts = [_count(db, m) for m in (Reservation, Conversation, Message)]

    # A run days ago: the "ends today" reservation has expired since; the next run makes it "today" again
    from datetime import timedelta

    from app.db.models import ReservationStatus, utcnow
    from app.services.reservations import TZ
    ending = db.scalar(select(Reservation).where(Reservation.demo_key == "confirmed"))
    ending.expires_at, ending.status = utcnow() - timedelta(days=3), ReservationStatus.expired
    db.commit()
    refresh_stores_and_builds(db, 12_000)
    refresh_stores_and_builds(db, 12_000)
    db.refresh(ending)
    assert ending.status == ReservationStatus.confirmed
    assert ending.expires_at.replace(tzinfo=ending.expires_at.tzinfo or TZ).astimezone(TZ).date() == utcnow().astimezone(TZ).date()         or ending.expires_at.replace(tzinfo=__import__("datetime").timezone.utc).astimezone(TZ).date() == utcnow().astimezone(TZ).date()
    demo1 = db.scalar(select(Store).join(Store.owner).where(User.email == "demo1@example.com"))
    assert demo1.address and demo1.hours and demo1.map_url is None

    assert {r.demo_key: (r.id, r.status.value, r.build_id) for r in db.scalars(select(Reservation))} == first
    assert {c.topic_id: c.id for c in db.scalars(select(Conversation).where(
        Conversation.topic_kind == TopicKind.reservation))} == convs
    assert [_count(db, m) for m in (Reservation, Conversation, Message)] == counts
    # A demo build reservation points at a build that still exists
    assert all(db.get(Build, b) is not None for _, _, b in first.values() if b)
    assert not db.scalars(select(Reservation).where(Reservation.store_id == age.id)).all()


def test_demo_branches_and_stock_rerun_without_duplicates_and_keep_ids(db):
    """Phase 12.1: demo1 — 3 branches in Tashkent with different stock, demo2 — two cities, demo3 — no stock by
    branch; re-runs (also --builds-only) keep the branch ids and do not add rows; the real store is not touched."""
    from app.db.models import Branch, OfferStock
    from scripts.seed_demo import refresh_stores_and_builds

    age = Store(owner=User(email="seller1@example.com", password_hash="x"), name="Age Computers")
    db.add(age)
    db.commit()
    rows = [{**_row(1, "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", 114), "category": "cpu", "brand": "Intel"},
            *[_row(n, f"Kingston DDR5 {n}GB", 10 + n) for n in range(2, 30)]]
    publish_import(db, _import(db, age), age, rows)
    seed_demo(db, 12_000)

    def state():
        by_store = {}
        for b in db.scalars(select(Branch).order_by(Branch.id)):
            by_store.setdefault(b.store_id, []).append((b.id, b.city, b.is_main))
        return by_store, _count(db, OfferStock)

    first = state()
    stores = {s.owner.email: s for s in db.scalars(select(Store))}
    demo1, demo2, demo3 = (first[0][stores[f"demo{i}@example.com"].id] for i in (1, 2, 3))
    assert [c for _, c, _ in demo1] == ["tashkent"] * 3 and sum(m for *_, m in demo1) == 1
    assert {c for _, c, _ in demo2} == {"samarkand", "tashkent"} and len(demo3) == 1
    assert stores["seller1@example.com"].id not in first[0]  # no address: nothing invented
    assert first[1] > 0 and not db.scalar(select(OfferStock.id).join(Offer).where(
        Offer.store_id == stores["demo3@example.com"].id))
    seed_demo(db, 12_000)
    refresh_stores_and_builds(db, 12_000)
    assert state() == first


def test_demo_stock_journal_is_the_same_on_every_run(db):
    from app.db.models import OfferStock, Reservation, StockMovement
    from scripts.seed_demo import refresh_stores_and_builds

    age = Store(owner=User(email="seller1@example.com", password_hash="x"), name="Age Computers")
    db.add(age)
    db.commit()
    rows = [
        {**_row(1, "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", 114), "category": "cpu", "brand": "Intel"},
        {**_row(2, "AMD Ryzen 5 7600X, 4.7 GHz, AM5, OEM", 190), "category": "cpu", "brand": "AMD"},
        *[_row(n, f"Kingston DDR5 {n}GB", 10 + n) for n in range(3, 40)],
    ]
    publish_import(db, _import(db, age), age, rows)
    seed_demo(db, 12_000)
    stores = {s.owner.email: s for s in db.scalars(select(Store).where(Store.is_demo.is_(True)))}
    assert stores["demo1@example.com"].stock_mode == "stock"
    assert stores["demo2@example.com"].stock_mode == stores["demo3@example.com"].stock_mode == "price"
    assert age.stock_mode == "price"

    def state():
        moves = db.scalars(select(StockMovement).where(StockMovement.store_id == stores["demo1@example.com"].id)).all()
        stock = {(s.offer_id, s.branch_id): (s.quantity, s.reserved) for s in db.scalars(select(OfferStock))}
        return sorted((m.offer_id, m.branch_id, m.kind, m.delta, m.quantity_after) for m in moves), stock

    first = state()
    kinds = {k for _, _, k, _, _ in first[0]}
    assert {"initial", "receipt", "sale", "adjust", "reserve"} <= kinds
    assert all(q is None or q >= 0 for q, _ in first[1].values())
    r = db.scalar(select(Reservation).where(Reservation.demo_key == "reserved"))
    assert r.reserved_qty == 1 and r.status.value == "confirmed"
    refresh_stores_and_builds(db, 12_000)
    refresh_stores_and_builds(db, 12_000)
    assert state() == first
    assert not db.scalars(select(StockMovement).where(StockMovement.store_id == age.id)).all()
