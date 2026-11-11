"""Seller cabinet (phase B3): the store's own offers after publishing.

The seller edits everything that is his (price, stock, condition, his line, note) at once: a new price goes to the
price history, Anti-Fraud is checked again. A shared card is changed at once only if no other store sells it;
otherwise the change waits for the admin as a suggestion (product_fixes). An offer is never deleted for real: its
price history stays.
"""

from datetime import timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session, selectinload

from app.db.models import (
    Category, Condition, Currency, FlagLevel, FlagStatus, Offer, OfferEvent, PriceHistory, PriceImport, Product,
    ProductFix, Store, utcnow,
)
from app.services.branches import available, seller_stocks, set_general, set_stock
from app.services.stock import overview as stock_overview
from app.services.warehouse import overview_extra
from app.services.builds import counts as build_counts
from app.services.chat import overview_counts as chat_counts
from app.services.reservations import store_counts as reservation_counts
from app.services.antifraud import check_offer, market_for, market_prices, save_offer_flags
from app.services.exchange import get_usd_rate
from app.services.manual import card_fields, product_brief
from app.services.market import diff_pct, label, market_condition, market_data
from app.services.spec_normalizer import INFERRED, SUSPECT

PAGE_SIZE = 50
STALE_DAYS = 30  # no price change and no price list confirming the offer for longer: "not updated for long"
LEVEL_RANK = {FlagLevel.info: 1, FlagLevel.warning: 2, FlagLevel.danger: 3}
SORTS = ("name", "price", "condition", "stock", "market", "flags", "updated")
BULK_PREVIEW = 200


def _usd_rate(db: Session) -> float | None:
    rate = get_usd_rate(db)
    return rate.rate if rate else None


def _usd(price: float | None, currency: Currency, usd_rate: float | None) -> float | None:
    if price is None:
        return None
    return price if currency == Currency.USD else (price / usd_rate if usd_rate else None)


def _aware(dt):
    # SQLite drops the timezone; we always store UTC
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def store_offers(db: Session, store: Store) -> list[Offer]:
    """All offers of the store except deleted ones, with what the table shows."""
    return db.scalars(
        select(Offer).where(Offer.store_id == store.id, Offer.removed_at.is_(None)).options(
            selectinload(Offer.product).selectinload(Product.category), selectinload(Offer.fraud_flags),
            selectinload(Offer.stocks), selectinload(Offer.barcodes))
    ).all()


def active_flags(offer: Offer) -> list[dict]:
    return [{"id": f.id, "type": f.type, "level": f.level.value, "reason_key": f.reason_key, "params": f.params,
             "source": f.source.value, "resolution": f.resolution, "admin_answer": f.admin_answer}
            for f in offer.fraud_flags if f.status == FlagStatus.active]


def disputed_flags(offer: Offer) -> list[dict]:
    """Phase 13: flags the seller disputed (waiting for the admin) or the admin took off — for the editor."""
    return [{"id": f.id, "type": f.type, "level": f.level.value, "reason_key": f.reason_key, "params": f.params,
             "status": f.status.value, "resolution": f.resolution, "dispute_comment": f.dispute_comment,
             "admin_answer": f.admin_answer} for f in offer.fraud_flags if f.status != FlagStatus.active]


def _flag_rank(offer: Offer) -> int:
    return max((LEVEL_RANK[f.level] for f in offer.fraud_flags if f.status == FlagStatus.active), default=0)


def _market(md, offer: Offer) -> dict | None:
    """The offer against the market median of its card (in stock, same condition), as on the market pages."""
    market = md.now((offer.product_id, market_condition(offer.condition.value)))
    usd = md.offer_usd.get(offer.id)
    if market is None or usd is None:
        return None
    diff = diff_pct(usd, market)
    return {"label": label(diff), "diff_pct": round(diff), "market_usd": round(market, 2)}


def offer_row(offer: Offer, market: dict | None = None) -> dict:
    product = offer.product
    return {
        "id": offer.id, "product_id": product.id, "name": product.normalized_name,
        "category": product.category.slug if product.category else "other", "raw_name": offer.raw_name,
        "price": offer.price, "currency": offer.currency.value, "condition": offer.condition.value,
        "is_in_stock": offer.is_in_stock, "note": offer.note, "updated_at": _aware(offer.updated_at),
        "flags": active_flags(offer), "market": market,
        "stocks": seller_stocks(offer),  # phase 12.1: by branch id; empty = the store does not track it by branch
        # phase 12.2, only the seller: purchase prices (offer currency) and the markup over the average one
        "cost_last": offer.cost_last, "cost_avg": offer.cost_avg, "markup": markup(offer),
        "barcodes": [{"id": b.id, "code": b.code} for b in offer.barcodes],  # phase 12.3
        "oversold": offer.oversold_at is not None,  # phase 12.4: "продано больше, чем по учёту"
    }


