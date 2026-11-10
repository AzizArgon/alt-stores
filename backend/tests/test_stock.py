"""Phase 12.2: stock keeping — the journal, the store's modes, operations, reservations, Excel."""

import pytest
from sqlalchemy import func, select

from app.db.models import Offer, Reservation, StockMovement, User, UserRole
from app.services import branches as br
from app.services import cabinet, stock, stock_excel
from app.services.importer import publish_import
from tests.test_branches import _branch_rows, _stores_with_branches, _stock
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_stores import client  # noqa: F401  (the client fixture)


def _moves(db, **where):
    q = select(StockMovement).order_by(StockMovement.id)
    for k, v in where.items():
        q = q.where(getattr(StockMovement, k) == v)
    return list(db.scalars(q))


def _world(db, mode="stock"):
    store, chil, yunus = _stores_with_branches(db)
    store.owner.role = UserRole.seller
    publish_import(db, _imp(db, store), store, FIRST[:2])
    offers = cabinet.store_offers(db, store)
    a, b = sorted(offers, key=lambda o: o.id)
    br.set_stock(a, chil.id, quantity=5)
    br.set_stock(a, yunus.id, quantity=2)
    db.commit()
    if mode == "stock":
        stock.set_mode(db, store, "stock", store.owner)
    return store, chil, yunus, a, b


def _op(db, store, kind, *lines):
    return stock.operate(db, store, store.owner, kind, list(lines))


def test_every_quantity_change_writes_the_journal(db):
    store, chil, yunus, a, b = _world(db, mode="price")
    manual = _moves(db)
    assert [(m.kind, m.branch_id, m.quantity_before, m.quantity_after, m.delta) for m in manual] == [
        ("manual", chil.id, None, 5, 5), ("manual", yunus.id, None, 2, 2)]
    cabinet.set_branch_stock(db, store, a, [{"branch_id": chil.id, "quantity": 3}])
    m = _moves(db)[-1]
    assert (m.kind, m.delta, m.quantity_after, m.user_id) == ("manual", -2, 3, store.user_id)
    # A price list with branch columns: "import" lines linked to the upload
    imp = _imp(db, store)
    imp.columns_json = {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    publish_import(db, imp, store, _branch_rows())
    assert _moves(db, import_id=imp.id) and all(m.kind == "import" for m in _moves(db, import_id=imp.id))


def test_switching_on_makes_the_opening_balance_and_back_keeps_the_journal(db):
    store, chil, yunus, a, b = _world(db, mode="price")
    res = stock.set_mode(db, store, "stock", store.owner)
    assert res["initial"] == 2 and store.stock_mode == "stock"
    init = _moves(db, kind="initial")
    assert [(m.branch_id, m.quantity_after) for m in init] == [(chil.id, 5), (yunus.id, 2)]
    n = len(_moves(db))
    stock.set_mode(db, store, "price", store.owner)
    assert store.stock_mode == "price" and len(_moves(db)) == n


def test_receipt_sale_and_adjustment(db):
    store, chil, yunus, a, b = _world(db)
    res = _op(db, store, "receipt", {"offer_id": a.id, "branch_id": chil.id, "qty": 3, "cost": 80},
              {"offer_id": b.id, "branch_id": yunus.id, "qty": 4, "cost": 100},
              {"offer_id": a.id, "branch_id": yunus.id, "qty": 1, "cost": 90})
    assert res["count"] == 3
    assert _stock(a) == {chil.id: (8, True), yunus.id: (3, True)} and _stock(b)[yunus.id] == (4, True)
    assert a.cost_last == 90 and a.cost_avg == 82.5 and len({m.doc for m in _moves(db, kind="receipt")}) == 1
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": chil.id, "qty": 2})
    sale = _moves(db, kind="sale")[-1]
    assert (sale.delta, sale.quantity_before, sale.quantity_after, sale.price) == (-2, 8, 6, a.price)
    _op(db, store, "adjust", {"offer_id": a.id, "branch_id": chil.id, "qty": 5, "reason": "inventory"})
    adj = _moves(db, kind="adjust")[-1]
    assert (adj.quantity_before, adj.quantity_after, adj.reason) == (6, 5, "inventory")
    with pytest.raises(stock.StockError, match="reason"):
        _op(db, store, "adjust", {"offer_id": a.id, "branch_id": chil.id, "qty": 1, "reason": "other"})


def test_quantity_never_below_zero_and_a_counter_sale_is_not_blocked(db):
    """Phase 12.4: a sale of more than the books have goes through: 0 left and "проверьте при ревизии"."""
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": yunus.id, "qty": 3})
    assert _stock(a)[yunus.id] == (0, False) and a.oversold_at is not None
    with pytest.raises(stock.StockError):
        stock.move(a, chil.id, "adjust", set_to=-1)
    # The whole document fails on a bad line: the first line is not sold either
    with pytest.raises(stock.StockError):
        _op(db, store, "sale", {"offer_id": a.id, "branch_id": chil.id, "qty": 1},
            {"offer_id": a.id, "branch_id": 999999, "qty": 1})
    assert _stock(a)[chil.id] == (5, True)


def test_operations_only_in_stock_mode_and_hand_edits_refused_there(db):
    store, chil, yunus, a, b = _world(db, mode="price")
    with pytest.raises(stock.StockError, match="mode_off"):
        _op(db, store, "receipt", {"offer_id": a.id, "branch_id": chil.id, "qty": 1})
    stock.set_mode(db, store, "stock", store.owner)
    with pytest.raises(cabinet.EditError, match="stock_mode"):
        cabinet.set_branch_stock(db, store, a, [{"branch_id": chil.id, "quantity": 1}])
    with pytest.raises(cabinet.EditError, match="stock_mode"):
        cabinet.bulk(db, store, [a], "branch_off", None, True, chil.id)


# --- reservations ---------------------------------------------------------------------------------------------------

def _reserve(db, store, offer, branch, qty=1):
    from app.services import reservations as res

    buyer = db.scalar(select(User).where(User.email == "buyer@example.com"))
    if buyer is None:
        buyer = User(email="buyer@example.com", password_hash="x", role=UserRole.buyer)
        db.add(buyer)
        db.commit()
    return res.create(db, buyer, {"kind": "offer", "item_id": offer.id, "name": "Азиз", "phone": "+998901234567",
                                  "contact": "call", "branch_id": branch.id, "quantity": qty})


def test_confirmation_reserves_and_issued_is_a_sale_by_the_reservation(db):
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db)
    r = _reserve(db, store, a, yunus, 2)
    assert _stock(a)[yunus.id] == (2, True)  # a new request reserves nothing
    res.advance(db, store.owner, r.id)  # confirmed
    row = next(s for s in a.stocks if s.branch_id == yunus.id)
    assert (row.quantity, row.reserved, r.reserved_qty) == (2, 2, 2) and not br.available(row)
    assert _moves(db, kind="reserve")[-1].reservation_id == r.id
    res.advance(db, store.owner, r.id)  # ready
    res.advance(db, store.owner, r.id)  # issued
    m = _moves(db, kind="res_sale")[-1]
    assert (m.delta, m.reserved_delta, m.quantity_after, m.price, m.reservation_id) == (-2, -2, 0, r.price, r.id)
    assert (row.quantity, row.reserved) == (0, 0)


