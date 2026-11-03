"""Demo stores for the catalog: 3 invented shops built from the assortment of a real store price list.

Each store gets part of the assortment (popular items overlap, so cards show 2-4 offers),
prices +-5-15%, some items out of stock, its own price-list freshness; one store sells in UZS,
one is verified, one has a few items far below the market (Anti-Fraud "price below market").
Goes through publish_import, so flags and price history work as for a real upload.
Demo price history for the last 3 months (price_history.is_demo): small moves, RAM and SSD grew noticeably.
Demo ready PCs (phase B4): 8 builds of the demo stores in three cities, every precision level, each check shown once.
Re-running updates the same stores and offers and recreates the demo builds, no duplicates. Usage (from backend/):
  .venv/Scripts/python.exe scripts/seed_demo.py
  .venv/Scripts/python.exe scripts/seed_demo.py --builds-only   # only store details and demo builds (server update)
"""

import random
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.orm import Session, selectinload  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import (  # noqa: E402
    Build, Category, Currency, ImportStatus, Offer, PriceHistory, PriceImport, Product, Store, User, UserRole, utcnow,
)
from app.services.exchange import RateBook, ensure_rates  # noqa: E402

DEMO_PASSWORD = "demo12345"
DEMO_FILENAME = "demo_seed.xlsx"
# Showcase items every demo store sells (matched by name, ids change on a clean DB)
SHOWCASE = ["Core i5-12400F", "Ryzen 5 7500F", "RTX 5060 TWIN EDGE OC", "990 PRO 1TB"]
POPULAR = {"cpu", "gpu", "ram", "ssd", "motherboard", "psu", "monitor"}
FALLBACK_USD_RATE = 12_000.0
# Demo history: days ago of the past price points, and how much a category grew over those 3 months
HISTORY_DAYS_AGO = [92, 78, 64, 50, 36, 22, 10]
TREND = {"ram": 0.24, "ssd": 0.09, "gpu": -0.04}

STORES = [
    {"email": "demo1@example.com", "name": "Silicon Plus", "city": "tashkent", "district": "Юнусабад",
     "address": "ул. Амира Темура, 107", "phone": "+998900000101", "telegram": "@silicon_plus_demo", "is_verified": True,
     "currency": Currency.USD, "days_old": 0, "below_market": []},
    {"email": "demo2@example.com", "name": "Byte Market", "city": "samarkand", "district": "Сиаб",
     "address": "ул. Ташкентская, 12", "phone": "+998900000202", "telegram": "@byte_market_demo", "is_verified": False,
     "currency": Currency.UZS, "days_old": 4, "below_market": []},
    # Published last: its cheap items are compared with all the other stores
    {"email": "demo3@example.com", "name": "PC Galaxy", "city": "bukhara", "district": "Центр",
     "address": "ул. Бахауддина Накшбанди, 41", "phone": "+998900000303", "telegram": None, "is_verified": False,
     "currency": Currency.USD, "days_old": 25, "below_market": ["Ryzen 5 7500F", "RTX 5060 TWIN EDGE OC", "990 PRO 1TB"]},
]
LIVE_EMAIL = "live@example.com"  # empty demo store for the live upload (scripts/demo_reset.py)
LIVE_CITY, LIVE_DISTRICT = "fergana", "Центр"
DEMO_EMAILS = [s["email"] for s in STORES] + [LIVE_EMAIL]


def _store(db: Session, spec: dict) -> Store:
    user = db.scalar(select(User).where(User.email == spec["email"]))
    if user is None:
        user = User(email=spec["email"], password_hash=hash_password(DEMO_PASSWORD), role=UserRole.seller)
        db.add(user)
    store = db.scalar(select(Store).where(Store.user_id == user.id)) if user.id else None
    if store is None:
        store = Store(owner=user)
        db.add(store)
    for field in ("name", "city", "district", "address", "phone", "telegram", "is_verified"):
        setattr(store, field, spec[field])
    store.is_demo = True
    db.commit()
    return store


