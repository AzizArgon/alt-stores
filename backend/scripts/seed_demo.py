"""Demo stores for the catalog: 3 invented shops built from the assortment of a real store price list.

Each store gets part of the assortment (popular items overlap, so cards show 2-4 offers),
prices +-5-15%, some items out of stock, its own price-list freshness; one store sells in UZS,
one is verified, one has a few items far below the market (Anti-Fraud "price below market").
Goes through publish_import, so flags and price history work as for a real upload.
Demo price history for the last 3 months (price_history.is_demo): small moves, RAM and SSD grew noticeably.
Demo ready PCs (phase B4): 8 builds of the demo stores in three cities, every precision level, each check shown once.
Re-running updates the same stores, offers and demo builds in place (ids stay), no duplicates. Usage (from backend/):
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
    Build, Category, Conversation, Currency, ImportStatus, Message, MessageAuthor, Offer, PriceHistory, PriceImport,
    Product, Reservation, ReservationEvent, ReservationStatus, Store, TopicKind, User, UserRole, utcnow,
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
     "hours": "Пн–Сб 10:00–19:00",
     "currency": Currency.USD, "days_old": 0, "below_market": []},
    {"email": "demo2@example.com", "name": "Byte Market", "city": "samarkand", "district": "Сиаб",
     "address": "ул. Ташкентская, 12", "phone": "+998900000202", "telegram": "@byte_market_demo", "is_verified": False,
     "hours": "Ежедневно 09:00–20:00",
     "currency": Currency.UZS, "days_old": 4, "below_market": []},
    # Published last: its cheap items are compared with all the other stores
    {"email": "demo3@example.com", "name": "PC Galaxy", "city": "bukhara", "district": "Центр",
     "address": "ул. Бахауддина Накшбанди, 41", "phone": "+998900000303", "telegram": None, "is_verified": False,
     "hours": "Пн–Пт 09:30–18:30, Сб 10:00–16:00",
     "currency": Currency.USD, "days_old": 25, "below_market": ["Ryzen 5 7500F", "RTX 5060 TWIN EDGE OC", "990 PRO 1TB"]},
]
# Phase 12.1: branches (demo_key keeps the ids over re-runs, also with --builds-only) and stock by branch.
# Silicon Plus: three branches in Tashkent with different stock; Byte Market: Samarkand + Tashkent;
# PC Galaxy: one branch, no stock by branch (the general flag, "уточняйте у магазина")
DEMO_BRANCHES = {
    "demo1@example.com": {
        "main": ("d1-yunusabad", "Юнусабад", "ЦУМ, 2 этаж"),
        "more": [("d1-chilanzar", "Чиланзар", "tashkent", "ул. Бунёдкор, 15", "напротив метро «Чиланзар»",
                  "Пн–Сб 10:00–20:00", "+998900000111"),
                 ("d1-sergeli", "Сергели", "tashkent", "ул. Янги Сергели, 3", "рынок «Сергели», вход 2",
                  "Ежедневно 09:00–19:00", None)],
    },
    "demo2@example.com": {
        "main": ("d2-samarkand", "Самарканд", "у Сиабского базара"),
        "more": [("d2-tashkent", "Ташкент, Мирабад", "tashkent", "ул. Шахрисабз, 22", "рядом с «Мирабадским рынком»",
                  "Пн–Сб 10:00–19:00", "+998900000222")],
    },
    "demo3@example.com": {"main": ("d3-main", None, "напротив хокимията")},
}
# Quantities by branch (in the order above) for the first goods of the store; None = "есть, количество не указано"
STOCK_PATTERNS = {
    # Silicon Plus keeps stock (phase 12.2): only numbers; one item "заканчивается" comes from its journal
    "demo1@example.com": [(5, 2, 0), (0, 0, 3), (2, 3, 4)],
    "demo2@example.com": [(3, 0), (0, 2)],
}
SHOWCASE_STOCK = {"demo1@example.com": (3, 0, 2), "demo2@example.com": (2, 1)}
STOCK_GOODS = 24  # how many goods of the store get stock by branch (the rest: the general flag)
STALE_EVERY = 7  # every 7th of them: the data of one branch is 4 days old ("давно не обновлялось")
LIVE_EMAIL = "live@example.com"  # empty demo store for the live upload (scripts/demo_reset.py)
LIVE_CITY, LIVE_DISTRICT = "fergana", "Центр"
LIVE_ADDRESS, LIVE_HOURS = "ул. Ал-Фергани, 25, ориентир — ТЦ «Фергана Сити»", "Пн–Сб 10:00–19:00"
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
    for field in ("name", "city", "district", "address", "phone", "telegram", "is_verified", "hours"):
        setattr(store, field, spec[field])
    # No invented coordinates: "Open in Yandex Maps" searches the address (phase 12)
    store.map_url = store.map_lat = store.map_lon = None
    store.is_demo = True
    db.commit()
    seed_branches(db, store, spec["email"])
    return store


def seed_branches(db: Session, store: Store, email: str) -> list:
    """The store's address is its main branch; the other demo branches by their constant keys."""
    from app.db.models import Branch
    from app.services.branches import ensure_main_branch, make_main

    spec = DEMO_BRANCHES.get(email)
    if spec is None:
        return []
    key, name, landmark = spec["main"]
    main = db.scalar(select(Branch).where(Branch.store_id == store.id, Branch.demo_key == key)) \
        or ensure_main_branch(db, store)
    main.demo_key, main.name, main.landmark = key, name, landmark
    main.city, main.address, main.hours = store.city, store.address, store.hours
    main.map_url = main.map_lat = main.map_lon = None
    make_main(db, store, main)
    branches = [main]
    for key, name, city, address, landmark, hours, phone in spec.get("more", []):
        b = db.scalar(select(Branch).where(Branch.store_id == store.id, Branch.demo_key == key))
        if b is None:
            b = Branch(store_id=store.id, demo_key=key)
            db.add(b)
        b.name, b.city, b.address, b.landmark, b.hours, b.phone = name, city, address, landmark, hours, phone
        b.is_main, b.map_url, b.map_lat, b.map_lon = False, None, None, None
        branches.append(b)
    db.commit()
    return branches


