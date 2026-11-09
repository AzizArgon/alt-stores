"""Phase 11: reservations - only on sale and only at a store, contacts, price snapshot, statuses in order, cancels,
expiry, limits, privacy, block, system lines in the chat, nothing changes in the stock or the market."""

from datetime import timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api import chat as chat_api
from app.api import reservations as res_api
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import (
    Build, Conversation, Currency, Message, MessageAuthor, Offer, PriceHistory, Reservation, Store, StoreBlock,
    StoreKind, User, UserRole, utcnow,
)
from app.services import reservations as svc
from app.services.antifraud import market_prices
from main import app
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)

PHONE = "+998 90 123-45-67"


@pytest.fixture(autouse=True)
def no_rate(monkeypatch):
    monkeypatch.setattr(chat_api, "get_usd_rate", lambda db: None)
    monkeypatch.setattr(res_api, "get_usd_rate", lambda db: None)


@pytest.fixture
def world(db):
    shop, other = _store(db, "shop@example.com"), _store(db, "other@example.com")
    cpu = _card(db, "cpu", "Intel Core i5-12400F", brand="Intel")
    _offer(db, shop, cpu, 120)
    _offer(db, other, cpu, 125)
    tg = Store(owner=User(email="tg@example.com", password_hash="x", role=UserRole.seller), name="@chan",
               kind=StoreKind.telegram)
    db.add(tg)
    db.commit()
    _offer(db, tg, cpu, 90)
    build = Build(store=shop, name="Gamer PC", price=700, currency=Currency.USD)
    db.add(build)
    buyers = [User(email=f"b{i}@example.com", password_hash="x", role=UserRole.buyer) for i in (1, 2)]
    db.add_all(buyers)
    db.commit()
    offers = {o.store.name: o for o in cpu.offers}
    return {"shop": shop, "other": other, "tg": tg, "build": build, "b1": buyers[0], "b2": buyers[1],
            "offer": offers["shop@example.com"], "tg_offer": offers["@chan"], "cpu": cpu}


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def _book(client, user, item_id, kind="offer", **extra):
    body = {"kind": kind, "item_id": item_id, "name": "Азиз", "phone": PHONE, "contact": "call", **extra}
    return client.post("/api/reservations", json=body, headers=_auth(user))


def _code(res):
    return res.json()["detail"]["code"]


def test_only_on_sale_and_only_at_a_store(client, db, world):
    assert _book(client, world["b1"], world["offer"].id).status_code == 201
    assert _book(client, world["b1"], world["build"].id, kind="build").status_code == 201
    assert _code(_book(client, world["b1"], world["tg_offer"].id)) == "not_a_store"
    world["offer"].is_in_stock = False
    db.commit()
    assert _code(_book(client, world["b2"], world["offer"].id)) == "not_on_sale"
    world["build"].is_in_stock = False
    db.commit()
    assert _code(_book(client, world["b2"], world["build"].id, kind="build")) == "not_on_sale"
    # A seller does not reserve
    assert _code(_book(client, world["other"].owner, world["offer"].id)) == "buyers_only"


def test_required_fields_and_phone_format(client, world):
    oid = world["offer"].id
    assert _code(_book(client, world["b1"], oid, name="  ")) == "name"
    assert _code(_book(client, world["b1"], oid, phone="12345")) == "phone"
    assert _code(_book(client, world["b1"], oid, phone="+7 900 123 45 67")) == "phone"
    assert _code(_book(client, world["b1"], oid, contact="telegram")) == "telegram"
    assert _code(_book(client, world["b1"], oid, comment="x" * 501)) == "comment"
    yesterday = (svc.today() - timedelta(days=1)).isoformat()
    assert _code(_book(client, world["b1"], oid, pickup_date=yesterday)) == "pickup_date"
    ok = _book(client, world["b1"], oid, phone="998901234567", contact="telegram", telegram="aziz_dev",
               pickup_date=svc.today().isoformat(), pickup_time="18:30").json()
    assert ok["phone"] == "+998901234567" and ok["telegram"] == "@aziz_dev" and ok["status"] == "new"
    # Remembered for the next form
    assert client.get("/api/reservations/contacts", headers=_auth(world["b1"])).json() == {
        "name": "Азиз", "phone": "+998901234567", "telegram": "@aziz_dev"}


