"""Stock keeping (phase 12.2): the journal of stock movements and the operations of the "Склад" section.

Every change of a quantity or a reserve of an offer in a branch is a StockMovement, written by `record` — the one
place the journal is written. `branches.set_stock` (hand edits, price lists of 12.1, bulk actions), `clear_stock`,
`restore_stock` (undo of an upload) and `move` (receipt, sale, adjustment, reservations, stock import) call it.
The kind and the links (who, which upload or reservation) come from the caller or from `journal(...)`.

Store modes: "price" — stock from price lists and hand edits, as before; "stock" — quantities change only by
operations (receipt, sale, adjustment, reservations, stock import), hand edits of quantities are refused.
Rules: a quantity never goes below 0; a sale takes only the available (quantity - reserved), a sale by a reservation
takes its own reserve. The buyer never sees quantities, reserves or purchase prices.
"""

import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from app.db.models import (
    Branch, Offer, OfferStock, Reservation, ReservationStatus, StockMovement, Store, User, utcnow,
)

KINDS = ("initial", "receipt", "sale", "adjust", "reserve", "unreserve", "res_sale", "import", "undo", "manual")
REASONS = ("inventory", "defect", "loss", "other")
_ctx: ContextVar[dict] = ContextVar("stock_journal", default={})


class StockError(ValueError):
    """The code goes to the client (texts in ru.json stock.error.*); params — e.g. how many are available."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code, self.params = code, params


@contextmanager
def journal(kind: str, **refs):
    """Everything set_stock changes inside is written with this kind and links (user_id, import_id, ...)."""
    token = _ctx.set({"kind": kind, **refs})
    try:
        yield
    finally:
        _ctx.reset(token)


def record(offer: Offer, row: OfferStock, q_before: int | None, r_before: int, *, force: bool = False,
           **fields) -> StockMovement | None:
    """Writes one journal line for a branch row that changed (q_before / r_before = the values before)."""
    if not force and q_before == row.quantity and (r_before or 0) == (row.reserved or 0):
        return None
    data = {**_ctx.get(), **{k: v for k, v in fields.items() if v is not None}}
    store_id = offer.store_id or (offer.store.id if offer.store is not None else None)
    m = StockMovement(
        store_id=store_id, branch_id=row.branch_id, kind=data.pop("kind", "manual"),
        delta=(row.quantity or 0) - (q_before or 0), reserved_delta=(row.reserved or 0) - (r_before or 0),
        quantity_before=q_before, quantity_after=row.quantity, reserved_after=row.reserved or 0, **data)
    offer.movements.add(m)
    return m


def _row(offer: Offer, branch_id: int) -> OfferStock:
    row = next((s for s in offer.stocks if s.branch_id == branch_id), None)
    if row is None:
        row = OfferStock(branch_id=branch_id, reserved=0, quantity=None, in_stock=False)
        offer.stocks.append(row)
    return row


def free(row: OfferStock | None) -> int:
    """Available to sell or reserve: quantity - reserved (an unknown quantity has no number: 0)."""
    if row is None or row.quantity is None:
        return 0
    return max(0, row.quantity - (row.reserved or 0))


def move(offer: Offer, branch_id: int, kind: str, qty: int = 0, *, set_to: int | None = None, **fields) -> StockMovement | None:
    """One operation on one branch row: receipt (+qty), sale (-qty of the available), res_sale (-qty and its
    reserve), reserve (+qty reserve of the available), unreserve (-qty reserve), adjust / import / initial (the
    quantity becomes set_to). Checks the rules, recomputes the offer and writes the journal."""
    from app.services.branches import recompute_offer

    row = _row(offer, branch_id)
    q0, r0 = row.quantity, row.reserved or 0
    qty = int(qty or 0)
    if kind in ("receipt", "sale", "res_sale", "reserve", "unreserve") and qty <= 0:
        raise StockError("qty")
    if kind == "receipt":
        row.quantity = (row.quantity or 0) + qty
    elif kind == "sale":
        if row.quantity is None:
            raise StockError("unknown_qty")
        if qty > free(row):
            raise StockError("not_enough", available=free(row))
        row.quantity -= qty
    elif kind == "res_sale":
        if row.quantity is None or row.quantity < qty:
            raise StockError("not_enough", available=row.quantity or 0)
        row.quantity -= qty
        row.reserved = max(0, r0 - qty)
    elif kind == "reserve":
        if row.quantity is None:
            raise StockError("unknown_qty")
        if qty > free(row):
            raise StockError("not_enough", available=free(row))
        row.reserved = r0 + qty
    elif kind == "unreserve":
        row.reserved = max(0, r0 - qty)
    else:  # adjust / import / initial / undo
        if set_to is None or int(set_to) < 0:
            raise StockError("qty")
        row.quantity = int(set_to)
    row.in_stock = (row.quantity or 0) - (row.reserved or 0) > 0 if row.quantity is not None else bool(row.in_stock)
    row.updated_at = utcnow()
    recompute_offer(offer)
    force = fields.pop("force", False) or kind == "initial"
    return record(offer, row, None if kind == "initial" else q0, r0, kind=kind, force=force, **fields)


# --- the store's mode -----------------------------------------------------------------------------------------------

def is_stock_mode(store: Store | None) -> bool:
    return store is not None and store.stock_mode == "stock"


def _active_reservations(db: Session, store: Store) -> list[Reservation]:
    return list(db.scalars(select(Reservation).where(
        Reservation.store_id == store.id, Reservation.offer_id.is_not(None),
        Reservation.status.in_([ReservationStatus.confirmed, ReservationStatus.ready])).order_by(Reservation.id)))


def mode_preview(db: Session, store: Store) -> dict:
    """Before switching on: how many rows become the opening balance, how many have no quantity."""
    rows = list(db.scalars(select(OfferStock).join(Offer).where(Offer.store_id == store.id)))
    return {"rows": sum(1 for r in rows if r.quantity is not None), "unknown": sum(1 for r in rows if r.quantity is None),
            "reservations": len(_active_reservations(db, store))}


def set_mode(db: Session, store: Store, mode: str, user: User | None) -> dict:
    """"Учёт остатков": the current quantities become the opening balance ("initial" lines), the reserves are
    reset and the confirmed reservations take their reserve when the stock is enough. Back to "price": the
    reserves are released (the journal stays)."""
    if mode not in ("price", "stock"):
        raise StockError("mode")
    if mode == store.stock_mode:
        return {"mode": mode, "initial": 0, "reserved": 0, "unreserved": []}
    uid = user.id if user else None
    offers = list(db.scalars(select(Offer).where(Offer.store_id == store.id)))
    result = {"mode": mode, "initial": 0, "reserved": 0, "unreserved": []}
    if mode == "stock":
        for offer in offers:
            for row in offer.stocks:
                if row.quantity is None:
                    continue
                r0 = row.reserved or 0
                row.reserved = 0
                record(offer, row, None, r0, kind="initial", force=True, user_id=uid)  # +quantity from nothing
                result["initial"] += 1
        store.stock_mode = "stock"
        db.flush()
        for r in _active_reservations(db, store):
            r.reserved_qty = 0
            if take_reserve(db, store, r, uid):
                result["reserved"] += 1
            else:
                result["unreserved"].append(r.id)
    else:
        for r in _active_reservations(db, store):
            release_reserve(db, store, r, uid)
        store.stock_mode = "price"
    db.commit()
    return result


# --- reservations ---------------------------------------------------------------------------------------------------

def _res_row(r: Reservation) -> OfferStock | None:
    if r.offer is None or r.branch_id is None:
        return None
    return next((s for s in r.offer.stocks if s.branch_id == r.branch_id), None)


def can_reserve(db: Session, store: Store, r: Reservation, branch_id: int | None = None) -> bool:
    if not is_stock_mode(store) or r.offer is None:
        return True
    bid = branch_id or r.branch_id
    row = next((s for s in r.offer.stocks if s.branch_id == bid), None)
    return row is not None and free(row) >= r.quantity


def take_reserve(db: Session, store: Store, r: Reservation, user_id: int | None) -> bool:
    """Confirmation in "Учёт остатков": reserve the quantity in the reservation's branch. False = not enough."""
    if not is_stock_mode(store) or r.offer is None or r.branch_id is None or r.reserved_qty:
        return bool(r.reserved_qty) or not is_stock_mode(store)
    if not can_reserve(db, store, r):
        return False
    move(r.offer, r.branch_id, "reserve", r.quantity, user_id=user_id, reservation_id=r.id)
    r.reserved_qty = r.quantity
    return True


