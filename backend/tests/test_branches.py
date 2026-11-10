"""Phase 12.1: branches of a store and stock by branch."""

import pytest
from sqlalchemy import select

from app.db.models import Branch, Offer, Reservation, Store, StoreKind, User
from app.services import branches as br
from app.services.importer import publish_import
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row


def _shop(db, email="a@example.com", city="tashkent", address="ул. Навои, 12"):
    store = Store(owner=User(email=email, password_hash="x"), name=email.split("@")[0], city=city, address=address,
                  district="ЦУМ", hours="Пн–Сб 10–19", map_url="https://yandex.uz/maps/?ll=69.28%2C41.31",
                  map_lat=41.31, map_lon=69.28)
    db.add(store)
    db.commit()
    return store


def _data(city="tashkent", address="ул. Бабура, 5", landmark="рынок", **kw):
    return {"city": city, "address": address, "landmark": landmark, **kw}


def test_store_address_moves_to_its_main_branch_without_losses(db):
    store = _shop(db)
    no_address = _shop(db, "b@example.com", address=None)
    channel = Store(owner=User(email="c@example.com", password_hash="x"), name="@ch", kind=StoreKind.telegram)
    db.add(channel)
    db.commit()
    assert br.migrate_branches(db) == 1
    main = br.main_branch(db, store.id)
    assert (main.city, main.address, main.landmark, main.hours, main.map_url, main.map_lat, main.map_lon) == (
        "tashkent", "ул. Навои, 12", "ЦУМ", "Пн–Сб 10–19", store.map_url, 41.31, 69.28)
    assert br.main_branch(db, no_address.id) is None and br.main_branch(db, channel.id) is None
    assert br.migrate_branches(db) == 0  # once
    assert len(br.store_branches(db, store.id)) == 1


def test_old_reservations_go_to_the_main_branch(db):
    store = _shop(db)
    r = Reservation(buyer=User(email="buyer@example.com", password_hash="x"), store=store, title="x", price=1,
                    currency="USD", name="A", phone="+998901234567", contact="call")
    db.add(r)
    db.commit()
    br.migrate_branches(db)
    assert r.branch_id == br.main_branch(db, store.id).id


def test_exactly_one_main_branch_and_it_is_the_store_address(db):
    store = _shop(db)
    br.migrate_branches(db)
    second = br.save_branch(db, store, _data(city="samarkand", address="ул. Регистан, 1"))
    assert not second.is_main
    br.make_main(db, store, second)
    assert [b.id for b in db.scalars(select(Branch).where(Branch.is_main.is_(True)))] == [second.id]
    assert (store.city, store.address, store.district) == ("samarkand", "ул. Регистан, 1", "рынок")


def test_main_and_last_branch_cannot_be_deleted(db):
    store = _shop(db)
    br.migrate_branches(db)
    main = br.main_branch(db, store.id)
    with pytest.raises(br.BranchError, match="delete_main"):
        br.delete_branch(db, store, main)
    other = br.save_branch(db, store, _data())
    br.delete_branch(db, store, other)
    assert len(br.store_branches(db, store.id)) == 1


@pytest.mark.parametrize("bad, code", [({"address": ""}, "address"), ({"landmark": " "}, "landmark"),
                                       ({"city": "moscow"}, "city"), ({"map_url": "https://google.com/maps"}, "map_url")])
def test_branch_needs_address_landmark_known_city_and_yandex_link(db, bad, code):
    store = _shop(db)
    with pytest.raises(br.BranchError, match=code):
        br.save_branch(db, store, {**_data(), **bad})


