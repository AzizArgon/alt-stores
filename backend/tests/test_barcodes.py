"""Phase 12.3: barcodes — the check of a code, store bindings, the common base, scans, Excel and the buyer."""

import io

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import BarcodeCode, Offer, Store, User, UserRole
from app.services import barcodes as bc
from app.services import cabinet, stock, stock_excel
from app.services.importer import publish_import
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row
from tests.test_stock import _moves, _world
from tests.test_stores import client  # noqa: F401  (the client fixture)

EAN13 = bc.make_ean13("200000000001")  # the internal range 200–299: never a real product
EAN13_B = bc.make_ean13("200000000002")


def _second_store(db, email="b@example.com"):
    store = Store(owner=User(email=email, password_hash="x", role=UserRole.seller), name=email.split("@")[0])
    db.add(store)
    db.commit()
    publish_import(db, _imp(db, store), store, FIRST[:3])
    return store


def _offer(db, store, product_id):
    return db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.product_id == product_id))


def _common(db, code):
    return db.scalar(select(BarcodeCode).where(BarcodeCode.code == code))


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


# --- the check of a code --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["4006381333931", "5901234123457", "96385074", "73513537", "036000291452"])
def test_right_check_digits_pass(code):
    assert bc.normalize(code) == ("0" + code if len(code) == 12 else code)


@pytest.mark.parametrize("code", ["4006381333932", "5901234123450", "96385075", "036000291453"])
def test_a_wrong_check_digit_is_a_misread(code):
    with pytest.raises(bc.BarcodeError) as e:
        bc.normalize(code)
    assert e.value.code == "checksum"


def test_upc_a_and_its_ean13_form_are_one_code():
    assert bc.normalize("036000291452") == bc.normalize("0036000291452") == "0036000291452"


@pytest.mark.parametrize("code,ok", [("ABC1", True), ("SN-2024/77-x", True), ("A" * 32, True), ("ABC", False),
                                     ("A" * 33, False), ("AB C1", False), ("", False), ("код1234", False)])
def test_other_formats_are_text_of_4_to_32_without_spaces(code, ok):
    if ok:
        assert bc.normalize(f" {code} ") == code
    else:
        with pytest.raises(bc.BarcodeError) as e:
            bc.normalize(code)
        assert e.value.code == "format"


def test_excel_number_cells_are_read_as_codes():
    assert bc.normalize(float(EAN13)) == EAN13
    assert bc.make_ean13("200000000001")[-1] == str(bc.check_digit("200000000001"))


# --- bindings and the common base -----------------------------------------------------------------------------------

def test_one_store_binding_works_only_for_that_store(db):
    store, chil, yunus, a, b = _world(db)
    other = _second_store(db)
    bc.bind(db, store, a, EAN13)
    assert bc.lookup(db, store, EAN13)["status"] == "found"
    assert _common(db, EAN13).status == "pending"
    # Another store: not confirmed — no suggestion
    assert bc.lookup(db, other, EAN13) == {"status": "unknown", "code": EAN13, "suggestion": None}
    assert bc.confirmed_product(db, EAN13) is None


def test_two_stores_on_the_same_card_confirm_the_code(db):
    store, chil, yunus, a, b = _world(db)
    other = _second_store(db)
    third = _second_store(db, "c@example.com")
    bc.bind(db, store, a, EAN13)
    bc.bind(db, other, _offer(db, other, a.product_id), EAN13)
    common = _common(db, EAN13)
    assert (common.status, common.product_id, common.stores) == ("confirmed", a.product_id, 2)
    # A third store gets the card offered at once, with its own offer on it
    res = bc.lookup(db, third, EAN13)
    assert res["suggestion"]["product_id"] == a.product_id
    assert res["suggestion"]["my_offer_id"] == _offer(db, third, a.product_id).id