def seed_stock(db: Session, store: Store, email: str) -> int:
    """Stock by branch for the first goods of the store (the showcase ones always); the same on every run."""
    from app.db.models import Branch, OfferStock
    from app.services.branches import set_stock

    pattern = STOCK_PATTERNS.get(email)
    if not pattern:
        return 0
    keys = [DEMO_BRANCHES[email]["main"][0]] + [b[0] for b in DEMO_BRANCHES[email].get("more", [])]
    ids = [db.scalar(select(Branch.id).where(Branch.store_id == store.id, Branch.demo_key == k)) for k in keys]
    offers = db.scalars(select(Offer).join(Offer.product).where(Offer.store_id == store.id, Offer.price.is_not(None),
                                                              Offer.removed_at.is_(None))
                        .order_by(Product.normalized_name)).all()
    showcase = [o for o in offers if any(s in o.product.normalized_name for s in SHOWCASE)]
    chosen = showcase + [o for o in offers if o not in showcase][:STOCK_GOODS]
    stale = utcnow() - timedelta(days=4)
    for i, offer in enumerate(chosen):
        values = SHOWCASE_STOCK[email] if offer in showcase else pattern[i % len(pattern)]
        for bid, q in zip(ids, values):
            row = set_stock(offer, bid, quantity=q, present=True if q is None else None)
            if i % STALE_EVERY == STALE_EVERY - 1 and bid == ids[-1]:
                row.updated_at = stale
    db.commit()
    return db.scalar(select(func.count(OfferStock.id)).join(Offer).where(Offer.store_id == store.id))


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
        store.address, store.hours = LIVE_ADDRESS, LIVE_HOURS
    db.commit()


def refresh_stores_and_builds(db: Session, usd_rate: float | None) -> list[dict]:
    """--builds-only: demo stores get their details (city, address...) and the demo builds are recreated.

    Offers, price history and passwords are not touched (the server has its own demo passwords and live data).
    """
    for spec in STORES:
        seed_stock(db, _store(db, spec), spec["email"])
    _live_store(db)
    return [{"demo_builds": seed_builds(db, usd_rate or FALLBACK_USD_RATE)}, {"demo_chats": seed_chats(db)},
            {"demo_reservations": seed_reservations(db)}, {"demo_stock_journal": seed_stock_journal(db)},
            {"demo_barcodes": seed_barcodes(db)}, {"demo_moderation": seed_moderation(db)},
            {"demo_notifications": seed_notifications(db)}]


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
        stock = seed_stock(db, store, spec["email"])
        report.append({"store": spec["name"], "rows": len(rows), **stats, "branch_stock_rows": stock})
    _live_store(db)
    store_ids = [db.scalar(select(Store.id).join(Store.owner).where(User.email == s["email"])) for s in STORES]
    report.append({"demo_history_points": seed_history(db, store_ids, fetch_rates)})
    report.append({"demo_builds": seed_builds(db, usd_rate)})
    report.append({"demo_chats": seed_chats(db)})
    report.append({"demo_reservations": seed_reservations(db)})
    report.append({"demo_stock_journal": seed_stock_journal(db)})
    report.append({"demo_barcodes": seed_barcodes(db)})
    report.append({"demo_moderation": seed_moderation(db)})
    report.append({"demo_notifications": seed_notifications(db)})
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
    """Demo builds are updated in place by a constant key (store + name, Build.is_demo): their ids stay, so
    conversations and bookings about them survive a re-run. A real store's builds are never touched."""
    from app.services.builds import save_build

    existing = {(b.store_id, b.name): b for b in db.scalars(select(Build).where(Build.is_demo.is_(True)))}
    kept: set[int] = set()
    made = 0
    for spec in DEMO_BUILDS:
        store = db.scalar(select(Store).join(Store.owner).where(User.email == spec["store"]))
        found = _demo_components(db, store, spec["parts"]) if store is not None else None
        if found is None:
            print(f"Demo build skipped (a card is not in the catalog): {spec['name']}")
            continue
        old = existing.get((store.id, spec["name"]))
        components, cost = found
        usd = round(cost * spec["markup"], -1) if spec.get("markup") else spec["usd"]
        uzs = next(s["currency"] for s in STORES if s["email"] == spec["store"]) == Currency.UZS
        price, currency = (round(usd * usd_rate, -5), "UZS") if uzs else (usd, "USD")
        build = save_build(db, store, {
            "name": spec["name"], "price": price, "currency": currency, "condition": spec.get("condition", "new"),
            "purpose": spec["purpose"], "description": spec.get("description"), "components": components,
        }, old)
        build.is_demo = True
        kept.add(build.id)
        for point in build.price_history:
            point.is_demo = True
        db.commit()
        made += 1
    for build in existing.values():  # a demo build no longer in the list
        if build.id not in kept:
            db.delete(build)
    db.commit()
    return made


# --- Demo conversations (phase 10) ----------------------------------------------------------------------------------
# The buyer of the demo with the demo stores: a product question answered, a build question waiting over a day,
# a question to the store answered, a fresh one unread. Recreated on every run (Conversation.is_demo), also in
# --builds-only mode; a real store is never touched.
DEMO_BUYER = "buyer1@example.com"
# (store, topic: ("offer", category) / ("build", index in DEMO_BUILDS of that store) / ("store",), [(author, text, hours ago)])
DEMO_CHATS = [
    ("demo1@example.com", ("offer", "gpu"), [
        ("buyer", "Здравствуйте! Видеокарта ещё в наличии? Гарантия официальная?", 30),
        ("store", "Здравствуйте! Да, в наличии. Гарантия 1 год от магазина, чек выдаём.", 29),
        ("buyer", "Спасибо, завтра заеду посмотреть.", 28)]),
    ("demo1@example.com", ("build", 0), [
        ("buyer", "Можно в этой сборке поставить SSD на 2 ТБ вместо 1 ТБ? Сколько будет стоить?", 27)]),
    ("demo2@example.com", ("store",), [
        ("buyer", "Вы работаете в воскресенье?", 50),
        ("store", "Да, с 10:00 до 18:00. Ждём вас!", 49)]),
    ("demo3@example.com", ("offer", "ssd"), [
        ("buyer", "Цена за SSD окончательная или можно немного уступить?", 2)]),
]


