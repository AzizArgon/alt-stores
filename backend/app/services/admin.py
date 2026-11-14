"""The admin panel (phase 13): what piles up and nobody else can decide.

Every action goes through `log()` into `admin_actions` (who, when, what, with what, comment). The admin never sees
passwords, never logs in as another user and never sees a store's stock, purchase prices or stock journal — those
are the seller's own data. Nothing is deleted: a block hides, a merge moves, a rejection keeps the row.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AdminAction, Barcode, BarcodeCode, Branch, BuildComponent, ArchivePrice, Build, Category, ChatReport, Conversation,
    FlagStatus, FraudFlag, Message, Offer, Product, ProductFix, Reservation, ReservationStatus, Store, StoreKind,
    TgChannel, TgPost, TopicKind, User, UserRole, utcnow,
)

ACTIONS = (
    "store_verify", "store_unverify", "store_block", "store_unblock",
    "report_dismiss", "report_block_user", "report_block_store",
    "flag_upheld", "flag_dismissed", "fix_accept", "fix_merge", "fix_reject",
    "barcode_resolve", "barcode_reject",
    "channel_add", "channel_edit", "channel_enable", "channel_disable", "channel_delete", "channel_fetch",
    "user_block", "user_unblock",
    "photo_accept", "photo_reject", "photo_main",
)
ACTIVE_RES = (ReservationStatus.new, ReservationStatus.confirmed, ReservationStatus.ready)


def _tell(db: Session, store, kind: str, **params) -> None:
    """Phase 12.5: an admin decision goes to the seller's bell (the overview shows the details)."""
    from app.services import notifications as notify

    notify.notify(db, notify.owner(db, store), kind, "/seller", **params)


class AdminError(ValueError):
    """code -> admin.error.<code> in ru.json."""

    def __init__(self, code: str, status: int = 400, **params):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


def _aware(at: datetime | None) -> datetime | None:
    return at if at is None or at.tzinfo else at.replace(tzinfo=timezone.utc)


def _text(value: str | None, limit: int = 500) -> str | None:
    value = (value or "").strip()
    return value[:limit] or None


def log(db: Session, admin: User, action: str, target_type: str, target_id, title: str | None = None,
        comment: str | None = None, **details) -> AdminAction:
    entry = AdminAction(admin_id=admin.id, admin_email=admin.email, action=action, target_type=target_type,
                        target_id=str(target_id), title=(title or "")[:255] or None, comment=_text(comment),
                        details=details)
    db.add(entry)
    return entry


