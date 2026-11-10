"""Branches of a store and stock by branch (phase 12.1).

One store = one catalog, one price list and one cabinet; it has one or more branches (points). Exactly one branch
is the main one: its city, address, hours and map are copied to the store row, so the code that reads the store's
address (chat, builds, old reservations) keeps working.

Stock: an offer may have a row per branch (OfferStock). Available = quantity - reserved (reserved comes in 12.2);
quantity None = "есть, количество не указано". `OfferStock.in_stock` keeps "available > 0" so SQL can filter by it.
An offer without rows is "the store does not keep stock by branch": its general flag is used ("уточняйте").
When an offer has rows, its general Offer.is_in_stock = available in at least one branch.
The buyer never sees a quantity, only "есть / нет".
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, or_, select, true
from sqlalchemy.orm import Session

from app.db.models import Branch, Offer, OfferStock, Reservation, Store, StoreKind, utcnow
from app.services.maps import parse_map_url

STALE_DAYS = 3  # older stock data of a branch: "давно не обновлялось, уточняйте у магазина"
LOCATION_FIELDS = ("city", "address", "hours", "map_url", "map_lat", "map_lon")


class BranchError(ValueError):
    """The code goes to the client (texts in ru.json branches.error.*)."""


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


# --- the branches themselves ---------------------------------------------------------------------------------------

def store_branches(db: Session, store_id: int) -> list[Branch]:
    return list(db.scalars(select(Branch).where(Branch.store_id == store_id)
                           .order_by(Branch.is_main.desc(), Branch.id)))


def main_branch(db: Session, store_id: int) -> Branch | None:
    return db.scalar(select(Branch).where(Branch.store_id == store_id, Branch.is_main.is_(True)))


def sync_store(store: Store, main: Branch) -> None:
    """The main branch is also the store's own address (store row)."""
    for f in LOCATION_FIELDS:
        setattr(store, f, getattr(main, f))
    store.district = main.landmark


def ensure_main_branch(db: Session, store: Store) -> Branch | None:
    """The store's address -> its main branch, once, without losing anything (a store without an address: none)."""
    if store.kind != StoreKind.shop or store.is_archive:
        return None
    main = main_branch(db, store.id)
    if main is not None:
        return main
    if db.scalar(select(Branch.id).where(Branch.store_id == store.id).limit(1)):
        first = store_branches(db, store.id)[0]
        first.is_main = True
        return first
    if not (store.address or "").strip():
        return None
    main = Branch(store_id=store.id, city=store.city or "tashkent", address=store.address, landmark=store.district,
                  hours=store.hours, map_url=store.map_url, map_lat=store.map_lat, map_lon=store.map_lon, is_main=True)
    db.add(main)
    db.flush()
    return main


def migrate_branches(db: Session) -> int:
    """Startup: every shop with an address gets its main branch; reservations without a branch -> the main one."""
    made = 0
    for store in db.scalars(select(Store).where(Store.kind == StoreKind.shop, Store.is_archive.is_(False))):
        had = main_branch(db, store.id) is not None
        main = ensure_main_branch(db, store)
        if main is None:
            continue
        made += not had
        for r in db.scalars(select(Reservation).where(Reservation.store_id == store.id, Reservation.branch_id.is_(None))):
            r.branch_id = main.id
    db.commit()
    return made


def _clean(value) -> str | None:
    return (value or "").strip() or None if isinstance(value, str) or value is None else value


def save_branch(db: Session, store: Store, data: dict, branch: Branch | None = None) -> Branch:
    """Add or change a branch: address and landmark are required, the map link is checked (as in phase 12)."""
    from app.db.seed import CITIES

    city = data.get("city")
    address, landmark = _clean(data.get("address")), _clean(data.get("landmark"))
    if city not in CITIES:
        raise BranchError("city")
    if not address or len(address) < 3:
        raise BranchError("address")
    if not landmark or len(landmark) < 2:
        raise BranchError("landmark")
    try:
        map_url, lat, lon = parse_map_url(data.get("map_url"))
    except ValueError:
        raise BranchError("map_url")
    first = not store_branches(db, store.id)
    if branch is None:
        branch = Branch(store_id=store.id, is_main=first)
        db.add(branch)
    branch.name, branch.city, branch.address, branch.landmark = _clean(data.get("name")), city, address, landmark
    branch.hours, branch.phone = _clean(data.get("hours")), _clean(data.get("phone"))
    branch.map_url, branch.map_lat, branch.map_lon = map_url, lat, lon
    db.flush()
    if branch.is_main:
        sync_store(store, branch)
    return branch