def _demo_buyer(db: Session) -> User:
    """The buyer of the demo; an existing account keeps its password (the server may have its own)."""
    user = db.scalar(select(User).where(User.email == DEMO_BUYER))
    if user is None:
        user = User(email=DEMO_BUYER, password_hash=hash_password(DEMO_PASSWORD), role=UserRole.buyer)
        db.add(user)
        db.commit()
    return user


def _chat_topic(db: Session, store: Store, topic: tuple) -> tuple[TopicKind, int] | None:
    if topic[0] == "store":
        return TopicKind.store, 0
    if topic[0] == "build":
        builds = db.scalars(select(Build).where(Build.store_id == store.id, Build.is_demo.is_(True)).order_by(Build.id)).all()
        return (TopicKind.build, builds[topic[1]].id) if len(builds) > topic[1] else None
    # Not the showcase i5-12400F: the check of the phase writes about it from the card itself
    offer = db.scalar(
        select(Offer).join(Offer.product).join(Product.category)
        .where(Offer.store_id == store.id, Category.slug == topic[1], Offer.is_in_stock.is_(True),
               Offer.removed_at.is_(None), Offer.price.is_not(None), ~Offer.raw_name.contains("12400F"))
        .order_by(Offer.id))
    return (TopicKind.offer, offer.id) if offer else None


def seed_chats(db: Session) -> int:
    buyer = _demo_buyer(db)
    for old in db.scalars(select(Conversation).where(Conversation.is_demo.is_(True),
                                                     Conversation.topic_kind != TopicKind.reservation)):
        db.delete(old)  # with its messages; demo reservations keep theirs (seed_reservations)
    db.commit()
    made, now = 0, utcnow()
    for email, topic, lines in DEMO_CHATS:
        store = db.scalar(select(Store).join(Store.owner).where(User.email == email, Store.is_demo.is_(True)))
        found = _chat_topic(db, store, topic) if store is not None else None
        if found is None:
            continue
        kind, topic_id = found
        # The buyer may have opened the same topic himself: that conversation is his, not demo - skip it
        if db.scalar(select(Conversation.id).where(Conversation.buyer_id == buyer.id, Conversation.store_id == store.id,
                                                   Conversation.topic_kind == kind, Conversation.topic_id == topic_id)):
            continue
        conv = Conversation(buyer_id=buyer.id, store_id=store.id, topic_kind=kind, topic_id=topic_id, is_demo=True,
                            created_at=now - timedelta(hours=lines[0][2]), last_message_at=now - timedelta(hours=lines[-1][2]))
        last = len(lines) - 1
        conv.messages = [
            # Everything but the last line was seen by the other side; the last one is read only if it is the store's
            Message(author=MessageAuthor(author), sender_id=buyer.id if author == "buyer" else store.user_id, text=text,
                    created_at=now - timedelta(hours=hours), is_read=i < last or author == "store")
            for i, (author, text, hours) in enumerate(lines)
        ]
        db.add(conv)
        db.commit()
        made += 1
    return made


# --- Demo reservations (phase 11) ----------------------------------------------------------------------------------
# buyer1 at the demo stores, one per status; the confirmed one ends today. Updated in place by a constant key
# (Reservation.demo_key): ids stay over re-runs, also in --builds-only mode; a real store is never touched.
# (key, store, topic as in DEMO_CHATS, path of statuses, hours ago, cancel reason)
DEMO_RESERVATIONS = [
    ("new", "demo2@example.com", ("offer", "gpu"), ["new"], 3, None),
    ("confirmed", "demo1@example.com", ("build", 0), ["new", "confirmed"], 40, None),
    ("ready", "demo3@example.com", ("offer", "ssd"), ["new", "confirmed", "ready"], 20, None),
    ("issued", "demo1@example.com", ("offer", "ram"), ["new", "confirmed", "ready", "issued"], 120, None),
    # Phase 12.2: confirmed in "Учёт остатков" — holds a reserve in its branch
    ("reserved", "demo1@example.com", ("offer", "cpu"), ["new", "confirmed"], 30, None),
    ("cancelled", "demo2@example.com", ("offer", "monitor"), ["new", "cancelled"], 70, "no_stock"),
]
DEMO_CONTACT = {"name": "Азиз", "phone": "+998901112233", "contact": "telegram", "telegram": "@buyer1_demo"}


def _reservation_item(db: Session, store: Store, topic: tuple):
    found = _chat_topic(db, store, topic)
    if found is None:
        return None
    kind, item_id = found
    return db.get(Offer, item_id) if kind == TopicKind.offer else db.get(Build, item_id)


def _pickup_branch_id(db: Session, store: Store, offer: Offer | None) -> int | None:
    """Phase 12.1: a demo reservation waits in a branch where the item is (else the main branch)."""
    from app.services.branches import available, main_branch

    for s in sorted(offer.stocks if offer is not None else [], key=lambda s: s.branch_id):
        if available(s):
            return s.branch_id
    main = main_branch(db, store.id)
    return main.id if main else None


