"""Phase 11: reservations - "put it aside for me" with the buyer's contacts.

No money and no delivery: the buyer pays and picks the item up in the store. A reservation never changes the
stock, the prices, the market price or the monitoring. Each one has its own conversation (topic "reservation"),
status changes write a system line there. The buyer's phone and Telegram are seen only by the store of this
reservation and only in it; the store never sees the buyer's email.

Statuses: new -> confirmed -> ready -> issued; or cancelled (by the store with a reason, by the buyer until
"issued"); or expired (the term, counted from the confirmation, has passed and the item was not issued).
"""

import json
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Branch, Build, Conversation, Message, MessageAuthor, Offer, Reservation, ReservationEvent, ReservationStatus as S, Store,
    StoreKind, TopicKind, User, UserRole, utcnow,
)
from app.services import stock  # phase 12.2: reserves in "Учёт остатков"
from app.services.branches import available, branch_public, store_branches
from app.services.chat import ChatError, _aware, _price, is_blocked

TZ = timezone(timedelta(hours=5))  # Tashkent: "today" and the dates in system lines
ACTIVE = (S.new, S.confirmed, S.ready)
NEXT = {S.new: S.confirmed, S.confirmed: S.ready, S.ready: S.issued}  # the store moves it on only in this order
CONTACTS = ("call", "telegram", "chat")
CANCEL_REASONS = ("no_stock", "price_changed", "no_show", "other")
MAX_ACTIVE = 5
NEW_PER_DAY = 10
SAME_ITEM = 2
MAX_COMMENT = 500
PHONE = re.compile(r"^\+?998(\d{9})$")
TELEGRAM = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{4,31})$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ReservationError(ChatError):
    """Codes go to reservation.error.<code> in ru.json."""


def today() -> date:
    return utcnow().astimezone(TZ).date()


def normalize_phone(raw: str | None) -> str | None:
    """+998 XX XXX-XX-XX in any spacing -> +998XXXXXXXXX; anything else -> None."""
    m = PHONE.match(re.sub(r"[\s\-()]", "", raw or ""))
    return f"+998{m.group(1)}" if m else None


def normalize_telegram(raw: str | None) -> str | None:
    m = TELEGRAM.match((raw or "").strip())
    return f"@{m.group(1)}" if m else None


# --- System lines in the conversation ---------------------------------------------------------------------------------

def system_text(key: str, **params) -> str:
    """A system line is stored as a key + params (the text is in ru.json: reservation.sys.<key>)."""
    return json.dumps({"key": key, "params": params}, ensure_ascii=False)


def _conversation(db: Session, r: Reservation) -> Conversation | None:
    return db.scalar(select(Conversation).where(Conversation.topic_kind == TopicKind.reservation,
                                                Conversation.topic_id == r.id))


def _system_line(db: Session, r: Reservation, key: str, actor: User | None, **params) -> None:
    """`actor` made the change: the line is unread for the other side only (sender_id = actor)."""
    conv = _conversation(db, r)
    if conv is None:
        return
    now = utcnow()
    db.add(Message(conversation_id=conv.id, author=MessageAuthor.system, sender_id=actor.id if actor else None,
                   text=system_text(key, **params), created_at=now))
    conv.last_message_at = now


def _until(r: Reservation) -> str:
    return _aware(r.expires_at).astimezone(TZ).strftime("%d.%m") if r.expires_at else ""


def _set_status(db: Session, r: Reservation, status: S, by: str, actor: User | None) -> None:
    r.status, r.updated_at = status, utcnow()
    r.events.append(ReservationEvent(status=status, by=by, at=r.updated_at))
    if by != "buyer":
        r.buyer_seen = False


# --- Creating ---------------------------------------------------------------------------------------------------------