def journal(db: Session, action: str | None = None, date_from: date | None = None, date_to: date | None = None,
            limit: int = 200) -> list[dict]:
    query = select(AdminAction).order_by(AdminAction.id.desc()).limit(limit)
    if action:
        query = query.where(or_(AdminAction.action == action, AdminAction.action.like(f"{action}_%")))
    if date_from:
        query = query.where(AdminAction.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(AdminAction.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return [{"id": a.id, "at": _aware(a.created_at), "admin": a.admin_email, "action": a.action,
             "target_type": a.target_type, "target_id": a.target_id, "title": a.title, "comment": a.comment,
             "details": a.details or {}} for a in db.scalars(query)]


# --- overview ---------------------------------------------------------------------------------------------------------

def _shops():
    return select(Store).where(Store.kind == StoreKind.shop, Store.is_archive.is_(False))


def counts(db: Session) -> dict:
    """How many things wait for a decision (the overview and the menu badges)."""
    return {
        "stores": db.scalar(select(func.count()).select_from(
            _shops().where(Store.is_verified.is_(False), Store.blocked_at.is_(None)).subquery())),
        "reports": db.scalar(select(func.count(ChatReport.id)).where(ChatReport.status == "new")),
        "flags": db.scalar(select(func.count(FraudFlag.id)).where(FraudFlag.status == FlagStatus.disputed)),
        "fixes": db.scalar(select(func.count(ProductFix.id)).where(ProductFix.status == "pending")),
        "barcodes": db.scalar(select(func.count(BarcodeCode.id)).where(BarcodeCode.status == "conflict")),
        "photos": _photos_waiting(db),  # phase 14
    }


def _photos_waiting(db: Session) -> int:
    from app.services.photos import pending_count

    return pending_count(db)


def overview(db: Session) -> dict:
    return {"waiting": counts(db), "channels": list_channels(db),
            "users": db.scalar(select(func.count(User.id)).where(User.role.in_([UserRole.buyer, UserRole.seller]),
                                                                  ~User.email.like("telegram+%"))),
            "blocked_users": db.scalar(select(func.count(User.id)).where(User.blocked_at.is_not(None))),
            "blocked_stores": db.scalar(select(func.count()).select_from(
                _shops().where(Store.blocked_at.is_not(None)).subquery())),
            "last_actions": journal(db, limit=5)}


# --- stores -----------------------------------------------------------------------------------------------------------

def _store_row(db: Session, s: Store, goods: dict) -> dict:
    return {"id": s.id, "name": s.name, "email": s.owner.email if s.owner else None, "city": s.city,
            "cities": sorted({b.city for b in s.branches}) or [s.city], "is_verified": s.is_verified,
            "is_demo": s.is_demo, "stock_mode": s.stock_mode, "blocked": s.blocked_at is not None,
            "block_reason": s.block_reason, "goods": goods.get(s.id, 0)}


def _goods_counts(db: Session, ids: list[int]) -> dict:
    return dict(db.execute(select(Offer.store_id, func.count(Offer.id)).where(
        Offer.store_id.in_(ids), Offer.price.is_not(None), Offer.removed_at.is_(None)).group_by(Offer.store_id)).all())


def list_stores(db: Session, f: dict) -> list[dict]:
    query = _shops().order_by(Store.name)
    if f.get("city"):
        query = query.where(Store.id.in_(select(Branch.store_id).where(Branch.city == f["city"], Branch.is_warehouse.is_(False))) | (Store.city == f["city"]))
    for key, col in (("verified", Store.is_verified), ("demo", Store.is_demo)):
        if f.get(key) is not None:
            query = query.where(col.is_(bool(f[key])))
    if f.get("mode"):
        query = query.where(Store.stock_mode == f["mode"])
    if f.get("blocked") is not None:
        query = query.where(Store.blocked_at.is_not(None) if f["blocked"] else Store.blocked_at.is_(None))
    if f.get("q"):
        query = query.where(func.py_lower(Store.name).contains(f["q"].lower()))
    stores = db.scalars(query).all()
    goods = _goods_counts(db, [s.id for s in stores])
    return [_store_row(db, s, goods) for s in stores]


def get_store(db: Session, store_id: int) -> Store:
    store = db.scalar(_shops().where(Store.id == store_id))
    if store is None:
        raise AdminError("not_found", 404)
    return store


def store_card(db: Session, store: Store) -> dict:
    """The profile, the branches with addresses, goods, flags and reports. No stock, costs or stock journal."""
    offers = select(Offer.id).where(Offer.store_id == store.id)
    flags = db.execute(select(FraudFlag.status, func.count(FraudFlag.id)).where(FraudFlag.offer_id.in_(offers))
                       .group_by(FraudFlag.status)).all()
    reports = db.scalars(select(ChatReport).join(Conversation, Conversation.id == ChatReport.conversation_id)
                         .where(Conversation.store_id == store.id).order_by(ChatReport.id.desc())).all()
    return {
        **_store_row(db, store, _goods_counts(db, [store.id])),
        "inn_stir": store.inn_stir, "phone": store.phone, "telegram": store.telegram, "address": store.address,
        "hours": store.hours, "kind": store.kind.value,
        "branches": [{"id": b.id, "name": b.name, "city": b.city, "address": b.address, "landmark": b.landmark,
                      "is_main": b.is_main} for b in store.branches],
        "flags": {s.value: n for s, n in flags},
        "reports": [report_row(db, r) for r in reports],
        "builds": db.scalar(select(func.count(Build.id)).where(Build.store_id == store.id)),
        "history": [a for a in journal(db, limit=500) if a["target_type"] == "store" and a["target_id"] == str(store.id)][:20],
    }


def set_verified(db: Session, admin: User, store: Store, verified: bool, comment: str | None) -> None:
    store.is_verified = verified
    log(db, admin, "store_verify" if verified else "store_unverify", "store", store.id, store.name, comment)
    db.commit()


def set_store_blocked(db: Session, admin: User, store: Store, blocked: bool, reason: str | None,
                      action: str | None = None, details: dict | None = None) -> None:
    if blocked and not _text(reason):
        raise AdminError("reason_required")
    store.blocked_at = utcnow() if blocked else None
    store.block_reason = _text(reason, 300) if blocked else None
    log(db, admin, action or ("store_block" if blocked else "store_unblock"), "store", store.id, store.name, reason,
        **(details or {}))
    _tell(db, store, "admin_store", blocked=blocked, reason=store.block_reason or "")
    db.commit()


# --- users ------------------------------------------------------------------------------------------------------------

def _user_row(u: User) -> dict:
    return {"id": u.id, "email": u.email, "role": u.role.value, "created_at": _aware(u.created_at),
            "blocked": u.blocked_at is not None, "block_reason": u.block_reason,
            "store": u.stores[0].name if u.stores else None}


def list_users(db: Session, q: str | None = None, role: str | None = None, blocked: bool | None = None) -> list[dict]:
    query = select(User).where(~User.email.like("telegram+%")).order_by(User.id.desc()).limit(200)
    if q:
        query = query.where(func.py_lower(User.email).contains(q.lower().strip()))
    if role:
        query = query.where(User.role == role)
    if blocked is not None:
        query = query.where(User.blocked_at.is_not(None) if blocked else User.blocked_at.is_(None))
    return [_user_row(u) for u in db.scalars(query)]


def set_user_blocked(db: Session, admin: User, user: User, blocked: bool, reason: str | None,
                     action: str | None = None, details: dict | None = None) -> None:
    if user.role == UserRole.admin:
        raise AdminError("admin_untouchable", 403)
    if blocked and not _text(reason):
        raise AdminError("reason_required")
    user.blocked_at = utcnow() if blocked else None
    user.block_reason = _text(reason, 300) if blocked else None
    log(db, admin, action or ("user_block" if blocked else "user_unblock"), "user", user.id, user.email, reason,
        **(details or {}))
    db.commit()


# --- chat reports -----------------------------------------------------------------------------------------------------

def report_row(db: Session, r: ChatReport) -> dict:
    conv = db.get(Conversation, r.conversation_id)
    reporter = db.get(User, r.reporter_id)
    store = conv.store if conv else None
    side = "store" if store is not None and reporter is not None and store.user_id == reporter.id else "buyer"
    return {"id": r.id, "reason": r.reason, "comment": r.comment, "status": r.status, "resolution": r.resolution,
            "admin_comment": r.admin_comment, "created_at": _aware(r.created_at), "resolved_at": _aware(r.resolved_at),
            "reporter": reporter.email if reporter else None, "reporter_side": side, "is_demo": r.is_demo,
            "store": {"id": store.id, "name": store.name, "blocked": store.blocked_at is not None} if store else None,
            "buyer": ({"id": conv.buyer.id, "email": conv.buyer.email, "blocked": conv.buyer.blocked_at is not None}
                      if conv else None),
            "topic": conv.topic_kind.value if conv else None}


def list_reports(db: Session, status: str | None = None) -> list[dict]:
    query = select(ChatReport).order_by(ChatReport.status != "new", ChatReport.id.desc())
    if status:
        query = query.where(ChatReport.status == status)
    return [report_row(db, r) for r in db.scalars(query)]


def report_detail(db: Session, report_id: int) -> dict:
    """Only the conversation this report is about: the admin reads no other chats."""
    r = db.get(ChatReport, report_id)
    if r is None:
        raise AdminError("not_found", 404)
    conv = db.get(Conversation, r.conversation_id)
    from app.services.chat import message_out

    messages = [{**message_out(m), "at": _aware(m.created_at)} for m in (conv.messages if conv else [])]
    return {**report_row(db, r), "conversation_id": conv.id if conv else None, "messages": messages}


def resolve_report(db: Session, admin: User, report_id: int, action: str, comment: str | None) -> None:
    r = db.get(ChatReport, report_id)
    if r is None:
        raise AdminError("not_found", 404)
    if action not in ("dismiss", "block_user", "block_store"):
        raise AdminError("bad_action")
    conv = db.get(Conversation, r.conversation_id)
    if action != "dismiss" and not _text(comment):
        raise AdminError("reason_required")
    title = f"#{r.id} · {conv.store.name if conv else ''}"
    r.status, r.resolution = "reviewed", {"dismiss": "dismissed"}.get(action, action)
    r.admin_comment, r.resolved_at = _text(comment), utcnow()
    if action == "dismiss":
        log(db, admin, "report_dismiss", "report", r.id, title, comment)
        db.commit()
    elif action == "block_user":
        set_user_blocked(db, admin, conv.buyer, True, comment, "report_block_user", {"report_id": r.id})
    else:
        set_store_blocked(db, admin, conv.store, True, comment, "report_block_store", {"report_id": r.id})


# --- disputed Anti-Fraud flags ----------------------------------------------------------------------------------------

def _flag_out(f: FraudFlag) -> dict:
    o = f.offer
    return {"id": f.id, "type": f.type, "level": f.level.value, "reason_key": f.reason_key, "params": f.params,
            "source": f.source.value, "status": f.status.value, "dispute_comment": f.dispute_comment,
            "disputed_at": _aware(f.disputed_at), "resolution": f.resolution, "admin_answer": f.admin_answer,
            "resolved_at": _aware(f.resolved_at),
            "offer": {"id": o.id, "raw_name": o.raw_name, "price": o.price, "currency": o.currency.value,
                      "condition": o.condition.value},
            "product": {"id": o.product.id, "name": o.product.normalized_name},
            "store": {"id": o.store.id, "name": o.store.name}}


def list_flags(db: Session, status: str = "disputed") -> list[dict]:
    query = select(FraudFlag).order_by(FraudFlag.disputed_at.desc(), FraudFlag.id.desc())
    if status == "disputed":
        query = query.where(FraudFlag.status == FlagStatus.disputed)
    else:
        query = query.where(FraudFlag.resolution.is_not(None)).limit(100)
    return [_flag_out(f) for f in db.scalars(query)]


def resolve_flag(db: Session, admin: User, flag_id: int, decision: str, answer: str | None) -> None:
    """upheld: the flag is right — active again with the answer; dismissed: off for good (antifraud keeps it off)."""
    f = db.get(FraudFlag, flag_id)
    if f is None:
        raise AdminError("not_found", 404)
    if decision not in ("upheld", "dismissed"):
        raise AdminError("bad_action")
    if decision == "upheld" and not _text(answer):
        raise AdminError("answer_required")
    f.status = FlagStatus.active if decision == "upheld" else FlagStatus.dismissed
    f.resolution, f.admin_answer, f.resolved_at = decision, _text(answer), utcnow()
    log(db, admin, f"flag_{decision}", "flag", f.id, f"{f.offer.store.name} · {f.offer.product.normalized_name}",
        answer, type=f.type)
    _tell(db, f.offer.store, "admin_flag", decision=decision, name=f.offer.product.normalized_name)
    db.commit()


def dispute_flag(db: Session, store: Store, flag_id: int, comment: str | None) -> FraudFlag:
    """The seller's "Оспорить флаг": off the storefront until the admin decides (as before phase 13)."""
    f = db.get(FraudFlag, flag_id)
    if f is None or f.offer.store_id != store.id:
        raise AdminError("not_found", 404)
    if f.status != FlagStatus.active or f.resolution == "upheld":
        raise AdminError("not_disputable")
    if not _text(comment):
        raise AdminError("comment_required")
    f.status, f.dispute_comment, f.disputed_at = FlagStatus.disputed, _text(comment), utcnow()
    from app.services import notifications as notify  # phase 12.5

    notify.notify_admins(db, "flag_disputed", "/admin/flags", store=store.name, name=f.offer.product.normalized_name)
    db.commit()
    return f


# --- card fixes (product_fixes) ---------------------------------------------------------------------------------------

def _fix_target(db: Session, fix: ProductFix) -> tuple[Category, tuple, Product | None]:
    from app.services.manual import card_fields

    after = fix.after or {}
    if after.get("merge_into"):  # phase 16.1: a possible duplicate — the decision is "merge into this card"
        other = db.get(Product, after["merge_into"])
        if other is None or other.merged_into:
            raise AdminError("not_found", 404)
        return other.category, (other.brand, other.normalized_name, other.specs_json, other.match_key), other
    category = db.scalar(select(Category).where(Category.slug == after.get("category")))
    if category is None:
        raise AdminError("unknown_category")
    fields = card_fields(category, after.get("brand"), after.get("model"), after.get("name"), after.get("specs") or {})
    other = db.scalar(select(Product).where(Product.match_key == fields[3], Product.id != fix.product_id))
    return category, fields, other


def merge_preview(db: Session, source: Product, target: Product) -> dict:
    """What moves to the target card: offers (with their stock), reservations, conversations, barcodes."""
    offer_ids = list(db.scalars(select(Offer.id).where(Offer.product_id == source.id)))
    target_stores = set(db.scalars(select(Offer.store_id).where(Offer.product_id == target.id)))
    both = db.scalar(select(func.count(Offer.id)).where(Offer.product_id == source.id, Offer.store_id.in_(target_stores))) if target_stores else 0
    return {
        "target": {"id": target.id, "name": target.normalized_name},
        "offers": len(offer_ids), "same_store": both,
        "reservations": db.scalar(select(func.count(Reservation.id)).where(Reservation.offer_id.in_(offer_ids))) if offer_ids else 0,
        "conversations": db.scalar(select(func.count(Conversation.id)).where(
            Conversation.topic_kind == TopicKind.offer, Conversation.topic_id.in_(offer_ids))) if offer_ids else 0,
        "barcodes": db.scalar(select(func.count(Barcode.id)).where(Barcode.offer_id.in_(offer_ids))) if offer_ids else 0,
        "stock_rows": sum(len(db.get(Offer, i).stocks) for i in offer_ids),
    }


def _fix_out(db: Session, fix: ProductFix, preview: bool = False) -> dict:
    product = db.get(Product, fix.product_id)
    store = db.get(Store, fix.store_id)
    out = {"id": fix.id, "status": fix.status, "before": fix.before, "after": fix.after,
           "created_at": _aware(fix.created_at), "resolved_at": _aware(fix.resolved_at),
           "reject_reason": fix.reject_reason, "merged_into": fix.merged_into, "is_demo": fix.is_demo,
           "kind": fix.kind or "fix",
           "store": {"id": store.id, "name": store.name} if store else None,
           "product": {"id": product.id, "name": product.normalized_name} if product else None,
           "stores_selling": len(set(db.scalars(select(Offer.store_id).where(
               Offer.product_id == fix.product_id, Offer.removed_at.is_(None))))) if product else 0}
    if preview and fix.status == "pending" and product is not None:
        try:
            _, (brand, name, specs, key), other = _fix_target(db, fix)
            out["result"] = {"name": name, "brand": brand, "match_key": key}
            out["merge"] = merge_preview(db, product, other) if other is not None else None
        except AdminError as e:
            out["result_error"] = e.code
    return out


def list_fixes(db: Session, status: str = "pending") -> list[dict]:
    query = select(ProductFix).order_by(ProductFix.id.desc())
    query = query.where(ProductFix.status == status) if status == "pending" else query.where(ProductFix.status != "pending").limit(100)
    return [_fix_out(db, f, preview=status == "pending") for f in db.scalars(query)]


def get_fix(db: Session, fix_id: int) -> ProductFix:
    fix = db.get(ProductFix, fix_id)
    if fix is None:
        raise AdminError("not_found", 404)
    return fix


def _merge_offer_into(db: Session, src: Offer, dst: Offer) -> None:
    """One store sold both cards: its offer of the old card ends (no price), everything it had goes to the
    store's offer of the target card — reservations, conversations, barcodes and stock (a journal line)."""
    from app.services.branches import recompute_offer
    from app.services.stock import _row, record

    for r in db.scalars(select(Reservation).where(Reservation.offer_id == src.id)):
        r.offer_id = dst.id
    for c in db.scalars(select(Conversation).where(Conversation.topic_kind == TopicKind.offer,
                                                   Conversation.topic_id == src.id)):
        clash = db.scalar(select(Conversation.id).where(
            Conversation.buyer_id == c.buyer_id, Conversation.store_id == c.store_id,
            Conversation.topic_kind == TopicKind.offer, Conversation.topic_id == dst.id))
        if clash is None:
            c.topic_id = dst.id
    db.flush()
    db.expire(src, ["barcodes"])
    db.expire(dst, ["barcodes"])
    for b in db.scalars(select(Barcode).where(Barcode.offer_id == src.id)):
        b.offer_id = dst.id  # one code — one offer of a store: the store had it only on the old offer
    db.flush()
    for s in list(src.stocks):
        row = _row(dst, s.branch_id)
        q0, r0 = row.quantity, row.reserved or 0
        if s.quantity is not None or row.quantity is not None:
            row.quantity = (row.quantity or 0) + (s.quantity or 0)
        row.reserved = (row.reserved or 0) + (s.reserved or 0)
        row.in_stock = bool(row.in_stock or s.in_stock)
        record(dst, row, q0, r0, kind="adjust", reason="other", comment="merge")
        sq, sr = s.quantity, s.reserved or 0
        s.quantity, s.reserved, s.in_stock = (0 if s.quantity is not None else None), 0, False
        record(src, s, sq, sr, kind="adjust", reason="other", comment="merge")
    recompute_offer(dst)
    dst.is_in_stock = dst.is_in_stock or (src.is_in_stock and dst.price is not None)
    src.removed_at, src.price, src.is_in_stock = utcnow(), None, False


def merge_products(db: Session, source: Product, target: Product) -> dict:
    from app.services.barcodes import refresh_common

    from app.services.photos import move_owner

    preview = merge_preview(db, source, target)
    move_owner(db, "product", source.id, target.id)  # phase 14: card photos go to the kept card
    codes = set()
    for offer in db.scalars(select(Offer).where(Offer.product_id == source.id)).all():
        codes |= {b.code for b in offer.barcodes}
        dst = db.scalar(select(Offer).where(Offer.product_id == target.id, Offer.store_id == offer.store_id))
        if dst is None:
            offer.product_id = target.id  # its stock, barcodes, reservations and conversations move with it
        else:
            move_owner(db, "offer", offer.id, dst.id)
            _merge_offer_into(db, offer, dst)
    db.flush()
    # The ended duplicates keep their price history on the old card: it stays, out of the catalog (no offers on sale)
    for c in db.scalars(select(BuildComponent).where(BuildComponent.product_id == source.id)):
        c.product_id = target.id
    for a in db.scalars(select(ArchivePrice).where(ArchivePrice.product_id == source.id)):
        a.product_id = target.id
    for bc in db.scalars(select(BarcodeCode).where(BarcodeCode.product_id == source.id)):
        codes.add(bc.code)
    for bc in db.scalars(select(BarcodeCode).where(BarcodeCode.admin_product_id == source.id)):
        bc.admin_product_id = target.id
    db.flush()
    for code in codes:
        refresh_common(db, code)
    # Phase 16.1: the old address leads to the kept card; the old key no longer catches new price rows
    source.merged_into, source.match_key = target.id, f"merged:{source.id}"
    if (source.specs_json or {}).get("pack") != (target.specs_json or {}).get("pack"):
        # OEM and BOX of one CPU are one card: the packaging stays in each store's own row, not on the card
        target.specs_json = {k: v for k, v in (target.specs_json or {}).items() if k != "pack"}
    db.flush()
    return preview


def accept_fix(db: Session, admin: User, fix_id: int, comment: str | None = None) -> dict:
    """Through the dictionary and the normalizer, a new match key; the key of another card -> the cards merge."""
    from app.services.cabinet import recheck_flags

    fix = get_fix(db, fix_id)
    if fix.status != "pending":
        raise AdminError("already_decided")
    product = db.get(Product, fix.product_id)
    category, (brand, name, specs, key), other = _fix_target(db, fix)
    merged = None
    if other is not None:
        merged = merge_products(db, product, other)
        fix.merged_into = other.id
        product = other
    else:
        product.category, product.brand, product.model = category, brand, (fix.after or {}).get("model")
        product.normalized_name, product.specs_json, product.match_key = name, specs, key
    fix.status, fix.resolved_at = "accepted", utcnow()
    db.flush()
    offers = db.scalars(select(Offer).where(Offer.product_id == product.id, Offer.price.is_not(None))).all()
    for store_id in {o.store_id for o in offers}:
        recheck_flags(db, [o for o in offers if o.store_id == store_id], db.get(Store, store_id))
    log(db, admin, "fix_merge" if merged else "fix_accept", "fix", fix.id, name, comment,
        product_id=fix.product_id, **({"merged_into": other.id, **{k: v for k, v in merged.items() if k != "target"}}
                                     if merged else {}))
    if fix.kind != "duplicate":  # a possible duplicate came from the scan, not from this store
        _tell(db, fix.store_id, "admin_fix", status="accepted", name=name)
    db.commit()
    return {"status": "merged" if merged else "applied", "product_id": product.id, "merge": merged}


def reject_fix(db: Session, admin: User, fix_id: int, reason: str | None) -> None:
    fix = get_fix(db, fix_id)
    if fix.status != "pending":
        raise AdminError("already_decided")
    if not _text(reason):
        raise AdminError("reason_required")
    fix.status, fix.reject_reason, fix.resolved_at = "rejected", _text(reason, 300), utcnow()
    log(db, admin, "fix_reject", "fix", fix.id, (fix.before or {}).get("name"), reason)
    if fix.kind != "duplicate":
        _tell(db, fix.store_id, "admin_fix", status="rejected", name=(fix.before or {}).get("name") or "")
    db.commit()


# --- barcode conflicts ------------------------------------------------------------------------------------------------

def _code_out(db: Session, common: BarcodeCode | None, code: str) -> dict:
    rows = db.execute(select(Barcode, Offer.product_id).join(Offer, Barcode.offer_id == Offer.id)
                      .where(Barcode.code == code)).all()
    by_product: dict[int, list] = {}
    for b, product_id in rows:
        store = db.get(Store, b.store_id)
        by_product.setdefault(product_id, []).append(
            {"id": store.id, "name": store.name, "admin_status": b.admin_status, "at": _aware(b.created_at)})
    return {"code": code, "status": common.status if common else None,
            "admin_status": common.admin_status if common else None,
            "product_id": common.product_id if common else None,
            "cards": [{"product_id": p, "name": db.get(Product, p).normalized_name, "stores": stores}
                      for p, stores in sorted(by_product.items())]}


def barcode_conflicts(db: Session) -> list[dict]:
    return [_code_out(db, c, c.code) for c in
            db.scalars(select(BarcodeCode).where(BarcodeCode.status == "conflict").order_by(BarcodeCode.code))]


def barcode_lookup(db: Session, raw: str) -> dict:
    from app.services.barcodes import BarcodeError, normalize

    try:
        code = normalize(raw)
    except BarcodeError as e:
        raise AdminError(f"barcode_{e.code}")
    return _code_out(db, db.scalar(select(BarcodeCode).where(BarcodeCode.code == code)), code)


def resolve_barcode(db: Session, admin: User, code: str, product_id: int | None, comment: str | None = None) -> dict:
    """product_id: "Правильная карточка — эта"; None: "Отклонить все" (the code stays out of the common base)."""
    from app.services.barcodes import refresh_common

    common = db.scalar(select(BarcodeCode).where(BarcodeCode.code == code))
    if common is None:
        raise AdminError("not_found", 404)
    cards = {c["product_id"] for c in _code_out(db, common, code)["cards"]}
    if product_id is not None and product_id not in cards:
        raise AdminError("bad_card")
    common.admin_status = "resolved" if product_id is not None else "rejected"
    common.admin_product_id = product_id
    stores = {s for c in (common.conflict_json or []) for s in c.get("stores", [])}
    refresh_common(db, code)
    name = db.get(Product, product_id).normalized_name if product_id else None
    for store_id in sorted(stores):
        _tell(db, store_id, "admin_barcode", code=code, status=common.admin_status)
    log(db, admin, "barcode_resolve" if product_id else "barcode_reject", "barcode", code, name or code, comment,
        product_id=product_id)
    db.commit()
    return _code_out(db, common, code)


# --- Telegram channels ------------------------------------------------------------------------------------------------

def _channel_out(db: Session, ch: TgChannel) -> dict:
    ads = db.scalar(select(func.count(Offer.id)).where(Offer.store_id == ch.store_id, Offer.is_in_stock.is_(True),
                                                      Offer.removed_at.is_(None)))
    posts = db.scalar(select(func.count(TgPost.id)).where(TgPost.channel_id == ch.id))
    return {"id": ch.id, "username": ch.username, "title": ch.title, "city": ch.city, "enabled": ch.enabled,
            "checked_at": _aware(ch.checked_at), "ads": ads, "posts": posts, "last_log": ch.last_log,
            "last_error": ch.last_error, "url": f"https://t.me/s/{ch.username}"}


def list_channels(db: Session) -> list[dict]:
    return [_channel_out(db, ch) for ch in
            db.scalars(select(TgChannel).where(TgChannel.deleted_at.is_(None)).order_by(TgChannel.username))]


def get_channel(db: Session, channel_id: int) -> TgChannel:
    ch = db.get(TgChannel, channel_id)
    if ch is None or ch.deleted_at is not None:
        raise AdminError("not_found", 404)
    return ch


def add_channel(db: Session, admin: User, username: str, title: str | None, city: str, fetch=None) -> dict:
    """Checks first that the public feed t.me/s/<name> opens and has posts; a deleted channel comes back."""
    from app.db.seed import CITIES
    from app.services import telegram

    if city not in CITIES:
        raise AdminError("bad_city")
    name = (username or "").strip().removeprefix("https://").removeprefix("t.me/").removeprefix("s/").lstrip("@").strip("/")
    if not telegram.CHANNEL_NAME.match(name):
        raise AdminError("channel_name")
    old = db.scalar(select(TgChannel).where(TgChannel.username == name))
    if old is not None and old.deleted_at is None:
        raise AdminError("channel_exists")
    try:
        posts = telegram.parse_feed((fetch or telegram.fetch_page)(name))
    except Exception:  # noqa: BLE001 — any network or HTTP error means "the feed does not open"
        raise AdminError("channel_unreachable")
    if not posts:
        raise AdminError("channel_empty")
    if old is not None:  # deleted earlier: back with its history
        old.deleted_at, old.enabled, old.city, old.title = None, True, city, _text(title, 255) or old.title
        old.store.blocked_at, old.store.block_reason, old.store.city = None, None, city
        ch = old
    else:
        ch = telegram.add_channel(db, name, _text(title, 255), city)
    log(db, admin, "channel_add", "channel", ch.id, f"@{ch.username}", None, city=city, posts_on_page=len(posts))
    db.commit()
    return _channel_out(db, ch)


def edit_channel(db: Session, admin: User, ch: TgChannel, city: str | None, enabled: bool | None) -> dict:
    from app.db.seed import CITIES

    if city is not None and city != ch.city:
        if city not in CITIES:
            raise AdminError("bad_city")
        ch.city = ch.store.city = city
        log(db, admin, "channel_edit", "channel", ch.id, f"@{ch.username}", None, city=city)
    if enabled is not None and enabled != ch.enabled:
        ch.enabled = enabled
        log(db, admin, "channel_enable" if enabled else "channel_disable", "channel", ch.id, f"@{ch.username}")
    db.commit()
    return _channel_out(db, ch)


def delete_channel(db: Session, admin: User, ch: TgChannel) -> None:
    """Off the list and not collected; its ads are hidden (its store is blocked), nothing is erased."""
    ch.deleted_at, ch.enabled = utcnow(), False
    ch.store.blocked_at, ch.store.block_reason = utcnow(), "channel_deleted"
    log(db, admin, "channel_delete", "channel", ch.id, f"@{ch.username}")
    db.commit()


def save_run(ch: TgChannel, result) -> None:
    ch.last_log = {"at": utcnow().isoformat(), "fetched": result.fetched, "new": result.new, "parsed": result.parsed,
                   "offers": result.offers, "skipped": result.skipped, "sold": result.sold, "gone": result.gone,
                   "error": result.error}
    ch.last_error = result.error


async def fetch_channel(db: Session, admin: User, ch: TgChannel, fetch=None, parse=None, pause=None) -> dict:
    """"Собрать сейчас": one channel, at most 50 posts (the free AI limits)."""
    from app.services import telegram

    kwargs = {k: v for k, v in (("fetch", fetch), ("parse", parse), ("pause", pause)) if v is not None}
    result = await telegram.run_channel(db, ch, telegram.MAX_POSTS, **kwargs)
    save_run(ch, result)
    log(db, admin, "channel_fetch", "channel", ch.id, f"@{ch.username}", None, new=result.new, offers=result.offers,
        error=result.error)
    db.commit()
    return _channel_out(db, ch)


# --- what the seller sees of the admin's decisions --------------------------------------------------------------------

def seller_decisions(db: Session, store: Store) -> dict:
    offers = select(Offer.id).where(Offer.store_id == store.id)
    flags = db.scalars(select(FraudFlag).where(FraudFlag.offer_id.in_(offers), or_(
        FraudFlag.status == FlagStatus.disputed, FraudFlag.resolution.is_not(None)))
        .order_by(FraudFlag.disputed_at.desc())).all()
    fixes = db.scalars(select(ProductFix).where(ProductFix.store_id == store.id, ProductFix.kind != "duplicate")
                       .order_by(ProductFix.id.desc()).limit(30)).all()
    codes = db.execute(select(Barcode, Offer).join(Offer, Barcode.offer_id == Offer.id).where(
        Barcode.store_id == store.id, Barcode.admin_status == "disputed")).all()
    return {
        "flags": [_flag_out(f) for f in flags],
        "fixes": [_fix_out(db, f) for f in fixes],
        "barcodes": [{"id": b.id, "code": b.code, "offer_id": o.id, "name": o.product.normalized_name,
                      "chosen": (lambda c: db.get(Product, c.product_id).normalized_name
                                 if c is not None and c.product_id else None)(
                          db.scalar(select(BarcodeCode).where(BarcodeCode.code == b.code)))} for b, o in codes],
        "blocked": store.blocked_at is not None, "block_reason": store.block_reason,
    }