def test_a_conflict_creates_no_common_binding(db):
    store, chil, yunus, a, b = _world(db)
    other = _second_store(db)
    bc.bind(db, store, a, EAN13)
    bc.bind(db, other, _offer(db, other, b.product_id), EAN13)  # the same code on another card
    common = _common(db, EAN13)
    assert common.status == "conflict" and common.product_id is None
    assert {c["product_id"] for c in common.conflict_json} == {a.product_id, b.product_id}
    assert bc.confirmed_product(db, EAN13) is None
    # Each store still has its own binding
    assert bc.lookup(db, store, EAN13)["status"] == bc.lookup(db, other, EAN13)["status"] == "found"


def test_a_code_is_one_offer_of_a_store_and_an_offer_has_many_codes(db):
    store, chil, yunus, a, b = _world(db)
    bc.bind(db, store, a, EAN13)
    bc.bind(db, store, a, EAN13_B)
    bc.bind(db, store, a, EAN13)  # again — nothing new
    assert [x["code"] for x in bc.codes(a)] == [EAN13, EAN13_B]
    with pytest.raises(bc.BarcodeError) as e:
        bc.bind(db, store, b, EAN13)
    assert e.value.code == "taken" and e.value.params["offer_id"] == a.id
    bc.unbind(db, store, a.barcodes[0].id)
    assert [x["code"] for x in bc.codes(a)] == [EAN13_B] and _common(db, EAN13) is None


def test_the_common_record_follows_a_relinked_offer(db):
    store, chil, yunus, a, b = _world(db)
    other = _second_store(db)
    bc.bind(db, store, a, EAN13)
    bc.bind(db, other, _offer(db, other, b.product_id), EAN13)
    assert _common(db, EAN13).status == "conflict"
    other_offer = _offer(db, other, b.product_id)
    db.delete(_offer(db, other, a.product_id))  # one offer per card: make room
    db.commit()
    cabinet.relink(db, other, other_offer, a.product)
    assert _common(db, EAN13).status == "confirmed"


# --- scans through the API ------------------------------------------------------------------------------------------

