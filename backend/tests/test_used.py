"""Phase 9, part A: new and used goods apart (one card), the "Used" section."""

from datetime import timedelta

from sqlalchemy import select

from app.db.models import Offer, Product, StoreKind, utcnow
from app.services.catalog import category_summary, product_card, search_products, used_offers
from app.services.importer import publish_import
from tests.test_publish import _import, _row, _store, db  # noqa: F401  (db is a fixture)


def _gpu(n, price, condition, name="MSI RTX 3060 Ventus 12GB"):
    category, brand = ("cpu", "Intel") if "Intel" in name else ("gpu", name.split()[0])
    return {**_row(n, name, price), "category": category, "brand": brand, "condition": condition}


def _three_stores(db):
    a, b, c = (_store(db, f"{x}@example.com") for x in "abc")
    publish_import(db, _import(db, a), a, [_gpu(1, 300, "new")])
    publish_import(db, _import(db, b), b, [_gpu(1, 320, "new_openbox")])
    publish_import(db, _import(db, c), c, [_gpu(1, 180, "used"), _gpu(2, 90, "unknown", "Intel Core i5-10400F")])
    return a, b, c


def test_catalog_counts_only_new_and_says_used_from(db):
    _three_stores(db)
    items = {i["name"]: i for i in search_products(db, 12_000)["items"]}
    gpu = next(i for n, i in items.items() if "3060" in n)
    assert gpu["min_price_usd"] == 300 and gpu["offers"] == 2  # new + open box; the used one is not "from"
    assert gpu["used_from"]["price"] == 180
    # A product with only a "condition not said" offer is not in the new catalog (not passed off as new)
    assert not any("10400" in n for n in items)
    summary = {s["slug"]: s for s in category_summary(db, 12_000)}
    assert summary["gpu"]["stores"] == 2 and "cpu" not in summary


def test_product_card_groups_offers(db):
    _three_stores(db)
    card = product_card(db, db.scalar(select(Product).where(Product.normalized_name.contains("3060"))).id, 12_000)
    assert sorted(o["group"] for o in card["offers"]) == ["new", "new", "used"]


def test_used_feed_filters_and_sorts(db):
    a, _, c = _three_stores(db)
    publish_import(db, _import(db, a), a, [_gpu(1, 250, "refurbished", "Gigabyte RTX 3060 Eagle 12GB")])
    feed = used_offers(db, 12_000)
    assert feed["total"] == 3 and all(i["condition"] in ("used", "refurbished", "unknown") for i in feed["items"])
    assert [i["price"] for i in used_offers(db, 12_000, sort="price_asc")["items"]] == [90, 180, 250]
    assert [i["price"] for i in used_offers(db, 12_000, sort="price_desc")["items"]] == [250, 180, 90]
    assert used_offers(db, 12_000, category="cpu")["total"] == 1
    assert used_offers(db, 12_000, conditions=["refurbished"])["total"] == 1
    assert used_offers(db, 12_000, price_min=100, price_max=200)["total"] == 1
    assert used_offers(db, 12_000, source="telegram")["total"] == 0
    c.city = "samarkand"
    db.commit()
    assert used_offers(db, 12_000, city="samarkand")["total"] == 2


def test_telegram_ad_hidden_when_old_or_removed_and_never_verified(db):
    store = _store(db, "tg@example.com")
    store.kind, store.is_verified, store.phone = StoreKind.telegram, True, "+998901234567"
    db.commit()
    publish_import(db, _import(db, store), store, [_gpu(1, 150, "used")])
    offer = db.scalar(select(Offer))
    offer.posted_at, offer.post_url = utcnow() - timedelta(days=2), "https://t.me/ch/5"
    db.commit()
    item = used_offers(db, 12_000)["items"][0]
    assert item["store"]["kind"] == "telegram" and item["store"]["is_verified"] is False
    assert item["store"]["phone"] is None and item["post_url"] == "https://t.me/ch/5"
    offer.posted_at = utcnow() - timedelta(days=31)
    db.commit()
    assert used_offers(db, 12_000)["total"] == 0 and product_card(db, offer.product_id, 12_000)["offers"] == []


def test_used_api(db, monkeypatch):
    from app.api import catalog as api

    _three_stores(db)
    monkeypatch.setattr(api, "_rate", lambda _db: (12_000.0, "2026-11-09"))
    res = api.list_used(condition="used,unknown", sort="price_asc", price_min=None, price_max=1_500_000, category=None,
                        city=None, source=None, page=1, db=db)
    assert [i["price"] for i in res["items"]] == [90]  # 180 USD = 2 160 000 sum: above the price filter


def test_below_market_compares_only_with_own_group(db):
    """Fix after phase 9: a fair used price is not 'below market' of new ones; too little data - no flag."""
    from app.db.models import Currency
    from app.services.importer import flag_rows

    a, b, c, d, e = (_store(db, f"m{x}@example.com") for x in "abcde")
    publish_import(db, _import(db, a), a, [_gpu(1, 300, "new")])
    publish_import(db, _import(db, b), b, [_gpu(1, 320, "new")])
    publish_import(db, _import(db, c), c, [_gpu(1, 180, "used")])
    publish_import(db, _import(db, d), d, [_gpu(1, 170, "unknown")])
    rows = [_gpu(1, 140, "used"), _gpu(2, 140, "new")]
    flag_rows(db, rows, e.id, Currency.USD)
    assert not [f for f in rows[0]["flags"] if f["type"] == "price_below_market"]  # 140 of used 175: fair
    assert any(f["type"] == "price_below_market" for f in rows[1]["flags"])  # 140 of new 310: suspicious
    # Only one used offer of other stores (d is the seller itself): too little data, no flag
    rows = [_gpu(1, 40, "used")]
    flag_rows(db, rows, d.id, Currency.USD)
    assert not [f for f in rows[0]["flags"] if f["type"] == "price_below_market"]
