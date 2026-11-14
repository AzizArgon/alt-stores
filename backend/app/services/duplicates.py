"""Phase 16.1: one product — one card. Cards that the current normalization gives one key are duplicates.

Sure duplicates (the same key: same category, same brand + model words) are merged into the card with more
offers — offers, price history, photos, barcodes, stock, reservations, chats, complaints and flags move with
them (admin.merge_products), the old address leads to the kept card. Doubtful ones (the same words in two
categories) go to the admin as "возможный дубль" (a pending ProductFix of kind "duplicate").
"""

import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Offer, Product, ProductFix, Store
from app.services.catalog import make_match_key
from app.services.spec_normalizer import strip_modifiers


def _active(db: Session) -> dict[int, int]:
    """Offers that still count (not removed) per card."""
    return dict(db.execute(select(Offer.product_id, func.count(Offer.id)).where(Offer.removed_at.is_(None))
                           .group_by(Offer.product_id)).all())


def _row(p: Product, offers: dict[int, int]) -> dict:
    return {"id": p.id, "name": p.normalized_name, "category": p.category.slug if p.category else "other",
            "offers": offers.get(p.id, 0)}


def scan(db: Session) -> dict:
    """{"keys": {product_id: new key}, "sure": [[keeper, *others]], "doubtful": [[a, b, ...]]} — nothing is changed."""
    products = db.scalars(select(Product).where(Product.merged_into.is_(None))
                          .options(selectinload(Product.category))).all()
    offers = _active(db)
    keys: dict[int, str] = {}
    by_key: dict[str, list[Product]] = defaultdict(list)
    for p in products:
        slug = p.category.slug if p.category else "other"
        keys[p.id] = make_match_key(slug, strip_modifiers(slug, p.normalized_name)[0] or p.normalized_name,
                                    p.brand, p.specs_json)
        by_key[keys[p.id]].append(p)
    # The card with more offers stays (its address is the one people know); equal — the older one
    order = lambda p: (-offers.get(p.id, 0), p.id)  # noqa: E731
    sure = [sorted(group, key=order) for group in by_key.values() if len(group) > 1]
    by_words: dict[str, list[str]] = defaultdict(list)
    for key in by_key:
        words = key.partition(":")[2]
        # A model needs a number and one more word: "Logitech" alone is not a product
        if len(words.split()) >= 2 and re.search(r"\d", words):
            by_words[words].append(key)
    doubtful = [sorted((min(by_key[k], key=order) for k in ks), key=order) for ks in by_words.values() if len(ks) > 1]
    return {"keys": keys, "sure": sure, "doubtful": doubtful, "offers": offers}


def report(db: Session, found: dict | None = None) -> dict:
    found = found or scan(db)
    offers = found["offers"]
    return {
        "sure": [[_row(p, offers) for p in g] for g in found["sure"]],
        "doubtful": [[_row(p, offers) for p in g] for g in found["doubtful"]],
        "merge_cards": sum(len(g) - 1 for g in found["sure"]),
    }


def _card(p: Product) -> dict:
    return {"name": p.normalized_name, "brand": p.brand, "model": p.model,
            "category": p.category.slug if p.category else "other", "specs": p.specs_json or {}}


def apply(db: Session) -> dict:
    """Merges the sure groups, stores the new keys, sends the doubtful pairs to the admin. Commits."""
    from app.services.admin import merge_products
    from app.services.cabinet import recheck_flags

    found = scan(db)
    out = report(db, found)
    merged_into: set[int] = set()
    for keeper, *others in found["sure"]:
        for p in others:
            merge_products(db, p, keeper)
        merged_into.add(keeper.id)
    db.flush()
    for pid, key in found["keys"].items():
        p = db.get(Product, pid)
        if p.merged_into is None:
            p.match_key = key
    sent = 0
    for keeper, *others in found["doubtful"]:
        for p in others:
            if p.merged_into is not None or keeper.merged_into is not None:
                continue
            exists = db.scalar(select(ProductFix.id).where(ProductFix.product_id == p.id, ProductFix.kind == "duplicate",
                                                           ProductFix.status == "pending"))
            store_id = db.scalar(select(Offer.store_id).where(Offer.product_id == p.id).order_by(Offer.id))
            if exists or store_id is None:
                continue
            db.add(ProductFix(product_id=p.id, store_id=store_id, kind="duplicate", before=_card(p),
                              after={**_card(keeper), "merge_into": keeper.id}))
            sent += 1
    db.flush()
    # The kept cards have more stores now: market prices of their offers are checked again

    for pid in merged_into:
        live = db.scalars(select(Offer).where(Offer.product_id == pid, Offer.price.is_not(None))).all()
        for store_id in {o.store_id for o in live}:
            recheck_flags(db, [o for o in live if o.store_id == store_id], db.get(Store, store_id))
    db.commit()
    return {**out, "merged": sum(len(g) - 1 for g in found["sure"]), "sent_to_admin": sent}