def release_reserve(db: Session, store: Store, r: Reservation, user_id: int | None) -> None:
    """Cancelled / expired after the confirmation (or the mode is switched off): the reserve goes back."""
    if not r.reserved_qty or r.offer is None or r.branch_id is None:
        r.reserved_qty = 0
        return
    move(r.offer, r.branch_id, "unreserve", r.reserved_qty, user_id=user_id, reservation_id=r.id)
    r.reserved_qty = 0


def issue(db: Session, store: Store, r: Reservation, user_id: int | None) -> None:
    """"Выдано": a sale by the reservation at the price of its snapshot (quantity -N, reserve -N)."""
    if not is_stock_mode(store) or r.offer is None or r.branch_id is None:
        return
    if not r.reserved_qty:
        take_reserve(db, store, r, user_id)  # issued without a reserve: sell from the available
        if not r.reserved_qty:
            raise StockError("not_enough", available=free(_res_row(r)))
    move(r.offer, r.branch_id, "res_sale", r.reserved_qty, user_id=user_id, reservation_id=r.id, price=r.price,
         currency=r.currency.value)
    r.reserved_qty = 0


def transfer(db: Session, store: Store, r: Reservation, branch_id: int, user_id: int | None) -> None:
    """The store changes the branch of a confirmed reservation: the reserve moves (when the new branch has it)."""
    if not is_stock_mode(store) or not r.reserved_qty or r.offer is None:
        return
    row = next((s for s in r.offer.stocks if s.branch_id == branch_id), None)
    if row is None or free(row) < r.quantity:
        raise StockError("not_enough", available=free(row))
    qty = r.reserved_qty
    move(r.offer, r.branch_id, "unreserve", qty, user_id=user_id, reservation_id=r.id)
    move(r.offer, branch_id, "reserve", qty, user_id=user_id, reservation_id=r.id)


