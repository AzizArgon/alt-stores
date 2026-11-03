"""Phase B4: ready PCs of stores — precision levels, form and text, checks, the in-store hint, apart from the market."""

import asyncio
from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import (
    Build, BuildPriceHistory, Category, Currency, ImportStatus, Offer, PriceImport, Product, Store, User, UserRole,
)
from app.db.seed import seed_categories
from app.services import builds, importer
from app.services.antifraud import market_prices
from app.services.catalog import make_match_key, search_products
from app.services.importer import publish_import
from app.services.market import build_market
from app.services.spec_normalizer import normalize_specs


@pytest.fixture(autouse=True)
def no_rate(monkeypatch):
    monkeypatch.setattr(builds, "get_usd_rate", lambda db: None)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    event.listen(engine, "connect", lambda c, _: c.create_function("py_lower", 1, lambda s: s and s.lower()))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        seed_categories(session)
        yield session


def _store(db, email, city="tashkent"):
    store = Store(owner=User(email=email, password_hash="x", role=UserRole.seller), name=email, city=city)
    db.add(store)
    db.commit()
    return store


def _card(db, slug, name, specs=None, brand=None):
    # The same key as the importer makes, so a parsed text finds the card
    key = make_match_key(slug, name, brand, normalize_specs(slug, name, specs or {}, brand))
    product = Product(category=db.scalar(select(Category).where(Category.slug == slug)), brand=brand, model=name,
                      normalized_name=name, match_key=key, specs_json=specs or {})
    db.add(product)
    db.commit()
    return product


def _offer(db, store, product, price, in_stock=True, currency=Currency.USD):
    db.add(Offer(store=store, product=product, raw_name=product.normalized_name, price=price, currency=currency,
                 is_in_stock=in_stock))
    db.commit()


@pytest.fixture
def parts(db):
    """Cards with known specs; two other stores sell some of them."""
    a, b = _store(db, "a@example.com"), _store(db, "b@example.com")
    cards = {
        "cpu": _card(db, "cpu", "AMD Ryzen 5 5600 OEM", {"brand": "AMD", "series": "Ryzen 5", "socket": "AM4"}, "AMD"),
        "cpu_intel": _card(db, "cpu", "Intel Core i5-12400F OEM",
                           {"brand": "Intel", "series": "Core i5", "socket": "LGA1700"}, "Intel"),
        "board": _card(db, "motherboard", "MSI B550M PRO-VDH",
                       {"socket": "AM4", "memory_type": "DDR4", "form_factor": "mATX"}, "MSI"),
        "ram": _card(db, "ram", "Kingston Fury 16GB DDR4 3200", {"type": "DDR4", "capacity": 16}, "Kingston"),
        "ram5": _card(db, "ram", "Kingston Fury 16GB DDR5 5600", {"type": "DDR5", "capacity": 16}, "Kingston"),
        "gpu": _card(db, "gpu", "MSI RTX 3050 VENTUS 8GB", {"chip": "RTX 3050"}, "MSI"),
        "case": _card(db, "case", "Zalman T8", {"board": "ITX"}, "Zalman"),
        "psu": _card(db, "psu", "Chieftec 650W", {"power": 650, "brand": "Chieftec"}, "Chieftec"),
    }
    for key, price in (("cpu", 100), ("board", 80), ("ram", 40), ("gpu", 200)):
        _offer(db, a, cards[key], price)
        _offer(db, b, cards[key], price)
    return cards


def _data(components, **kw):
    return {"name": "Игровой ПК", "price": 500, "currency": "USD", "condition": "new", "purpose": "gaming",
            "components": components, **kw}


def _c(slot, product=None, raw="", qty=1, specs=None, category=None):
    return {"slot": slot, "product_id": product.id if product else None, "raw_text": raw, "quantity": qty,
            "specs": specs or {}, "category": category}


def _gpu_spec(chip="RTX 3060"):
    return _c("gpu", specs={"chip": chip, "memory": 12})