def make_main(db: Session, store: Store, branch: Branch) -> None:
    for b in store_branches(db, store.id):
        b.is_main = b.id == branch.id
    db.flush()
    sync_store(store, branch)


def delete_branch(db: Session, store: Store, branch: Branch) -> None:
    """The main branch and the last one stay: first make another branch the main one."""
    if branch.is_main:
        raise BranchError("delete_main")
    if len(store_branches(db, store.id)) <= 1:
        raise BranchError("delete_last")
    main = main_branch(db, store.id)
    for r in db.scalars(select(Reservation).where(Reservation.branch_id == branch.id)):
        r.branch_id = main.id
    offer_ids = list(db.scalars(select(OfferStock.offer_id).where(OfferStock.branch_id == branch.id)))
    db.delete(branch)
    db.flush()
    for offer in db.scalars(select(Offer).where(Offer.id.in_(offer_ids))):
        db.expire(offer, ["stocks"])
        recompute_offer(offer)


def branch_public(branch: Branch, store: Store) -> dict:
    """A branch as the buyer sees it (no columns of the price list)."""
    return {"id": branch.id, "name": branch.name, "city": branch.city, "address": branch.address,
            "landmark": branch.landmark, "district": branch.landmark, "hours": branch.hours,
            "phone": branch.phone or store.phone, "own_phone": branch.phone, "map_url": branch.map_url,
            "map_lat": branch.map_lat, "map_lon": branch.map_lon, "is_main": branch.is_main}


def branch_seller(branch: Branch, store: Store) -> dict:
    return {**branch_public(branch, store), "columns": branch.columns_json or []}


# --- stock by branch -----------------------------------------------------------------------------------------------

def available(stock: OfferStock) -> bool:
    """"Есть в филиале": available (quantity - reserved) > 0; no quantity = the seller's "есть" mark."""
    if stock.quantity is None:
        return bool(stock.in_stock)
    return stock.quantity - (stock.reserved or 0) > 0


def is_stale(stock: OfferStock) -> bool:
    at = _aware(stock.updated_at)
    return at is None or datetime.now(timezone.utc) - at > timedelta(days=STALE_DAYS)


def set_stock(offer: Offer, branch_id: int, quantity: int | None = None, present: bool | None = None) -> OfferStock:
    """Set one branch: a quantity (>= 0), or only "есть / нет" (quantity unknown). Recomputes the offer."""
    from app.services.stock import record  # the journal of movements (phase 12.2)

    row = next((s for s in offer.stocks if s.branch_id == branch_id), None)
    if row is None:
        row = OfferStock(branch_id=branch_id, reserved=0)
        offer.stocks.append(row)
    q0, r0 = row.quantity, row.reserved or 0
    if quantity is not None:
        row.quantity = max(0, int(quantity))
    elif present is not None:
        row.quantity = None if present else 0
        row.in_stock = bool(present)
    row.in_stock = available(row) if row.quantity is not None else bool(row.in_stock)
    row.updated_at = utcnow()
    recompute_offer(offer)
    record(offer, row, q0, r0)
    return row


def set_general(db: Session, offer: Offer, in_stock: bool) -> None:
    """The seller's general "в наличии / нет" for an offer tracked by branch: "нет" = "нет" in every branch;
    "есть" with no branch available = "есть" in the main branch. An offer not tracked: only the general flag."""
    if not offer.stocks:
        offer.is_in_stock = in_stock
        return
    if not in_stock:
        for s in list(offer.stocks):
            set_stock(offer, s.branch_id, quantity=0)
    elif not any(available(s) for s in offer.stocks):
        main = main_branch(db, offer.store_id)
        set_stock(offer, main.id if main else offer.stocks[0].branch_id, present=True)


def seller_stocks(offer: Offer) -> dict:
    """The seller's own view (never the buyer's): {branch_id: {quantity, in_stock, stale}}."""
    return {str(s.branch_id): {"quantity": s.quantity, "reserved": s.reserved or 0, "in_stock": available(s),
                               "stale": is_stale(s)} for s in offer.stocks}