def test_in_stock_means_available_above_zero(db):
    store = _shop(db)
    br.migrate_branches(db)
    a, b = br.main_branch(db, store.id), br.save_branch(db, store, _data())
    publish_import(db, _imp(db, store), store, FIRST[:1])
    offer = db.scalar(select(Offer))
    br.set_stock(offer, a.id, quantity=2)
    assert offer.is_in_stock
    row = br.set_stock(offer, a.id, quantity=0)
    assert not br.available(row) and not offer.is_in_stock
    row.quantity, row.reserved = 3, 3  # all reserved (12.2): nothing available
    assert not br.available(row)
    br.set_stock(offer, b.id, present=True)  # "есть, количество не указано"
    assert offer.is_in_stock and next(s for s in offer.stocks if s.branch_id == b.id).quantity is None


# --- price lists with branch columns -------------------------------------------------------------------------------

from app.db.models import PriceImport  # noqa: E402
from app.services import branch_stock  # noqa: E402
from app.services.price_cleaner import clean_markdown, stock_value  # noqa: E402

BRANCH_MD = """## Прайс
| Наименование | Цена | Чиланзар | Юнусабад | Склад |
|---|---|---|---|---|
| Kingston DDR5 32GB 6000MHz | 120 | 5 | + | - |
| Lexar DDR4 8GB 3200MHz | 58 | 0 | нет | |
| Patriot DDR4 16GB 3200MHz | 40 | да | есть | 2 |
"""


@pytest.mark.parametrize("cell, value", [("5", 5), ("0", 0), ("+", True), ("да", True), ("есть", True),
                                         ("нет", False), ("", None), ("12,0", 12)])
def test_branch_stock_values(cell, value):
    assert stock_value(cell) == value


def test_branch_columns_are_found_and_kept_out_of_the_name():
    rows = clean_markdown(BRANCH_MD)
    assert rows[0].branch_cells == {"Чиланзар": 5, "Юнусабад": True, "Склад": None}
    assert rows[1].branch_cells == {"Чиланзар": 0, "Юнусабад": False, "Склад": None} and not rows[1].is_in_stock
    assert rows[0].raw_name == "Kingston DDR5 32GB 6000MHz" and rows[0].price == 120
    assert "+" not in rows[0].ai_text


def test_one_stock_column_stays_the_general_stock():
    md = "| Наименование | Цена | Наличие |\n|---|---|---|\n| Kingston DDR5 32GB | 120 | нет |\n"
    row = clean_markdown(md)[0]
    assert row.branch_cells == {} and not row.is_in_stock
    # ...unless the seller already matched this column to a branch
    assert clean_markdown(md, {"наличие"})[0].branch_cells == {"Наличие": False}


def _branch_rows():
    rows = []
    for r in clean_markdown(BRANCH_MD):
        rows.append({**_row(r.row, r.raw_name, r.price), "branches": r.branch_cells, "is_in_stock": r.is_in_stock})
    return rows


def _stores_with_branches(db):
    store = _shop(db)
    br.migrate_branches(db)
    chil = br.main_branch(db, store.id)
    chil.name = "Чиланзар"
    yunus = br.save_branch(db, store, _data(name="Юнусабад"))
    db.commit()
    return store, chil, yunus


def _stock(offer):
    return {s.branch_id: (s.quantity, s.in_stock) for s in offer.stocks}