def test_not_enough_stock_cannot_be_confirmed(db):
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db)
    r = _reserve(db, store, a, yunus, 2)
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": yunus.id, "qty": 1})
    with pytest.raises(res.ReservationError, match="reserve_short"):
        res.advance(db, store.owner, r.id)
    assert db.get(Reservation, r.id).status.value == "new"


def test_cancel_and_expiry_release_the_reserve(db):
    from datetime import timedelta

    from app.db.models import utcnow
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db)
    r1, r2 = _reserve(db, store, a, chil, 2), _reserve(db, store, a, chil, 1)
    res.advance(db, store.owner, r1.id)
    res.advance(db, store.owner, r2.id)
    row = next(s for s in a.stocks if s.branch_id == chil.id)
    assert row.reserved == 3
    res.cancel(db, store.owner, r1.id, "no_show")
    assert row.reserved == 1 and _moves(db, kind="unreserve")[-1].reservation_id == r1.id
    r2.expires_at = utcnow() - timedelta(hours=1)
    db.commit()
    res.expire_due(db)
    assert row.reserved == 0 and row.quantity == 5


def test_changing_the_branch_moves_the_reserve(db):
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db)
    r = _reserve(db, store, a, chil, 2)
    res.advance(db, store.owner, r.id)
    res.change_branch(db, store.owner, r.id, yunus.id)
    rows = {s.branch_id: s for s in a.stocks}
    assert (rows[chil.id].reserved, rows[yunus.id].reserved) == (0, 2)
    _op(db, store, "sale", {"offer_id": a.id, "branch_id": chil.id, "qty": 5})
    with pytest.raises(res.ReservationError, match="branch_no_stock"):
        res.change_branch(db, store.owner, r.id, chil.id)  # nothing there now
    assert rows[yunus.id].reserved == 2


