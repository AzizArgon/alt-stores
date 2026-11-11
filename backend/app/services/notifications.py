"""Phase 12.5: notifications — the bell of the cabinet, the storefront and the admin.

A notification is made by an event of the existing code (a message, a reservation, a sale, an upload, an admin
decision) and is added to the caller's session: it is saved with the caller's own commit, the logic of the event
does not change. The text is an i18n key + params (`notify.<kind>` in ru.json), never a stored sentence.

Repeats are joined by `group_key`: several messages in one conversation while unread — one notification with a
number; "товар заканчивается" — at most once a day per item. Notifications older than 30 days are deleted (the hourly
job and every list)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Notification, Store, User, UserRole, utcnow

KEEP_DAYS = 30
# Kinds by type: the icon and the filter of "Все уведомления"
TYPES = {
    "messages": ("message",),
    "reservations": ("reservation_new", "reservation_cancelled", "reservation_expired", "reservation_confirmed",
                     "reservation_ready", "reservation_cancelled_store", "reservation_branch", "reservation_expiring"),
    "stock": ("low_stock", "oversold"),
    "imports": ("import_ready", "import_failed"),
    "admin": ("admin_flag", "admin_fix", "admin_barcode", "admin_store", "report", "flag_disputed", "fix_suggested",
              "barcode_conflict", "photo_review", "photo_approved", "photo_rejected"),
}
TYPE_OF = {k: t for t, kinds in TYPES.items() for k in kinds}


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def notify(db: Session, user_id: int | None, kind: str, link: str, group: str | None = None, **params) -> Notification | None:
    """A notification for one user; an unread one of the same group gets +1 and moves up instead of a new one."""
    if not user_id:
        return None
    now = utcnow()
    if group:
        db.flush()
        n = db.scalar(select(Notification).where(Notification.user_id == user_id, Notification.group_key == group,
                                                 Notification.is_read.is_(False)).order_by(Notification.id.desc()))
        if n is not None:
            n.count = (n.count or 1) + 1
            n.kind, n.link, n.created_at = kind, link, now
            n.params = {**params, "count": n.count}
            return n
    n = Notification(user_id=user_id, kind=kind, link=link, group_key=group, params={**params, "count": 1},
                     created_at=now)
    db.add(n)
    return n


def notify_once(db: Session, user_id: int | None, kind: str, link: str, group: str, days: float | None = 1,
                **params) -> Notification | None:
    """At most one notification of `group` in `days` (None — ever, within the 30 days kept)."""
    if not user_id:
        return None
    db.flush()
    q = select(Notification.id).where(Notification.user_id == user_id, Notification.group_key == group)
    if days is not None:
        q = q.where(Notification.created_at >= utcnow() - timedelta(days=days))
    if db.scalar(q.limit(1)) is not None:
        return None
    n = Notification(user_id=user_id, kind=kind, link=link, group_key=group, params={**params, "count": 1},
                     created_at=utcnow())
    db.add(n)
    return n


def owner(db: Session, store: Store | int | None) -> int | None:
    """The account of a store (one account per store)."""
    if isinstance(store, int):
        store = db.get(Store, store)
    return store.user_id if store is not None else None


def notify_admins(db: Session, kind: str, link: str, group: str | None = None, **params) -> None:
    for uid in db.scalars(select(User.id).where(User.role == UserRole.admin, User.blocked_at.is_(None))).all():
        notify(db, uid, kind, link, group, **params)


def read_group(db: Session, user_id: int, group: str) -> None:
    """The user opened what the notification is about (a conversation): it becomes read."""
    db.query(Notification).filter(Notification.user_id == user_id, Notification.group_key == group,
                                  Notification.is_read.is_(False)).update({"is_read": True}, synchronize_session="fetch")


# --- lists ------------------------------------------------------------------------------------------------------------

def purge(db: Session) -> int:
    n = db.execute(delete(Notification).where(Notification.created_at < utcnow() - timedelta(days=KEEP_DAYS))).rowcount
    db.commit()
    return n or 0


def out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "type": TYPE_OF.get(n.kind, "other"), "params": n.params or {}, "link": n.link,
            "count": n.count or 1, "is_read": n.is_read, "created_at": _aware(n.created_at)}


def unread_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                               Notification.is_read.is_(False))) or 0


def list_for(db: Session, user: User, type_: str | None = None, limit: int = 10, offset: int = 0) -> dict:
    purge(db)
    q = select(Notification).where(Notification.user_id == user.id)
    if type_ in TYPES:
        q = q.where(Notification.kind.in_(TYPES[type_]))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [out(n) for n in items], "total": total, "unread": unread_count(db, user)}


def mark_read(db: Session, user: User, notification_id: int) -> bool:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        return False
    n.is_read = True
    db.commit()
    return True


def mark_all(db: Session, user: User) -> int:
    n = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).update(
        {"is_read": True}, synchronize_session="fetch")
    db.commit()
    return n
