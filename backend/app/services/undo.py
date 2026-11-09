""""Undo this upload" (phase 12): the last published price list of a store goes back as if it never was.

At the publication publish_import saves a snapshot (PriceImport.undo_json):
  offers   - every offer the upload touched: its state before (None = created by this upload) and after;
  history  - price_history rows the upload added; events - offer_events rows it added;
  products - cards the upload created.
Undo returns the "before" values, deletes the upload's history and events, deletes its new offers (or takes them
off sale when a reservation or a conversation is tied to them) and leaves new cards without offers: the catalog
shows only cards with offers, so they are hidden, not deleted. An offer the seller changed by hand after the upload
(editor, inline edit, bulk action, manual adding) is a conflict: it stays as it is.
Manual adding ("Find in the catalog", "Create a card"), Telegram posts and builds are never undone.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Condition, Conversation, Currency, ImportStatus, Offer, OfferEvent, PriceHistory, PriceImport, Product,
    Reservation, Store, TopicKind, utcnow,
)

UNDO_DAYS = 7
UNDO_SOURCES = ("file", "text")  # a price list file or a pasted post
STATE_FIELDS = ("price", "currency", "is_in_stock", "condition", "note", "product_id", "removed_at")
SAME_SECOND = timedelta(seconds=1)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _iso(dt: datetime | None) -> str | None:
    return _aware(dt).isoformat() if dt is not None else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def offer_state(o: Offer) -> dict:
    return {"price": o.price, "currency": o.currency.value, "is_in_stock": o.is_in_stock,
            "condition": o.condition.value, "note": o.note, "product_id": o.product_id,
            "removed_at": _iso(o.removed_at), "updated_at": _iso(o.updated_at)}


def make_snapshot(before: dict[int, dict | None], offers: list[Offer], history: list[PriceHistory],
                  events: list[OfferEvent], products: list[Product]) -> dict:
    """Called after a flush: every object has its id."""
    return {
        "offers": [{"id": o.id, "before": before.get(o.id), "after": offer_state(o)} for o in offers],
        "history": [h.id for h in history if h.id is not None],
        "events": [e.id for e in events if e.id is not None],
        "products": [p.id for p in products if p.id is not None],
    }


def _on_sale(state: dict) -> bool:
    return bool(state["is_in_stock"]) and state["removed_at"] is None


def last_upload(db: Session, store: Store) -> PriceImport | None:
    """The store's last published (or undone) file or post: only it may be undone."""
    return db.scalar(
        select(PriceImport).where(
            PriceImport.store_id == store.id, PriceImport.source.in_(UNDO_SOURCES),
            PriceImport.status.in_((ImportStatus.published, ImportStatus.undone)))
        .order_by(PriceImport.published_at.desc().nulls_last(), PriceImport.id.desc()))


def undo_deadline(imp: PriceImport) -> datetime | None:
    return _aware(imp.published_at) + timedelta(days=UNDO_DAYS) if imp.published_at else None


def can_undo(db: Session, imp: PriceImport) -> str | None:
    """None when the upload can be undone, else the reason code (texts in ru.json undo.error.*)."""
    if imp.status == ImportStatus.undone:
        return "already_undone"
    if imp.status != ImportStatus.published or not imp.undo_json or imp.source not in UNDO_SOURCES:
        return "not_undoable"
    store = db.get(Store, imp.store_id)
    last = last_upload(db, store)
    if last is None or last.id != imp.id:
        return "not_last"
    if datetime.now(timezone.utc) > undo_deadline(imp):
        return "too_old"
    return None


def undoable_id(db: Session, store: Store) -> int | None:
    last = last_upload(db, store)
    return last.id if last is not None and can_undo(db, last) is None else None


def _changed_by_hand(offer: Offer, after: dict) -> bool:
    """The seller changed the offer after the upload: any field differs or the row was saved again later."""
    now = offer_state(offer)
    if any(now[f] != after[f] for f in STATE_FIELDS):
        return True
    then = _parse(after["updated_at"])
    return then is not None and offer.updated_at is not None and _aware(offer.updated_at) - then > SAME_SECOND


def _has_ties(db: Session, offer: Offer) -> bool:
    """A reservation or a conversation about the offer: it must not disappear under the buyer."""
    if db.scalar(select(Reservation.id).where(Reservation.offer_id == offer.id).limit(1)):
        return True
    return bool(db.scalar(select(Conversation.id).where(
        Conversation.topic_kind == TopicKind.offer, Conversation.topic_id == offer.id).limit(1)))


def _item(offer: Offer, before: dict | None, after: dict) -> dict:
    return {"offer_id": offer.id, "name": offer.product.normalized_name, "raw_name": offer.raw_name,
            "price": before["price"] if before else None, "currency": (before or after)["currency"],
            "old_price": after["price"], "old_currency": after["currency"]}


