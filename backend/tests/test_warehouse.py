"""Phase 12.4 "Склад как в жизни": the warehouse, "Выкладка", a sale that is never blocked, "Возврат", "Ревизия"."""

import pytest
from sqlalchemy import select

from app.db.models import Branch, Offer, Reservation
from app.services import barcodes as bc
from app.services import branches as br
from app.services import cabinet, catalog, stock, warehouse
from app.services.reservations import ReservationError
from tests.test_import_modes import db  # noqa: F401  (the db fixture)
from tests.test_stock import _moves, _op, _reserve, _world
from tests.test_stock import _stock as _stock_  # noqa: F401
from tests.test_stores import client  # noqa: F401  (the client fixture)


def _wh_world(db):
    store, chil, yunus, a, b = _world(db)
    warehouse.set_warehouse(db, store, True, store.owner)
    wh = br.warehouse_of(db, store.id)
    return store, chil, yunus, wh, a, b


def _row(offer, branch):
    return next((s for s in offer.stocks if s.branch_id == branch.id), None)


# --- the buyer never sees the warehouse -----------------------------------------------------------------------------

def test_the_warehouse_is_not_seen_by_the_buyer(db, client):
    store, chil, yunus, wh, a, b = _wh_world(db)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": wh.id, "qty": 7})
    assert _row(b, wh).quantity == 7 and b.is_in_stock is False  # only in the warehouse: "нет в наличии"
    # Not a branch of the storefront, the "Stores" list or the reservation form
    assert wh.id not in {x.id for x in store.branches} and wh.id not in {x.id for x in br.store_branches(db, store.id)}
    data = client.get(f"/api/catalog/products/{b.product_id}").json()
    mine = next(o for o in data["offers"] if o["store"]["id"] == store.id)
    assert mine["is_in_stock"] is False and wh.id not in {x["id"] for x in mine["stock"]["branches"]}
    assert all(x["in_stock"] is False for x in mine["stock"]["branches"])
    page = client.get(f"/api/catalog/stores/{store.id}").text
    assert '"is_warehouse"' not in page
    with pytest.raises(ReservationError):
        _reserve(db, store, a, wh, 1)
    # The city: a warehouse in another city does not put the store there
    wh.city = "samarkand"
    db.commit()
    assert not db.scalars(select(Offer.id).where(br.in_city("samarkand"), Offer.store_id == store.id)).all()
    assert not db.scalars(select(Offer.id).where(br.in_stock_in("samarkand"), Offer.store_id == store.id)).all()
    # The market takes only offers on sale: the warehouse stock does not make one
    assert catalog is not None and b.is_in_stock is False


def test_receipt_to_the_warehouse_or_straight_to_a_branch(db):
    store, chil, yunus, a, b = _world(db)
    wh = Branch(store_id=store.id, city="tashkent", address="", is_warehouse=True)
    db.add(wh)
    db.commit()
    with pytest.raises(stock.StockError, match="branch"):  # a warehouse that is off is not a place
        _op(db, store, "receipt", {"offer_id": b.id, "branch_id": wh.id, "qty": 1})
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": yunus.id, "qty": 2})  # "Склада нет": into a branch
    assert _row(b, yunus).quantity == 2 and b.is_in_stock
    warehouse.set_warehouse(db, store, True, store.owner)
    assert br.warehouse_of(db, store.id).id == wh.id  # the same row is used again
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": wh.id, "qty": 3, "cost": 50})
    assert _row(b, wh).quantity == 3 and b.cost_last == 50


def test_an_unknown_code_becomes_an_item_and_a_receipt_line(db):
    store, chil, yunus, wh, a, b = _wh_world(db)
    code = bc.make_ean13("200000000777")
    assert bc.lookup(db, store, code)["status"] == "unknown"
    bc.bind(db, store, b, code, user_id=store.user_id, source="scan")  # "Добавить товар с этим штрихкодом"
    found = bc.lookup(db, store, code)
    assert found["status"] == "found" and found["offer_id"] == b.id
    _op(db, store, "receipt", {"offer_id": found["offer_id"], "branch_id": wh.id, "qty": 1})
    assert _row(b, wh).quantity == 1


# --- "Выкладка" -----------------------------------------------------------------------------------------------------

