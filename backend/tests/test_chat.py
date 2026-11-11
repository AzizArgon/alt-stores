"""Phase 10: chat of a buyer with a store - access, one conversation per topic, counters, limits, block, report."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import chat as chat_api
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import (
    Build, ChatReport, Conversation, Currency, Message, MessageAuthor, Store, StoreKind, User, UserRole, utcnow,
)
from app.services import chat
from main import app
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def no_rate(monkeypatch):
    monkeypatch.setattr(chat_api, "get_usd_rate", lambda db: None)


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
            "offer": offers["shop@example.com"], "tg_offer": offers["@chan"]}


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def _open(client, user, **body):
    return client.post("/api/chat/conversations", json=body, headers=_auth(user))


def test_write_again_opens_the_same_conversation(client, world):
    first = _open(client, world["b1"], topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    again = _open(client, world["b1"], topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    build = _open(client, world["b1"], topic_kind="build", topic_id=world["build"].id).json()["id"]
    question = _open(client, world["b1"], topic_kind="store", store_id=world["shop"].id).json()["id"]
    assert first == again and len({first, build, question}) == 3


def test_telegram_ad_has_no_write(client, world):
    res = _open(client, world["b1"], topic_kind="offer", topic_id=world["tg_offer"].id)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "not_a_store"


def test_only_participants_read_and_write(client, world):
    conv = _open(client, world["b1"], topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "Есть в наличии?"}, headers=_auth(world["b1"]))
    stranger, other_seller = world["b2"], world["other"].owner
    for user in (stranger, other_seller):
        assert client.get(f"/api/chat/conversations/{conv}", headers=_auth(user)).status_code == 404
        res = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "hi"}, headers=_auth(user))
        assert res.status_code == 404
    assert client.get("/api/chat/conversations", headers=_auth(other_seller)).json() == []
    assert client.get("/api/chat/conversations", headers=_auth(stranger)).json() == []
    assert client.get(f"/api/chat/conversations/{conv}").status_code == 401  # a guest
    # The store sees it, but never the buyer's email
    mine = client.get("/api/chat/conversations", headers=_auth(world["shop"].owner)).json()
    assert [c["id"] for c in mine] == [conv] and "b1@example.com" not in str(mine)
    assert mine[0]["buyer_no"] == world["b1"].id


def test_unread_counters_of_both_sides(client, world):
    b1, seller = world["b1"], world["shop"].owner
    conv = _open(client, b1, topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    unread = lambda u: client.get("/api/chat/unread", headers=_auth(u)).json()["count"]  # noqa: E731
    for text in ("Здравствуйте", "Есть в наличии?"):
        client.post(f"/api/chat/conversations/{conv}/messages", json={"text": text}, headers=_auth(b1))
    assert unread(seller) == 2 and unread(b1) == 0
    detail = client.get(f"/api/chat/conversations/{conv}", headers=_auth(seller)).json()
    assert [m["text"] for m in detail["messages"]] == ["Здравствуйте", "Есть в наличии?"]
    assert unread(seller) == 0
    sent = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "Да, в наличии"}, headers=_auth(seller))
    assert unread(b1) == 1
    # Polling: only messages after the last one the page has
    new = client.get(f"/api/chat/conversations/{conv}?after={detail['messages'][-1]['id']}", headers=_auth(b1)).json()
    assert [m["text"] for m in new["messages"]] == ["Да, в наличии"] and sent.json()["author"] == "store"
    assert unread(b1) == 0
    assert new["topic"]["title"] == "Intel Core i5-12400F" and new["topic"]["in_stock"] is True


def test_overview_counts_new_and_waiting(db, world):
    conv = chat.open_conversation(db, world["b1"], "offer", world["offer"].id)
    db.add(Message(conversation=conv, author=MessageAuthor.buyer, sender_id=world["b1"].id, text="?",
                   created_at=utcnow() - timedelta(hours=30)))
    conv.last_message_at = utcnow() - timedelta(hours=30)
    db.commit()
    assert chat.overview_counts(db, world["shop"]) == {"new_messages": 1, "waiting_day": 1}


def test_rate_limits(client, world, monkeypatch):
    monkeypatch.setattr(chat, "PER_MINUTE", 3)
    b1 = world["b1"]
    conv = _open(client, b1, topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    codes = [client.post(f"/api/chat/conversations/{conv}/messages", json={"text": f"m{i}"}, headers=_auth(b1))
             for i in range(4)]
    assert [r.status_code for r in codes] == [201, 201, 201, 429]
    assert codes[-1].json()["detail"]["code"] == "rate_minute"
    monkeypatch.setattr(chat, "NEW_PER_DAY", 1)
    res = _open(client, b1, topic_kind="build", topic_id=world["build"].id)
    assert res.status_code == 429 and res.json()["detail"]["code"] == "rate_new"


def test_block_stops_the_buyer_in_the_whole_store(client, world):
    b1, seller = world["b1"], world["shop"].owner
    conv = _open(client, b1, topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "спам"}, headers=_auth(b1))
    assert client.post(f"/api/chat/conversations/{conv}/block", json={}, headers=_auth(b1)).status_code == 403
    assert client.post(f"/api/chat/conversations/{conv}/block", json={}, headers=_auth(seller)).status_code == 200
    res = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "ещё"}, headers=_auth(b1))
    assert res.status_code == 403 and res.json()["detail"]["code"] == "blocked"
    res = _open(client, b1, topic_kind="build", topic_id=world["build"].id)  # another topic of the same store
    assert res.status_code == 403
    assert _open(client, b1, topic_kind="store", store_id=world["other"].id).status_code == 200  # other stores - yes
    client.post(f"/api/chat/conversations/{conv}/block", json={"blocked": False}, headers=_auth(seller))
    res = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "ещё"}, headers=_auth(b1))
    assert res.status_code == 201


def test_report_is_kept(client, db, world):
    conv = _open(client, world["b1"], topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    res = client.post(f"/api/chat/conversations/{conv}/report", json={"reason": "fraud", "comment": "просит предоплату"},
                      headers=_auth(world["b1"]))
    assert res.status_code == 201
    item = db.scalar(select(ChatReport))
    assert (item.conversation_id, item.reason, item.reporter_id) == (conv, "fraud", world["b1"].id)
    bad = client.post(f"/api/chat/conversations/{conv}/report", json={"reason": "x"}, headers=_auth(world["b1"]))
    assert bad.status_code == 400
    assert client.post(f"/api/chat/conversations/{conv}/report", json={"reason": "spam"},
                       headers=_auth(world["b2"])).status_code == 404


def test_html_is_kept_as_text_and_long_text_refused(client, world):
    b1 = world["b1"]
    conv = _open(client, b1, topic_kind="offer", topic_id=world["offer"].id).json()["id"]
    evil = '<img src=x onerror="alert(1)"> https://t.me/x +998901234567'
    res = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": evil}, headers=_auth(b1))
    assert res.json()["text"] == evil  # stored and returned as is; the page shows it as text
    long = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "a" * 2001}, headers=_auth(b1))
    assert long.status_code == 400 and long.json()["detail"]["code"] == "too_long"
    empty = client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "   "}, headers=_auth(b1))
    assert empty.json()["detail"]["code"] == "empty"
    assert client.post(f"/api/chat/conversations/{conv}/messages", json={"text": "a" * 2000},
                       headers=_auth(b1)).status_code == 201


def test_seller_cannot_open_as_buyer_and_list_filters(client, db, world):
    seller = world["shop"].owner
    assert _open(client, seller, topic_kind="offer", topic_id=world["offer"].id).status_code == 403
    b1 = world["b1"]
    for kind, tid in (("offer", world["offer"].id), ("build", world["build"].id)):
        conv = _open(client, b1, topic_kind=kind, topic_id=tid).json()["id"]
        client.post(f"/api/chat/conversations/{conv}/messages", json={"text": kind}, headers=_auth(b1))
    _open(client, b1, topic_kind="store", store_id=world["shop"].id)  # no messages yet: the store does not see it
    lst = lambda f: [c["topic"]["kind"] for c in client.get(  # noqa: E731
        f"/api/chat/conversations?filter={f}", headers=_auth(seller)).json()]
    assert sorted(lst("all")) == ["build", "offer"] and lst("build") == ["build"] and lst("offer") == ["offer"]
    assert len(lst("unread")) == 2
    assert len(client.get("/api/chat/conversations", headers=_auth(b1)).json()) == 3
    assert db.scalar(select(Conversation).where(Conversation.topic_kind == "store")).topic_id == 0