def seed_reservations(db: Session) -> int:
    from app.services.reservations import TZ, system_text

    buyer, now = _demo_buyer(db), utcnow()
    made = 0
    for key, email, topic, path, hours, reason in DEMO_RESERVATIONS:
        store = db.scalar(select(Store).join(Store.owner).where(User.email == email, Store.is_demo.is_(True)))
        item = _reservation_item(db, store, topic) if store is not None else None
        if item is None:
            continue
        r = db.scalar(select(Reservation).where(Reservation.demo_key == key, Reservation.is_demo.is_(True)))
        if r is None:
            r = Reservation(demo_key=key, is_demo=True)
            db.add(r)
        is_offer = isinstance(item, Offer)
        status = ReservationStatus(path[-1])
        created = now - timedelta(hours=hours)
        r.buyer_id, r.store_id = buyer.id, store.id
        r.offer_id, r.build_id = (item.id, None) if is_offer else (None, item.id)
        r.title = item.product.normalized_name if is_offer else item.name
        r.condition, r.price, r.currency, r.quantity = item.condition, item.price, item.currency, 1
        for field, value in DEMO_CONTACT.items():
            setattr(r, field, value)
        r.pickup_date, r.pickup_time = None, None
        r.branch_id = _pickup_branch_id(db, store, item if is_offer else None)
        r.comment = "Заеду после работы, если можно — отложите до вечера." if key == "new" else None
        r.status, r.created_at, r.updated_at = status, created, created + timedelta(hours=len(path) - 1)
        r.cancelled_by = "store" if reason else None
        r.cancel_reason, r.cancel_text = reason, None
        if key == "confirmed":  # ends today (Tashkent) of every run, whenever it is: the overview shows it
            r.expires_at = datetime.combine(now.astimezone(TZ).date(), time(23, 59), TZ).astimezone(timezone.utc)
        elif "confirmed" in path:
            r.expires_at = created + timedelta(hours=1, days=store.reservation_days or 2)
        else:
            r.expires_at = None
        r.buyer_seen = key != "ready"  # one changed status the buyer has not seen yet
        r.events = [ReservationEvent(status=ReservationStatus(st), by="buyer" if st == "new" else "store",
                                     at=created + timedelta(hours=i)) for i, st in enumerate(path)]
        db.flush()
        conv = db.scalar(select(Conversation).where(Conversation.topic_kind == TopicKind.reservation,
                                                    Conversation.topic_id == r.id))
        if conv is None:
            conv = Conversation(buyer_id=buyer.id, store_id=store.id, topic_kind=TopicKind.reservation, topic_id=r.id,
                                is_demo=True)
            db.add(conv)
        conv.created_at = created
        until = _aware_until(r)
        lines = [(st, buyer.id if st == "new" else store.user_id) for st in path]
        conv.messages = [
            Message(author=MessageAuthor.system, sender_id=sender, created_at=created + timedelta(hours=i),
                    text=system_text("created" if st == "new" else "cancelled_store" if st == "cancelled" else st,
                                     until=until, reason=reason or "", text=""),
                    is_read=i < len(lines) - 1 or key != "ready")
            for i, (st, sender) in enumerate(lines)
        ]
        conv.last_message_at = created + timedelta(hours=len(path) - 1)
        db.commit()
        made += 1
    return made


def _aware_until(r: Reservation) -> str:
    from app.services.reservations import TZ
    if r.expires_at is None:
        return ""
    at = r.expires_at if r.expires_at.tzinfo else r.expires_at.replace(tzinfo=timezone.utc)
    return at.astimezone(TZ).strftime("%d.%m")


# --- Phase 12.2: Silicon Plus keeps stock ("Учёт остатков") with a journal of the last weeks ----------------------
JOURNAL_EMAIL = "demo1@example.com"
JOURNAL_DAYS = 18  # the opening balance
# (goods index among the tracked ones by name, branch index, days ago, kind, quantity, extra); receipts of one day
# are one document. The chain is built backwards from today's quantities, so they stay as seed_stock set them.
JOURNAL_EVENTS = [
    (0, 0, 15, "receipt", 4, {}), (2, 1, 15, "receipt", 3, {}), (5, 2, 15, "receipt", 2, {}),
    (0, 0, 12, "sale", 1, {}), (2, 1, 11, "sale", 1, {}), (8, 0, 10, "receipt", 2, {}),
    (5, 2, 8, "sale", 1, {"comment": "Оптовый покупатель"}), (11, 1, 6, "adjust", -1, {"reason": "defect", "comment": "Повреждена коробка"}),
    (0, 0, 4, "receipt", 2, {}), (8, 0, 3, "sale", 1, {}), (2, 1, 2, "sale", 1, {}),
]
LOW_GOODS = 14  # this one "заканчивается": a sale left 1 in the main branch


