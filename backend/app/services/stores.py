"""Stores as the buyer sees them (phase 12): the "Stores" list and the store page /store/<id>.

Only shops: Telegram channels are ads, not stores; archive sources (old price lists) are not on sale.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Build, Offer, Product, Store, StoreKind
from app.services.branches import branch_public, store_in_city
from app.services.builds import build_summary, load_builds
from app.services.catalog import _in_group, card_specs, store_brief, visible
from app.services.exchange import to_uzs

PAGE_SIZE = 24


def _shops():
    return select(Store).where(Store.kind == StoreKind.shop, Store.is_archive.is_(False))


def store_public(store: Store, city: str | None = None) -> dict:
    """The store card: what store_brief has (city, address, phone, Telegram) and where to go; its branches
    (phase 12.1), the chosen city's first, and how many of them are in that city."""
    branches = sorted(store.branches, key=lambda b: (city is not None and b.city != city, not b.is_main, b.id))
    return {**store_brief(store), "is_demo": store.is_demo,
            "branches": [branch_public(b, store) for b in branches],
            "branches_here": sum(1 for b in branches if b.city == city) if city else len(branches),
            "cities": sorted({b.city for b in branches})}


def _on_sale(group: str | None = None):
    return [visible(), Offer.is_in_stock.is_(True), _in_group(group)]


def list_stores(db: Session, city: str | None = None) -> list[dict]:
    """Partner stores, verified ones first, then by goods in stock."""
    query = _shops().options(selectinload(Store.branches))
    if city:
        query = query.where(store_in_city(city))  # a store is in every city of its branches
    stores = db.scalars(query).all()
    counts = dict(db.execute(
        select(Offer.store_id, func.count(Offer.id)).where(*_on_sale(), Offer.store_id.in_([s.id for s in stores]))
        .group_by(Offer.store_id)).all())
    items = [{**store_public(s, city), "in_stock": counts.get(s.id, 0)} for s in stores]
    items.sort(key=lambda s: (not s["is_verified"], -s["in_stock"], s["name"].lower()))
    return items


def get_shop(db: Session, store_id: int) -> Store | None:
    return db.scalar(_shops().where(Store.id == store_id))


def store_page(db: Session, store: Store, usd_rate: float | None) -> dict:
    """The store: its card, how many goods are on sale (new / used) and its ready PCs on sale."""
    counts = {g: db.scalar(select(func.count(Offer.id)).where(Offer.store_id == store.id, *_on_sale(g)))
              for g in ("new", "used")}
    builds = load_builds(db, select(Build).where(Build.store_id == store.id, Build.is_in_stock.is_(True))
                         .order_by(Build.updated_at.desc()))
    return {**store_public(store), "counts": counts, "builds": [build_summary(b, usd_rate) for b in builds]}


def store_offers(db: Session, store: Store, usd_rate: float | None, group: str = "new", page: int = 1,
                 page_size: int = PAGE_SIZE) -> dict:
    """The store's goods in stock as catalog tiles, with the store's own price (not "from")."""
    query = (select(Offer).join(Offer.product).where(Offer.store_id == store.id, *_on_sale(group))
             .order_by(Product.normalized_name))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    offers = db.scalars(query.options(selectinload(Offer.product).selectinload(Product.category))
                        .offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for o in offers:
        p = o.product
        slug = p.category.slug if p.category else "other"
        items.append({
            "id": p.id, "offer_id": o.id, "name": p.normalized_name, "brand": p.brand, "category": slug,
            "min_price": o.price, "min_currency": o.currency.value, "price_uzs": to_uzs(o.price, o.currency, usd_rate),
            "condition": o.condition.value, "specs": card_specs(slug, p.specs_json or {}), "own": True,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