def _demo_import(db: Session, store: Store, currency: Currency) -> PriceImport:
    """One import record per demo store, reused on every run."""
    imp = db.scalar(select(PriceImport).where(PriceImport.store_id == store.id, PriceImport.filename == DEMO_FILENAME))
    if imp is None:
        imp = PriceImport(store_id=store.id, filename=DEMO_FILENAME, currency=currency)
        db.add(imp)
    imp.currency = currency
    imp.status = ImportStatus.ready
    db.commit()
    return imp


def real_store(db: Session) -> Store | None:
    """The real store the demo is built from: not demo, not archive, with the most offers (its email may change)."""
    return db.scalar(
        select(Store).join(Store.owner).join(Offer, Offer.store_id == Store.id)
        .where(Store.is_demo.is_(False), Store.is_archive.is_(False), User.email.not_in(DEMO_EMAILS))
        .group_by(Store.id).order_by(func.count(Offer.id).desc())
    )


def _source_offers(db: Session) -> list[Offer]:
    source = real_store(db)
    if source is None:
        raise SystemExit("No real store: publish the real price list first")
    return db.scalars(
        select(Offer).where(Offer.store_id == source.id, Offer.is_in_stock.is_(True), Offer.price.is_not(None),
                            Offer.currency == Currency.USD)
        .options(selectinload(Offer.product).selectinload(Product.category)).order_by(Offer.id)
    ).all()


def _rows(spec: dict, offers: list[Offer], usd_rate: float) -> list[dict]:
    rng = random.Random(spec["email"])  # same assortment and prices on every run
    rows = []
    for o in offers:
        p = o.product
        category = p.category.slug if p.category else "other"
        showcase = any(s in p.normalized_name for s in SHOWCASE)
        if not showcase and rng.random() >= (0.55 if category in POPULAR else 0.2):
            continue
        sign = rng.choice((-1, 1))
        factor = 1 + sign * rng.uniform(0.05, 0.15)
        if any(s in p.normalized_name for s in spec["below_market"]):
            factor = 0.5
        price_usd = o.price * factor
        price = round(price_usd * usd_rate, -3) if spec["currency"] == Currency.UZS else round(price_usd)
        rows.append({
            "row": len(rows) + 1, "raw_name": p.normalized_name, "category": category, "brand": p.brand,
            "model": p.model, "name": p.normalized_name, "price": price, "condition": o.condition.value,
            "specs": p.specs_json or {}, "is_in_stock": showcase or rng.random() < 0.88,
        })
    return rows


def seed_history(db: Session, store_ids: list[int], fetch_rates: bool = False) -> int:
    """Invented past prices of the demo stores' offers, leading up to today's price. Old demo history is replaced.

    UZS prices of the past are converted by the CBU rate of that day, as a real store would have written them.
    """
    db.execute(delete(PriceHistory).where(PriceHistory.is_demo.is_(True)))
    today = utcnow().date()
    days = [today - timedelta(days=d) for d in HISTORY_DAYS_AGO]
    if fetch_rates:
        ensure_rates(db, set(days))
    rates = RateBook(db)
    added = 0
    for store_id in store_ids:
        offers = db.scalars(
            select(Offer).where(Offer.store_id == store_id, Offer.price.is_not(None))
            .options(selectinload(Offer.product).selectinload(Product.category)).order_by(Offer.raw_name)
        ).all()
        for o in offers:
            rng = random.Random(f"{store_id}:{o.raw_name}")
            category = o.product.category.slug if o.product.category else "other"
            usd_now = o.price / (rates.on(today) or FALLBACK_USD_RATE) if o.currency == Currency.UZS else o.price
            growth = TREND.get(category, 0.0)
            for ago, day in zip(HISTORY_DAYS_AGO, days):
                # Linear trend towards today's price plus a small store's own move (+-2%)
                usd = usd_now / (1 + growth * ago / HISTORY_DAYS_AGO[0]) * (1 + rng.uniform(-0.02, 0.02))
                if o.currency == Currency.UZS:
                    price = round(usd * (rates.on(day) or FALLBACK_USD_RATE), -3)
                else:
                    price = round(usd)
                at = datetime.combine(day, time(12), tzinfo=timezone.utc)
                db.add(PriceHistory(offer_id=o.id, price=price, currency=o.currency, recorded_at=at, is_demo=True))
                added += 1
    db.commit()
    return added