def markup(offer: Offer) -> float | None:
    if not offer.cost_avg or offer.price is None:
        return None
    return round((offer.price - offer.cost_avg) / offer.cost_avg * 100, 1)


def _matches(offer: Offer, row: dict, f: dict, stale_before) -> bool:
    q = (f.get("q") or "").strip().lower()
    if q and q not in row["name"].lower() and q not in offer.raw_name.lower() and not _barcode_hit(q, row):
        return False
    if f.get("category") and row["category"] != f["category"]:
        return False
    in_stock = offer.is_in_stock
    if f.get("branch"):  # phase 12.1: "в наличии / нет" in one branch
        row_ = row["stocks"].get(str(f["branch"]))
        in_stock = bool(row_ and row_["in_stock"])
    if f.get("stock") == "in" and not in_stock or f.get("stock") == "out" and in_stock:
        return False
    if f.get("flagged") and _flag_rank(offer) < LEVEL_RANK[FlagLevel.warning]:
        return False  # "with suspicions": warnings and dangers; a soft info note is not a suspicion
    if f.get("condition") and row["condition"] != f["condition"]:
        return False
    if f.get("stale") and _aware(offer.updated_at) >= stale_before:
        return False
    if f.get("market") and (row["market"] or {}).get("label") != f["market"]:
        return False
    if f.get("no_photo") and row.get("photo"):
        return False
    return True


def _barcode_hit(q: str, row: dict) -> bool:
    """"My goods" search by a barcode: the whole code (UPC-A as EAN-13 too) or its part of 4+ characters."""
    from app.services.barcodes import BarcodeError, normalize

    try:
        full = normalize(q).lower()
    except BarcodeError:
        full = None
    return any(b["code"].lower() == full or (len(q) >= 4 and q in b["code"].lower()) for b in row["barcodes"])


def _sort_key(sort: str, usd_rate: float | None):
    big = float("inf")
    return {
        "name": lambda r: r[1]["name"].lower(),
        "price": lambda r: _usd(r[0].price, r[0].currency, usd_rate) if r[0].price is not None else big,
        "condition": lambda r: r[1]["condition"],
        "stock": lambda r: not r[0].is_in_stock,
        "market": lambda r: r[1]["market"]["diff_pct"] if r[1]["market"] else big,
        "flags": lambda r: -_flag_rank(r[0]),
        "updated": lambda r: _aware(r[0].updated_at),
    }[sort]


def filtered_offers(db: Session, store: Store, f: dict) -> list[tuple[Offer, dict]]:
    md = market_data(db)
    stale_before = utcnow() - timedelta(days=STALE_DAYS)
    rows = []
    offers = store_offers(db, store)
    from app.services.photos import own_counts, published

    cards = published(db, "product", {o.product_id for o in offers})
    own = own_counts(db, store, [o.id for o in offers])
    for offer in offers:
        row = offer_row(offer, _market(md, offer))
        # Phase 14: the row's picture (own photo, else the card's) and how many there are
        mine = own.get(offer.id, {})
        row["photo"] = mine.get("thumb") or (cards[offer.product_id][0]["thumb"] if offer.product_id in cards else None)
        row["photos"] = {"own": mine.get("count", 0), "card": len(cards.get(offer.product_id, []))}
        if _matches(offer, row, f, stale_before):
            rows.append((offer, row))
    return rows


def list_offers(db: Session, store: Store, f: dict, sort: str = "updated", desc: bool = True, page: int = 1) -> dict:
    """"My goods": search, filters, sorting by any column, 50 rows a page."""
    rows = filtered_offers(db, store, f)
    rows.sort(key=_sort_key(sort if sort in SORTS else "updated", _usd_rate(db)), reverse=desc)
    start = (max(page, 1) - 1) * PAGE_SIZE
    return {"total": len(rows), "page_size": PAGE_SIZE, "items": [r for _, r in rows[start:start + PAGE_SIZE]]}