def test_put_out_is_two_linked_lines_and_not_more_than_the_warehouse_has(db):
    store, chil, yunus, wh, a, b = _wh_world(db)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": wh.id, "qty": 5})
    res = _op(db, store, "move", {"offer_id": b.id, "branch_id": yunus.id, "qty": 3})
    out, into = _moves(db, kind="move_out")[-1], _moves(db, kind="move_in")[-1]
    assert out.doc == into.doc == res["doc"] and res["doc"].startswith("M-")
    assert (out.branch_id, out.delta, into.branch_id, into.delta) == (wh.id, -3, yunus.id, 3)
    assert _row(b, wh).quantity == 2 and _row(b, yunus).quantity == 3 and b.is_in_stock
    with pytest.raises(stock.StockError) as e:
        _op(db, store, "move", {"offer_id": b.id, "branch_id": yunus.id, "qty": 3})
    assert e.value.code == "not_enough_wh" and e.value.params["available"] == 2
    with pytest.raises(stock.StockError, match="branch"):
        _op(db, store, "move", {"offer_id": b.id, "branch_id": wh.id, "qty": 1})
    warehouse.set_warehouse(db, store, False, store.owner, "write_off")
    with pytest.raises(stock.StockError, match="no_warehouse"):
        _op(db, store, "move", {"offer_id": b.id, "branch_id": yunus.id, "qty": 1})


# --- a sale at the counter ------------------------------------------------------------------------------------------

def test_a_sale_of_more_than_the_books_leaves_0_and_a_mark(db):
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": yunus.id, "qty": 4})
    m = _moves(db, kind="sale")[-1]
    assert (m.quantity_before, m.quantity_after, m.reason) == (2, 0, "oversold")
    assert cabinet.offer_row(a)["oversold"] is True
    assert cabinet.overview(db, store)["warehouse"]["oversold"][0]["offer_id"] == a.id
    # A stocktake (or an adjustment) clears the mark
    _op(db, store, "adjust", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1, "reason": "inventory"})
    assert a.oversold_at is None


def test_selling_a_reserved_item_asks_and_marks_the_reservation(db):
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db)
    r = _reserve(db, store, a, yunus, 2)
    res.advance(db, store.owner, r.id)  # confirmed: 2 of 2 reserved
    with pytest.raises(stock.StockError) as e:
        _op(db, store, "sale", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1})
    assert e.value.code == "reserved" and e.value.params["reserved"] == 2
    stock.operate(db, store, store.owner, "sale", [{"offer_id": a.id, "branch_id": yunus.id, "qty": 1}], confirm=True)
    db.refresh(r)
    row = _row(a, yunus)
    assert (row.quantity, row.reserved, r.reserved_qty) == (1, 1, 1) and r.sold_out_at is not None
    assert res.out(db, r, "store", None)["sold_out"] is True and "sold_out" not in res.out(db, r, "buyer", None)
    assert cabinet.overview(db, store)["warehouse"]["sold_reservations"][0]["id"] == r.id


# --- "Возврат" ------------------------------------------------------------------------------------------------------

def test_a_return_and_a_defective_return(db):
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "return", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1, "reason": "changed_mind"})
    assert _row(a, yunus).quantity == 3 and _moves(db, kind="return")[-1].delta == 1
    _op(db, store, "return", {"offer_id": a.id, "branch_id": yunus.id, "qty": 2, "reason": "defect", "restock": False})
    m = _moves(db, kind="return")[-1]
    assert (m.delta, m.reason, m.units, m.quantity_after) == (0, "defect_out", 2, 3)
    with pytest.raises(stock.StockError, match="reason"):
        _op(db, store, "return", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1, "reason": "other"})


# --- "Ревизия" ------------------------------------------------------------------------------------------------------