def test_unknown_code_then_binding_then_a_receipt_line(db, client):
    store, chil, yunus, a, b = _world(db)
    h = _h(store.owner)
    assert client.get("/api/seller/barcodes/lookup", params={"code": EAN13}, headers=h).json()["status"] == "unknown"
    bad = client.get("/api/seller/barcodes/lookup", params={"code": EAN13[:-1] + "0" if EAN13[-1] != "0" else EAN13[:-1] + "1"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "checksum"
    res = client.post("/api/seller/barcodes", json={"code": EAN13, "offer_id": a.id, "source": "scan"}, headers=h)
    assert res.status_code == 201 and res.json()["offer"]["barcodes"] == [EAN13]
    found = client.get("/api/seller/barcodes/lookup", params={"code": EAN13}, headers=h).json()
    assert found["status"] == "found" and found["offer"]["id"] == a.id
    # The goods input finds the offer by the code too
    assert client.get("/api/seller/stock/search", params={"q": EAN13}, headers=h).json()[0]["id"] == a.id
    # Two scans = one line of 2; posted through the journal of 12.2
    res = client.post("/api/seller/stock/operations", headers=h, json={"kind": "receipt", "scan": True, "lines": [
        {"offer_id": a.id, "branch_id": chil.id, "qty": 2, "cost": 30}]})
    assert res.status_code == 200
    m = _moves(db, kind="receipt")[-1]
    assert (m.offer_id, m.quantity_before, m.quantity_after, m.doc) == (a.id, 5, 7, res.json()["doc"])


def test_a_price_only_store_scans_as_a_hand_edit(db):
    store, chil, yunus, a, b = _world(db, mode="price")
    with pytest.raises(stock.StockError):
        stock.operate(db, store, store.owner, "receipt", [{"offer_id": a.id, "branch_id": chil.id, "qty": 1}])
    stock.operate(db, store, store.owner, "receipt", [{"offer_id": a.id, "branch_id": chil.id, "qty": 2}], scan=True)
    stock.operate(db, store, store.owner, "sale", [{"offer_id": a.id, "branch_id": yunus.id, "qty": 5}], scan=True)
    q = {s.branch_id: s.quantity for s in a.stocks}
    assert q == {chil.id: 7, yunus.id: 0}
    assert [(m.kind, m.quantity_after) for m in _moves(db)[-2:]] == [("manual", 7), ("manual", 0)]


def test_the_buyer_finds_a_card_only_by_a_confirmed_code(db, client):
    store, chil, yunus, a, b = _world(db)
    other = _second_store(db)
    bc.bind(db, store, a, EAN13)
    assert client.get(f"/api/catalog/barcode/{EAN13}").status_code == 404  # one store: not confirmed
    bc.bind(db, other, _offer(db, other, a.product_id), EAN13)
    assert client.get(f"/api/catalog/barcode/{EAN13}").json() == {"product_id": a.product_id}
    assert client.get("/api/catalog/barcode/123").status_code == 404
    # The barcode tables never reach the storefront's card
    assert "barcode" not in client.get(f"/api/catalog/products/{a.product_id}").text


def test_my_goods_shows_and_searches_barcodes(db):
    store, chil, yunus, a, b = _world(db)
    bc.bind(db, store, a, EAN13)
    rows = cabinet.list_offers(db, store, {"q": EAN13})["items"]
    assert [r["id"] for r in rows] == [a.id] and rows[0]["barcodes"][0]["code"] == EAN13
    assert [r["id"] for r in cabinet.list_offers(db, store, {"q": EAN13[-5:]})["items"]] == [a.id]


# --- Excel ----------------------------------------------------------------------------------------------------------

def test_export_fills_the_barcode_column_and_the_stock_import_binds_new_codes(db):
    store, chil, yunus, a, b = _world(db)
    bc.bind(db, store, a, EAN13)
    ws = load_workbook(io.BytesIO(stock_excel.export_offers(db, store, cabinet.store_offers(db, store), False))).active
    header = [c.value for c in ws[1]]
    col = header.index("Штрихкод")
    values = {r[0]: r[col] for r in ws.iter_rows(min_row=2, values_only=True)}
    assert values == {a.id: EAN13, b.id: None}
    # The seller adds a code for b (and a broken one) and loads the file back
    wb = Workbook()
    wb.active.append(["Код ALT", "Товар", "Штрихкод", "Чиланзар"])
    wb.active.append([b.id, b.product.normalized_name, f"{EAN13_B}, 2000000000009", None])
    buf = io.BytesIO()
    wb.save(buf)
    plan = stock_excel.stock_import(db, store, store.owner, buf.getvalue(), "s.xlsx", False)
    assert plan["barcodes"] == 1 and not bc.codes(b)
    stock_excel.stock_import(db, store, store.owner, buf.getvalue(), "s.xlsx", True)
    assert [x["code"] for x in bc.codes(b)] == [EAN13_B]
    # A file of only codes and quantities finds the offer by the code
    wb = Workbook()
    wb.active.append(["Товар", "Штрихкод", "Чиланзар"])
    wb.active.append([None, int(EAN13_B), 9])
    buf = io.BytesIO()
    wb.save(buf)
    stock_excel.stock_import(db, store, store.owner, buf.getvalue(), "s.xlsx", True)
    assert {s.branch_id: s.quantity for s in b.stocks}[chil.id] == 9


def test_a_price_list_barcode_column_binds_codes(db):
    from app.services.price_cleaner import clean_markdown

    rows = clean_markdown(f"| Наименование | Штрихкод | Цена |\n|---|---|---|\n| Kingston DDR5 32GB 6000MHz | {EAN13} | 120 |")
    assert rows[0].barcode == EAN13 and rows[0].article is None and rows[0].price == 120
    store, chil, yunus, a, b = _world(db)
    row = _row(9, "Kingston DDR5 32GB 6000MHz", 121) | {"barcode": EAN13}
    stats = publish_import(db, _imp(db, store, mode="append"), store, [row, _row(10, "Lexar DDR4 8GB 3200MHz", 58) | {"barcode": "123"}])
    assert stats["barcodes"] == 1
    assert bc.lookup(db, store, EAN13)["status"] == "found"
