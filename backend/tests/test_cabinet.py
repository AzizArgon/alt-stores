"""Phase B3: the seller cabinet — "My goods", the offer editor, the shared card, bulk actions."""

import pytest
from sqlalchemy import select

from app.db.models import Currency, Offer, PriceHistory, Product, ProductFix
from app.services import cabinet
from app.services.cabinet import EditError
from app.services.importer import publish_import
from tests.test_import_modes import _imp, db  # noqa: F401  (db is a fixture)
from tests.test_publish import _row, _store


def _publish(db, store, rows, currency=Currency.USD):
    imp = _imp(db, store)
    imp.currency = currency
    publish_import(db, imp, store, rows)


def _offer(db, store, raw):
    return db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.raw_name == raw))


@pytest.fixture
def shop(db):
    store = _store(db, "a@example.com")
    _publish(db, store, [_row(1, "Lexar DDR4 8GB 3200MHz", 58), _row(2, "Kingston DDR5 32GB 6000MHz", 120)])
    return store


def test_price_edit_goes_to_price_history(db, shop):
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    row = cabinet.update_offer(db, shop, offer, {"price": 61})
    assert row["price"] == 61
    assert [h.price for h in offer.price_history] == [58, 61]
    cabinet.update_offer(db, shop, offer, {"note": "Подписчикам 59$"})  # no price change -> no history row
    assert len(offer.price_history) == 2 and offer.note == "Подписчикам 59$"


def test_condition_edit_rechecks_anti_fraud(db, shop):
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    offer.raw_name = "Lexar DDR4 8GB 3200MHz б/у"  # the seller's own line says "used"
    cabinet.update_offer(db, shop, offer, {})
    assert any(f["type"] == "used_as_new" for f in cabinet.active_flags(offer))
    cabinet.update_offer(db, shop, offer, {"condition": "used"})
    assert not any(f["type"] == "used_as_new" for f in cabinet.active_flags(offer))
    assert [(e.field, e.value) for e in offer.events] == [("condition", "used")]


def test_stock_toggle_is_logged_and_needs_a_price(db, shop):
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    cabinet.update_offer(db, shop, offer, {"is_in_stock": False})
    assert not offer.is_in_stock and offer.events[-1].value == "0"
    offer.price = None
    with pytest.raises(EditError, match="price_required"):
        cabinet.update_offer(db, shop, offer, {"is_in_stock": True})


def test_relink_moves_the_offer_and_the_old_card_stays(db, shop):
    other = _store(db, "b@example.com")
    _publish(db, other, [_row(1, "Patriot DDR4 16GB 3200MHz", 40)])
    target = _offer(db, other, "Patriot DDR4 16GB 3200MHz").product
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    old = offer.product
    cabinet.relink(db, shop, offer, target)
    assert offer.product_id == target.id
    assert db.get(Product, old.id) is not None  # not deleted: no offers left, so the catalog does not show it
    assert not db.scalars(select(Offer).where(Offer.product_id == old.id)).all()
    kingston = _offer(db, shop, "Kingston DDR5 32GB 6000MHz")
    with pytest.raises(EditError, match="offer_exists"):  # one offer per card per store
        cabinet.relink(db, shop, kingston, target)


def test_card_of_one_store_is_edited_at_once(db, shop):
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    product_id = offer.product_id
    res = cabinet.edit_card(db, shop, offer, {"category": "ram", "brand": "Lexar", "model": "LD4AU008G",
                                              "name": "Lexar DDR4 8GB 3200MHz LD4AU008G", "specs": {"type": "DDR4"}})
    assert res["status"] == "applied"
    product = db.get(Product, product_id)
    assert product.model == "LD4AU008G" and "ld4au008g" in product.match_key
    # The key of another card: the seller is offered to move the offer there instead of a duplicate
    kingston = _offer(db, shop, "Kingston DDR5 32GB 6000MHz")
    res = cabinet.edit_card(db, shop, kingston, {"category": "ram", "brand": "Lexar", "model": "LD4AU008G",
                                                 "name": "Lexar DDR4 8GB 3200MHz LD4AU008G", "specs": {"type": "DDR4"}})
    assert res["status"] == "exists" and res["product"]["id"] == product_id