def test_price_snapshot_stays_and_nothing_changes_in_the_market(client, db, world):
    offer = world["offer"]
    key = {world["cpu"].match_key}
    market_before = market_prices(db, key, None, None)
    history_before = db.scalar(select(func.count(PriceHistory.id)))
    r = _book(client, world["b1"], offer.id).json()
    db.refresh(offer)
    assert offer.is_in_stock and offer.price == 120  # stock and price untouched
    assert market_prices(db, key, None, None) == market_before
    assert db.scalar(select(func.count(PriceHistory.id))) == history_before
    offer.price = 135
    db.commit()
    seen = client.get(f"/api/reservations/{r['id']}", headers=_auth(world["shop"].owner)).json()
    assert seen["price"] == 120 and seen["current"]["price"] == 135 and seen["price_changed"] is True


def test_statuses_only_in_order_and_store_cancel_needs_a_reason(client, db, world):
    seller = _auth(world["shop"].owner)
    rid = _book(client, world["b1"], world["offer"].id).json()["id"]
    steps = [client.post(f"/api/reservations/{rid}/advance", headers=seller).json() for _ in range(3)]
    assert [s["status"] for s in steps] == ["confirmed", "ready", "issued"]
    # The term is counted from the confirmation (2 days by default)
    exp = steps[0]["expires_at"]
    assert exp is not None
    assert _code(client.post(f"/api/reservations/{rid}/advance", headers=seller)) == "bad_status"
    assert _code(client.post(f"/api/reservations/{rid}/cancel", json={}, headers=_auth(world["b1"]))) == "bad_status"
    # The buyer cannot move it on
    rid2 = _book(client, world["b1"], world["offer"].id).json()["id"]
    assert _code(client.post(f"/api/reservations/{rid2}/advance", headers=_auth(world["b1"]))) == "sellers_only"
    assert _code(client.post(f"/api/reservations/{rid2}/cancel", json={}, headers=seller)) == "reason"
    assert _code(client.post(f"/api/reservations/{rid2}/cancel", json={"reason": "other"}, headers=seller)) == "reason_text"
    done = client.post(f"/api/reservations/{rid2}/cancel", json={"reason": "no_stock"}, headers=seller).json()
    assert done["status"] == "cancelled" and done["cancelled_by"] == "store" and done["cancel_reason"] == "no_stock"
    assert [h["status"] for h in done["history"]] == ["new", "cancelled"]
    assert [h["by"] for h in done["history"]] == ["buyer", "store"]


def test_buyer_cancels_before_issued(client, world):
    seller = _auth(world["shop"].owner)
    rid = _book(client, world["b1"], world["offer"].id).json()["id"]
    client.post(f"/api/reservations/{rid}/advance", headers=seller)
    client.post(f"/api/reservations/{rid}/advance", headers=seller)
    out = client.post(f"/api/reservations/{rid}/cancel", json={}, headers=_auth(world["b1"])).json()
    assert out["status"] == "cancelled" and out["cancelled_by"] == "buyer"


def test_expires_automatically(client, db, world):
    seller = _auth(world["shop"].owner)
    rid = _book(client, world["b1"], world["offer"].id).json()["id"]
    client.post(f"/api/reservations/{rid}/advance", headers=seller)
    r = db.get(Reservation, rid)
    r.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    mine = client.get("/api/reservations?done=true", headers=_auth(world["b1"])).json()
    assert [x["status"] for x in mine] == ["expired"]
    assert mine[0]["history"][-1]["by"] == "system"
    # A new (unconfirmed) one does not expire
    assert svc.expire_due(db) == 0


def test_limits(client, db, world, monkeypatch):
    b1, oid = world["b1"], world["offer"].id
    assert _book(client, b1, oid).status_code == 201
    assert _book(client, b1, oid).status_code == 201
    assert _code(_book(client, b1, oid)) == "limit_same"
    monkeypatch.setattr(svc, "MAX_ACTIVE", 3)
    assert _book(client, b1, world["build"].id, kind="build").status_code == 201
    other_offer = db.scalar(select(Offer).where(Offer.store_id == world["other"].id))
    assert _code(_book(client, b1, other_offer.id)) == "limit_active"
    monkeypatch.setattr(svc, "MAX_ACTIVE", 50)
    monkeypatch.setattr(svc, "NEW_PER_DAY", 3)
    assert _code(_book(client, b1, other_offer.id)) == "limit_day"