def _item(db: Session, kind: str, item_id: int) -> tuple[Store, Offer | None, Build | None]:
    """Only what is on sale now: an offer in stock with a price, a build not taken off sale."""
    if kind == "offer":
        offer = db.get(Offer, item_id)
        if offer is None:
            raise ReservationError("not_found", 404)
        if not offer.is_in_stock or offer.removed_at is not None or offer.price is None:
            raise ReservationError("not_on_sale")
        return offer.store, offer, None
    if kind == "build":
        build = db.get(Build, item_id)
        if build is None:
            raise ReservationError("not_found", 404)
        if not build.is_in_stock:
            raise ReservationError("not_on_sale")
        return build.store, None, build
    raise ReservationError("bad_item")


def validate_contacts(data: dict) -> dict:
    """Name, phone and the way to contact; returns the clean values or raises a code for the field."""
    name = (data.get("name") or "").strip()
    if not name or len(name) > 100:
        raise ReservationError("name")
    phone = normalize_phone(data.get("phone"))
    if phone is None:
        raise ReservationError("phone")
    contact = data.get("contact") or "call"
    if contact not in CONTACTS:
        raise ReservationError("contact")
    telegram = normalize_telegram(data.get("telegram")) if data.get("telegram") else None
    if contact == "telegram" and telegram is None:
        raise ReservationError("telegram")
    return {"name": name, "phone": phone, "contact": contact, "telegram": telegram}


def _pickup(data: dict) -> tuple[date | None, str | None]:
    raw_date, raw_time = data.get("pickup_date") or None, (data.get("pickup_time") or "").strip() or None
    pickup = None
    if raw_date:
        try:
            pickup = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
        except ValueError:
            raise ReservationError("pickup_date")
        if pickup < today():
            raise ReservationError("pickup_date")
    if raw_time and not TIME.match(raw_time):
        raise ReservationError("pickup_time")
    return pickup, raw_time


def _check_limits(db: Session, user: User, offer: Offer | None, build: Build | None) -> None:
    mine = Reservation.buyer_id == user.id
    active = Reservation.status.in_(ACTIVE)
    if db.scalar(select(func.count(Reservation.id)).where(mine, active)) >= MAX_ACTIVE:
        raise ReservationError("limit_active", 429)
    day_ago = utcnow() - timedelta(days=1)
    if db.scalar(select(func.count(Reservation.id)).where(mine, Reservation.created_at >= day_ago)) >= NEW_PER_DAY:
        raise ReservationError("limit_day", 429)
    same = Reservation.offer_id == offer.id if offer else Reservation.build_id == build.id
    if db.scalar(select(func.count(Reservation.id)).where(mine, active, same)) >= SAME_ITEM:
        raise ReservationError("limit_same", 429)


def _pickup_branch(db: Session, store: Store, offer: Offer | None, branch_id) -> Branch | None:
    """Phase 12.1: the branch where the buyer picks it up — required when the store has branches; with stock by
    branch only a branch where the item is available (the reservation of the stock itself comes in 12.2)."""
    branches = store_branches(db, store.id)
    if not branches:
        return None
    branch = next((b for b in branches if b.id == branch_id), None) if branch_id else None
    if branch is None:
        raise ReservationError("branch")
    if offer is not None and offer.stocks:
        row = next((s for s in offer.stocks if s.branch_id == branch.id), None)
        if row is None or not available(row):
            raise ReservationError("branch_no_stock")
    return branch