def test_card_sold_by_other_stores_gets_a_suggestion(db, shop):
    other = _store(db, "b@example.com")
    _publish(db, other, [_row(1, "Lexar DDR4 8GB 3200MHz", 57)])
    offer = _offer(db, shop, "Lexar DDR4 8GB 3200MHz")
    before = (offer.product.normalized_name, offer.product.match_key)
    res = cabinet.edit_card(db, shop, offer, {"category": "ram", "brand": "Lexar", "model": None,
                                              "name": "Lexar DDR4 16GB 3200MHz", "specs": {}})
    assert res == {"status": "suggested"}
    assert (offer.product.normalized_name, offer.product.match_key) == before  # the card is not changed
    fix = db.scalar(select(ProductFix))
    assert fix.after["name"] == "Lexar DDR4 16GB 3200MHz" and fix.status == "pending"
    assert cabinet.offer_detail(db, shop, offer)["pending_fix"]["name"] == "Lexar DDR4 16GB 3200MHz"


def test_bulk_price_change_rounds_and_writes_history(db):
    store = _store(db, "a@example.com")
    _publish(db, store, [_row(1, "Lexar DDR4 8GB 3200MHz", 58), _row(2, "Kingston DDR5 32GB 6000MHz", 120)])
    sum_store = _store(db, "s@example.com")
    _publish(db, sum_store, [_row(1, "Patriot DDR4 16GB 3200MHz", 512_000)], Currency.UZS)

    offers = cabinet.store_offers(db, store)
    preview = cabinet.bulk(db, store, offers, "price", 5, apply=False)
    assert preview["count"] == 2 and {i["price"] for i in preview["items"]} == {61.0, 126.0}  # 60.9, 126
    assert _offer(db, store, "Lexar DDR4 8GB 3200MHz").price == 58  # the preview writes nothing
    cabinet.bulk(db, store, offers, "price", 5, apply=True)
    lexar = _offer(db, store, "Lexar DDR4 8GB 3200MHz")
    assert lexar.price == 61 and [h.price for h in lexar.price_history] == [58, 61]

    cabinet.bulk(db, sum_store, cabinet.store_offers(db, sum_store), "price", 5, apply=True)
    assert _offer(db, sum_store, "Patriot DDR4 16GB 3200MHz").price == 538_000  # 537 600 -> to 1 000 sum
    assert cabinet.round_price(3.47, Currency.USD) == 3.5


def test_bulk_off_and_on_sale(db, shop):
    offers = cabinet.store_offers(db, shop)
    assert cabinet.bulk(db, shop, offers, "off", None, apply=True)["count"] == 2
    assert cabinet.overview(db, shop)["out_of_stock"] == 2
    assert cabinet.bulk(db, shop, offers, "on", None, apply=True)["count"] == 2


def test_list_filters_and_delete_keeps_history(db, shop):
    res = cabinet.list_offers(db, shop, {"q": "kingston"}, "name", False)
    assert res["total"] == 1 and res["items"][0]["raw_name"] == "Kingston DDR5 32GB 6000MHz"
    offer = _offer(db, shop, "Kingston DDR5 32GB 6000MHz")
    cabinet.update_offer(db, shop, offer, {"is_in_stock": False})
    assert cabinet.list_offers(db, shop, {"stock": "out"})["total"] == 1
    assert [r["price"] for r in cabinet.list_offers(db, shop, {}, "price", True)["items"]] == [120, 58]

    cabinet.remove_offer(db, offer)
    assert cabinet.list_offers(db, shop, {})["total"] == 1
    assert db.scalars(select(PriceHistory).where(PriceHistory.offer_id == offer.id)).all()  # history kept
    assert db.get(Product, offer.product_id) is not None  # the card too
    # The next price list with the item brings the offer back
    _publish(db, shop, [_row(1, "Lexar DDR4 8GB 3200MHz", 58), _row(2, "Kingston DDR5 32GB 6000MHz", 118)])
    assert offer.removed_at is None and offer.price == 118