# --- operations of the "Склад" section ------------------------------------------------------------------------------

def _offer(db: Session, store: Store, offer_id: int) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None or offer.store_id != store.id:
        raise StockError("offer")
    return offer


def _branch_ids(db: Session, store: Store) -> set[int]:
    return set(db.scalars(select(Branch.id).where(Branch.store_id == store.id)))


def _update_cost(offer: Offer, cost: float, qty: int, db: Session) -> None:
    rows = db.execute(select(StockMovement.cost, StockMovement.delta).where(
        StockMovement.offer_id == offer.id, StockMovement.kind == "receipt", StockMovement.cost.is_not(None))).all()
    total = sum(c * d for c, d in rows) + cost * qty
    count = sum(d for _, d in rows) + qty
    offer.cost_last = cost
    offer.cost_avg = round(total / count, 2) if count else cost


def operate_price_mode(db: Session, store: Store, user: User, kind: str, lines: list[dict]) -> dict:
    """"Сканирование" of a store in "Только прайс" (phase 12.3): a receipt / sale changes the branch's stock as a
    hand edit would ("manual" lines of the journal): receipt — the quantity grows (an unknown one counts as 0),
    sale — it falls, not below 0 (an unknown quantity stays "есть")."""
    from app.services.branches import set_stock

    if kind not in ("receipt", "sale") or not lines:
        raise StockError("lines")
    branches = _branch_ids(db, store)
    with journal("manual", user_id=user.id):
        for i, line in enumerate(lines):
            try:
                offer = _offer(db, store, int(line["offer_id"]))
                bid, qty = int(line["branch_id"]), int(line["qty"])
                if bid not in branches:
                    raise StockError("branch")
                if qty <= 0:
                    raise StockError("qty")
                if offer.price is None:
                    raise StockError("price_required")
                row = next((s for s in offer.stocks if s.branch_id == bid), None)
                now = row.quantity if row is not None else None
                if kind == "receipt":
                    set_stock(offer, bid, quantity=(now or 0) + qty)
                elif now is not None:
                    set_stock(offer, bid, quantity=max(0, now - qty))
            except StockError as e:
                db.rollback()
                e.params["line"] = i + 1
                raise
            except (KeyError, TypeError, ValueError):
                db.rollback()
                raise StockError("lines", line=i + 1)
            offer.updated_at = utcnow()
    db.commit()
    return {"doc": None, "count": len(lines)}