def test_form_build_with_all_three_levels(db, parts):
    shop = _store(db, "shop@example.com")
    build = builds.save_build(db, shop, _data([
        _c("cpu", parts["cpu"]), _gpu_spec(), _c("ram", specs={"type": "DDR4", "capacity": "16GB", "junk": 1}, qty=2),
        _c("psu", raw="650W"), _c("other", raw="Wi-Fi адаптер"),
    ]))
    detail = builds.build_detail(db, build, None)
    assert [c["level"] for c in detail["components"]] == ["exact", "specs", "specs", "none", "none"]
    assert detail["components"][2]["specs"] == {"type": "DDR4", "capacity": 16}  # by the dictionary, junk dropped
    assert detail["precision"] == {"exact": 1, "total": 5}
    assert detail["ram_gb"] == 32 and detail["cpu_brand"] == "amd" and detail["gpu_chip"] == "RTX 3060"
    builds.save_build(db, shop, {**_data([_c("cpu", parts["cpu"]), _gpu_spec()]), "price": 550}, build)
    builds.save_build(db, shop, {**_data([_c("cpu", parts["cpu"]), _gpu_spec()]), "price": 550, "description": "x"}, build)
    assert [h.price for h in db.scalars(select(BuildPriceHistory).order_by(BuildPriceHistory.id))] == [500, 550]


def test_required_minimum_cpu_model_and_gpu_chip_or_integrated(db, parts):
    shop = _store(db, "s@example.com")
    with pytest.raises(builds.BuildError) as e:
        builds.save_build(db, shop, _data([_c("cpu", specs={"socket": "AM4"}), _c("gpu", raw="игровая видеокарта")]))
    assert e.value.params["missing"] == ["cpu", "gpu"]
    with pytest.raises(builds.BuildError) as e:
        builds.save_build(db, shop, _data([_c("gpu", parts["gpu"])]))
    assert e.value.params["missing"] == ["cpu"]
    assert db.scalar(select(Build)) is None
    office = builds.save_build(db, shop, _data([_c("cpu", specs={"model": "i5-12400F"}), _c("gpu", specs={"integrated": True})]))
    assert [builds.component_out(c)["level"] for c in office.components] == ["specs", "integrated"]
    assert builds.precision(office) == {"exact": 1, "total": 2}


EXAMPLE = "Игровой ПК\nRyzen 5 5600 / B550M / 16GB DDR4 3200 / RTX 3060 12GB / SSD 1TB / 650W\nЦена: 650$"
# What the AI answered for the example (recorded)
RECORDED = {
    "Ryzen 5 5600": {"category": "cpu", "brand": "AMD", "model": "Ryzen 5 5600", "name": "AMD Ryzen 5 5600 OEM"},
    "B550M": {"category": "motherboard", "brand": None, "model": "B550M", "name": "B550M",
              "specs": {"socket": "AM4", "memory_type": "DDR4"}},  # guesses: not in the text
    "16GB DDR4 3200": {"category": "ram", "brand": None, "model": None, "name": "DDR4 16GB 3200MHz"},
    "RTX 3060 12GB": {"category": "gpu", "brand": None, "model": "RTX 3060", "name": "RTX 3060 12GB"},
    "SSD 1TB": {"category": "ssd", "brand": None, "model": None, "name": "SSD 1TB"},
    "650W": {"category": "psu", "brand": None, "model": None, "name": "650W"},
}


@pytest.fixture
def fake_ai(monkeypatch):
    asked = []

    async def parse_rows(rows, stats):
        asked.extend(r.name for r in rows)
        return [{"row": r.row, "condition": "new", "specs": {}, "risks": [], **RECORDED[r.name]}
                for r in rows if r.name in RECORDED]

    monkeypatch.setattr(importer, "parse_rows", parse_rows)
    monkeypatch.setattr(importer, "parse_by_rules", lambda name: None)
    return asked