def _live_store(db: Session) -> None:
    for store in db.scalars(select(Store).join(Store.owner).where(User.email == LIVE_EMAIL)):
        store.is_demo = True
        store.city, store.district = LIVE_CITY, LIVE_DISTRICT
    db.commit()


def refresh_stores_and_builds(db: Session, usd_rate: float | None) -> list[dict]:
    """--builds-only: demo stores get their details (city, address...) and the demo builds are recreated.

    Offers, price history and passwords are not touched (the server has its own demo passwords and live data).
    """
    for spec in STORES:
        _store(db, spec)
    _live_store(db)
    return [{"demo_builds": seed_builds(db, usd_rate or FALLBACK_USD_RATE)}]


def seed_demo(db: Session, usd_rate: float | None, fetch_rates: bool = False) -> list[dict]:
    from app.services.importer import publish_import

    usd_rate = usd_rate or FALLBACK_USD_RATE
    offers = _source_offers(db)
    report = []
    for spec in STORES:
        store = _store(db, spec)
        rows = _rows(spec, offers, usd_rate)
        stats = publish_import(db, _demo_import(db, store, spec["currency"]), store, rows)
        # Price list freshness differs between stores ("recommended" order uses it)
        updated = utcnow() - timedelta(days=spec["days_old"])
        for offer in db.scalars(select(Offer).where(Offer.store_id == store.id)):
            offer.updated_at = updated
        db.commit()
        report.append({"store": spec["name"], "rows": len(rows), **stats})
    _live_store(db)
    store_ids = [db.scalar(select(Store.id).join(Store.owner).where(User.email == s["email"])) for s in STORES]
    report.append({"demo_history_points": seed_history(db, store_ids, fetch_rates)})
    report.append({"demo_builds": seed_builds(db, usd_rate)})
    return report