def seed_stock_journal(db: Session) -> int:
    """The same journal on every run (also --builds-only): the store's lines are written again, ids of goods kept."""
    from app.db.models import Branch, OfferStock, StockMovement

    store = db.scalar(select(Store).join(Store.owner).where(User.email == JOURNAL_EMAIL, Store.is_demo.is_(True)))
    if store is None:
        return 0
    db.execute(delete(StockMovement).where(StockMovement.store_id == store.id))
    _reset_warehouse(db, store)  # phase 12.4: the warehouse rows are made again below
    keys = [DEMO_BRANCHES[JOURNAL_EMAIL]["main"][0]] + [b[0] for b in DEMO_BRANCHES[JOURNAL_EMAIL]["more"]]
    bids = [db.scalar(select(Branch.id).where(Branch.store_id == store.id, Branch.demo_key == k)) for k in keys]
    store.stock_mode, store.low_stock = "stock", 1
    for other in db.scalars(select(Store).where(Store.is_demo.is_(True), Store.id != store.id)):
        other.stock_mode = "price"  # PC Galaxy, the live store: "Только прайс" (Byte Market: seed_no_warehouse)
        other.has_warehouse = False
    now = utcnow()
    reserved = db.scalar(select(Reservation).where(Reservation.demo_key == "reserved", Reservation.is_demo.is_(True)))
    issued = db.scalar(select(Reservation).where(Reservation.demo_key == "issued", Reservation.is_demo.is_(True)))
    for r in db.scalars(select(Reservation).where(Reservation.store_id == store.id)):
        r.reserved_qty, r.sold_out_at = 0, None
    offers = db.scalars(select(Offer).join(Offer.product).where(Offer.store_id == store.id)
                        .order_by(Product.normalized_name)).all()
    for o in offers:
        o.cost_last = o.cost_avg = None
        o.oversold_at = None
        for s in o.stocks:
            s.reserved = 0
            if s.quantity is None:
                s.quantity = 2
    # The reserved item needs stock in its branch; the low one: 1 in the main branch
    if reserved is not None and reserved.offer is not None and reserved.branch_id:
        row = next((s for s in reserved.offer.stocks if s.branch_id == reserved.branch_id), None)
        if row is None:
            row = OfferStock(branch_id=reserved.branch_id, reserved=0, quantity=3)
            reserved.offer.stocks.append(row)
        row.quantity = max(row.quantity or 0, 3)
    db.flush()
    tracked = [o for o in offers if o.stocks and o.price is not None and (reserved is None or o.id != reserved.offer_id)]
    chains: dict[tuple[int, int], list] = {}

    def add(offer, bid, days, kind, qty, extra, **refs):
        chains.setdefault((offer.id, bid), []).append((now - timedelta(days=days), kind, qty, extra, refs))

    for gi, bi, days, kind, qty, extra in JOURNAL_EVENTS:
        if gi < len(tracked):
            add(tracked[gi], bids[bi], days, kind, qty, extra)
    if LOW_GOODS < len(tracked):
        low = tracked[LOW_GOODS]
        row = next((s for s in low.stocks if s.branch_id == bids[0]), None)
        if row is not None:
            row.quantity = 1
            add(low, bids[0], 1, "sale", 1, {})
    if issued is not None and issued.offer is not None and issued.branch_id:
        add(issued.offer, issued.branch_id, 115 / 24, "res_sale", 1, {"price": issued.price}, reservation_id=issued.id)
    by_id = {o.id: o for o in offers}
    lines = 0
    for o in offers:
        for s in o.stocks:
            events = sorted(chains.get((o.id, s.branch_id), []), key=lambda e: e[0])
            sign = {"receipt": 1, "sale": -1, "res_sale": -1, "adjust": 1}
            final = s.quantity
            q = final - sum(sign[k] * n for _, k, n, _, _ in events)
            if q < 0:  # never below zero: a bigger opening balance and the same today
                q = 0
                events = [e for e in events if e[1] != "receipt"]
                q = max(0, final - sum(sign[k] * n for _, k, n, _, _ in events))
            db.add(StockMovement(store_id=store.id, offer_id=o.id, branch_id=s.branch_id, kind="initial", delta=q,
                                 quantity_before=None, quantity_after=q, reserved_after=0,
                                 created_at=now - timedelta(days=JOURNAL_DAYS)))
            lines += 1
            for at, kind, n, extra, refs in events:
                delta = sign[kind] * n
                cost = round(o.price * 0.86, 0 if o.currency == Currency.UZS else 2) if kind == "receipt" else None
                db.add(StockMovement(
                    store_id=store.id, offer_id=o.id, branch_id=s.branch_id, kind=kind, delta=delta,
                    reserved_delta=-n if kind == "res_sale" else 0, quantity_before=q, quantity_after=q + delta,
                    reserved_after=0, cost=cost, price=extra.get("price", o.price) if kind in ("sale", "res_sale") else None,
                    currency=o.currency.value, reason=extra.get("reason"), comment=extra.get("comment"),
                    doc=f"{kind[:1].upper()}-{at:%y%m%d}-demo" if kind != "res_sale" else None,
                    user_id=store.user_id, created_at=at, **refs))
                if cost is not None:
                    o.cost_last = cost
                    o.cost_avg = cost
                q += delta
                lines += 1
            s.quantity = q
            s.in_stock = q - (s.reserved or 0) > 0
    # The confirmed demo reservation holds its reserve
    if reserved is not None and reserved.offer is not None and reserved.branch_id:
        row = next(s for s in reserved.offer.stocks if s.branch_id == reserved.branch_id)
        row.reserved = reserved.quantity
        row.in_stock = row.quantity - row.reserved > 0
        reserved.reserved_qty = reserved.quantity
        db.add(StockMovement(store_id=store.id, offer_id=reserved.offer_id, branch_id=row.branch_id, kind="reserve",
                             delta=0, reserved_delta=reserved.quantity, quantity_before=row.quantity,
                             quantity_after=row.quantity, reserved_after=row.reserved, user_id=store.user_id,
                             reservation_id=reserved.id, created_at=reserved.created_at + timedelta(hours=1)))
        lines += 1
    from app.services.branches import recompute_offer

    db.flush()
    lines += seed_warehouse(db, store, tracked, bids, now)
    for o in by_id.values():
        recompute_offer(o)
    db.commit()
    lines += seed_no_warehouse(db)
    return lines


# --- Phase 12.4: Silicon Plus has a warehouse, Byte Market has none -------------------------------------------------
WAREHOUSE_KEY = "d1-warehouse"
STOCKTAKE_KEY = "d1-stocktake"
NO_WAREHOUSE_EMAIL = "demo2@example.com"
WH_QTY = [6, 4, 3, 5, 2, 8, 3, 4]  # the warehouse stock of the first tracked goods (after the put-out)
WH_RECEIPT_DAYS, PUT_OUT_DAYS, STOCKTAKE_DAYS = 7, 5, 3
PUT_OUT_QTY = 2


def _reset_warehouse(db: Session, store: Store) -> None:
    """Before the journal is written again: the warehouse rows go; goods kept only there are on sale again."""
    from app.db.models import Branch, OfferStock

    wh = db.scalar(select(Branch).where(Branch.store_id == store.id, Branch.demo_key == WAREHOUSE_KEY))
    if wh is None:
        return
    for row in list(db.scalars(select(OfferStock).where(OfferStock.branch_id == wh.id))):
        offer = db.get(Offer, row.offer_id)
        offer.stocks.remove(row)
        if not offer.stocks:
            offer.is_in_stock = offer.price is not None
    db.flush()
    db.info.pop("warehouse_ids", None)


