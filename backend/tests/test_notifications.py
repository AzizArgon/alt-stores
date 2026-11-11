"""Phase 12.5: notifications — events make them for the right person only, repeats are joined, read / read all,
older than 30 days go."""

from datetime import timedelta

from sqlalchemy import select

from app.db.models import Notification, User, UserRole, utcnow
from app.services import chat, notifications as notify, reservations as res
from tests.test_reservations import _auth, _book, client, no_rate, world  # noqa: F401  (fixtures)
from tests.test_builds import db  # noqa: F401
from tests.test_stock import _op, _world


def _of(db, user):
    return db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id)).all()


def test_messages_go_to_the_other_side_and_join_in_one_conversation(db, world):
    shop, b1, b2 = world["shop"], world["b1"], world["b2"]
    conv = chat.open_conversation(db, b1, "offer", world["offer"].id)
    for text in ("Здравствуйте", "Есть в наличии?", "Ответьте, пожалуйста"):
        chat.send_message(db, b1, conv.id, text)
    mine = _of(db, shop.owner)
    assert [(n.kind, n.count, n.link) for n in mine] == [("message", 3, f"/seller/messages/{conv.id}")]
    assert _of(db, b1) == [] and _of(db, b2) == [] and _of(db, world["other"].owner) == []
    # The store answers: the buyer's bell; opening the conversation reads the store's notification
    chat.send_message(db, shop.owner, conv.id, "Есть")
    assert [(n.kind, n.params["store"]) for n in _of(db, b1)] == [("message", shop.name)]
    chat.read_messages(db, shop.owner, conv.id)
    assert _of(db, shop.owner)[0].is_read
    # A new message after it was read — a new notification
    chat.send_message(db, b1, conv.id, "Спасибо")
    assert [n.count for n in _of(db, shop.owner)] == [3, 1]


def test_reservation_events(client, db, world):
    shop, b1 = world["shop"], world["b1"]
    rid = _book(client, b1, world["offer"].id).json()["id"]
    assert [n.kind for n in _of(db, shop.owner)] == ["reservation_new"]
    assert _of(db, b1) == [] and _of(db, world["other"].owner) == []
    assert client.post(f"/api/reservations/{rid}/advance", headers=_auth(shop.owner)).status_code == 200
    assert [n.kind for n in _of(db, b1)] == ["reservation_confirmed"]
    # Expires today: one reminder only
    r = db.get(res.Reservation, rid)
    r.expires_at = utcnow() + timedelta(minutes=30)
    db.commit()
    assert res.remind_expiring(db) == 1 and res.remind_expiring(db) == 0
    client.post(f"/api/reservations/{rid}/cancel", json={}, headers=_auth(b1))
    assert [n.kind for n in _of(db, shop.owner)] == ["reservation_new", "reservation_cancelled"]
    # The store cancels another one: the buyer's bell
    rid2 = _book(client, b1, world["build"].id, kind="build").json()["id"]
    client.post(f"/api/reservations/{rid2}/cancel", json={"reason": "no_stock"}, headers=_auth(shop.owner))
    assert _of(db, b1)[-1].kind == "reservation_cancelled_store"


def test_low_stock_once_a_day_and_oversold(db):
    store, chil, yunus, a, b = _world(db)
    for _ in range(2):
        _op(db, store, "sale", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1})
    low = [n for n in _of(db, store.owner) if n.kind == "low_stock"]
    assert len(low) == 1  # 2 -> 1 -> 0: only one a day
    low[0].created_at = utcnow() - timedelta(days=2)
    db.commit()
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": chil.id, "qty": 9})  # more than the books: 5
    kinds = [n.kind for n in _of(db, store.owner)]
    assert kinds.count("low_stock") == 2 and "oversold" in kinds


def test_admins_get_complaints_and_read_all_and_purge(client, db, world):
    admin = User(email="admin@example.com", password_hash="x", role=UserRole.admin)
    db.add(admin)
    db.commit()
    conv = chat.open_conversation(db, world["b1"], "offer", world["offer"].id)
    chat.send_message(db, world["b1"], conv.id, "Привет")
    chat.report(db, world["shop"].owner, conv.id, "spam", None)
    assert [n.kind for n in _of(db, admin)] == ["report"]
    assert all(n.kind != "report" for n in _of(db, world["shop"].owner))
    h = _auth(world["shop"].owner)
    data = client.get("/api/notifications", headers=h).json()
    assert data["unread"] == 1 and data["items"][0]["type"] == "messages"
    # Somebody else's notification can't be read
    assert client.post(f"/api/notifications/{_of(db, admin)[0].id}/read", headers=h).status_code == 404
    assert client.post(f"/api/notifications/{data['items'][0]['id']}/read", headers=h).status_code == 200
    assert client.get("/api/notifications/unread", headers=h).json()["count"] == 0
    notify.notify(db, admin.id, "fix_suggested", "/admin/fixes")
    db.commit()
    assert client.post("/api/notifications/read-all", headers=_auth(admin)).json()["count"] == 2
    old = _of(db, admin)[0]
    old.created_at = utcnow() - timedelta(days=31)
    db.commit()
    assert notify.purge(db) == 1 and len(_of(db, admin)) == 1
