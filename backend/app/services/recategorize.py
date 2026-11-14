"""Phase 16.1: existing cards go to the category the rules give (categorize.py) — ink out of "Принтеры",
bags, pads, webcams out of "Прочее". The card keeps its id, offers and history; only the category, the specs
(by the new category's dictionary) and the match key change. A card that meets the same product already in the
new category is merged into it (duplicates.merge). Printers get "3 в 1" / "4 в 1" instead of "МФУ".
"""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Category, Offer, Product, Store, User
from app.services.catalog import make_match_key, rebuild_specs
from app.services.categorize import refine_category
from app.db.seed import seed_categories


def plan(db: Session) -> list[tuple[Product, str]]:
    """[(card, new category slug)] — nothing is changed."""
    products = db.scalars(select(Product).where(Product.merged_into.is_(None))
                          .options(selectinload(Product.category), selectinload(Product.offers))).all()
    moves = []
    for p in products:
        slug = p.category.slug if p.category else "other"
        new = refine_category(slug, p.normalized_name)
        # The stores' rows only for "Прочее": a row may describe a whole set ("клавиатура, мышь, коврик") or carry
        # an ad ("скидка на проекционный экран"), the card's own name is the safer word elsewhere
        for o in sorted(p.offers, key=lambda o: o.id) if slug == "other" else ():
            if new != slug:
                break
            new = refine_category(slug, o.raw_name)
        if new != slug:
            moves.append((p, new))
    return moves


def report(db: Session) -> dict:
    moves = plan(db)
    counts = Counter((p.category.slug if p.category else "other", new) for p, new in moves)
    return {"moves": [{"id": p.id, "name": p.normalized_name, "from": p.category.slug if p.category else "other",
                       "to": new} for p, new in moves],
            "by_pair": {f"{a} -> {b}": n for (a, b), n in counts.most_common()},
            "categories": category_counts(db)}


def category_counts(db: Session) -> dict[str, int]:
    """Cards with at least one offer, per category (merged duplicates do not count)."""
    live = select(Offer.product_id).where(Offer.removed_at.is_(None))
    return dict(db.execute(select(Category.slug, func.count(Product.id)).join(Product, Product.category_id == Category.id)
                           .where(Product.merged_into.is_(None), Product.id.in_(live))
                           .group_by(Category.slug).order_by(func.count(Product.id).desc())).all())


def apply(db: Session) -> dict:
    """Moves the cards, recomputes their specs and keys, merges the ones that meet a card in the new category,
    recomputes the specs of all printers (3 in 1 / 4 in 1). Commits."""
    from app.services.admin import merge_products

    seed_categories(db)  # the new categories on an old DB
    before = category_counts(db)
    moves = plan(db)
    cats = {c.slug: c for c in db.scalars(select(Category))}
    for p, new in moves:
        p.category = cats[new]
    db.flush()
    demo = set(db.scalars(select(Store.id).join(User).where(User.email.like("demo%@example.com"))))
    printers = set(db.scalars(select(Product.id).join(Category).where(Category.slug == "printer")))
    moved = {p.id for p, _ in moves}
    rebuild_specs(db, demo_store_ids=demo, commit=False, ids=moved | printers)
    merged = 0
    for p, new in moves:
        key = make_match_key(new, p.normalized_name, p.brand, p.specs_json)
        other = db.scalar(select(Product).where(Product.match_key == key, Product.id != p.id,
                                                Product.merged_into.is_(None)))
        if other is None:
            p.match_key = key
            continue
        count = lambda x: db.scalar(select(func.count(Offer.id)).where(Offer.product_id == x.id))  # noqa: E731
        keeper, gone = (other, p) if count(other) >= count(p) else (p, other)
        keeper.match_key = key
        merge_products(db, gone, keeper)
        merged += 1
    db.commit()
    return {"moved": len(moves), "merged": merged, "before": before, "after": category_counts(db)}