def seed_warehouse(db: Session, store: Store, tracked: list, bids: list, now) -> int:
    """Silicon Plus: "есть отдельный склад" — one receipt to the warehouse, one put-out to Юнусабад, one item only in
    the warehouse, one applied stocktake of Юнусабад with a shortage and a surplus. The same ids on every run."""
    from app.db.models import Branch, OfferStock, StockMovement, Stocktake

    wh = db.scalar(select(Branch).where(Branch.store_id == store.id, Branch.demo_key == WAREHOUSE_KEY))
    if wh is None:
        wh = Branch(store_id=store.id, city=store.city or "tashkent", address="", is_warehouse=True, demo_key=WAREHOUSE_KEY)
        db.add(wh)
        db.flush()
    store.has_warehouse = True
    db.info.pop("warehouse_ids", None)
    yunus = bids[0]
    lines = 0
    events = {0, 2, 5, 8, 11, 14}  # goods with journal lines (JOURNAL_EVENTS, LOW_GOODS)
    free = [i for i in range(len(tracked)) if i not in events]

    def initial(offer, bid):
        return db.scalar(select(StockMovement).where(StockMovement.offer_id == offer.id, StockMovement.branch_id == bid,
                                                     StockMovement.kind == "initial"))

    def line(offer, bid, kind, before, after, at, doc, **extra):
        db.add(StockMovement(store_id=store.id, offer_id=offer.id, branch_id=bid, kind=kind, delta=after - before,
                             quantity_before=before, quantity_after=after, reserved_after=0, doc=doc,
                             user_id=store.user_id, created_at=at, currency=offer.currency.value, **extra))

    # The put-out item: the receipt brought WH + 2, two went to Юнусабад
    moved = tracked[free.pop(0)] if free else None
    receipt_at, receipt_doc = now - timedelta(days=WH_RECEIPT_DAYS), f"R-{now - timedelta(days=WH_RECEIPT_DAYS):%y%m%d}-demo-wh"
    goods = [(o, q) for o, q in zip(tracked[:len(WH_QTY)], WH_QTY) if o is not moved]
    # One item only in the warehouse: a good without stock by branch (on the storefront it becomes "нет в наличии")
    untracked = db.scalars(select(Offer).join(Offer.product).where(
        Offer.store_id == store.id, Offer.price.is_not(None), Offer.removed_at.is_(None), ~Offer.stocks.any())
        .order_by(Product.normalized_name)).first()
    if untracked is not None:
        goods.append((untracked, 3))
    if moved is not None:
        goods.append((moved, 4))
    for offer, q in goods:
        got = q + (PUT_OUT_QTY if offer is moved else 0)
        cost = round(offer.price * 0.85, 0 if offer.currency == Currency.UZS else 2)
        offer.stocks.append(OfferStock(branch_id=wh.id, quantity=q, reserved=0, in_stock=True, updated_at=receipt_at))
        line(offer, wh.id, "receipt", 0, got, receipt_at, receipt_doc, cost=cost)
        offer.cost_last = offer.cost_avg = cost
        lines += 1
    if moved is not None:
        at, doc = now - timedelta(days=PUT_OUT_DAYS), f"M-{now - timedelta(days=PUT_OUT_DAYS):%y%m%d}-demo"
        row = next((s for s in moved.stocks if s.branch_id == yunus), None)
        if row is None:
            row = OfferStock(branch_id=yunus, quantity=0, reserved=0)
            moved.stocks.append(row)
        cur = row.quantity or 0
        line(moved, wh.id, "move_out", 4 + PUT_OUT_QTY, 4, at, doc)
        line(moved, yunus, "move_in", cur, cur + PUT_OUT_QTY, at, doc)
        row.quantity, row.in_stock = cur + PUT_OUT_QTY, True
        lines += 2
    # The stocktake of Юнусабад: a shortage, a surplus and two matches; the journal before it agrees with them
    at = now - timedelta(days=STOCKTAKE_DAYS)
    rows = []
    for i in free:
        r = next((s for s in tracked[i].stocks if s.branch_id == yunus and s.quantity is not None), None)
        if r is not None and initial(tracked[i], yunus) is not None:
            rows.append((tracked[i], r))
    short = rows.pop(0) if rows else None
    over = next((x for x in rows if x[1].quantity >= 1), None)
    if over:
        rows.remove(over)
    result = []
    doc = f"I-{at:%y%m%d}-demo"
    for kind, pair in (("short", short), ("over", over)):
        if pair is None:
            continue
        offer, r = pair
        before = r.quantity + 1 if kind == "short" else r.quantity - 1
        first = initial(offer, yunus)
        first.quantity_after = first.delta = before
        line(offer, yunus, "inventory", before, r.quantity, at, doc, reason="inventory")
        lines += 1
        result.append({"offer_id": offer.id, "name": offer.product.normalized_name,
                       "category": offer.product.category.slug if offer.product.category else "other",
                       "expected": before, "counted": r.quantity, "diff": r.quantity - before, "status": kind})
    for offer, r in rows[:2]:
        result.append({"offer_id": offer.id, "name": offer.product.normalized_name,
                       "category": offer.product.category.slug if offer.product.category else "other",
                       "expected": r.quantity, "counted": r.quantity, "diff": 0, "status": "match"})
    st = db.scalar(select(Stocktake).where(Stocktake.store_id == store.id, Stocktake.demo_key == STOCKTAKE_KEY))
    if st is None:
        st = Stocktake(store_id=store.id, demo_key=STOCKTAKE_KEY)
        db.add(st)
    st.branch_id, st.status, st.doc, st.categories_json, st.excluded_json = yunus, "applied", doc, [], []
    st.counts_json = {str(x["offer_id"]): x["counted"] for x in result if x["counted"]}
    st.result_json, st.positions = result, len(result)
    st.shortage = sum(-x["diff"] for x in result if x["diff"] < 0)
    st.surplus = sum(x["diff"] for x in result if x["diff"] > 0)
    st.user_id, st.created_at, st.finished_at = store.user_id, at - timedelta(minutes=40), at
    # Other stocktakes of the demo store (a reviewer's tries) go away: the history is the same on every run
    for other in db.scalars(select(Stocktake).where(Stocktake.store_id == store.id, Stocktake.demo_key.is_(None))):
        db.delete(other)
    for o in tracked:
        o.oversold_at = None
    return lines


def seed_no_warehouse(db: Session) -> int:
    """Byte Market: "Учёт остатков", "склада нет" — receipts go straight into a branch. The journal: the opening
    balance of its quantities; the confirmed reservations take their reserve."""
    from app.db.models import StockMovement, Stocktake
    from app.services import stock

    store = db.scalar(select(Store).join(Store.owner).where(User.email == NO_WAREHOUSE_EMAIL, Store.is_demo.is_(True)))
    if store is None:
        return 0
    db.execute(delete(StockMovement).where(StockMovement.store_id == store.id))
    db.execute(delete(Stocktake).where(Stocktake.store_id == store.id))
    store.stock_mode, store.has_warehouse = "stock", False
    at = utcnow() - timedelta(days=JOURNAL_DAYS)
    lines = 0
    for o in db.scalars(select(Offer).where(Offer.store_id == store.id)):
        o.oversold_at = None
        for s in o.stocks:
            s.reserved = 0
            if s.quantity is None:
                continue
            db.add(StockMovement(store_id=store.id, offer_id=o.id, branch_id=s.branch_id, kind="initial", delta=s.quantity,
                                 quantity_after=s.quantity, reserved_after=0, created_at=at))
            lines += 1
    db.flush()
    for r in db.scalars(select(Reservation).where(Reservation.store_id == store.id)):
        r.reserved_qty, r.sold_out_at = 0, None
        if r.status in (ReservationStatus.confirmed, ReservationStatus.ready):
            stock.take_reserve(db, store, r, store.user_id)
    db.commit()
    return lines