def test_switching_on_reserves_confirmed_reservations_when_enough(db):
    from app.services import reservations as res

    store, chil, yunus, a, b = _world(db, mode="price")
    ok, short = _reserve(db, store, a, chil, 2), _reserve(db, store, a, yunus, 2)
    res.advance(db, store.owner, ok.id)
    res.advance(db, store.owner, short.id)  # "Только прайс": confirmed without a reserve
    assert ok.reserved_qty == short.reserved_qty == 0
    br.set_stock(a, yunus.id, quantity=1)
    db.commit()
    result = stock.set_mode(db, store, "stock", store.owner)
    assert result["reserved"] == 1 and result["unreserved"] == [short.id]
    assert ok.reserved_qty == 2 and [u["id"] for u in stock.overview(db, store)["unreserved"]] == [short.id]


# --- Excel ----------------------------------------------------------------------------------------------------------

def test_stock_import_goes_through_the_journal(db):
    import io

    from openpyxl import Workbook

    store, chil, yunus, a, b = _world(db)
    wb = Workbook()
    wb.active.append(["Товар", "Чиланзар", "Юнусабад"])
    wb.active.append([a.product.normalized_name, 7, "+"])  # "+" changes nothing
    wb.active.append(["Нет такого товара", 1, 1])
    buf = io.BytesIO()
    wb.save(buf)
    plan = stock_excel.stock_import(db, store, store.owner, buf.getvalue(), "s.xlsx", False)
    assert plan["total"] == 1 and plan["unknown"] == 1 and _stock(a)[chil.id] == (5, True)
    assert {x["branch_id"]: x["changed"] for x in plan["branches"]} == {chil.id: 1, yunus.id: 0}
    stock_excel.stock_import(db, store, store.owner, buf.getvalue(), "s.xlsx", True)
    m = _moves(db, kind="import")[-1]
    assert _stock(a) == {chil.id: (7, True), yunus.id: (2, True)} and (m.quantity_before, m.quantity_after) == (5, 7)


def test_export_then_import_of_the_same_file_changes_nothing(db):
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "receipt", {"offer_id": b.id, "branch_id": chil.id, "qty": 3, "cost": 50})
    content = stock_excel.export_offers(db, store, cabinet.store_offers(db, store), with_cost=True)
    n = len(_moves(db))
    plan = stock_excel.stock_import(db, store, store.owner, content, "goods.xlsx", True)
    assert plan["total"] == 0 and plan["rows"] == 2 and plan["unknown"] == 0 and len(_moves(db)) == n


def test_purchase_prices_never_reach_the_shop_window(db, client):
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "receipt", {"offer_id": a.id, "branch_id": chil.id, "qty": 1, "cost": 12.34})
    assert cabinet.offer_row(a)["cost_avg"] == 12.34  # the seller sees it
    for url in (f"/api/catalog/products/{a.product_id}?city=tashkent", "/api/catalog/products?city=tashkent",
                f"/api/catalog/stores/{store.id}"):
        text = client.get(url).text
        assert "cost" not in text and "12.34" not in text and '"reserved"' not in text, url


def test_undo_in_stock_mode_writes_reverse_lines(db):
    from app.services.undo import undo_import

    store, chil, yunus, a, b = _world(db)
    imp = _imp(db, store)
    imp.columns_json = {"Чиланзар": chil.id, "Юнусабад": yunus.id, "Склад": None}
    publish_import(db, imp, store, _branch_rows())
    lines = _moves(db, import_id=imp.id, kind="import")
    assert lines
    undo_import(db, imp)
    back = _moves(db, import_id=imp.id, kind="undo")
    assert back and len(_moves(db, import_id=imp.id, kind="import")) == len(lines)  # nothing deleted
    offer = db.get(Offer, a.id)
    assert _stock(offer)[chil.id][0] == 5


def test_price_only_mode_works_as_before(db):
    store, chil, yunus, a, b = _world(db, mode="price")
    publish_import(db, _imp(db, store), store, FIRST[1:2])  # full list without a: "нет" everywhere
    assert not a.is_in_stock and _stock(a) == {chil.id: (0, False), yunus.id: (0, False)}
    assert stock.overview(db, store) is None
    assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.kind == "initial")) == 0


def test_stock_mode_price_list_without_branch_numbers_keeps_quantities(db):
    store, chil, yunus, a, b = _world(db)
    publish_import(db, _imp(db, store), store, FIRST[1:2])  # full list without a: quantities kept
    assert _stock(a) == {chil.id: (5, True), yunus.id: (2, True)} and a.is_in_stock


def test_low_stock_in_the_overview(db):
    store, chil, yunus, a, b = _world(db)
    store.low_stock = 2
    low = stock.overview(db, store)["low"]
    assert [(i["offer_id"], i["branch_id"], i["available"]) for i in low] == [(a.id, yunus.id, 2)]