def operate(db: Session, store: Store, user: User, kind: str, lines: list[dict], scan: bool = False) -> dict:
    """A document of one kind (receipt / sale / adjust): all lines or none (an error names the line).
    `scan`: from "Сканирование" — a store in "Только прайс" changes its stock as a hand edit (phase 12.3)."""
    if not is_stock_mode(store) and scan:
        return operate_price_mode(db, store, user, kind, lines)
    if not is_stock_mode(store):
        raise StockError("mode_off")
    if kind not in ("receipt", "sale", "adjust") or not lines:
        raise StockError("lines")
    branches = _branch_ids(db, store)
    doc = f"{kind[:1].upper()}-{utcnow():%y%m%d}-{secrets.token_hex(2)}"
    done = []
    for i, line in enumerate(lines):
        try:
            offer = _offer(db, store, int(line["offer_id"]))
            bid = int(line["branch_id"])
            if bid not in branches:
                raise StockError("branch")
            comment = (line.get("comment") or "").strip()[:300] or None
            if kind == "receipt":
                cost = line.get("cost")
                if cost is not None and float(cost) < 0:
                    raise StockError("cost")
                if cost is not None:
                    _update_cost(offer, float(cost), int(line["qty"]), db)
                db.flush()
                m = move(offer, bid, "receipt", int(line["qty"]), user_id=user.id, doc=doc, comment=comment,
                         cost=float(cost) if cost is not None else None, currency=offer.currency.value)
            elif kind == "sale":
                price = line.get("price")
                price = float(price) if price not in (None, "") else offer.price
                m = move(offer, bid, "sale", int(line["qty"]), user_id=user.id, doc=doc, comment=comment,
                         price=price, currency=offer.currency.value)
            else:
                reason = line.get("reason") or "other"
                if reason not in REASONS or (reason == "other" and not comment):
                    raise StockError("reason")
                m = move(offer, bid, "adjust", set_to=int(line["qty"]), user_id=user.id, doc=doc, reason=reason,
                         comment=comment, force=True)
        except StockError as e:
            db.rollback()
            e.params["line"] = i + 1
            raise
        except (KeyError, TypeError, ValueError):
            db.rollback()
            raise StockError("lines", line=i + 1)
        offer.updated_at = utcnow()
        done.append(m)
    db.commit()
    return {"doc": doc, "count": len(done)}


# --- the journal ----------------------------------------------------------------------------------------------------

def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def journal_query(store: Store, f: dict):
    q = select(StockMovement).where(StockMovement.store_id == store.id)
    if f.get("offer_id"):
        q = q.where(StockMovement.offer_id == f["offer_id"])
    if f.get("branch_id"):
        q = q.where(StockMovement.branch_id == f["branch_id"])
    if f.get("kind"):
        q = q.where(StockMovement.kind.in_(f["kind"].split(",")))
    if f.get("date_from"):
        q = q.where(StockMovement.created_at >= datetime.combine(f["date_from"], datetime.min.time(), timezone.utc))
    if f.get("date_to"):
        q = q.where(StockMovement.created_at < datetime.combine(f["date_to"], datetime.min.time(), timezone.utc)
                    + timedelta(days=1))
    return q