# --- Phase 12.3: barcodes of Silicon Plus and Byte Market ----------------------------------------------------------
# Only internal codes: EAN-13 with the prefix 290 (the range 200–299 is for in-store use and never meets a real
# product), with the right check digit. 8 cards bound by both stores (confirmed in the common base), 6 only by
# Silicon Plus and 3 only by Byte Market (pending), one code bound to different cards (a conflict for the admin).
# The same codes on every run (also --builds-only): rows are updated in place, nothing is duplicated.
BARCODE_STORES = ("demo1@example.com", "demo2@example.com")
BARCODE_BOTH, BARCODE_FIRST, BARCODE_SECOND = 8, 6, 3
DEMO_UNKNOWN_CODE = 99  # a valid code bound nowhere: the "Привязать штрихкод" scene


def demo_code(i: int) -> str:
    from app.services.barcodes import make_ean13

    return make_ean13(f"2900000{i:05d}")


def seed_barcodes(db: Session) -> int:
    from app.db.models import Barcode
    from app.services.barcodes import refresh_common

    stores = [db.scalar(select(Store).join(Store.owner).where(User.email == e, Store.is_demo.is_(True))) for e in BARCODE_STORES]
    if None in stores:
        return 0
    first, second = stores
    offers = {}
    for st in stores:
        rows = db.scalars(select(Offer).join(Offer.product).where(Offer.store_id == st.id, Offer.removed_at.is_(None),
                                                                  Offer.price.is_not(None)).order_by(Product.normalized_name, Offer.id))
        offers[st.id] = {o.product_id: o for o in rows}
    both = [p for p in offers[first.id] if p in offers[second.id]][:BARCODE_BOTH]
    only_first = [p for p in offers[first.id] if p not in offers[second.id]][:BARCODE_FIRST]
    only_second = [p for p in offers[second.id] if p not in offers[first.id]][:BARCODE_SECOND]
    wanted: dict[tuple[int, str], Offer] = {}
    n = 1
    for p in both:
        for st in stores:
            wanted[(st.id, demo_code(n))] = offers[st.id][p]
        n += 1
    for st, products in ((first, only_first), (second, only_second)):
        for p in products:
            wanted[(st.id, demo_code(n))] = offers[st.id][p]
            n += 1
    if only_first and len(only_second) > 1:  # the conflict: the same code on two different cards
        wanted[(first.id, demo_code(50))] = offers[first.id][only_first[-1]]
        wanted[(second.id, demo_code(50))] = offers[second.id][only_second[-1]]
    ids = [st.id for st in stores]
    existing = {(b.store_id, b.code): b for b in db.scalars(select(Barcode).where(Barcode.store_id.in_(ids), Barcode.is_demo.is_(True)))}
    codes = {code for _, code in wanted} | {code for _, code in existing}
    for key, b in existing.items():
        if key not in wanted:
            db.delete(b)
    for (store_id, code), offer in wanted.items():
        b = existing.get((store_id, code))
        if b is None:
            clash = db.scalar(select(Barcode).where(Barcode.store_id == store_id, Barcode.code == code))
            if clash is not None:  # the seller bound this demo code by hand: leave it
                continue
            db.add(Barcode(store_id=store_id, offer_id=offer.id, code=code, source="demo", is_demo=True))
        else:
            b.offer_id = offer.id
    db.flush()
    for code in sorted(codes):
        refresh_common(db, code)
    db.commit()
    return len(wanted)


# --- Phase 13: what waits for the admin -------------------------------------------------------------------------------
# Byte Market and PC Galaxy are demo stores without the check; the barcode conflict comes from seed_barcodes.
# One report, one disputed flag and one card fix, all marked is_demo: updated in place (the same ids), reset to
# "waiting" on every run (also --builds-only).
DEMO_REPORT_COMMENT = "Покупатель пишет грубо и требует скидку"
DEMO_RUDE_LINE = "Если не сделаете скидку 30%, напишу везде, что вы мошенники!"
DEMO_DISPUTE = "Это акция до конца недели: цена верная, товар новый"


