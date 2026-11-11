"""Phase 12: "Undo this upload" - the snapshot at the publication, undo, conflicts with hand edits, limits."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.models import (
    Conversation, ImportStatus, Offer, UserRole, PriceHistory, PriceImport, Product, Reservation, TopicKind, User, utcnow,
)
from app.services import cabinet
from app.services.importer import publish_import
from app.services.manual import save_offer
from app.services.undo import can_undo, plan_undo, undo_import, undoable_id
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row, _store


def _offer(db, prefix):
    return db.scalar(select(Offer).where(Offer.raw_name.like(prefix + "%")))


def _setup(db):
    """First price list, then a second full one: Lexar dearer, Kingston gone (off sale), Goodram new."""
    store = _store(db, "a@example.com")
    publish_import(db, _imp(db, store), store, FIRST)
    db.scalar(select(Offer).where(Offer.raw_name.like("Patriot%"))).is_in_stock = False  # off sale before
    db.commit()
    second = [_row(1, "Lexar DDR4 8GB 3200MHz", 65), _row(3, "Patriot DDR4 16GB 3200MHz", 40),
              _row(4, "Crucial DDR5 16GB 5600MHz", 70), _row(5, "Goodram DDR4 8GB 2666MHz", 25)]
    imp = _imp(db, store)
    publish_import(db, imp, store, second)
    return store, imp


def test_publication_saves_the_snapshot(db):
    store, imp = _setup(db)
    snap = imp.undo_json
    by_id = {e["id"]: e for e in snap["offers"]}
    lexar, kingston, goodram = _offer(db, "Lexar"), _offer(db, "Kingston"), _offer(db, "Goodram")
    assert by_id[lexar.id]["before"]["price"] == 58 and by_id[lexar.id]["after"]["price"] == 65
    assert by_id[kingston.id]["before"]["is_in_stock"] and not by_id[kingston.id]["after"]["is_in_stock"]
    assert by_id[goodram.id]["before"] is None
    assert goodram.product_id in snap["products"]
    lexar_history = db.scalars(select(PriceHistory).where(PriceHistory.offer_id == lexar.id)
                               .order_by(PriceHistory.id)).all()
    goodram_history = db.scalars(select(PriceHistory.id).where(PriceHistory.offer_id == goodram.id)).all()
    assert [h.price for h in lexar_history] == [58, 65]
    assert set(snap["history"]) == {lexar_history[1].id, *goodram_history}
    assert imp.published_at is not None and undoable_id(db, store) == imp.id


def test_summary_and_undo_bring_everything_back(db):
    store, imp = _setup(db)
    plan = plan_undo(db, imp)
    assert [i["raw_name"] for i in plan["prices"]] == ["Lexar DDR4 8GB 3200MHz"]
    assert plan["prices"][0]["price"] == 58 and plan["prices"][0]["old_price"] == 65
    assert [i["raw_name"] for i in plan["back_in_stock"]] == ["Kingston DDR5 32GB 6000MHz"]
    assert [i["raw_name"] for i in plan["out_of_stock"]] == ["Patriot DDR4 16GB 3200MHz"]
    assert [i["raw_name"] for i in plan["removed_new"]] == ["Goodram DDR4 8GB 2666MHz"]
    assert plan["conflicts"] == [] and plan["kept_new"] == []
    goodram_card = _offer(db, "Goodram").product_id

    result = undo_import(db, imp)
    assert result["prices"] == 1 and result["removed_new"] == 1 and result["hidden_cards"] == 1
    lexar = _offer(db, "Lexar")
    assert lexar.price == 58
    # The upload's price history is gone: only the first price stays
    assert [h.price for h in db.scalars(select(PriceHistory).where(PriceHistory.offer_id == lexar.id))] == [58]
    assert _offer(db, "Kingston").is_in_stock
    assert not _offer(db, "Patriot").is_in_stock
    assert _offer(db, "Goodram") is None
    assert db.get(Product, goodram_card) is not None  # the card is kept, without offers it is out of the catalog
    assert imp.status == ImportStatus.undone and imp.undone_at is not None


def test_new_offer_with_reservation_or_chat_is_taken_off_sale(db):
    store, imp = _setup(db)
    goodram = _offer(db, "Goodram")
    buyer = User(email="b@example.com", password_hash="x")
    db.add(buyer)
    db.flush()
    db.add(Reservation(buyer_id=buyer.id, store_id=store.id, offer_id=goodram.id, title="Goodram", price=25,
                       currency=goodram.currency, name="B", phone="+998901234567", contact="call"))
    db.commit()
    assert [i["raw_name"] for i in plan_undo(db, imp)["kept_new"]] == ["Goodram DDR4 8GB 2666MHz"]
    undo_import(db, imp)
    kept = _offer(db, "Goodram")
    assert kept is not None and not kept.is_in_stock


def test_conversation_also_keeps_a_new_offer(db):
    store, imp = _setup(db)
    goodram = _offer(db, "Goodram")
    buyer = User(email="b@example.com", password_hash="x")
    db.add(buyer)
    db.flush()
    db.add(Conversation(buyer_id=buyer.id, store_id=store.id, topic_kind=TopicKind.offer, topic_id=goodram.id))
    db.commit()
    undo_import(db, imp)
    assert _offer(db, "Goodram") is not None


def test_hand_edits_after_the_upload_are_left_as_they_are(db):
    store, imp = _setup(db)
    lexar = _offer(db, "Lexar")
    cabinet.update_offer(db, store, lexar, {"price": 70})
    kingston = _offer(db, "Kingston")
    cabinet.bulk(db, store, [kingston], "on", None, True)
    plan = plan_undo(db, imp)
    assert sorted(i["raw_name"] for i in plan["conflicts"]) == ["Kingston DDR5 32GB 6000MHz", "Lexar DDR4 8GB 3200MHz"]
    assert plan["prices"] == [] and plan["back_in_stock"] == []
    undo_import(db, imp)
    assert _offer(db, "Lexar").price == 70
    assert [h.price for h in db.scalars(select(PriceHistory).where(PriceHistory.offer_id == lexar.id))] == [58, 65, 70]
    assert _offer(db, "Kingston").is_in_stock
    assert _offer(db, "Goodram") is None  # the rest is undone


def test_manual_adding_is_a_conflict_and_not_undone(db):
    store, imp = _setup(db)
    lexar = _offer(db, "Lexar")
    save_offer(db, store, lexar.product, 61, lexar.currency, lexar.condition, True)
    assert [i["raw_name"] for i in plan_undo(db, imp)["conflicts"]] == ["Lexar DDR4 8GB 3200MHz"]
    # A manual adding is an import of its own, it never becomes "the last upload"
    assert undoable_id(db, store) == imp.id


def test_only_the_last_upload_and_only_7_days(db):
    store, first = _setup(db)
    imp = _imp(db, store, mode="append")
    publish_import(db, imp, store, [_row(1, "Lexar DDR4 8GB 3200MHz", 66)])
    assert can_undo(db, first) == "not_last"
    assert can_undo(db, imp) is None
    for old in db.scalars(select(PriceImport).where(PriceImport.id != imp.id)):
        old.published_at = utcnow() - timedelta(days=9)
    imp.published_at = utcnow() - timedelta(days=8)
    db.commit()
    assert can_undo(db, imp) == "too_old" and undoable_id(db, store) is None


def test_undone_upload_can_not_be_undone_again(db):
    store, imp = _setup(db)
    undo_import(db, imp)
    assert can_undo(db, imp) == "already_undone"
    # The previous upload does not become undoable: only the last one ever is
    assert undoable_id(db, store) is None


def test_manual_and_telegram_imports_have_no_snapshot(db):
    store = _store(db, "a@example.com")
    imp = _imp(db, store, source="telegram", mode="append")
    publish_import(db, imp, store, FIRST, mode="append")
    assert imp.undo_json is None and can_undo(db, imp) == "not_undoable"


@pytest.mark.parametrize("path", ["/api/imports/{id}/undo"])
def test_api_summary_and_undo(db, path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.db.database import get_db
    from main import app

    store, imp = _setup(db)
    store.owner.role = UserRole.seller
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {create_access_token(store.owner.id, "seller")}"}
        listed = client.get("/api/imports", headers=headers).json()
        assert [i["can_undo"] for i in listed if i["id"] == imp.id] == [True]
        r = client.get(path.format(id=imp.id), headers=headers)
        assert r.status_code == 200 and len(r.json()["removed_new"]) == 1
        assert client.post(path.format(id=imp.id), headers=headers).json()["prices"] == 1
        again = client.post(path.format(id=imp.id), headers=headers)
        assert again.status_code == 409 and again.json()["detail"]["code"] == "already_undone"
        # An undone upload can not be published again
        assert client.post(f"/api/imports/{imp.id}/publish", headers=headers, json={"rows": []}).status_code == 409
    finally:
        app.dependency_overrides.clear()