def create(db: Session, user: User, data: dict) -> Reservation:
    if user.role != UserRole.buyer:
        raise ReservationError("buyers_only", 403)
    store, offer, build = _item(db, data.get("kind"), int(data.get("item_id") or 0))
    # A Telegram channel is not a store (only "Open the post"); an archive price list has nobody to answer
    if store.kind == StoreKind.telegram or store.is_archive:
        raise ReservationError("not_a_store")
    if is_blocked(db, store.id, user.id):
        raise ReservationError("blocked", 403)
    contacts = validate_contacts(data)
    quantity = data.get("quantity") or 1
    if not isinstance(quantity, int) or not 1 <= quantity <= 99:
        raise ReservationError("quantity")
    pickup_date, pickup_time = _pickup(data)
    comment = (data.get("comment") or "").strip() or None
    if comment and len(comment) > MAX_COMMENT:
        raise ReservationError("comment")
    expire_due(db)
    _check_limits(db, user, offer, build)
    branch = _pickup_branch(db, store, offer, data.get("branch_id"))

    item = offer or build
    r = Reservation(
        buyer_id=user.id, store_id=store.id, offer_id=offer.id if offer else None, build_id=build.id if build else None,
        title=offer.product.normalized_name if offer else build.name, condition=item.condition,
        price=item.price, currency=item.currency, quantity=quantity, **contacts,
        pickup_date=pickup_date, pickup_time=pickup_time, comment=comment, branch_id=branch.id if branch else None,
    )
    r.events.append(ReservationEvent(status=S.new, by="buyer"))
    db.add(r)
    db.flush()
    db.add(Conversation(buyer_id=user.id, store_id=store.id, topic_kind=TopicKind.reservation, topic_id=r.id))
    db.flush()
    _system_line(db, r, "created", user)
    # Filled in the next form (the buyer may change them there)
    user.contact_name, user.contact_phone = contacts["name"], contacts["phone"]
    if contacts["telegram"]:
        user.contact_telegram = contacts["telegram"]
    db.commit()
    return r


# --- Status changes ---------------------------------------------------------------------------------------------------

def expire_due(db: Session) -> int:
    """Confirmed / ready reservations whose term has passed become "expired" (lists call it; and once an hour)."""
    now = utcnow()
    due = db.scalars(select(Reservation).where(Reservation.status.in_((S.confirmed, S.ready)),
                                               Reservation.expires_at.is_not(None), Reservation.expires_at < now)).all()
    for r in due:
        stock.release_reserve(db, r.store, r, None)
        _set_status(db, r, S.expired, "system", None)
        _system_line(db, r, "expired", None)
    if due:
        db.commit()
    return len(due)


def _store_of(db: Session, user: User) -> Store:
    store = db.scalar(select(Store).where(Store.user_id == user.id)) if user.role == UserRole.seller else None
    if store is None:
        raise ReservationError("sellers_only", 403)
    return store


def get_for(db: Session, user: User, res_id: int) -> tuple[str, Reservation]:
    """Only the buyer and the store of this reservation: for anyone else it does not exist (404)."""
    r = db.get(Reservation, res_id)
    if r is not None:
        if user.role == UserRole.seller:
            store = db.scalar(select(Store).where(Store.user_id == user.id))
            if store is not None and r.store_id == store.id:
                return "store", r
        elif r.buyer_id == user.id:
            return "buyer", r
    raise ReservationError("not_found", 404)


def advance(db: Session, user: User, res_id: int) -> Reservation:
    """The store moves the reservation one step on: new -> confirmed -> ready -> issued."""
    side, r = get_for(db, user, res_id)
    if side != "store":
        raise ReservationError("sellers_only", 403)
    expire_due(db)
    nxt = NEXT.get(r.status)
    if nxt is None:
        raise ReservationError("bad_status")
    if nxt == S.confirmed:
        r.expires_at = utcnow() + timedelta(days=r.store.reservation_days or 2)
        # Phase 12.2, "Учёт остатков": the confirmation reserves the items in the branch (not enough — refused)
        if not stock.take_reserve(db, r.store, r, user.id):
            db.rollback()
            raise ReservationError("reserve_short")
    if nxt == S.issued:
        try:
            stock.issue(db, r.store, r, user.id)  # a sale by the reservation
        except stock.StockError:
            db.rollback()
            raise ReservationError("reserve_short")
    _set_status(db, r, nxt, "store", user)
    _system_line(db, r, nxt.value, user, until=_until(r))
    db.commit()
    return r