def test_text_build_exact_specs_and_none(db, parts, fake_ai):
    draft = asyncio.run(builds.parse_build_text(db, EXAMPLE))
    assert (draft["name"], draft["price"], draft["currency"], draft["purpose"]) == ("Игровой ПК", 650, "USD", "gaming")
    got = {c["slot"]: c for c in draft["components"]}
    assert [c["slot"] for c in draft["components"]] == ["cpu", "motherboard", "ram", "gpu", "storage", "psu"]
    assert got["cpu"]["level"] == "exact" and got["cpu"]["product"]["id"] == parts["cpu"].id
    # "16GB DDR4 3200" is only specs: never tied to a random Kingston card of the catalog
    assert got["ram"]["level"] == "specs" and got["ram"]["product"] is None
    assert got["ram"]["specs"] == {"type": "DDR4", "capacity": 16}  # a bare "3200" is not read as MHz
    assert got["gpu"]["specs"]["chip"] == "RTX 3060" and got["gpu"]["specs"]["memory"] == 12
    assert got["psu"]["specs"] == {"power": 650} and got["storage"]["specs"]["capacity"] == 1000
    # AI guesses (socket and memory of "B550M") do not become specs
    assert "socket" not in got["motherboard"]["specs"] and got["motherboard"]["product"] is None
    assert draft["missing"] == [] and len(fake_ai) == 6  # the price never goes to the AI
    components = [{"slot": c["slot"], "product_id": c["product"]["id"] if c["product"] else None,
                   "raw_text": c["raw_text"], "quantity": c["quantity"], "category": c["category"], "specs": c["specs"]}
                  for c in draft["components"]]
    build = builds.save_build(db, _store(db, "s@example.com"), {**_data(components), "text": EXAMPLE})
    assert build.text == EXAMPLE and builds.precision(build) == {"exact": 1, "total": 6}


def test_text_build_slot_keys_quantity_and_integrated(db, parts, fake_ai):
    draft = asyncio.run(builds.parse_build_text(
        db, "Офисный ПК\nПроцессор: Ryzen 5 5600\nОЗУ: 2 x 16GB DDR4 3200\nВидеокарта: встроенная\n4 500 000 сум"))
    assert draft["currency"] == "UZS" and draft["price"] == 4_500_000 and draft["purpose"] == "office"
    assert [(c["slot"], c["quantity"], c["level"]) for c in draft["components"]] == [
        ("cpu", 1, "exact"), ("ram", 2, "specs"), ("gpu", 1, "integrated")]


def test_text_build_without_gpu_says_what_is_missing(db, parts, fake_ai):
    draft = asyncio.run(builds.parse_build_text(db, "ПК\nRyzen 5 5600 / 16GB DDR4 3200\n500$"))
    assert draft["missing"] == ["gpu"]


def test_builds_do_not_touch_market_prices_indexes_or_catalog(db, parts):
    before = market_prices(db, {parts["cpu"].match_key}, None, None)
    total = search_products(db, None, "", None, None, None, True, 1, {})["total"]
    offers = build_market(db, date.today()).offers
    shop = _store(db, "s@example.com")
    builds.save_build(db, shop, _data([_c("cpu", parts["cpu"]), _c("gpu", parts["gpu"])], price=10))
    assert market_prices(db, {parts["cpu"].match_key}, None, None) == before
    assert search_products(db, None, "", None, None, None, True, 1, {})["total"] == total
    assert build_market(db, date.today()).offers == offers
    assert db.scalar(select(Offer).where(Offer.store_id == shop.id)) is None


def test_full_price_list_does_not_touch_builds(db, parts):
    shop = _store(db, "s@example.com")
    build = builds.save_build(db, shop, _data([_c("cpu", parts["cpu"]), _gpu_spec()]))
    imp = PriceImport(store_id=shop.id, filename="p.xlsx", mode="full", currency=Currency.USD, status=ImportStatus.ready)
    db.add(imp)
    db.commit()
    row = {"row": 1, "raw_name": "Kingston DDR4 8GB", "category": "ram", "name": "Kingston DDR4 8GB", "price": 20,
           "condition": "new", "specs": {}, "is_in_stock": True}
    publish_import(db, imp, shop, [row])
    publish_import(db, imp, shop, [{**row, "raw_name": "Other", "name": "Other RAM DDR4 4GB"}], "full")
    db.refresh(build)
    assert build.is_in_stock and len(build.components) == 2 and build.price == 500