# Phase 12.5: the bell of demo1 and buyer1 — 5–6 notifications of different kinds, some read. demo_key keeps them
# over re-runs (also --builds-only): updated in place, never doubled; a real store is never touched.
def seed_notifications(db: Session) -> int:
    from app.db.models import Notification, PriceImport

    shop = db.scalar(select(Store).join(Store.owner).where(User.email == STORES[0]["email"], Store.is_demo.is_(True)))
    buyer = db.scalar(select(User).where(User.email == DEMO_BUYER))
    if shop is None or buyer is None:
        return 0
    res = {k: db.scalar(select(Reservation.id).where(Reservation.demo_key == k, Reservation.is_demo.is_(True)))
           for k in ("confirmed", "reserved", "ready", "cancelled")}
    conv = db.scalar(select(Conversation).where(Conversation.is_demo.is_(True), Conversation.store_id == shop.id,
                                                Conversation.topic_kind != TopicKind.reservation).order_by(Conversation.id))
    bconv = db.scalar(select(Conversation).where(Conversation.is_demo.is_(True), Conversation.buyer_id == buyer.id,
                                                 Conversation.topic_kind != TopicKind.reservation).order_by(Conversation.id))
    offer = db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.removed_at.is_(None), Offer.price.is_not(None))
                      .order_by(Offer.id))
    imp = db.scalar(select(PriceImport).where(PriceImport.store_id == shop.id).order_by(PriceImport.id.desc()))
    rlink = lambda key, seller: (f"/seller/reservations?id={res[key]}" if seller else f"/reservations?id={res[key]}") if res[key] else (
        "/seller/reservations" if seller else "/reservations")
    name = offer.product.normalized_name if offer is not None else "Intel Core i5-12400F"
    # (user, key, kind, link, params, count, minutes ago, read)
    rows = [
        (shop.user_id, "s_msg", "message",
         f"/seller/messages/{conv.id}" if conv else "/seller/messages", {"text": "Здравствуйте! Есть в наличии?"}, 2, 4, False),
        (shop.user_id, "s_res", "reservation_new", rlink("reserved", True), {"title": name, "qty": 1}, 1, 25, False),
        (shop.user_id, "s_low", "low_stock", f"/seller/stock?tab=receipt&offer={offer.id}" if offer else "/seller/stock",
         {"name": name, "left": 1}, 1, 90, False),
        (shop.user_id, "s_imp", "import_ready", f"/seller/imports/{imp.id}" if imp else "/seller/imports",
         {"name": imp.filename if imp else "price.xlsx", "rows": 0}, 1, 60 * 5, True),
        (shop.user_id, "s_fix", "admin_fix", "/seller", {"status": "accepted", "name": name}, 1, 60 * 26, True),
        (shop.user_id, "s_cancel", "reservation_cancelled", rlink("confirmed", True), {"title": name}, 1, 60 * 50, True),
        (buyer.id, "b_reply", "message", f"/messages/{bconv.id}" if bconv else "/messages",
         {"store": bconv.store.name if bconv else shop.name, "text": "Да, есть. Ждём вас!"}, 1, 7, False),
        (buyer.id, "b_conf", "reservation_confirmed", rlink("confirmed", False),
         {"title": name, "store": shop.name, "until": (utcnow() + timedelta(days=2)).strftime("%d.%m")}, 1, 35, False),
        (buyer.id, "b_ready", "reservation_ready", rlink("ready", False), {"title": name, "store": shop.name}, 1, 60 * 3, True),
        (buyer.id, "b_exp", "reservation_expiring", rlink("reserved", False), {"title": name, "store": shop.name}, 1, 60 * 8, False),
        (buyer.id, "b_cancel", "reservation_cancelled_store", rlink("cancelled", False),
         {"title": name, "store": shop.name, "reason": "no_stock"}, 1, 60 * 30, True),
    ]
    now = utcnow()
    for user_id, key, kind, link, params, count, ago, read in rows:
        n = db.scalar(select(Notification).where(Notification.user_id == user_id, Notification.demo_key == key))
        if n is None:
            n = Notification(user_id=user_id, demo_key=key)
            db.add(n)
        n.kind, n.link, n.params, n.count, n.is_read = kind, link, {**params, "count": count}, count, read
        n.group_key, n.created_at = None, now - timedelta(minutes=ago)
    db.commit()
    return len(rows)


def seed_moderation(db: Session) -> dict:
    from app.db.models import ChatReport, FlagLevel, FlagSource, FlagStatus, FraudFlag, ProductFix

    made = {}
    shop = db.scalar(select(Store).join(Store.owner).where(User.email == STORES[0]["email"], Store.is_demo.is_(True)))
    if shop is None:
        return made
    # A report of the store on a demo reservation conversation (those keep their ids over re-runs)
    conv = db.scalar(select(Conversation).where(Conversation.is_demo.is_(True), Conversation.store_id == shop.id,
                                                Conversation.topic_kind == TopicKind.reservation).order_by(Conversation.id))
    report = db.scalar(select(ChatReport).where(ChatReport.is_demo.is_(True)))
    if conv is not None:
        # The buyer's line the store complains about (added once, it stays over re-runs)
        if not any(m.text == DEMO_RUDE_LINE for m in conv.messages):
            conv.messages.append(Message(author=MessageAuthor.buyer, sender_id=conv.buyer_id, text=DEMO_RUDE_LINE,
                                         is_read=True))
        report = report or ChatReport(is_demo=True)
        report.conversation_id, report.reporter_id, report.reason = conv.id, shop.user_id, "abuse"
        report.comment, report.status, report.resolution = DEMO_REPORT_COMMENT, "new", None
        report.admin_comment = report.resolved_at = None
        db.add(report)
        made["report"] = 1
    # A disputed "below the market" flag of a showcase offer
    offer = db.scalar(select(Offer).join(Offer.product).where(
        Offer.store_id == shop.id, Offer.price.is_not(None), Product.normalized_name.contains(SHOWCASE[0])))
    flag = db.scalar(select(FraudFlag).where(FraudFlag.is_demo.is_(True)))
    if offer is not None:
        if flag is None:
            flag = FraudFlag(is_demo=True)
            offer.fraud_flags.append(flag)
        flag.offer_id, flag.type, flag.level, flag.source = offer.id, "price_below_market", FlagLevel.warning, FlagSource.rule
        flag.reason_key, flag.params = "below_market", {"percent": 22, "median": round((offer.price or 0) * 1.3), "count": 3}
        flag.status, flag.dispute_comment, flag.disputed_at = FlagStatus.disputed, DEMO_DISPUTE, utcnow()
        flag.resolution = flag.admin_answer = flag.resolved_at = None
        made["flag"] = 1
    # A card fix: the store suggests "BOX" in the name of a card other demo stores sell too
    fix = db.scalar(select(ProductFix).where(ProductFix.is_demo.is_(True)))
    product = db.get(Product, fix.product_id) if fix is not None else None
    if product is None:
        others = select(Offer.product_id).where(Offer.store_id != shop.id, Offer.price.is_not(None))
        product = db.scalar(select(Product).join(Offer, Offer.product_id == Product.id).join(Product.category).where(
            Offer.store_id == shop.id, Offer.price.is_not(None), Product.id.in_(others), Category.slug == "cpu")
            .order_by(Product.normalized_name))
    if product is not None:
        if fix is None:
            card = {"name": product.normalized_name, "brand": product.brand, "model": product.model,
                    "category": product.category.slug if product.category else "other",
                    "specs": {k: v for k, v in (product.specs_json or {}).items() if not k.startswith("_")}}
            fix = ProductFix(is_demo=True, product_id=product.id, before=card, after={**card})
        fix.store_id = shop.id
        base = fix.before["name"].removesuffix(" BOX")
        fix.after = {**fix.before, "name": f"{base} BOX", "model": f"{(fix.before.get('model') or base).removesuffix(' BOX')} BOX"}
        fix.status, fix.reject_reason, fix.resolved_at, fix.merged_into = "pending", None, None, None
        db.add(fix)
        made["fix"] = 1
    db.commit()
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