def overview(db: Session, store: Store) -> dict:
    """The cabinet front page: counts of the store's goods and the last price list."""
    stale_before = utcnow() - timedelta(days=STALE_DAYS)
    offers = store_offers(db, store)
    last = db.scalar(select(PriceImport).where(PriceImport.store_id == store.id, PriceImport.source == "file",
                                               PriceImport.status == "published").order_by(PriceImport.id.desc()))
    return {
        "total": len(offers),
        "in_stock": sum(o.is_in_stock for o in offers),
        "out_of_stock": sum(not o.is_in_stock for o in offers),
        "flagged": sum(_flag_rank(o) >= LEVEL_RANK[FlagLevel.warning] for o in offers),
        "stale": sum(_aware(o.updated_at) < stale_before for o in offers),
        "last_upload": {"id": last.id, "filename": last.filename, "created_at": _aware(last.created_at)} if last else None,
        "undo": _undo_brief(db, store),  # "Undo this upload" (phase 12)
        "categories": sorted({o.product.category.slug for o in offers if o.product.category}),
        "builds": build_counts(db, store),  # ready PCs live apart from the goods (phase B4)
        "chat": chat_counts(db, store),  # new messages and buyers waiting longer than a day (phase 10)
        "reservations": reservation_counts(db, store),  # new ones and the ones ending today (phase 11)
        "stock_mode": store.stock_mode,
        "stock": stock_overview(db, store),  # phase 12.2: running low, reservations without a reserve, movements
        "warehouse": overview_extra(db, store) if store.stock_mode == "stock" else None,  # phase 12.4
    }


def _undo_brief(db: Session, store: Store) -> dict | None:
    from app.services.undo import undo_deadline, undoable_id

    imp_id = undoable_id(db, store)
    if imp_id is None:
        return None
    imp = db.get(PriceImport, imp_id)
    return {"id": imp.id, "filename": imp.filename, "source": imp.source, "deadline": undo_deadline(imp)}


def _check_row(offer: Offer) -> dict:
    product = offer.product
    return {
        "raw_name": offer.raw_name, "name": product.normalized_name,
        "category": product.category.slug if product.category else "other", "brand": product.brand,
        "model": product.model, "specs": product.specs_json or {}, "price": offer.price,
        "currency": offer.currency.value, "condition": offer.condition.value, "is_in_stock": offer.is_in_stock,
        "note": offer.note,
    }


def recheck_flags(db: Session, offers: list[Offer], store: Store) -> None:
    """Anti-Fraud rules again after an edit (no AI request), market prices from other stores."""
    usd_rate = _usd_rate(db)
    market = market_prices(db, {o.product.match_key for o in offers}, store.id, usd_rate)
    for offer in offers:
        save_offer_flags(offer, check_offer(_check_row(offer), market_for(market, offer.product.match_key, offer.condition.value), usd_rate))


class EditError(ValueError):
    """A change that can't be made: the code goes to the client (texts are in ru.json)."""


def apply_changes(offer: Offer, changes: dict, source: str) -> None:
    """Price, currency, stock, condition, the seller's line and note. Writes price history and events."""
    if "raw_name" in changes:
        raw = (changes["raw_name"] or "").strip()
        if not raw:
            raise EditError("raw_name_required")
        offer.raw_name = raw
    if "note" in changes:
        offer.note = (changes["note"] or "").strip() or None
    old_price, old_currency = offer.price, offer.currency
    if changes.get("price") is not None:
        offer.price = changes["price"]
    if changes.get("currency"):
        offer.currency = Currency(changes["currency"])
    if changes.get("condition") and changes["condition"] != offer.condition.value:
        offer.condition = Condition(changes["condition"])
        offer.events.append(OfferEvent(field="condition", value=offer.condition.value, source=source))
    if changes.get("is_in_stock") is not None and changes["is_in_stock"] != offer.is_in_stock:
        if changes["is_in_stock"] and offer.price is None:
            raise EditError("price_required")
        if offer.stocks and offer.store is not None and offer.store.stock_mode == "stock":
            raise EditError("stock_mode")  # "Учёт остатков": quantities change only by operations (phase 12.2)
        set_general(object_session(offer), offer, changes["is_in_stock"])  # by branch too (phase 12.1)
        offer.events.append(OfferEvent(field="stock", value=str(int(offer.is_in_stock)), source=source))
    if offer.price is not None and (offer.price != old_price or offer.currency != old_currency):
        offer.price_history.append(PriceHistory(price=offer.price, currency=offer.currency))
    offer.updated_at = utcnow()