def test_flags_of_exact_parts_move_to_build(db, parts):
    xeon = _card(db, "cpu", "Intel Xeon E5-2680 v4", {"series": "Xeon"}, "Intel")
    miner = _card(db, "gpu", "Sapphire RX 580 8GB Mining", {"chip": "RX 580"}, "Sapphire")
    build = builds.save_build(db, _store(db, "s@example.com"), _data([_c("cpu", xeon), _c("gpu", miner)]))
    flags = builds.build_flags(build)
    assert {"server_hardware", "mining"} <= {f["type"] for f in flags}
    assert {f["params"].get("component") for f in flags if f["type"] == "mining"} == {"Sapphire RX 580 8GB Mining"}
    # "Only specs" parts are not checked by the offer rules: there is no card to speak about
    vague = builds.save_build(db, _store(db, "t@example.com"), _data([
        _c("cpu", parts["cpu"]), _c("gpu", raw="RX 580 майнинг", specs={"chip": "RX 580"})]))
    assert "mining" not in {f["type"] for f in builds.build_flags(vague)}


def test_name_says_one_gpu_parts_another(db, parts):
    build = builds.save_build(db, _store(db, "s@example.com"),
                              _data([_c("cpu", parts["cpu"]), _c("gpu", parts["gpu"])], name="Игровой ПК RTX 4060"))
    flag = next(f for f in builds.build_flags(build) if f["type"] == "build_name_mismatch")
    assert flag["level"] == "warning" and flag["params"] == {"said": "RTX 4060", "actual": "RTX 3050"}
    honest = builds.save_build(db, _store(db, "t@example.com"),
                               _data([_c("cpu", parts["cpu"]), _gpu_spec("RTX 3050")], name="ПК на RTX 3050"))
    assert not [f for f in builds.build_flags(honest) if f["type"] == "build_name_mismatch"]


def test_psu_without_maker_is_info(db, parts):
    shop = _store(db, "s@example.com")
    base = [_c("cpu", parts["cpu"]), _gpu_spec()]
    for psu in (_c("psu", specs={"power": 650}), _c("psu", raw="БП 650W")):
        flags = builds.build_flags(builds.save_build(db, shop, _data(base + [psu])))
        assert [(f["type"], f["level"]) for f in flags] == [("build_psu_brand", "info")]
    for psu in (_c("psu", specs={"power": 650, "brand": "Chieftec"}), _c("psu", parts["psu"])):
        assert builds.build_flags(builds.save_build(db, shop, _data(base + [psu]))) == []


def test_compatibility_by_exact_and_specs_parts(db, parts):
    shop = _store(db, "s@example.com")
    bad = builds.save_build(db, shop, _data([
        _c("cpu", parts["cpu_intel"]), _c("motherboard", parts["board"]), _c("ram", parts["ram5"]),
        _c("case", parts["case"]), _gpu_spec(),
    ]))
    assert {i["key"] for i in builds.compatibility(bad)} == {"socket", "memory", "form_factor"}
    by_specs = builds.save_build(db, shop, _data([
        _c("cpu", specs={"model": "Ryzen 5 5600", "socket": "AM4"}),
        _c("motherboard", specs={"socket": "LGA1700", "memory_type": "DDR5"}),
        _c("ram", specs={"type": "DDR4", "capacity": 16}), _gpu_spec(),
    ]))
    assert {i["key"] for i in builds.compatibility(by_specs)} == {"socket", "memory"}
    good = builds.save_build(db, shop, _data([_c("cpu", parts["cpu"]), _c("motherboard", parts["board"]),
                                              _c("ram", parts["ram"]), _gpu_spec()]))
    assert builds.compatibility(good) == []


def test_compatibility_needs_known_specs(db, parts):
    blank_board = _card(db, "motherboard", "Noname board")
    build = builds.save_build(db, _store(db, "s@example.com"), _data([
        _c("cpu", parts["cpu_intel"]), _c("motherboard", blank_board), _c("ram", raw="DDR5 16GB"), _gpu_spec(),
    ]))
    assert builds.compatibility(build) == []  # nothing known about the board: nothing is checked or invented