# --- Demo ready PCs (phase B4) -------------------------------------------------------------------------------------
# A part: (slot, category, name part, specs, sold). A card is found by the name part and the specs in the current
# catalog (ids change on a clean DB); without a name and sold=None the specs stay "only specs" (no card).
# sold: the card must (True) or must not (False) be on sale in the same store — for the in-store hint.
# Category None: "not specified" with the name as the seller's text; {"integrated": True}: integrated graphics.
DEMO_BUILDS = [
    # Fully exact, the store sells every part: the page shows "these parts separately in this store"
    {"store": "demo1@example.com", "name": "Игровой ПК Ryzen 5 7500F + RTX 5060", "purpose": "gaming", "markup": 1.06,
     "description": "Сборка, проверка и установка Windows — бесплатно. Гарантия 1 год на всю сборку.",
     "parts": [("cpu", "cpu", "Ryzen 5 7500F", {}, True),
               ("motherboard", "motherboard", None, {"socket": "AM5", "memory_type": "DDR5"}, True),
               ("ram", "ram", None, {"type": "DDR5", "form_factor": "DIMM", "capacity": 16}, True),
               ("gpu", "gpu", "RTX 5060 TWIN EDGE", {}, True), ("storage", "ssd", "990 PRO 1TB", {}, True),
               ("psu", "psu", None, {"power": 650}, True)]},
    # Fully exact, but the store does not sell its PSU separately: no hint
    {"store": "demo2@example.com", "name": "Игровой ПК Core i5-12400F + RTX 5060", "purpose": "gaming", "usd": 860,
     "description": "Тихая сборка для игр в Full HD.",
     "parts": [("cpu", "cpu", "Core i5-12400F", {}, True),
               ("motherboard", "motherboard", None, {"socket": "LGA1700", "memory_type": "DDR4"}, True),
               ("ram", "ram", None, {"type": "DDR4", "form_factor": "DIMM"}, True),
               ("gpu", "gpu", "RTX 5060 TWIN EDGE", {}, True), ("storage", "ssd", "990 PRO 1TB", {}, True),
               ("psu", "psu", None, {"power": 750}, False)]},
    # Office PC with integrated graphics, the PSU only by its power (no maker: info)
    {"store": "demo3@example.com", "name": "Офисный ПК Core i3-13100", "purpose": "office", "usd": 340,
     "description": "Для офиса, учёбы и интернета. Без дискретной видеокарты.",
     "parts": [("cpu", "cpu", "Core i3-13100,", {}, None), ("gpu", "gpu", None, {"integrated": True}, None),
               ("ram", "ram", None, {"type": "DDR4", "capacity": 8}, None),
               ("storage", "ssd", None, {"capacity": 256, "form_factor": "M.2"}, None),
               ("psu", "psu", None, {"power": 400}, None)]},
    # "Abstract": only specs, as in most posts; a case "not specified"
    {"store": "demo1@example.com", "name": "Игровой ПК RTX 3060 / 16GB / SSD 512GB", "purpose": "gaming", "usd": 620,
     "parts": [("cpu", "cpu", None, {"model": "Ryzen 5 5600", "socket": "AM4"}, None),
               ("ram", "ram", None, {"type": "DDR4", "capacity": 16}, None),
               ("gpu", "gpu", None, {"chip": "RTX 3060", "memory": 12}, None),
               ("storage", "ssd", None, {"capacity": 512}, None), ("psu", "psu", None, {"power": 650}, None),
               ("case", None, "Корпус с подсветкой", {}, None)]},
    # A catch: the name says RTX 4060, the parts say RTX 3050
    {"store": "demo2@example.com", "name": "Игровой ПК RTX 4060 / i5-12400F", "purpose": "gaming", "usd": 690,
     "description": "Мощная видеокарта RTX 4060 — потянет все новинки!",
     "parts": [("cpu", "cpu", "Core i5-12400F", {}, None), ("gpu", "gpu", "RTX 3050 WINDFORCE", {}, None),
               ("ram", "ram", None, {"type": "DDR4", "capacity": 16}, None),
               ("storage", "ssd", None, {"capacity": 512}, None), ("psu", "psu", "Deepcool PF550", {}, None)]},
    # Top PC with an LGA1851 CPU on an LGA1700 board: "check with the seller"
    {"store": "demo3@example.com", "name": "Топовый ПК Core Ultra 7 265K + RX 9070 XT", "purpose": "work", "usd": 2650,
     "description": "Для монтажа, 3D и игр в 4K.",
     "parts": [("cpu", "cpu", "Ultra 7-265K,", {}, None), ("motherboard", "motherboard", "Z790", {"socket": "LGA1700"}, None),
               ("ram", "ram", None, {"type": "DDR5", "capacity": 32}, None), ("gpu", "gpu", "RX 9070 XT", {}, None),
               ("storage", "ssd", None, {"capacity": 2000, "form_factor": "M.2"}, None),
               ("psu", "psu", "Deepcool PN1200M", {}, None)]},
    {"store": "demo1@example.com", "name": "Б/у игровой ПК Core i7-12700K + RTX 3060", "purpose": "gaming", "usd": 780,
     "condition": "used", "description": "Б/у, 1 год работы, без майнинга. Чек и коробки есть.",
     "parts": [("cpu", "cpu", "Core i7-12700K,", {}, None), ("gpu", "gpu", "RTX 3060", {}, None),
               ("ram", "ram", None, {"type": "DDR4", "capacity": 32}, None),
               ("storage", "ssd", None, {"capacity": 1000}, None),
               ("psu", "psu", None, {"power": 750, "brand": "Deepcool"}, None)]},
    {"store": "demo2@example.com", "name": "Офисный ПК Ryzen 5 5600 + GT 730", "purpose": "office", "usd": 410,
     "parts": [("cpu", "cpu", "Ryzen 5 5600,", {}, None), ("gpu", "gpu", "GT 730", {}, None),
               ("ram", "ram", None, {"type": "DDR4", "capacity": 16}, None),
               ("storage", "ssd", None, {"capacity": 512}, None)]},
]