def update_offer(db: Session, store: Store, offer: Offer, changes: dict) -> dict:
    apply_changes(offer, changes, "edit")
    recheck_flags(db, [offer], store)
    db.commit()
    return offer_row(offer, _market(market_data(db), offer))


def remove_offer(db: Session, offer: Offer) -> None:
    """"Delete my offer": off the catalog and the cabinet, the card and the price history stay."""
    offer.events.append(OfferEvent(field="removed", value="1", source="edit"))
    offer.removed_at = utcnow()
    offer.is_in_stock = False
    offer.price = None
    from app.services.photos import delete_owner

    delete_owner(db, "offer", offer.id)  # phase 14: the store's photos of the item go with it
    db.commit()


def other_stores(db: Session, product: Product, store: Store) -> int:
    """How many other stores sell this card now (deleted offers do not count)."""
    return len(set(db.scalars(select(Offer.store_id).where(
        Offer.product_id == product.id, Offer.store_id != store.id, Offer.removed_at.is_(None)))))


def _card(product: Product) -> dict:
    specs = {k: v for k, v in (product.specs_json or {}).items() if k not in (INFERRED, SUSPECT)}
    return {"name": product.normalized_name, "brand": product.brand, "model": product.model,
            "category": product.category.slug if product.category else "other", "specs": specs}


def offer_detail(db: Session, store: Store, offer: Offer) -> dict:
    """The editor: the offer, its card, who else sells it and the history of this offer by dates."""
    product = offer.product
    history = [{"at": _aware(h.recorded_at), "field": "price", "price": h.price, "currency": h.currency.value}
               for h in offer.price_history if not h.is_demo]
    history += [{"at": _aware(e.recorded_at), "field": e.field, "value": e.value, "source": e.source} for e in offer.events]
    history.sort(key=lambda h: h["at"], reverse=True)
    pending = db.scalar(select(ProductFix).where(ProductFix.product_id == product.id, ProductFix.store_id == store.id,
                                                 ProductFix.status == "pending").order_by(ProductFix.id.desc()))
    return {
        **offer_row(offer, _market(market_data(db), offer)),
        "card": _card(product), "other_stores": other_stores(db, product, store),
        "history": history, "pending_fix": pending.after if pending else None,
        "disputed_flags": disputed_flags(offer),
    }


def edit_card(db: Session, store: Store, offer: Offer, data: dict) -> dict:
    """The shared card. Only this store sells it -> changed at once (dictionary, normalizer, new key); the key of
    another card -> {"status": "exists"}, the seller may move the offer there. Other stores sell it -> a suggestion."""
    product = offer.product
    category = db.scalar(select(Category).where(Category.slug == data["category"]))
    if category is None:
        raise EditError("unknown_category")
    if not (data.get("name") or data.get("model") or "").strip():
        raise EditError("name_required")
    if other_stores(db, product, store):
        after = {k: data.get(k) for k in ("name", "brand", "model", "category")} | {"specs": data.get("specs") or {}}
        db.add(ProductFix(product_id=product.id, store_id=store.id, before=_card(product), after=after))
        from app.services import notifications as notify  # phase 12.5

        notify.notify_admins(db, "fix_suggested", "/admin/fixes", store=store.name, name=product.normalized_name)
        db.commit()
        return {"status": "suggested"}
    brand, name, specs, key = card_fields(category, data.get("brand"), data.get("model"), data.get("name"),
                                          data.get("specs") or {})
    existing = db.scalar(select(Product).where(Product.match_key == key, Product.id != product.id))
    if existing is not None:
        return {"status": "exists", "product": product_brief(existing)}
    product.category, product.brand, product.model = category, brand, data.get("model")
    product.normalized_name, product.specs_json, product.match_key = name, specs, key
    db.flush()
    recheck_flags(db, [offer], store)
    db.commit()
    return {"status": "applied", "card": _card(product)}