def test_store_reference_only_for_exact_parts_of_this_store(db, parts):
    shop = _store(db, "s@example.com")
    for key, price in (("cpu", 120), ("board", 90), ("ram", 45), ("gpu", 210)):
        _offer(db, shop, parts[key], price)
    exact = [_c("cpu", parts["cpu"]), _c("motherboard", parts["board"]), _c("ram", parts["ram"], qty=2),
             _c("gpu", parts["gpu"])]
    build = builds.save_build(db, shop, _data(exact))
    # This store's own prices with the quantity; the other stores sell the same parts cheaper — never used
    assert builds.store_reference(db, build, None) == {"price": 120 + 90 + 2 * 45 + 210, "currency": "USD"}
    assert builds.store_reference(db, build, 12_000) == {"price": 510 * 12_000, "currency": "UZS", "usd": 510}
    # One part not sold here (another store has it): no hint
    other = builds.save_build(db, shop, _data(exact + [_c("psu", parts["psu"])]))
    _offer(db, _store(db, "c@example.com"), parts["psu"], 50)
    assert builds.store_reference(db, other, None) is None
    # One part only by specs: no hint
    vague = builds.save_build(db, shop, _data(exact[:3] + [_gpu_spec()]))
    assert builds.store_reference(db, vague, None) is None
    # Out of stock here: no hint
    db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.product_id == parts["gpu"].id)).is_in_stock = False
    db.commit()
    assert builds.store_reference(db, build, None) is None


def test_storefront_list_filters_city_and_exact_only(db, parts):
    a = _store(db, "a2@example.com", "tashkent")
    b = _store(db, "b2@example.com", "samarkand")
    builds.save_build(db, a, _data([_c("cpu", parts["cpu"]), _c("gpu", parts["gpu"]), _c("ram", parts["ram"])]))
    builds.save_build(db, b, _data([_c("cpu", parts["cpu_intel"]), _c("gpu", specs={"integrated": True}),
                                    _c("ram", specs={"capacity": 8})], purpose="office", name="Офисный ПК"))
    off = builds.save_build(db, b, _data([_c("cpu", parts["cpu"]), _gpu_spec()], name="Снят"))
    builds.set_on_sale(db, off, False)
    everything = builds.list_builds(db, None, {})
    assert everything["total"] == 2 and everything["exact_total"] == 1
    assert builds.list_builds(db, None, {}, city="samarkand")["items"][0]["name"] == "Офисный ПК"
    assert [s["name"] for s in builds.list_builds(db, None, {"cpu": ["amd"]})["items"]] == ["Игровой ПК"]
    assert builds.list_builds(db, None, {"gpu": ["RTX 3050"], "ram": [16]})["total"] == 1
    assert builds.list_builds(db, None, {"gpu": ["integrated"]})["items"][0]["name"] == "Офисный ПК"
    assert [s["name"] for s in builds.list_builds(db, None, {"exact_only": True})["items"]] == ["Игровой ПК"]
    assert "market" not in everything["items"][0]  # builds of different stores are not compared


def test_seller_api_add_edit_take_off_sale_delete(db, parts):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.db.database import get_db
    from main import app

    shop = _store(db, "s@example.com")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: shop.owner
    try:
        client = TestClient(app)
        no_cpu = client.post("/api/seller/builds", json=_data([_gpu_spec()]))
        assert no_cpu.status_code == 422 and no_cpu.json()["detail"] == {"code": "build_required", "missing": ["cpu"]}
        body = _data([_c("cpu", parts["cpu"]), _gpu_spec(), _c("other", raw="Wi-Fi")])
        res = client.post("/api/seller/builds", json=body)
        assert res.status_code == 201
        build_id = res.json()["id"]
        found = client.get("/api/seller/builds/search", params={"q": "b550m", "slot": "motherboard"}).json()
        assert [p["id"] for p in found] == [parts["board"].id]
        assert client.put(f"/api/seller/builds/{build_id}", json={**body, "price": 480}).json()["price"] == 480
        assert client.get("/api/seller/builds").json()["items"][0]["precision"] == {"exact": 1, "total": 3}
        assert client.get("/api/builds").json()["total"] == 1
        assert client.post(f"/api/seller/builds/{build_id}/sale", json={"on_sale": False}).status_code == 200
        assert client.get("/api/builds").json()["total"] == 0 and client.get(f"/api/builds/{build_id}").status_code == 404
        assert client.get("/api/seller/overview").json()["builds"] == {"on_sale": 0, "off_sale": 1}
        assert client.delete(f"/api/seller/builds/{build_id}").status_code == 204
        assert db.scalar(select(Build)) is None
    finally:
        app.dependency_overrides.clear()