def _sold_ids(db: Session, store: Store) -> set[int]:
    return set(db.scalars(select(Offer.product_id).where(
        Offer.store_id == store.id, Offer.is_in_stock.is_(True), Offer.price.is_not(None), Offer.removed_at.is_(None))))


def _fits(values: dict, specs: dict) -> bool:
    # A PSU "power" is from the given one to +40% (not a 1200 W unit for a 650 W build); other values must be equal
    return all(v <= (values.get(k) or 0) <= v * 1.4 if k == "power" else values.get(k) == v for k, v in specs.items())


def _find_card(db: Session, slug: str, name: str | None, specs: dict, sold_ids: set[int], sold: bool | None):
    query = select(Product).join(Product.category).where(Category.slug == slug).order_by(Product.id)
    if name:
        query = query.where(Product.normalized_name.ilike(f"%{name}%"))
    return next((p for p in db.scalars(query) if _fits(p.specs_json or {}, specs)
                 and (sold is None or (p.id in sold_ids) == sold)), None)


def _demo_components(db: Session, store: Store, parts: list) -> tuple[list[dict], float] | None:
    """The parts of a demo build and what its exact parts cost in this store (USD); None: a card is missing."""
    sold_ids, components, cost = _sold_ids(db, store), [], 0.0
    for slot, slug, name, specs, sold in parts:
        if slug is None:
            components.append({"slot": slot, "raw_text": name or ""})
        elif name or sold is not None:
            card = _find_card(db, slug, name, specs, sold_ids, sold)
            if card is None:
                return None
            components.append({"slot": slot, "product_id": card.id})
            offer = db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.product_id == card.id))
            if offer is not None and offer.price:
                cost += offer.price / FALLBACK_USD_RATE if offer.currency == Currency.UZS else offer.price
        else:
            components.append({"slot": slot, "category": slug, "specs": specs})
    return components, cost


def seed_builds(db: Session, usd_rate: float) -> int:
    """Demo builds are recreated on every run (Build.is_demo); a real store's builds are never touched."""
    from app.services.builds import save_build

    for old in db.scalars(select(Build).where(Build.is_demo.is_(True))):
        db.delete(old)  # with its parts and price history
    db.commit()
    made = 0
    for spec in DEMO_BUILDS:
        store = db.scalar(select(Store).join(Store.owner).where(User.email == spec["store"]))
        found = _demo_components(db, store, spec["parts"]) if store is not None else None
        if found is None:
            print(f"Demo build skipped (a card is not in the catalog): {spec['name']}")
            continue
        components, cost = found
        usd = round(cost * spec["markup"], -1) if spec.get("markup") else spec["usd"]
        uzs = next(s["currency"] for s in STORES if s["email"] == spec["store"]) == Currency.UZS
        price, currency = (round(usd * usd_rate, -5), "UZS") if uzs else (usd, "USD")
        build = save_build(db, store, {
            "name": spec["name"], "price": price, "currency": currency, "condition": spec.get("condition", "new"),
            "purpose": spec["purpose"], "description": spec.get("description"), "components": components,
        })
        build.is_demo = True
        for point in build.price_history:
            point.is_demo = True
        db.commit()
        made += 1
    return made


if __name__ == "__main__":
    from app.db.database import SessionLocal, init_db
    from app.services.exchange import get_usd_rate

    init_db()
    with SessionLocal() as db:
        rate = get_usd_rate(db)
        if "--builds-only" in sys.argv:
            report = refresh_stores_and_builds(db, rate.rate if rate else None)
        else:
            report = seed_demo(db, rate.rate if rate else None, fetch_rates=True)
        for line in report:
            print(line)