def test_a_stocktake_counts_finds_all_four_kinds_and_applies_through_the_journal(db):
    store, chil, yunus, a, b = _world(db)
    extra = sorted(cabinet.store_offers(db, store), key=lambda o: o.id)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": chil.id, "qty": 2})
    # Books of Чиланзар: a = 5, b = 2. A third item that is not in the books there (from another branch)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": yunus.id, "qty": 1})
    st = warehouse.start(db, store, store.owner, chil.id)
    for _ in range(5):
        warehouse.count(db, store, st, a.id)  # a: 5 = 5 — match
    warehouse.count(db, store, st, b.id, set_to=3)  # b: 3 > 2 — surplus
    # The page is closed and opened again: the same unfinished stocktake with its counts
    again = warehouse.start(db, store, store.owner, chil.id)
    assert again.id == st.id and again.counts_json == {str(a.id): 5, str(b.id): 3}
    assert warehouse.list_stocktakes(db, store)["open"][0]["id"] == st.id
    # One more item in the books, never scanned: "не найдено"; another one short
    c = extra[0] if extra[0].id not in (a.id, b.id) else None
    warehouse.count(db, store, st, a.id, set_to=4)  # a: 4 < 5 — shortage
    warehouse.finish(db, store, st)
    kinds = {line["offer_id"]: line["status"] for line in st.result_json}
    assert kinds == {a.id: "short", b.id: "over"} and c is None
    warehouse.resume(db, st)
    warehouse.count(db, store, st, a.id, set_to=5)
    warehouse.finish(db, store, st)
    assert {x["offer_id"]: x["status"] for x in st.result_json} == {a.id: "match", b.id: "over"}
    warehouse.resume(db, st)
    warehouse.count(db, store, st, a.id, set_to=0)  # a never scanned at all
    warehouse.finish(db, store, st)
    assert {x["offer_id"]: x["status"] for x in st.result_json} == {a.id: "missing", b.id: "over"}
    # The seller leaves b out: only a changes
    warehouse.exclude(db, st, b.id, True)
    warehouse.apply(db, store, st, store.owner)
    inv = _moves(db, kind="inventory")
    assert [(m.offer_id, m.quantity_before, m.quantity_after, m.doc) for m in inv] == [(a.id, 5, 0, st.doc)]
    assert _row(b, chil).quantity == 2 and st.status == "applied"
    assert (st.positions, st.shortage, st.surplus) == (2, 5, 0)
    hist = warehouse.list_stocktakes(db, store)
    assert not hist["open"] and hist["history"][0]["id"] == st.id
    assert stock.list_journal(db, store, {"doc": st.doc})["total"] == 1


def test_a_stocktake_over_line_and_only_chosen_categories(db):
    store, chil, yunus, a, b = _world(db)
    st = warehouse.start(db, store, store.owner, yunus.id, ["no-such-category"])
    assert st.categories_json == []  # unknown slugs are dropped
    warehouse.count(db, store, st, b.id)  # b is not in Юнусабад's books: over
    warehouse.finish(db, store, st)
    assert {x["offer_id"]: x["status"] for x in st.result_json} == {a.id: "missing", b.id: "over"}
    warehouse.apply(db, store, st, store.owner)
    assert _row(b, yunus).quantity == 1 and _row(a, yunus).quantity == 0 and st.surplus == 1
    with pytest.raises(stock.StockError, match="stocktake_state"):
        warehouse.count(db, store, st, a.id)


# --- switching the warehouse off ------------------------------------------------------------------------------------

def test_switching_the_warehouse_off_with_stock_asks_then_moves_or_writes_off(db):
    store, chil, yunus, wh, a, b = _wh_world(db)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": wh.id, "qty": 4})
    assert cabinet.overview(db, store)["warehouse"]["only_warehouse"][0]["offer_id"] == b.id
    with pytest.raises(stock.StockError) as e:
        warehouse.set_warehouse(db, store, False, store.owner)
    assert e.value.code == "warehouse_stock" and e.value.params == {"positions": 1, "units": 4}
    res = warehouse.set_warehouse(db, store, False, store.owner, "move", chil.id)
    assert res["moved"] == 4 and _row(b, chil).quantity == 4 and _row(b, wh).quantity == 0
    assert not store.has_warehouse and wh.id not in stock._branch_ids(db, store)
    warehouse.set_warehouse(db, store, True, store.owner)
    _op(db, store, "receipt", {"offer_id": a.id, "branch_id": wh.id, "qty": 2})
    res = warehouse.set_warehouse(db, store, False, store.owner, "write_off")
    m = _moves(db, kind="adjust")[-1]
    assert res["written_off"] == 2 and (m.branch_id, m.quantity_after, m.reason) == (wh.id, 0, "wh_off")


def test_the_store_api_gives_the_warehouse_only_to_the_seller(db, client):
    from tests.test_barcodes import _h

    store, chil, yunus, wh, a, b = _wh_world(db)
    store.name = "Склад-тест"
    db.commit()
    me = client.get("/api/stores/me", headers=_h(store.owner)).json()
    assert me["has_warehouse"] and me["warehouse"]["id"] == wh.id and wh.id not in {x["id"] for x in me["branches"]}
    r = client.put(f"/api/stores/me/branches/{wh.id}", headers=_h(store.owner),
                   json={"city": "tashkent", "address": "ул. Навои, 1", "landmark": "ЦУМ"})
    assert r.status_code == 404  # the warehouse is not edited as a branch
    r = client.post("/api/seller/stock/warehouse", headers=_h(store.owner), json={"on": False})
    assert r.status_code == 200 and not r.json()["has_warehouse"]
    assert db.scalar(select(Reservation.id)) is None