def clear_stock(offer: Offer, branch_id: int) -> None:
    """"Не указано": the branch row goes away (the offer is not tracked there)."""
    _journal_gone(offer, [s for s in offer.stocks if s.branch_id == branch_id])
    offer.stocks[:] = [s for s in offer.stocks if s.branch_id != branch_id]
    recompute_offer(offer)


def recompute_offer(offer: Offer) -> None:
    """The general "в наличии" of a tracked offer = available in at least one branch."""
    if offer.stocks:
        offer.is_in_stock = any(available(s) for s in offer.stocks)


def stock_state(offer: Offer) -> dict:
    """For the undo snapshot: {branch_id: [quantity, in_stock, updated_at]}."""
    return {str(s.branch_id): [s.quantity, bool(s.in_stock), _aware(s.updated_at).isoformat() if s.updated_at else None]
            for s in offer.stocks}


def _journal_gone(offer: Offer, rows: list[OfferStock]) -> None:
    """A branch row removed ("не указано", undo): a journal line "the quantity is no longer known"."""
    from app.services.stock import record

    for s in rows:
        if s.quantity is not None or s.reserved:
            q0, r0 = s.quantity, s.reserved or 0
            gone = OfferStock(branch_id=s.branch_id, quantity=None, reserved=s.reserved or 0)
            record(offer, gone, q0, r0)


def restore_stock(offer: Offer, state: dict) -> None:
    """Undo of an upload: the branch rows go back to the snapshot; the journal gets reverse lines (the kind and
    the upload come from the caller's journal(...)). Reserves stay as they are."""
    from app.services.stock import record

    keep = {int(k) for k in state}
    _journal_gone(offer, [s for s in offer.stocks if s.branch_id not in keep])
    offer.stocks[:] = [s for s in offer.stocks if s.branch_id in keep]
    for key, (quantity, present, at) in state.items():
        row = next((s for s in offer.stocks if s.branch_id == int(key)), None)
        if row is None:
            row = OfferStock(branch_id=int(key), reserved=0)
            offer.stocks.append(row)
        q0, r0 = row.quantity, row.reserved or 0
        row.quantity, row.in_stock = quantity, present
        if quantity is not None:
            row.in_stock = quantity - (row.reserved or 0) > 0
        row.updated_at = datetime.fromisoformat(at) if at else utcnow()
        record(offer, row, q0, r0)


def offer_branches(offer: Offer, branches: list[Branch], store: Store, city: str | None = None) -> dict:
    """The buyer's view of an offer by branch: "есть в N из M" (in the city, or everywhere), the list ✓ / ✗ with
    addresses (the city's branches first). Never a quantity. tracked=False: "уточняйте у магазина"."""
    rows = {s.branch_id: s for s in offer.stocks}
    tracked = bool(rows)
    items = []
    for b in branches:
        s = rows.get(b.id)
        items.append({**branch_public(b, store),
                      "in_stock": (s is not None and available(s)) if tracked else None,
                      "updated_at": s.updated_at if s is not None else None,
                      "stale": tracked and s is not None and is_stale(s)})
    items.sort(key=lambda i: (city is not None and i["city"] != city, not i["is_main"], i["id"]))
    scope = [i for i in items if city is None or i["city"] == city]
    return {"tracked": tracked, "branches": items, "available": sum(1 for i in scope if i["in_stock"]),
            "total": len(scope), "stale": any(i["stale"] for i in scope if i["in_stock"] is not None)}


# --- SQL: city and stock in the city -------------------------------------------------------------------------------

def in_city(city: str | None):
    """Offers of the stores present in a city: a branch there (or the store's own city: Telegram, no branches)."""
    if not city:
        return true()
    return or_(Offer.store_id.in_(select(Store.id).where(Store.city == city)),
               Offer.store_id.in_(select(Branch.store_id).where(Branch.city == city)))


def store_in_city(city: str):
    return or_(Store.city == city, Store.id.in_(select(Branch.store_id).where(Branch.city == city)))


def in_stock_in(city: str | None):
    """"В наличии" (in a city): available in a branch of that city; an offer without stock by branch — its general
    flag. Without a city — the general flag (= available somewhere)."""
    if not city:
        return Offer.is_in_stock.is_(True)
    tracked = exists().where(OfferStock.offer_id == Offer.id)
    there = exists().where(OfferStock.offer_id == Offer.id, OfferStock.in_stock.is_(True),
                           OfferStock.branch_id == Branch.id, Branch.city == city)
    return or_(and_(~tracked, Offer.is_in_stock.is_(True)), there)