def test_stranger_sees_neither_the_reservation_nor_the_phone(client, world):
    r = _book(client, world["b1"], world["offer"].id).json()
    for user in (world["b2"], world["other"].owner):
        assert client.get(f"/api/reservations/{r['id']}", headers=_auth(user)).status_code == 404
        assert client.get(f"/api/chat/conversations/{r['conversation_id']}", headers=_auth(user)).status_code == 404
    other_list = client.get("/api/reservations/store", headers=_auth(world["other"].owner)).json()
    assert other_list == []
    mine = client.get("/api/reservations/store", headers=_auth(world["shop"].owner)).json()
    assert mine[0]["phone"] == "+998901234567" and "email" not in str(mine[0])
    # Search by name or phone digits
    assert len(client.get("/api/reservations/store?q=4567", headers=_auth(world["shop"].owner)).json()) == 1
    assert client.get("/api/reservations/store?q=Пётр", headers=_auth(world["shop"].owner)).json() == []


def test_blocked_buyer_cannot_reserve(client, db, world):
    db.add(StoreBlock(store_id=world["shop"].id, user_id=world["b1"].id))
    db.commit()
    assert _code(_book(client, world["b1"], world["offer"].id)) == "blocked"
    assert _book(client, world["b2"], world["offer"].id).status_code == 201


def test_system_lines_in_the_chat_and_unseen_badge(client, db, world):
    b1, seller = _auth(world["b1"]), _auth(world["shop"].owner)
    r = _book(client, world["b1"], world["offer"].id).json()
    conv = db.get(Conversation, r["conversation_id"])
    assert conv.topic_kind.value == "reservation" and conv.topic_id == r["id"]
    # The "created" line is new for the store, not for the buyer
    assert client.get("/api/chat/unread", headers=b1).json()["count"] == 0
    assert client.get("/api/chat/unread", headers=seller).json()["count"] == 1
    client.post(f"/api/reservations/{r['id']}/advance", headers=seller)
    assert client.get("/api/chat/unread", headers=b1).json()["count"] == 1
    assert client.get("/api/reservations/unseen", headers=b1).json()["count"] == 1
    thread = client.get(f"/api/chat/conversations/{conv.id}", headers=b1).json()
    lines = [m for m in thread["messages"] if m["author"] == "system"]
    assert [m["key"] for m in lines] == ["created", "confirmed"] and lines[1]["params"]["until"]
    assert thread["topic"]["kind"] == "reservation" and thread["topic"]["status"] == "confirmed"
    # Opening "My reservations" = seen
    client.get("/api/reservations", headers=b1)
    assert client.get("/api/reservations/unseen", headers=b1).json()["count"] == 0
    # System lines do not count in the chat rate limits and cannot be opened by "Write"
    assert db.scalar(select(func.count(Message.id)).where(Message.author == MessageAuthor.system)) == 2
    res = client.post("/api/chat/conversations", json={"topic_kind": "reservation", "topic_id": r["id"]}, headers=b1)
    assert res.status_code == 422


def test_overview_counts_new_and_ending_today(client, db, world):
    seller = _auth(world["shop"].owner)
    _book(client, world["b1"], world["offer"].id)
    rid = _book(client, world["b1"], world["build"].id, kind="build").json()["id"]
    client.post(f"/api/reservations/{rid}/advance", headers=seller)
    r = db.get(Reservation, rid)
    from datetime import datetime, time
    end = datetime.combine(svc.today(), time(23, 58), svc.TZ).astimezone(timezone.utc)
    r.expires_at = end
    db.commit()
    counts = client.get("/api/seller/overview", headers=seller).json()["reservations"]
    if end > utcnow():  # not run in the last 2 minutes of the day
        assert counts == {"new": 1, "ending_today": 1}


def test_store_reservation_days_in_profile(client, db, world):
    seller = _auth(world["shop"].owner)
    profile = client.get("/api/stores/me", headers=seller).json()
    assert profile["reservation_days"] == 2
    profile["reservation_days"] = 9
    assert client.put("/api/stores/me", json=profile, headers=seller).status_code == 422
    profile["reservation_days"] = 5
    assert client.put("/api/stores/me", json=profile, headers=seller).json()["reservation_days"] == 5
    rid = _book(client, world["b1"], world["offer"].id).json()["id"]
    out = client.post(f"/api/reservations/{rid}/advance", headers=seller).json()
    r = db.get(Reservation, rid)
    assert out["status"] == "confirmed" and (r.expires_at - r.created_at.replace(tzinfo=r.expires_at.tzinfo)).days >= 4
