"""Phase 12.4 "Склад как в жизни": the store's warehouse and the stocktake ("Ревизия").

The warehouse is a Branch with is_warehouse — one per store, a place of storage (no address for buyers). When the
store has it, receipts go there and branches get goods by "Выкладка" (stock.put_out). The buyer never sees it:
`branches.shop_rows`, `Store.branches` and the SQL of the city leave it out. Switching it off with stock asks
first: the stock goes to a branch ("Выкладка" lines) or is written off (adjustments) — always through the journal.

A stocktake counts one place: every scan of an item on the shelf is +1 in `counts_json` (saved on the server at
once, so a reload or a closed page loses nothing). "Завершить подсчёт" builds the differences against the books:
match / short / over / missing (the books say it is here, it was never scanned). The seller may leave lines out;
"Применить" makes the others "inventory" lines of the journal with the stocktake's document number.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Branch, Category, Offer, OfferStock, Product, Reservation, ReservationStatus, Stocktake, Store, User, utcnow
from app.services import stock
from app.services.branches import shop_rows, store_branches, warehouse_of
from app.services.stock import StockError, free, move, new_doc

OPEN = ("counting", "review")


# --- the warehouse --------------------------------------------------------------------------------------------------

def _forget_cache(db: Session) -> None:
    db.info.pop("warehouse_ids", None)


def warehouse_rows(db: Session, store: Store) -> list[tuple[OfferStock, Offer]]:
    wh = warehouse_of(db, store.id)
    if wh is None:
        return []
    return list(db.execute(select(OfferStock, Offer).join(Offer).where(
        OfferStock.branch_id == wh.id, OfferStock.quantity > 0)).all())


def set_warehouse(db: Session, store: Store, on: bool, user: User | None, action: str | None = None,
                  branch_id: int | None = None) -> dict:
    """On: the warehouse row is made (or the old one is used again). Off with stock: `action` "move" to
    `branch_id` or "write_off"; without an action -> StockError("warehouse_stock") with how much is there."""
    uid = user.id if user else None
    if on:
        wh = warehouse_of(db, store.id)
        if wh is None:
            wh = Branch(store_id=store.id, name=None, city=store.city or "tashkent", address="", is_warehouse=True,
                        is_main=False)
            db.add(wh)
        store.has_warehouse = True
        _forget_cache(db)
        db.commit()
        return {"has_warehouse": True, "moved": 0, "written_off": 0}
    rows = warehouse_rows(db, store)
    result = {"has_warehouse": False, "moved": 0, "written_off": 0}
    if rows and action not in ("move", "write_off"):
        raise StockError("warehouse_stock", positions=len(rows), units=sum(r.quantity for r, _ in rows))
    if rows and action == "move":
        if branch_id not in {b.id for b in store_branches(db, store.id)}:
            raise StockError("branch")
    doc = new_doc("move" if action == "move" else "adjust")
    wh = warehouse_of(db, store.id)
    for row, offer in rows:
        qty = free(row)
        if action == "move" and qty > 0:
            move(offer, wh.id, "move_out", qty, user_id=uid, doc=doc)
            move(offer, branch_id, "move_in", qty, user_id=uid, doc=doc)
            result["moved"] += qty
        left = next(s for s in offer.stocks if s.branch_id == wh.id).quantity or 0
        if left:
            move(offer, wh.id, "adjust", set_to=0, user_id=uid, doc=doc, reason="wh_off", force=True)
            result["written_off"] += left
    store.has_warehouse = False
    _forget_cache(db)
    db.commit()
    return result


def warehouse_out(db: Session, store: Store) -> dict | None:
    wh = warehouse_of(db, store.id) if store.has_warehouse else None
    return {"id": wh.id, "name": wh.name, "is_warehouse": True} if wh is not None else None


# --- the stocktake --------------------------------------------------------------------------------------------------

def _place(db: Session, store: Store, branch_id: int) -> Branch:
    branch = next((b for b in store_branches(db, store.id, warehouse=True) if b.id == branch_id), None)
    if branch is None:
        raise StockError("branch")
    return branch


def get(db: Session, store: Store, stocktake_id: int) -> Stocktake:
    st = db.get(Stocktake, stocktake_id)
    if st is None or st.store_id != store.id:
        raise StockError("stocktake")
    return st


def start(db: Session, store: Store, user: User, branch_id: int, categories: list[str] | None = None) -> Stocktake:
    """A new count of one place; an unfinished one of the same place is continued instead."""
    if not stock.is_stock_mode(store):
        raise StockError("mode_off")
    _place(db, store, branch_id)
    st = db.scalar(select(Stocktake).where(Stocktake.store_id == store.id, Stocktake.branch_id == branch_id,
                                           Stocktake.status.in_(OPEN)))
    if st is not None:
        return st
    known = set(db.scalars(select(Category.slug)))
    st = Stocktake(store_id=store.id, branch_id=branch_id, status="counting", doc=new_doc("inventory"),
                   categories_json=[c for c in (categories or []) if c in known], counts_json={}, result_json=[],
                   excluded_json=[], user_id=user.id)
    db.add(st)
    db.commit()
    return st


def _offer(db: Session, store: Store, offer_id: int) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None or offer.store_id != store.id:
        raise StockError("offer")
    return offer


def count(db: Session, store: Store, st: Stocktake, offer_id: int, delta: int | None = 1,
          set_to: int | None = None) -> Stocktake:
    """A scan: +1 ("насчитано"); `set_to` — the seller corrected the number (0 removes the line)."""
    if st.status != "counting":
        raise StockError("stocktake_state")
    _offer(db, store, offer_id)
    counts = dict(st.counts_json or {})
    key = str(offer_id)
    value = int(set_to) if set_to is not None else counts.get(key, 0) + int(delta or 0)
    if value <= 0:
        counts.pop(key, None)
    else:
        counts[key] = min(value, 1_000_000)
    st.counts_json = counts  # a new dict: JSON columns see only a new value
    db.commit()
    return st


def _expected(db: Session, store: Store, st: Stocktake) -> dict[int, int]:
    """The books of the place: offers with a quantity > 0 there (in the chosen categories)."""
    q = (select(OfferStock.offer_id, OfferStock.quantity).join(Offer, OfferStock.offer_id == Offer.id)
         .join(Product, Offer.product_id == Product.id)
         .where(Offer.store_id == store.id, OfferStock.branch_id == st.branch_id, OfferStock.quantity > 0,
                Offer.removed_at.is_(None)))
    if st.categories_json:
        q = q.join(Category, Product.category_id == Category.id).where(Category.slug.in_(st.categories_json))
    return {oid: qty for oid, qty in db.execute(q).all()}


def _names(db: Session, ids) -> dict[int, tuple[str, str]]:
    rows = db.execute(select(Offer.id, Product.normalized_name, Category.slug).join(Product, Offer.product_id == Product.id)
                      .outerjoin(Category, Product.category_id == Category.id).where(Offer.id.in_(set(ids)))).all()
    return {oid: (name, slug or "other") for oid, name, slug in rows}


def status_of(expected: int, counted: int, scanned: bool) -> str:
    if not scanned and expected > 0:
        return "missing"
    return "match" if counted == expected else ("short" if counted < expected else "over")


def finish(db: Session, store: Store, st: Stocktake) -> Stocktake:
    """"Завершить подсчёт": the table of differences (kept, so the review survives a reload)."""
    if st.status != "counting":
        raise StockError("stocktake_state")
    expected = _expected(db, store, st)
    counts = {int(k): v for k, v in (st.counts_json or {}).items()}
    # A counted item outside the place's books: its quantity there is what the books say (maybe 0 or unknown)
    extra = set(counts) - set(expected)
    if extra:
        for oid, qty in db.execute(select(OfferStock.offer_id, OfferStock.quantity).where(
                OfferStock.branch_id == st.branch_id, OfferStock.offer_id.in_(extra))).all():
            expected[oid] = qty or 0
    names = _names(db, set(expected) | set(counts))
    lines = []
    for oid in set(expected) | set(counts):
        exp, got = expected.get(oid, 0), counts.get(oid, 0)
        name, cat = names.get(oid, ("—", "other"))
        lines.append({"offer_id": oid, "name": name, "category": cat, "expected": exp, "counted": got,
                      "diff": got - exp, "status": status_of(exp, got, oid in counts)})
    order = {"missing": 0, "short": 1, "over": 2, "match": 3}
    lines.sort(key=lambda x: (order[x["status"]], x["name"]))
    st.result_json, st.status, st.excluded_json = lines, "review", []
    db.commit()
    return st


def resume(db: Session, st: Stocktake) -> Stocktake:
    if st.status != "review":
        raise StockError("stocktake_state")
    st.status, st.result_json, st.excluded_json = "counting", [], []
    db.commit()
    return st


def exclude(db: Session, st: Stocktake, offer_id: int, excluded: bool) -> Stocktake:
    if st.status != "review":
        raise StockError("stocktake_state")
    ids = set(st.excluded_json or [])
    ids.add(offer_id) if excluded else ids.discard(offer_id)
    st.excluded_json = sorted(ids)
    db.commit()
    return st


def apply(db: Session, store: Store, st: Stocktake, user: User) -> Stocktake:
    """"Применить": every difference that is not left out becomes an "inventory" line (the quantity = counted)."""
    if st.status != "review":
        raise StockError("stocktake_state")
    skip = set(st.excluded_json or [])
    shortage = surplus = 0
    for line in st.result_json:
        if line["offer_id"] in skip:
            continue
        offer = db.get(Offer, line["offer_id"])
        if offer is None:
            continue
        offer.oversold_at = None  # checked by the count
        if line["diff"] == 0:
            continue
        move(offer, st.branch_id, "inventory", set_to=line["counted"], user_id=user.id, doc=st.doc,
             reason="inventory", force=True)
        offer.updated_at = utcnow()
        shortage += max(0, -line["diff"])
        surplus += max(0, line["diff"])
    st.positions = len(st.result_json)
    st.shortage, st.surplus = shortage, surplus
    st.status, st.finished_at = "applied", utcnow()
    db.commit()
    return st


def cancel(db: Session, st: Stocktake) -> None:
    if st.status not in OPEN:
        raise StockError("stocktake_state")
    st.status, st.finished_at = "cancelled", utcnow()
    db.commit()


def stocktake_out(db: Session, store: Store, st: Stocktake, full: bool = True) -> dict:
    branch = db.get(Branch, st.branch_id) if st.branch_id else None
    out = {"id": st.id, "status": st.status, "doc": st.doc, "branch_id": st.branch_id,
           "branch": (branch.name or branch.address) if branch and not branch.is_warehouse else None,
           "is_warehouse": bool(branch and branch.is_warehouse), "categories": st.categories_json or [],
           "positions": st.positions, "shortage": st.shortage, "surplus": st.surplus,
           "created_at": stock._aware(st.created_at), "finished_at": stock._aware(st.finished_at),
           "counted_positions": len(st.counts_json or {}), "counted_units": sum((st.counts_json or {}).values())}
    if not full:
        return out
    counts = {int(k): v for k, v in (st.counts_json or {}).items()}
    if st.status == "counting":
        expected = _expected(db, store, st)
        names = _names(db, set(counts) | set(expected))
        out["expected_positions"] = len(expected)
        out["found_positions"] = len(set(counts) & set(expected))
        out["counts"] = [{"offer_id": oid, "name": names.get(oid, ("—",))[0], "counted": n,
                          "expected": expected.get(oid)} for oid, n in counts.items()]
        out["counts"].reverse()  # the last scan first
    else:
        out["lines"] = st.result_json or []
        out["excluded"] = st.excluded_json or []
    return out


def list_stocktakes(db: Session, store: Store) -> dict:
    rows = list(db.scalars(select(Stocktake).where(Stocktake.store_id == store.id, Stocktake.status != "cancelled")
                           .order_by(Stocktake.id.desc()).limit(30)))
    return {"open": [stocktake_out(db, store, s, full=False) for s in rows if s.status in OPEN],
            "history": [stocktake_out(db, store, s, full=False) for s in rows if s.status == "applied"]}


# --- the overview (phase 12.4) -------------------------------------------------------------------------------------

def overview_extra(db: Session, store: Store) -> dict:
    """"Продано больше, чем по учёту", reservations whose item was sold, an unfinished and the last stocktake,
    goods only in the warehouse (none of the branches has them)."""
    oversold = list(db.scalars(select(Offer).where(Offer.store_id == store.id, Offer.oversold_at.is_not(None),
                                                   Offer.removed_at.is_(None)).order_by(Offer.oversold_at.desc())))
    names = _names(db, [o.id for o in oversold])
    sold_res = list(db.scalars(select(Reservation).where(
        Reservation.store_id == store.id, Reservation.sold_out_at.is_not(None),
        Reservation.status.in_([ReservationStatus.new, ReservationStatus.confirmed, ReservationStatus.ready]))))
    lists = list_stocktakes(db, store)
    only_wh = []
    if store.has_warehouse:
        for row, offer in warehouse_rows(db, store):
            if offer.removed_at is None and not any((s.quantity or 0) > 0 for s in shop_rows(offer)):
                only_wh.append({"offer_id": offer.id, "quantity": row.quantity})
        wn = _names(db, [i["offer_id"] for i in only_wh])
        for i in only_wh:
            i["name"] = wn.get(i["offer_id"], ("—",))[0]
    return {"oversold": [{"offer_id": o.id, "name": names.get(o.id, ("—",))[0]} for o in oversold[:20]],
            "oversold_total": len(oversold),
            "sold_reservations": [{"id": r.id, "title": r.title} for r in sold_res],
            "open_stocktakes": lists["open"], "last_stocktake": lists["history"][0] if lists["history"] else None,
            "only_warehouse": only_wh[:20], "only_warehouse_total": len(only_wh)}