def relink(db: Session, store: Store, offer: Offer, product: Product) -> dict:
    """"Not this product": the offer moves to another card. The old card, left without offers, drops out of the
    catalog by itself (the catalog shows only cards with offers) and is not deleted."""
    if product.id == offer.product_id:
        return offer_row(offer)
    mine = db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.product_id == product.id))
    if mine is not None:
        raise EditError("offer_exists")  # one offer per card per store
    offer.product = product
    offer.events.append(OfferEvent(field="product", value=str(product.id), source="edit"))
    offer.updated_at = utcnow()
    db.flush()
    from app.services.barcodes import refresh_offer

    refresh_offer(db, offer)  # phase 12.3: the codes of the offer follow it to the other card
    recheck_flags(db, [offer], store)
    db.commit()
    return offer_row(offer)


def round_price(value: float, currency: Currency) -> float:
    """Bulk prices: sums to 1 000 sum, dollars to whole dollars (under $10 — to 10 cents)."""
    if currency == Currency.UZS:
        return max(1000, round(value / 1000) * 1000)
    return round(value, 1) if value < 10 else float(round(value))


def set_branch_stock(db: Session, store: Store, offer: Offer, items: list[dict]) -> dict:
    """The editor and the inline cell of "My goods": a quantity per branch, "есть / нет", or "не указано"."""
    from app.services.branches import clear_stock, store_branches

    from app.services.stock import journal

    if store.stock_mode == "stock":
        raise EditError("stock_mode")
    ids = {b.id for b in store_branches(db, store.id)}
    was = offer.is_in_stock
    with journal("manual", user_id=store.user_id):
        _set_branch_items(offer, items, ids)
    if was != offer.is_in_stock:
        offer.events.append(OfferEvent(field="stock", value=str(int(offer.is_in_stock)), source="edit"))
    offer.updated_at = utcnow()
    db.commit()
    return offer_row(offer, _market(market_data(db), offer))


def _set_branch_items(offer: Offer, items: list[dict], ids: set[int]) -> None:
    from app.services.branches import clear_stock

    for it in items:
        if it["branch_id"] not in ids:
            raise EditError("branch")
        if it.get("clear"):
            clear_stock(offer, it["branch_id"])
        elif it.get("quantity") is not None or it.get("present") is not None:
            if offer.price is None and (it.get("present") or (it.get("quantity") or 0) > 0):
                raise EditError("price_required")
            set_stock(offer, it["branch_id"], quantity=it.get("quantity"), present=it.get("present"))


def _branch_changes(offer: Offer, branch_id: int, present: bool) -> bool:
    row = next((s for s in offer.stocks if s.branch_id == branch_id), None)
    if present:
        return offer.price is not None and not (row is not None and available(row))
    return row is None or available(row)


def bulk(db: Session, store: Store, offers: list[Offer], action: str, percent: float | None, apply: bool,
         branch_id: int | None = None) -> dict:
    """Bulk actions: off sale, back on sale (only priced offers), price +-N%, "в филиале …: есть / нет" (phase
    12.1). apply=False is the preview."""
    from app.services.stock import journal

    if action in ("branch_on", "branch_off") and store.stock_mode == "stock":
        raise EditError("stock_mode")
    changed: list[tuple[Offer, dict]] = []
    for offer in offers:
        if action in ("branch_on", "branch_off"):
            if branch_id and _branch_changes(offer, branch_id, action == "branch_on"):
                changed.append((offer, {"branch": action == "branch_on"}))
            continue
        if action == "off" and offer.is_in_stock:
            changed.append((offer, {"is_in_stock": False}))
        elif action == "on" and not offer.is_in_stock and offer.price is not None:
            changed.append((offer, {"is_in_stock": True}))
        elif action == "price" and offer.price is not None:
            new = round_price(offer.price * (1 + percent / 100), offer.currency)
            if new != offer.price:
                changed.append((offer, {"price": new}))
    preview = [{"id": o.id, "name": o.product.normalized_name, "currency": o.currency.value,
                "old_price": o.price, "price": c.get("price", o.price)} for o, c in changed[:BULK_PREVIEW]]
    if apply:
        for offer, c in changed:
            if "branch" in c:
                was = offer.is_in_stock
                with journal("manual", user_id=store.user_id):
                    set_stock(offer, branch_id, present=c["branch"])
                if was != offer.is_in_stock:
                    offer.events.append(OfferEvent(field="stock", value=str(int(offer.is_in_stock)), source="bulk"))
                offer.updated_at = utcnow()
                continue
            apply_changes(offer, c, "bulk")
        recheck_flags(db, [o for o, _ in changed], store)
        db.commit()
    return {"count": len(changed), "selected": len(offers), "items": preview, "applied": apply}