def change_branch(db: Session, user: User, res_id: int, branch_id: int) -> Reservation:
    """The store moves an active reservation to another of its branches; a system line tells the buyer."""
    side, r = get_for(db, user, res_id)
    if side != "store":
        raise ReservationError("sellers_only", 403)
    if r.status not in ACTIVE:
        raise ReservationError("bad_status")
    branch = next((b for b in store_branches(db, r.store_id) if b.id == branch_id), None)
    if branch is None:
        raise ReservationError("branch")
    if branch.id == r.branch_id:
        return r
    try:
        stock.transfer(db, r.store, r, branch.id, user.id)  # phase 12.2: the reserve moves with it
    except stock.StockError:
        db.rollback()
        raise ReservationError("branch_no_stock")
    r.branch_id, r.updated_at, r.buyer_seen = branch.id, utcnow(), False
    _system_line(db, r, "branch_changed", user, branch=branch.name or "", address=branch.address,
                 city=branch.city)
    db.commit()
    db.refresh(r)
    return r


def cancel(db: Session, user: User, res_id: int, reason: str | None = None, text: str | None = None) -> Reservation:
    """The store cancels with a reason from the list; the buyer cancels any time before "issued"."""
    side, r = get_for(db, user, res_id)
    expire_due(db)
    if r.status not in ACTIVE:
        raise ReservationError("bad_status")
    text = (text or "").strip()[:200] or None
    if side == "store":
        if reason not in CANCEL_REASONS:
            raise ReservationError("reason")
        if reason == "other" and not text:
            raise ReservationError("reason_text")
        r.cancel_reason, r.cancel_text = reason, text
    r.cancelled_by = side
    stock.release_reserve(db, r.store, r, user.id)  # phase 12.2: the reserve goes back
    _set_status(db, r, S.cancelled, side, user)
    _system_line(db, r, f"cancelled_{side}", user, reason=reason or "", text=text or "")
    db.commit()
    return r


# --- Out ---------------------------------------------------------------------------------------------------------------

def _current(r: Reservation, usd_rate: float | None) -> dict:
    """The item as it is now: on sale or not, and its price (the reservation keeps its own snapshot)."""
    if r.offer is not None:
        o = r.offer
        on_sale = o.is_in_stock and o.removed_at is None and o.price is not None
        return {"exists": True, "on_sale": on_sale, "product_id": o.product_id,
                "category": o.product.category.slug if o.product.category else "other",
                **(_price(o.price, o.currency, usd_rate) if o.price is not None else {"price": None})}
    if r.build is not None:
        b = r.build
        return {"exists": True, "on_sale": b.is_in_stock, "build_id": b.id, "category": "build",
                **_price(b.price, b.currency, usd_rate)}
    return {"exists": False, "on_sale": False, "price": None}


def out(db: Session, r: Reservation, side: str, usd_rate: float | None) -> dict:
    conv = _conversation(db, r)
    cur = _current(r, usd_rate)
    data = {
        "id": r.id, "status": r.status.value, "kind": "offer" if r.offer_id or not r.build_id else "build",
        "offer_id": r.offer_id, "build_id": r.build_id, "title": r.title, "condition": r.condition.value,
        **_price(r.price, r.currency, usd_rate), "quantity": r.quantity,
        "current": cur, "price_changed": cur.get("price") is not None and (
            cur["price"] != r.price or cur["currency"] != r.currency.value),
        "contact": r.contact, "pickup_date": r.pickup_date.isoformat() if r.pickup_date else None,
        "pickup_time": r.pickup_time, "comment": r.comment,
        "cancelled_by": r.cancelled_by, "cancel_reason": r.cancel_reason, "cancel_text": r.cancel_text,
        "expires_at": _aware(r.expires_at) if r.expires_at else None,
        "created_at": _aware(r.created_at), "updated_at": _aware(r.updated_at),
        "store": {"id": r.store.id, "name": r.store.name, "city": r.store.city, "address": r.store.address,
                  "district": r.store.district, "phone": r.store.phone, "hours": r.store.hours,
                  "map_url": r.store.map_url, "map_lat": r.store.map_lat, "map_lon": r.store.map_lon},
        # Phase 12.1: where to pick it up (address, hours, map); the store may change it
        "branch": branch_public(r.branch, r.store) if r.branch else None,
        "branches": [branch_public(b, r.store) for b in store_branches(db, r.store_id)] if side == "store" else [],
        "conversation_id": conv.id if conv else None, "is_demo": r.is_demo,
        "history": [{"status": e.status.value, "by": e.by, "at": _aware(e.at)} for e in r.events],
        "next": NEXT[r.status].value if r.status in NEXT else None, "can_cancel": r.status in ACTIVE,
        "seen": r.buyer_seen,
    }
    # The buyer's phone and Telegram: only to the buyer and to the store of this reservation (never the email)
    data.update({"name": r.name, "phone": r.phone, "telegram": r.telegram, "buyer_no": r.buyer_id})
    if side == "store" and r.store.stock_mode == "stock":
        data["reserved_qty"] = r.reserved_qty  # phase 12.2: only the store sees its reserve
    return data