def movement_out(db: Session, m: StockMovement, store: Store, names: dict, branches: dict) -> dict:
    who = "store" if m.user_id == store.user_id else ("buyer" if m.user_id else ("import" if m.import_id else "system"))
    return {"id": m.id, "kind": m.kind, "offer_id": m.offer_id, "name": names.get(m.offer_id),
            "branch_id": m.branch_id, "branch": branches.get(m.branch_id), "delta": m.delta,
            "reserved_delta": m.reserved_delta, "before": m.quantity_before, "after": m.quantity_after,
            "reserved_after": m.reserved_after, "cost": m.cost, "price": m.price, "currency": m.currency,
            "reason": m.reason, "comment": m.comment, "doc": m.doc, "who": who,
            "reservation_id": m.reservation_id, "import_id": m.import_id, "at": _aware(m.created_at)}


def _names(db: Session, ids) -> dict:
    from app.db.models import Product

    rows = db.execute(select(Offer.id, Product.normalized_name).join(Product, Offer.product_id == Product.id)
                      .where(Offer.id.in_(set(ids)))).all()
    return dict(rows)


def _branch_names(db: Session, store: Store) -> dict:
    return {b.id: b.name or b.address for b in db.scalars(select(Branch).where(Branch.store_id == store.id))}


def list_journal(db: Session, store: Store, f: dict, page: int = 1, size: int = 50) -> dict:
    q = journal_query(store, f)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = list(db.scalars(q.order_by(StockMovement.id.desc()).offset((page - 1) * size).limit(size)))
    names, branches = _names(db, [m.offer_id for m in items]), _branch_names(db, store)
    return {"items": [movement_out(db, m, store, names, branches) for m in items], "total": total, "page": page,
            "pages": max(1, -(-total // size))}


def all_movements(db: Session, store: Store, f: dict) -> list[dict]:
    items = list(db.scalars(journal_query(store, f).order_by(StockMovement.id)))
    names, branches = _names(db, [m.offer_id for m in items]), _branch_names(db, store)
    return [movement_out(db, m, store, names, branches) for m in items]


# --- the overview ---------------------------------------------------------------------------------------------------

def overview(db: Session, store: Store) -> dict | None:
    """"Заканчивается" (available <= the store's threshold in a branch), reservations without a reserve, the last
    movements. Only in "Учёт остатков"."""
    if not is_stock_mode(store):
        return None
    branches = _branch_names(db, store)
    low = []
    rows = db.execute(select(OfferStock, Offer).join(Offer).where(
        Offer.store_id == store.id, Offer.removed_at.is_(None), OfferStock.quantity.is_not(None))).all()
    threshold = store.low_stock if store.low_stock is not None else 1
    seen_out: set[int] = set()
    for row, offer in rows:
        # Running low in a branch (1..threshold), or sold out in every branch (once per item); a branch that
        # simply does not carry the item (0 there, available elsewhere) is normal
        out = not offer.is_in_stock and offer.price is not None and offer.id not in seen_out
        if 0 < free(row) <= threshold or out:
            seen_out.add(offer.id)
            low.append({"offer_id": offer.id, "branch_id": row.branch_id, "branch": branches.get(row.branch_id),
                        "available": free(row)})
    names = _names(db, [i["offer_id"] for i in low])
    for i in low:
        i["name"] = names.get(i["offer_id"])
    low.sort(key=lambda i: (i["available"], i["name"] or ""))
    unreserved = [{"id": r.id, "title": r.title, "quantity": r.quantity, "branch": branches.get(r.branch_id)}
                  for r in _active_reservations(db, store) if not r.reserved_qty]
    last = list_journal(db, store, {}, size=5)["items"]
    return {"low": low[:20], "low_total": len(low), "threshold": store.low_stock, "unreserved": unreserved,
            "last": last}
