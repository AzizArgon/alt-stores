"""Phase 13: the admin panel — access only for admin, the journal, store and user blocks, reports, disputed flags,
card fixes with a merge, barcode conflicts, Telegram channels; the admin never gets a store's stock or costs."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api import admin as admin_api
from app.api import chat as chat_api
from app.api import reservations as res_api
from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.db.models import (
    AdminAction, Barcode, BarcodeCode, Branch, Category, ChatReport, Conversation, FlagLevel, FlagSource, FlagStatus,
    FraudFlag, Message, MessageAuthor, Offer, OfferStock, Product, ProductFix, Reservation, Store, StoreKind, TgChannel,
    TopicKind, User, UserRole,
)
from app.services import admin as svc
from app.services import catalog, stores
from app.services.antifraud import save_offer_flags
from app.services.barcodes import bind, make_ean13
from app.services.manual import card_fields
from app.services.market import build_market
from main import app
from scripts.create_admin import create_admin
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)

PHONE = "+998 90 123-45-67"


@pytest.fixture(autouse=True)
def no_rate(monkeypatch):
    monkeypatch.setattr(chat_api, "get_usd_rate", lambda db: None)
    monkeypatch.setattr(res_api, "get_usd_rate", lambda db: None)
    admin_api.admin_failures.clear()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.fixture
def world(db):
    admin, _ = create_admin(db, "admin@example.com", "admin12345")
    shop, other = _store(db, "shop@example.com"), _store(db, "other@example.com")
    cpu = _card(db, "cpu", "Intel Core i5-12400F", brand="Intel")
    _offer(db, shop, cpu, 120)
    _offer(db, other, cpu, 125)
    buyer = User(email="buyer@example.com", password_hash=hash_password("buyer12345"), role=UserRole.buyer)
    db.add(buyer)
    db.commit()
    offer = db.scalar(select(Offer).where(Offer.store_id == shop.id))
    return {"admin": admin, "shop": shop, "other": other, "cpu": cpu, "buyer": buyer, "offer": offer}


def _actions(db):
    return [a.action for a in db.scalars(select(AdminAction).order_by(AdminAction.id))]


# --- access -----------------------------------------------------------------------------------------------------------

def test_only_admin_gets_in(client, db, world):
    for who in ("buyer",):
        assert client.get("/api/admin/overview", headers=_h(world[who])).status_code == 403
    assert client.get("/api/admin/stores", headers=_h(world["shop"].owner)).status_code == 403
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers=_h(world["admin"])).status_code == 200


def test_admin_login_refuses_others_and_is_rate_limited(client, world):
    ok = client.post("/api/admin/login", json={"email": "admin@example.com", "password": "admin12345"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "admin"
    not_admin = client.post("/api/admin/login", json={"email": "buyer@example.com", "password": "buyer12345"})
    assert not_admin.status_code == 403 and not_admin.json()["detail"]["code"] == "not_admin"
    for _ in range(admin_api.ADMIN_MAX_FAILURES):
        assert client.post("/api/admin/login", json={"email": "admin@example.com", "password": "wrong"}).status_code == 401
    # Locked for the window, even with the right password
    assert client.post("/api/admin/login", json={"email": "admin@example.com", "password": "admin12345"}).status_code == 429


def test_one_login_keeps_the_admin_limit_and_journal(client, db, world):
    """Phase 16.3: the admin logs in through the one /api/auth/login — the door is not weaker than /api/admin/login."""
    login = lambda pw, email="admin@example.com": client.post("/api/auth/login", json={"email": email, "password": pw})  # noqa: E731
    ok = login("admin12345")
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "admin"
    for _ in range(admin_api.ADMIN_MAX_FAILURES):
        assert login("wrong").status_code == 401
    # Locked for the window even with the right password, the same 5 failures / 15 min as the admin door
    locked = login("admin12345")
    assert locked.status_code == 429 and locked.json()["detail"] == {"code": "too_many_logins", "minutes": admin_api.ADMIN_WINDOW_MINUTES}
    # The two doors share one counter: the old admin door is locked too
    assert client.post("/api/admin/login", json={"email": "admin@example.com", "password": "admin12345"}).status_code == 429
    # The journal keeps the admin's sign-in and every wrong password with the address
    actions = [a.action for a in db.scalars(select(AdminAction).order_by(AdminAction.id))]
    assert actions.count("login_admin") == 1 and actions.count("login_failed") == admin_api.ADMIN_MAX_FAILURES
    assert all(a.details.get("ip") for a in db.scalars(select(AdminAction).where(AdminAction.action.like("login_%"))))
    admin_api.admin_failures.clear()


def test_one_login_journal_is_only_for_admins(client, db, world):
    assert client.post("/api/auth/login", json={"email": "buyer@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "buyer@example.com", "password": "buyer12345"}).status_code == 200
    assert db.scalar(select(func.count(AdminAction.id)).where(AdminAction.action.like("login_%"))) == 0
    # A wrong password of a buyer does not count against the admin's lock
    assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin12345"}).status_code == 200


def test_no_admin_registration_and_script_makes_one(client, db, world):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": "12345678", "role": "admin"})
    assert r.status_code == 422
    user, created = create_admin(db, "buyer@example.com", "newpass123")
    assert not created and user.role == UserRole.admin
    with pytest.raises(SystemExit):  # a seller with a store is refused
        create_admin(db, "shop@example.com", "newpass123")


def test_admin_gets_no_stock_or_costs(client, db, world):
    offer = world["offer"]
    offer.cost_last, offer.cost_avg = 99.0, 98.0
    db.commit()
    card = client.get(f"/api/admin/stores/{world['shop'].id}", headers=_h(world["admin"]))
    assert card.status_code == 200
    text = card.text
    assert "cost" not in text and "quantity" not in text and "movements" not in text
    assert client.get("/api/seller/stock/search?q=i5", headers=_h(world["admin"])).status_code == 403
    assert client.get("/api/seller/offers", headers=_h(world["admin"])).status_code == 403


# --- stores -----------------------------------------------------------------------------------------------------------

def test_verify_and_block_store_hides_it_everywhere(client, db, world):
    shop, admin = world["shop"], world["admin"]
    r = client.post(f"/api/admin/stores/{shop.id}/verify", json={"verified": True, "comment": "СТИР проверен"},
                    headers=_h(admin))
    assert r.json()["is_verified"] is True
    assert client.post(f"/api/admin/stores/{shop.id}/block", json={"blocked": True}, headers=_h(admin)).status_code == 400
    r = client.post(f"/api/admin/stores/{shop.id}/block", json={"blocked": True, "reason": "Обман покупателей"},
                    headers=_h(admin))
    assert r.json()["blocked"] is True
    # Off the product card, the "Stores" list and the market; the seller sees the reason
    card = catalog.product_card(db, world["cpu"].id, None)
    assert [o["store"]["id"] for o in card["offers"]] == [world["other"].id]
    assert shop.id not in [s["id"] for s in stores.list_stores(db)]
    assert stores.get_shop(db, shop.id) is None
    md = build_market(db, __import__("datetime").date.today())
    assert all(store_id != shop.id for _, _, store_id, _ in md.offers)
    me = client.get("/api/stores/me", headers=_h(shop.owner)).json()
    assert me["block_reason"] == "Обман покупателей"
    # No new reservations
    body = {"kind": "offer", "item_id": world["offer"].id, "name": "Азиз", "phone": PHONE, "contact": "call"}
    r = client.post("/api/reservations", json=body, headers=_h(world["buyer"]))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "store_blocked"
    # Unblock: back again; the journal has every step
    client.post(f"/api/admin/stores/{shop.id}/block", json={"blocked": False}, headers=_h(admin))
    assert shop.id in [s["id"] for s in stores.list_stores(db)]
    assert _actions(db) == ["store_verify", "store_block", "store_unblock"]
    log = client.get("/api/admin/log?action=store", headers=_h(admin)).json()
    assert [a["action"] for a in log] == ["store_unblock", "store_block", "store_verify"]
    assert log[-1]["comment"] == "СТИР проверен" and log[-1]["admin"] == "admin@example.com"


def test_existing_reservation_of_a_blocked_store_stays_visible(client, db, world):
    body = {"kind": "offer", "item_id": world["offer"].id, "name": "Азиз", "phone": PHONE, "contact": "call"}
    assert client.post("/api/reservations", json=body, headers=_h(world["buyer"])).status_code == 201
    svc.set_store_blocked(db, world["admin"], world["shop"], True, "Проверка")
    assert len(client.get("/api/reservations", headers=_h(world["buyer"])).json()) == 1
    assert len(client.get("/api/seller/reservations", headers=_h(world["shop"].owner)).json()) == 1


# --- users and reports ------------------------------------------------------------------------------------------------

def _report(db, world, text="Купи у меня дешевле"):
    conv = Conversation(buyer_id=world["buyer"].id, store_id=world["shop"].id, topic_kind=TopicKind.offer,
                        topic_id=world["offer"].id)
    conv.messages = [Message(author=MessageAuthor.buyer, sender_id=world["buyer"].id, text=text)]
    other = Conversation(buyer_id=world["buyer"].id, store_id=world["other"].id, topic_kind=TopicKind.store, topic_id=0)
    other.messages = [Message(author=MessageAuthor.buyer, sender_id=world["buyer"].id, text="Секретный разговор")]
    db.add_all([conv, other])
    db.flush()
    r = ChatReport(conversation_id=conv.id, reporter_id=world["shop"].owner.id, reason="spam")
    db.add(r)
    db.commit()
    return r


def test_report_shows_only_its_conversation_and_blocks_the_user(client, db, world):
    r = _report(db, world)
    admin = world["admin"]
    detail = client.get(f"/api/admin/reports/{r.id}", headers=_h(admin)).json()
    assert [m["text"] for m in detail["messages"]] == ["Купи у меня дешевле"]
    assert "Секретный" not in client.get("/api/admin/reports", headers=_h(admin)).text
    assert client.get("/api/admin/counts", headers=_h(admin)).json()["reports"] == 1
    res = client.post(f"/api/admin/reports/{r.id}", json={"action": "block_user", "comment": "Спам"}, headers=_h(admin))
    assert res.json()["status"] == "reviewed" and res.json()["resolution"] == "block_user"
    # Blocked: no login (with the reason), no messages, no reservations
    login = client.post("/api/auth/login", json={"email": "buyer@example.com", "password": "buyer12345"})
    assert login.status_code == 403 and login.json()["detail"] == {"code": "user_blocked", "reason": "Спам"}
    conv_id = detail["conversation_id"]
    assert client.post(f"/api/chat/conversations/{conv_id}/messages", json={"text": "ещё"},
                       headers=_h(world["buyer"])).status_code == 403
    body = {"kind": "offer", "item_id": world["offer"].id, "name": "Азиз", "phone": PHONE, "contact": "call"}
    assert client.post("/api/reservations", json=body, headers=_h(world["buyer"])).status_code == 403
    # Unblock in "Users"
    client.post(f"/api/admin/users/{world['buyer'].id}/block", json={"blocked": False}, headers=_h(admin))
    assert client.post("/api/auth/login", json={"email": "buyer@example.com", "password": "buyer12345"}).status_code == 200
    assert _actions(db) == ["report_block_user", "user_unblock"]


def test_admin_cannot_be_blocked_and_users_search(client, db, world):
    admin = world["admin"]
    r = client.post(f"/api/admin/users/{admin.id}/block", json={"blocked": True, "reason": "x"}, headers=_h(admin))
    assert r.status_code == 403
    found = client.get("/api/admin/users?q=buyer", headers=_h(admin)).json()
    assert [u["email"] for u in found] == ["buyer@example.com"]
    assert "password" not in client.get("/api/admin/users", headers=_h(admin)).text


def test_report_dismiss_and_block_store(client, db, world):
    r = _report(db, world)
    client.post(f"/api/admin/reports/{r.id}", json={"action": "dismiss"}, headers=_h(world["admin"]))
    assert db.get(ChatReport, r.id).resolution == "dismissed"
    r2 = ChatReport(conversation_id=r.conversation_id, reporter_id=world["buyer"].id, reason="fraud")
    db.add(r2)
    db.commit()
    client.post(f"/api/admin/reports/{r2.id}", json={"action": "block_store", "comment": "Предоплата"},
                headers=_h(world["admin"]))
    assert world["shop"].blocked_at is not None
    assert _actions(db) == ["report_dismiss", "report_block_store"]


# --- flags ------------------------------------------------------------------------------------------------------------

def _flag(db, offer, type_="below_market"):
    save_offer_flags(offer, [{"type": type_, "level": "warning", "reason_key": "below_market", "params": {"pct": 30},
                              "source": "rule"}])
    db.commit()
    return offer.fraud_flags[0]


def test_dispute_and_dismissed_flag_never_comes_back(client, db, world):
    offer, seller = world["offer"], world["shop"].owner
    f = _flag(db, offer)
    assert client.post(f"/api/seller/flags/{f.id}/dispute", json={"comment": ""}, headers=_h(seller)).status_code == 400
    assert client.post(f"/api/seller/flags/{f.id}/dispute", json={"comment": "Акция до пятницы"},
                       headers=_h(seller)).status_code == 200
    listed = client.get("/api/admin/flags", headers=_h(world["admin"])).json()
    assert listed[0]["dispute_comment"] == "Акция до пятницы" and listed[0]["offer"]["raw_name"]
    client.post(f"/api/admin/flags/{f.id}", json={"decision": "dismissed"}, headers=_h(world["admin"]))
    # The next upload raises the same check: the flag stays off
    _flag(db, offer)
    assert [x.status for x in offer.fraud_flags] == [FlagStatus.dismissed]
    decisions = client.get("/api/seller/decisions", headers=_h(seller)).json()
    assert decisions["flags"][0]["resolution"] == "dismissed"


def test_upheld_flag_shows_the_answer_and_survives_a_reupload(client, db, world):
    offer, seller = world["offer"], world["shop"].owner
    f = _flag(db, offer)
    client.post(f"/api/seller/flags/{f.id}/dispute", json={"comment": "Цена верная"}, headers=_h(seller))
    assert client.post(f"/api/admin/flags/{f.id}", json={"decision": "upheld"}, headers=_h(world["admin"])).status_code == 400
    client.post(f"/api/admin/flags/{f.id}", json={"decision": "upheld", "answer": "Цена ниже рынка на 30%"},
                headers=_h(world["admin"]))
    _flag(db, offer)
    assert len(offer.fraud_flags) == 1 and offer.fraud_flags[0].admin_answer == "Цена ниже рынка на 30%"
    # Not disputable twice
    assert client.post(f"/api/seller/flags/{f.id}/dispute", json={"comment": "ещё раз"}, headers=_h(seller)).status_code == 400
    assert _actions(db) == ["flag_upheld"]


# --- card fixes -------------------------------------------------------------------------------------------------------

def _fix(db, world, product, after):
    fix = ProductFix(product_id=product.id, store_id=world["shop"].id, before={"name": product.normalized_name},
                     after=after)
    db.add(fix)
    db.commit()
    return fix


def test_fix_accept_and_reject(client, db, world):
    cpu, admin = world["cpu"], world["admin"]
    fix = _fix(db, world, cpu, {"name": "Intel Core i5-12400F OEM", "brand": "Intel", "model": "Core i5-12400F OEM",
                                "category": "cpu", "specs": {}})
    listed = client.get("/api/admin/fixes", headers=_h(admin)).json()
    assert listed[0]["stores_selling"] == 2 and listed[0]["merge"] is None
    r = client.post(f"/api/admin/fixes/{fix.id}/accept", json={}, headers=_h(admin)).json()
    assert r["status"] == "applied"
    db.refresh(cpu)
    assert cpu.normalized_name == listed[0]["result"]["name"] and cpu.match_key == listed[0]["result"]["match_key"]
    fix2 = _fix(db, world, cpu, {"name": "Плохое имя", "brand": None, "model": None, "category": "cpu", "specs": {}})
    assert client.post(f"/api/admin/fixes/{fix2.id}/reject", json={}, headers=_h(admin)).status_code == 400
    client.post(f"/api/admin/fixes/{fix2.id}/reject", json={"reason": "Это другая модель"}, headers=_h(admin))
    fixes = client.get("/api/seller/decisions", headers=_h(world["shop"].owner)).json()["fixes"]
    assert {f["status"] for f in fixes} == {"accepted", "rejected"}
    assert _actions(db) == ["fix_accept", "fix_reject"]


def test_fix_merge_moves_offers_reservations_conversations_barcodes_and_stock(client, db, world):
    admin, shop, other = world["admin"], world["shop"], world["other"]
    dup = _card(db, "cpu", "Core i5 12400F box")
    third = _store(db, "third@example.com")
    _offer(db, third, dup, 130)
    _offer(db, shop, dup, 121)  # the shop sells both cards: its two offers become one
    target = world["cpu"]
    category = db.scalar(select(Category).where(Category.slug == "cpu"))
    after = {"name": target.normalized_name, "brand": "Intel", "model": target.normalized_name, "category": "cpu",
             "specs": {}}
    target.match_key = card_fields(category, "Intel", target.normalized_name, target.normalized_name, {})[3]
    db.commit()
    third_offer = db.scalar(select(Offer).where(Offer.store_id == third.id))
    shop_dup = db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.product_id == dup.id))
    branch = Branch(store_id=third.id, city="tashkent", address="ул. 1", is_main=True)
    db.add(branch)
    db.flush()
    third_offer.stocks.append(OfferStock(branch_id=branch.id, quantity=5, in_stock=True))
    code = make_ean13("290000000777")
    bind(db, third, third_offer, code)
    bind(db, shop, shop_dup, make_ean13("290000000778"))
    res = Reservation(buyer_id=world["buyer"].id, store_id=third.id, offer_id=third_offer.id, title="x", price=130,
                      currency=third_offer.currency, name="Азиз", phone="+998901234567", contact="call")
    conv = Conversation(buyer_id=world["buyer"].id, store_id=shop.id, topic_kind=TopicKind.offer, topic_id=shop_dup.id)
    db.add_all([res, conv])
    db.commit()
    fix = _fix(db, world, dup, after)
    preview = client.get("/api/admin/fixes", headers=_h(admin)).json()[0]["merge"]
    assert preview["target"]["id"] == target.id
    assert (preview["offers"], preview["same_store"], preview["reservations"], preview["conversations"],
            preview["barcodes"], preview["stock_rows"]) == (2, 1, 1, 1, 2, 1)
    r = client.post(f"/api/admin/fixes/{fix.id}/accept", json={}, headers=_h(admin)).json()
    assert r["status"] == "merged" and r["product_id"] == target.id
    db.expire_all()
    assert db.get(Offer, third_offer.id).product_id == target.id  # with its stock and barcode
    assert db.get(Offer, third_offer.id).stocks[0].quantity == 5
    shop_main = db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.product_id == target.id))
    assert db.get(Offer, shop_dup.id).price is None  # the duplicate ended
    assert db.get(Conversation, conv.id).topic_id == shop_main.id
    assert {b.code for b in shop_main.barcodes} == {make_ean13("290000000778")}
    assert db.get(Reservation, res.id).offer_id == third_offer.id
    assert db.scalar(select(BarcodeCode).where(BarcodeCode.code == code)).product_id == target.id
    card = catalog.product_card(db, target.id, None)
    assert {o["store"]["id"] for o in card["offers"]} == {shop.id, other.id, third.id}
    assert db.get(ProductFix, fix.id).merged_into == target.id
    assert _actions(db) == ["fix_merge"]


# --- barcodes ---------------------------------------------------------------------------------------------------------

def test_barcode_conflict_resolution(client, db, world):
    admin, shop, other = world["admin"], world["shop"], world["other"]
    gpu = _card(db, "gpu", "RTX 4060")
    _offer(db, other, gpu, 300)
    code = make_ean13("290000000050")
    bind(db, shop, world["offer"], code)
    bind(db, other, db.scalar(select(Offer).where(Offer.store_id == other.id, Offer.product_id == gpu.id)), code)
    conflicts = client.get("/api/admin/barcodes/conflicts", headers=_h(admin)).json()
    assert len(conflicts) == 1 and len(conflicts[0]["cards"]) == 2
    r = client.post(f"/api/admin/barcodes/{code}", json={"product_id": world["cpu"].id}, headers=_h(admin)).json()
    assert r["status"] == "confirmed" and r["product_id"] == world["cpu"].id
    other_binding = db.scalar(select(Barcode).where(Barcode.store_id == other.id, Barcode.code == code))
    assert other_binding.admin_status == "disputed"
    assert client.get("/api/seller/decisions", headers=_h(other.owner)).json()["barcodes"][0]["code"] == code
    looked = client.get(f"/api/admin/barcodes/lookup?code={code}", headers=_h(admin)).json()
    assert looked["status"] == "confirmed"
    # "Reject all" for another conflict: no card in the common base
    code2 = make_ean13("290000000051")
    bind(db, shop, world["offer"], code2)
    bind(db, other, other_binding_offer(db, other, gpu), code2)
    client.post(f"/api/admin/barcodes/{code2}", json={"product_id": None}, headers=_h(admin))
    assert db.scalar(select(BarcodeCode).where(BarcodeCode.code == code2)).product_id is None
    assert _actions(db) == ["barcode_resolve", "barcode_reject"]


def other_binding_offer(db, store, product):
    return db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.product_id == product.id))


# --- Telegram channels ------------------------------------------------------------------------------------------------

FEED = '<div class="tgme_widget_message " data-post="pcshop/10"><div class="js-message_text">RTX 4060 300$</div></div>'


def test_channels_add_disable_delete_hides_ads(client, db, world, monkeypatch):
    admin = world["admin"]
    from app.services import telegram

    monkeypatch.setattr(telegram, "fetch_page", lambda name, before=None: FEED)
    r = client.post("/api/admin/channels", json={"username": "@pcshop_uz", "city": "samarkand"}, headers=_h(admin))
    assert r.status_code == 201 and r.json()["city"] == "samarkand"
    ch = db.scalar(select(TgChannel))
    assert client.post("/api/admin/channels", json={"username": "pcshop_uz"}, headers=_h(admin)).status_code == 400
    monkeypatch.setattr(telegram, "fetch_page", lambda name, before=None: "<html></html>")
    assert client.post("/api/admin/channels", json={"username": "empty_chan"}, headers=_h(admin)).json()["detail"]["code"] == "channel_empty"
    # An ad of the channel on the card
    _offer(db, ch.store, world["cpu"], 90)
    assert ch.store_id in {o["store"]["id"] for o in catalog.product_card(db, world["cpu"].id, None)["offers"]}
    client.patch(f"/api/admin/channels/{ch.id}", json={"enabled": False, "city": "tashkent"}, headers=_h(admin))
    assert not ch.enabled and ch.city == "tashkent"
    client.delete(f"/api/admin/channels/{ch.id}", headers=_h(admin))
    assert client.get("/api/admin/channels", headers=_h(admin)).json() == []
    assert ch.store_id not in {o["store"]["id"] for o in catalog.product_card(db, world["cpu"].id, None)["offers"]}
    assert db.scalar(select(func.count(Offer.id)).where(Offer.store_id == ch.store_id)) == 1  # hidden, not erased
    assert _actions(db) == ["channel_add", "channel_edit", "channel_disable", "channel_delete"]


def test_channel_fetch_now_saves_the_log(client, db, world, monkeypatch):
    from app.services import telegram

    monkeypatch.setattr(telegram, "fetch_page", lambda name, before=None: FEED)
    ch = svc.add_channel(db, world["admin"], "pcshop_uz", None, "tashkent")

    async def parse(rows, *a, **k):
        return []

    monkeypatch.setattr(telegram, "parse_clean_rows", parse)
    monkeypatch.setattr(telegram.time, "sleep", lambda s: None)
    r = client.post(f"/api/admin/channels/{ch['id']}/fetch", headers=_h(world["admin"]))
    assert r.status_code == 200 and r.json()["last_log"]["fetched"] >= 1
    assert _actions(db)[-1] == "channel_fetch"


def test_overview_counts(client, db, world):
    _report(db, world)
    f = _flag(db, world["offer"])
    f.status = FlagStatus.disputed
    _fix(db, world, world["cpu"], {"name": "x", "category": "cpu"})
    db.commit()
    w = client.get("/api/admin/overview", headers=_h(world["admin"])).json()["waiting"]
    assert w == {"stores": 2, "reports": 1, "flags": 1, "fixes": 1, "barcodes": 0, "photos": 0}