def list_for_buyer(db: Session, user: User, usd_rate: float | None, done: bool = False) -> list[dict]:
    expire_due(db)
    q = select(Reservation).where(Reservation.buyer_id == user.id,
                                  Reservation.status.not_in(ACTIVE) if done else Reservation.status.in_(ACTIVE))
    items = db.scalars(q.order_by(Reservation.updated_at.desc())).all()
    result = [out(db, r, "buyer", usd_rate) for r in items]
    changed = False
    for r in items:  # opening the list = the buyer has seen the new statuses
        if not r.buyer_seen:
            r.buyer_seen, changed = True, True
    if changed:
        db.commit()
    return result


def unseen_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count(Reservation.id)).where(Reservation.buyer_id == user.id,
                                                              Reservation.buyer_seen.is_(False))) or 0


def list_for_store(db: Session, user: User, usd_rate: float | None, status: str = "all", q: str = "") -> list[dict]:
    store = _store_of(db, user)
    expire_due(db)
    query = select(Reservation).where(Reservation.store_id == store.id)
    if status == "active":
        query = query.where(Reservation.status.in_(ACTIVE))
    elif status != "all":
        try:
            query = query.where(Reservation.status == S(status))
        except ValueError:
            raise ReservationError("bad_status")
    q = (q or "").strip()
    if q:
        digits = re.sub(r"\D", "", q)
        conds = [Reservation.name.ilike(f"%{q}%")]
        if len(digits) >= 3:
            conds.append(Reservation.phone.contains(digits))
        query = query.where(or_(*conds))
    items = db.scalars(query.order_by(Reservation.created_at.desc())).all()
    return [out(db, r, "store", usd_rate) for r in items]


def store_counts(db: Session, store: Store) -> dict:
    """For the cabinet: new reservations and active ones whose term ends today (Tashkent time)."""
    expire_due(db)
    new = db.scalar(select(func.count(Reservation.id)).where(Reservation.store_id == store.id,
                                                             Reservation.status == S.new)) or 0
    start = datetime.combine(today(), time.min, TZ)
    end = start + timedelta(days=1)
    ending = db.scalar(select(func.count(Reservation.id)).where(
        Reservation.store_id == store.id, Reservation.status.in_((S.confirmed, S.ready)),
        Reservation.expires_at >= start.astimezone(timezone.utc), Reservation.expires_at < end.astimezone(timezone.utc))) or 0
    return {"new": new, "ending_today": ending}


def contacts_of(user: User) -> dict:
    return {"name": user.contact_name or "", "phone": user.contact_phone or "", "telegram": user.contact_telegram or ""}


def topic(db: Session, conv: Conversation, usd_rate: float | None) -> dict:
    """The topic card of a reservation conversation."""
    r = db.get(Reservation, conv.topic_id)
    if r is None:
        return {"kind": "reservation", "missing": True}
    cur = _current(r, usd_rate)
    return {"kind": "reservation", "reservation_id": r.id, "title": r.title, "status": r.status.value,
            "category": cur.get("category", "other"), "condition": r.condition.value,
            **_price(r.price, r.currency, usd_rate)}
