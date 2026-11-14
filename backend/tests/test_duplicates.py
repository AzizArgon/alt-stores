"""Phase 16.1: one product — one card. Normalization of the model, pairs that are NOT duplicates, the scan
and the merge (everything moves, nothing is lost, the old address leads to the kept card)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.database import get_db
from app.db.models import Offer, PriceHistory, Product, ProductFix
from app.services import duplicates
from app.services.catalog import make_match_key, resolve_merged
from app.services.importer import publish_import
from main import app
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)
from tests.test_publish import _import, _row


def key(name, slug="cpu", brand="Intel", specs=None):
    return make_match_key(slug, name, brand, specs)


def test_type_word_at_the_start_in_three_languages_and_slang():
    base = key("Intel Core i5-12400F")
    for name in ("Процессор Intel Core i5-12400F", "Protsessor Intel Core i5-12400F", "Processor Intel Core i5-12400F",
                 "проц Intel Core i5 12400F", "CPU Intel Core i5-12400F"):
        assert key(name) == base, name
    gpu = key("MSI GeForce RTX 4060 Ventus 2X 8GB", "gpu", "MSI")
    assert key("Видеокарта MSI RTX 4060 Ventus 2X 8GB", "gpu", "MSI") == gpu
    assert key("Videokarta MSI RTX 4060 Ventus 2X 8GB", "gpu", "MSI") == gpu
    assert key("видюха MSI RTX4060 Ventus 2X 8 GB", "gpu", "MSI") == gpu


def test_hyphen_space_case_and_characteristics_after_the_model():
    base = key("Intel Core i5-12400F")
    assert key("Intel Core i5 12400F") == key("intel core I5-12400f") == base
    assert key("Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700") == base
    assert key("Intel-Core i5 - 12400F, 2.7 GHz, 18MB, oem, LGA1700, Alder Lake") == base


def test_oem_and_box_are_one_card():
    base = key("Intel Core i5-12400F")
    assert key("Intel Core i5-12400F OEM") == key("Intel Core i5-12400F BOX") == key("i5 12400F tray") == base
    assert key("Intel Core i5-12400F", specs={"pack": "BOX"}) == base


def test_different_products_stay_apart():
    assert key("Intel Core i5-12400F") != key("Intel Core i5-12400")
    assert key("Процессор Intel Core i5 12400F BOX") != key("Intel Core i5-12400 OEM")
    assert key("RTX 4060 8GB", "gpu", "MSI") != key("RTX 4060 Ti 8GB", "gpu", "MSI")
    assert key("RTX 4060 Ti 8GB", "gpu", "MSI") != key("RTX 4060 Ti 16GB", "gpu", "MSI")
    assert key("Samsung 990 Pro 1TB", "ssd", "Samsung") != key("Samsung 990 Pro 2TB", "ssd", "Samsung")
    assert key("Kingston Fury Beast 16GB DDR4 3200", "ram", "Kingston") != \
        key("Kingston Fury Beast 32GB DDR4 3200", "ram", "Kingston")


def _world(db):
    a, b, c = _store(db, "a@example.com"), _store(db, "b@example.com"), _store(db, "c@example.com")
    old = _card(db, "cpu", "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", {"pack": "OEM"}, "Intel")
    for s, price in ((a, 120), (b, 125)):
        _offer(db, s, old, price)
    dup = _card(db, "cpu", "Процессор Intel Core i5 12400F", {"pack": "BOX"}, "Intel")
    # The keys of the old normalization: the cards did not meet
    old.match_key, dup.match_key = "cpu:12400f core i5 intel oem", "cpu:12400f box core i5 intel"
    _offer(db, c, dup, 130)
    _offer(db, a, dup, 119)  # store a sold both cards
    other = _card(db, "cpu", "Intel Core i5-12400", brand="Intel")
    _offer(db, c, other, 140)
    for o in db.scalars(select(Offer)):
        db.add(PriceHistory(offer_id=o.id, price=o.price, currency=o.currency))
    db.commit()
    return {"a": a, "b": b, "c": c, "old": old, "dup": dup, "other": other}


def test_scan_reports_and_changes_nothing(db):
    w = _world(db)
    r = duplicates.report(db)
    assert [[p["id"] for p in g] for g in r["sure"]] == [[w["old"].id, w["dup"].id]]  # more offers stays
    assert r["merge_cards"] == 1
    db.expire_all()
    assert db.get(Product, w["dup"].id).merged_into is None


def test_apply_merges_moves_everything_and_loses_no_offer(db):
    w = _world(db)
    offers_before = db.scalar(select(func.count(Offer.id)))
    history_before = db.scalar(select(func.count(PriceHistory.id)))
    a_before = db.scalar(select(func.count(Offer.id)).where(Offer.store_id == w["a"].id))
    result = duplicates.apply(db)
    assert result["merged"] == 1
    db.expire_all()
    old, dup = db.get(Product, w["old"].id), db.get(Product, w["dup"].id)
    assert dup.merged_into == old.id and resolve_merged(db, dup.id) == old.id
    live = db.scalars(select(Offer).where(Offer.product_id == old.id, Offer.price.is_not(None))).all()
    assert sorted(o.store_id for o in live) == sorted([w["a"].id, w["b"].id, w["c"].id])  # store a keeps one offer
    assert db.scalar(select(func.count(Offer.id))) == offers_before  # the ended one stays with its history
    assert db.scalar(select(func.count(Offer.id)).where(Offer.store_id == w["a"].id)) == a_before
    assert db.scalar(select(func.count(PriceHistory.id))) == history_before
    assert "pack" not in (old.specs_json or {})  # OEM and BOX: the packaging stays in the stores' rows
    assert db.get(Product, w["other"].id).merged_into is None  # i5-12400 is another CPU
    assert duplicates.report(db)["sure"] == []  # nothing left, a second run is a no-op


def test_old_address_leads_to_the_kept_card(db):
    w = _world(db)
    duplicates.apply(db)
    app.dependency_overrides[get_db] = lambda: db
    try:
        card = TestClient(app).get(f"/api/catalog/products/{w['dup'].id}").json()
    finally:
        app.dependency_overrides.clear()
    assert card["id"] == w["old"].id and len(card["offers"]) == 3


def test_a_new_price_row_sits_on_the_existing_card(db):
    a, b = _store(db, "a@example.com"), _store(db, "b@example.com")
    cpu = lambda name: {**_row(1, name, 120), "category": "cpu", "brand": "Intel"}  # noqa: E731
    publish_import(db, _import(db, a), a, [cpu("Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700")])
    publish_import(db, _import(db, b), b, [cpu("Процессор Intel Core i5 12400F")])
    assert db.scalar(select(func.count(Product.id))) == 1


def test_doubtful_pair_goes_to_the_admin(db):
    s = _store(db, "a@example.com")
    printer = _card(db, "printer", "Canon PIXMA G3410", brand="Canon")
    lost = _card(db, "other", "Canon PIXMA G3410", brand="Canon")
    _offer(db, s, printer, 200)
    _offer(db, s, lost, 199)
    assert len(duplicates.report(db)["doubtful"]) == 1
    result = duplicates.apply(db)
    assert result["sent_to_admin"] == 1 and result["merged"] == 0
    fix = db.scalar(select(ProductFix))
    assert fix.kind == "duplicate" and fix.product_id == lost.id and fix.after["merge_into"] == printer.id
    duplicates.apply(db)
    assert db.scalar(select(func.count(ProductFix.id))) == 1  # not sent twice