def test_columns_matching_is_suggested_confirmed_and_remembered(db):
    store, chil, yunus = _stores_with_branches(db)
    imp = _imp(db, store)
    imp.stats_json = {"branch_columns": ["Чиланзар", "Юнусабад", "Склад"]}
    info = branch_stock.branch_info(db, imp)
    assert not info["confirmed"] and info["mapping"] == {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    with pytest.raises(branch_stock.ColumnsError):
        branch_stock.confirm_columns(db, store, imp, {"Чиланзар": chil.id, "Юнусабад": chil.id})
    branch_stock.confirm_columns(db, store, imp, {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None})
    assert branch_stock.branch_info(db, imp)["confirmed"]
    assert branch_stock.known_branch_columns(db, store.id) == {"чиланзар", "юнусабад"}
    # The next price list: the same columns are matched by themselves
    nxt = _imp(db, store)
    nxt.stats_json = {"branch_columns": ["Юнусабад"]}
    yunus.name = "Другое имя"
    assert branch_stock.branch_info(db, nxt)["mapping"] == {"Юнусабад": yunus.id}


def test_branch_columns_set_stock_by_branch_and_the_summary_shows_it(db):
    store, chil, yunus = _stores_with_branches(db)
    imp = _imp(db, store)
    imp.columns_json = {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    from app.services.importer import plan_import

    plan = plan_import(db, imp, store, _branch_rows())
    assert {b["branch_id"]: b["appear"] for b in plan["branches"]} == {chil.id: 2, yunus.id: 2}
    publish_import(db, imp, store, _branch_rows())
    offers = {o.raw_name: o for o in db.scalars(select(Offer))}
    kingston, lexar, patriot = (offers[n] for n in ("Kingston DDR5 32GB 6000MHz", "Lexar DDR4 8GB 3200MHz",
                                                    "Patriot DDR4 16GB 3200MHz"))
    assert _stock(kingston) == {chil.id: (5, True), yunus.id: (None, True)}
    assert _stock(lexar) == {chil.id: (0, False), yunus.id: (0, False)} and not lexar.is_in_stock
    assert _stock(patriot) == {chil.id: (None, True), yunus.id: (None, True)} and patriot.is_in_stock


def test_price_list_of_one_branch_changes_only_that_branch(db):
    store, chil, yunus = _stores_with_branches(db)
    imp = _imp(db, store)
    imp.columns_json = {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    publish_import(db, imp, store, _branch_rows())
    # Yunusabad sends its own full list: only Kingston, now sold out there
    one = _imp(db, store)
    one.branch_id = yunus.id
    publish_import(db, one, store, [{**_row(1, "Kingston DDR5 32GB 6000MHz", 120), "is_in_stock": False}])
    offers = {o.raw_name: o for o in db.scalars(select(Offer))}
    assert _stock(offers["Kingston DDR5 32GB 6000MHz"]) == {chil.id: (5, True), yunus.id: (0, False)}
    # Patriot is missing from the full branch list: "нет" in Yunusabad only, still on sale in Chilanzar
    assert _stock(offers["Patriot DDR4 16GB 3200MHz"]) == {chil.id: (None, True), yunus.id: (0, False)}
    assert offers["Patriot DDR4 16GB 3200MHz"].is_in_stock


def test_undo_brings_back_the_stock_by_branch(db):
    from app.services.undo import undo_import

    store, chil, yunus = _stores_with_branches(db)
    imp = _imp(db, store)
    imp.columns_json = {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    publish_import(db, imp, store, _branch_rows())
    one = _imp(db, store)
    one.branch_id = yunus.id
    publish_import(db, one, store, [{**_row(1, "Kingston DDR5 32GB 6000MHz", 120), "is_in_stock": False}])
    undo_import(db, one)
    offers = {o.raw_name: o for o in db.scalars(select(Offer))}
    assert _stock(offers["Kingston DDR5 32GB 6000MHz"]) == {chil.id: (5, True), yunus.id: (None, True)}
    assert _stock(offers["Patriot DDR4 16GB 3200MHz"]) == {chil.id: (None, True), yunus.id: (None, True)}


def test_general_price_list_keeps_branch_stock_honest(db):
    store, chil, yunus = _stores_with_branches(db)
    publish_import(db, _imp(db, store), store, FIRST[:2])
    offer = db.scalar(select(Offer).where(Offer.raw_name == FIRST[0]["raw_name"]))
    br.set_stock(offer, yunus.id, quantity=0)
    db.commit()
    assert not offer.is_in_stock
    # A price list without branch columns says "in stock": the main branch gets "есть"
    publish_import(db, _imp(db, store), store, FIRST[:2])
    assert offer.is_in_stock and _stock(offer)[chil.id] == (None, True)
    # ...and "sold out" (missing in a full list) is "нет" everywhere
    publish_import(db, _imp(db, store), store, FIRST[1:2])
    assert not offer.is_in_stock and all(not s.in_stock for s in offer.stocks)


# --- the shop window ------------------------------------------------------------------------------------------------

from datetime import timedelta  # noqa: E402

from app.db.models import utcnow  # noqa: E402
from app.services.catalog import product_card, search_products  # noqa: E402
from tests.test_stores import client  # noqa: E402,F401  (the client fixture)


def _two_city_store(db):
    store, chil, yunus = _stores_with_branches(db)
    sam = br.save_branch(db, store, _data(city="samarkand", address="ул. Регистан, 1", name="Самарканд"))
    publish_import(db, _imp(db, store), store, FIRST[:1])
    offer = db.scalar(select(Offer))
    br.set_stock(offer, chil.id, quantity=3)
    br.set_stock(offer, yunus.id, quantity=0)
    br.set_stock(offer, sam.id, quantity=0)
    db.commit()
    return store, offer, (chil, yunus, sam)


def test_city_filter_counts_stock_in_the_city_branches(db):
    store, offer, (chil, yunus, sam) = _two_city_store(db)
    assert search_products(db, None, city="tashkent")["total"] == 1
    # The store is in Samarkand too, but the item is not there
    assert search_products(db, None, city="samarkand")["total"] == 0
    assert search_products(db, None, city="samarkand", in_stock=False)["total"] == 1
    assert search_products(db, None, city="bukhara", in_stock=False)["total"] == 0
    card = product_card(db, offer.product_id, None, city="tashkent")
    stock = card["offers"][0]["stock"]
    assert card["offers"][0]["is_in_stock"] and (stock["available"], stock["total"]) == (1, 2)
    assert [b["city"] for b in stock["branches"]][:2] == ["tashkent", "tashkent"]  # the city's branches first
    card = product_card(db, offer.product_id, None, city="samarkand")
    assert not card["offers"][0]["is_in_stock"]
    assert product_card(db, offer.product_id, None)["offers"][0]["stock"]["total"] == 3  # all of Uzbekistan


def test_store_without_branch_stock_uses_its_general_flag(db):
    store, _, _ = _stores_with_branches(db)
    publish_import(db, _imp(db, store), store, FIRST[:1])
    offer = db.scalar(select(Offer))
    card = product_card(db, offer.product_id, None, city="tashkent")
    assert card["offers"][0]["is_in_stock"] and card["offers"][0]["stock"]["tracked"] is False
    assert search_products(db, None, city="tashkent")["total"] == 1


def test_old_branch_data_is_marked_stale(db):
    store, offer, (chil, _, _) = _two_city_store(db)
    row = next(s for s in offer.stocks if s.branch_id == chil.id)
    row.updated_at = utcnow() - timedelta(days=4)
    db.commit()
    stock = product_card(db, offer.product_id, None, city="tashkent")["offers"][0]["stock"]
    assert stock["stale"] and next(b for b in stock["branches"] if b["id"] == chil.id)["stale"]


def test_quantity_never_reaches_the_shop_window_api(db, client):
    store, offer, _ = _two_city_store(db)
    for url in (f"/api/catalog/products/{offer.product_id}?city=tashkent", "/api/catalog/stores?city=tashkent",
                f"/api/catalog/stores/{store.id}", "/api/catalog/products?city=tashkent"):
        text = client.get(url).text
        assert '"quantity"' not in text and '"reserved"' not in text, url


def test_stores_list_shows_a_store_in_every_city_of_its_branches(db, client):
    store, _, _ = _two_city_store(db)
    for city, here in (("tashkent", 2), ("samarkand", 1)):
        items = client.get(f"/api/catalog/stores?city={city}").json()["items"]
        assert [(i["id"], i["branches_here"]) for i in items] == [(store.id, here)]
    assert client.get("/api/catalog/stores?city=bukhara").json()["items"] == []