def plan_undo(db: Session, imp: PriceImport) -> dict:
    """"What will come back": the same groups as "what will change" (phase B3), nothing is written.

    prices - the old price comes back; back_in_stock - taken off sale by the upload, comes back on sale;
    out_of_stock - put on sale by the upload, goes off sale again; removed_new - new offers that go away;
    kept_new - new offers with a reservation or a conversation: off sale, not deleted; conflicts - changed by hand.
    """
    snap = imp.undo_json or {}
    ids = [o["id"] for o in snap.get("offers", [])]
    offers = {o.id: o for o in db.scalars(
        select(Offer).where(Offer.id.in_(ids)).options(selectinload(Offer.product)))}
    groups = {k: [] for k in ("prices", "back_in_stock", "out_of_stock", "removed_new", "kept_new", "conflicts")}
    for entry in snap.get("offers", []):
        offer = offers.get(entry["id"])
        if offer is None:
            continue  # deleted since: nothing to return
        before, after = entry["before"], entry["after"]
        item = _item(offer, before, after)
        if _changed_by_hand(offer, after):
            groups["conflicts"].append(item)
        elif before is None:
            groups["kept_new" if _has_ties(db, offer) else "removed_new"].append(item)
        else:
            if before["price"] is not None and (before["price"], before["currency"]) != (after["price"], after["currency"]):
                groups["prices"].append(item)
            if _on_sale(before) and not _on_sale(after):
                groups["back_in_stock"].append(item)
            elif not _on_sale(before) and _on_sale(after):
                groups["out_of_stock"].append(item)
    return {"import_id": imp.id, "filename": imp.filename, "deadline": undo_deadline(imp), **groups}


def undo_import(db: Session, imp: PriceImport) -> dict:
    """Returns the store's offers to the state before the upload (see the module doc). Counts as in plan_undo."""
    from app.services.cabinet import recheck_flags  # cabinet imports the importer that imports this module

    plan = plan_undo(db, imp)
    snap = imp.undo_json or {}
    store = db.get(Store, imp.store_id)
    conflict_ids = {i["offer_id"] for i in plan["conflicts"]}
    entries = [e for e in snap.get("offers", []) if e["id"] not in conflict_ids]
    offers = {o.id: o for o in db.scalars(select(Offer).where(Offer.id.in_([e["id"] for e in entries])))}
    # The upload's own price history and events of the offers that go back (the conflicts keep theirs)
    db.execute(delete(PriceHistory).where(PriceHistory.id.in_(snap.get("history", [])),
                                          PriceHistory.offer_id.in_(offers)))
    db.execute(delete(OfferEvent).where(OfferEvent.id.in_(snap.get("events", [])), OfferEvent.offer_id.in_(offers)))
    db.expire_all()
    kept_new = {i["offer_id"] for i in plan["kept_new"]}
    recheck: list[Offer] = []
    for entry in entries:
        offer = offers.get(entry["id"])
        if offer is None:
            continue
        before = entry["before"]
        if before is None:
            if offer.id in kept_new:
                offer.is_in_stock = False
                offer.events.append(OfferEvent(field="stock", value="0", source="undo"))
                recheck.append(offer)
            else:
                db.delete(offer)
            continue
        offer.price = before["price"]
        offer.currency = Currency(before["currency"])
        offer.is_in_stock = before["is_in_stock"]
        offer.condition = Condition(before["condition"])
        offer.note = before["note"]
        offer.product_id = before["product_id"]
        offer.removed_at = _parse(before["removed_at"])
        db.flush()
        # The freshness of "recommended" goes back too (onupdate would set "now")
        if before["updated_at"]:
            db.execute(Offer.__table__.update().where(Offer.id == offer.id)
                       .values(updated_at=_parse(before["updated_at"])))
        recheck.append(offer)
    db.flush()
    db.expire_all()
    recheck = [o for o in db.scalars(select(Offer).where(Offer.id.in_([o.id for o in recheck]))
                                     .options(selectinload(Offer.product), selectinload(Offer.fraud_flags)))]
    if recheck:
        recheck_flags(db, recheck, store)  # Anti-Fraud again: the old prices meet the market again
    # Cards the upload created and that now have no offer: out of the catalog by themselves (kept for the history)
    hidden = [pid for pid in snap.get("products", [])
              if db.scalar(select(Offer.id).where(Offer.product_id == pid).limit(1)) is None]
    result = {k: len(plan[k]) for k in ("prices", "back_in_stock", "out_of_stock", "removed_new", "kept_new",
                                        "conflicts")}
    result["hidden_cards"] = len(hidden)
    imp.status = ImportStatus.undone
    imp.undone_at = utcnow()
    imp.undo_json = {**snap, "result": result}
    db.commit()
    return result

