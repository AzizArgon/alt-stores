"""Phase 10: chat of a buyer with a store about one topic (an offer, a build or a question to the store).

Not a messenger "about everything": a conversation is tied to its topic, one per buyer + store + topic.
Only the two sides read and write it. The seller never sees the buyer's email: "Buyer No. <id>".
No WebSocket: the open conversation asks for new messages (after_id) every few seconds.
"""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Build, ChatReport, Conversation, Message, MessageAuthor, Offer, Store, StoreBlock, StoreKind, TopicKind, User,
    UserRole, utcnow,
)
from app.services.exchange import to_usd, to_uzs

MAX_TEXT = 2000
PER_MINUTE = 20
PER_DAY = 300
NEW_PER_DAY = 20
NO_ANSWER_HOURS = 24
REPORT_REASONS = ("spam", "abuse", "fraud", "other")


class ChatError(Exception):
    """A refused action: the code (and HTTP status) goes to the client, the text is in ru.json (chat.error.<code>)."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code, self.status = code, status


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


# --- Who is who -------------------------------------------------------------------------------------------------------

def side_of(db: Session, user: User) -> tuple[str, Store | None]:
    """A seller speaks for their store; anyone else (a buyer) for themself."""
    if user.role == UserRole.seller:
        store = db.scalar(select(Store).where(Store.user_id == user.id))
        if store is None:
            raise ChatError("no_store", 404)
        return "store", store
    return "buyer", None


def _mine(db: Session, user: User) -> tuple[str, object]:
    """(side, SQL condition of "my conversations")."""
    side, store = side_of(db, user)
    return side, (Conversation.store_id == store.id) if side == "store" else (Conversation.buyer_id == user.id)


def get_conversation(db: Session, user: User, conv_id: int) -> tuple[str, Conversation]:
    """Only the two sides: for anyone else the conversation does not exist (404, not 403)."""
    side, mine = _mine(db, user)
    conv = db.scalar(select(Conversation).where(Conversation.id == conv_id, mine))
    if conv is None:
        raise ChatError("not_found", 404)
    return side, conv


def _other(side: str) -> MessageAuthor:
    return MessageAuthor.store if side == "buyer" else MessageAuthor.buyer


def is_blocked(db: Session, store_id: int, user_id: int) -> bool:
    return db.scalar(select(StoreBlock.id).where(StoreBlock.store_id == store_id, StoreBlock.user_id == user_id)) is not None


# --- Topic card -------------------------------------------------------------------------------------------------------

def _price(price, currency, usd_rate) -> dict:
    return {"price": price, "currency": currency.value, "price_uzs": to_uzs(price, currency, usd_rate),
            "price_usd": to_usd(price, currency, usd_rate)}


def topic_card(db: Session, conv: Conversation, usd_rate: float | None) -> dict:
    """What the conversation is about, as it is now: the price may have changed, the offer may be gone."""
    kind = conv.topic_kind
    if kind == TopicKind.offer:
        o = db.get(Offer, conv.topic_id)
        if o is None:
            return {"kind": "offer", "missing": True}
        on_sale = o.is_in_stock and o.removed_at is None and o.price is not None
        return {"kind": "offer", "title": o.product.normalized_name, "product_id": o.product_id,
                "category": o.product.category.slug if o.product.category else "other",
                "condition": o.condition.value, "in_stock": on_sale, **_price(o.price, o.currency, usd_rate)}
    if kind == TopicKind.build:
        b = db.get(Build, conv.topic_id)
        if b is None:
            return {"kind": "build", "missing": True}
        return {"kind": "build", "title": b.name, "build_id": b.id, "category": "build", "condition": b.condition.value,
                "in_stock": b.is_in_stock, **_price(b.price, b.currency, usd_rate)}
    if kind == TopicKind.reservation:
        from app.services.reservations import topic
        return topic(db, conv, usd_rate)
    return {"kind": kind.value, "title": conv.store.name, "store_id": conv.store_id}


# --- Opening a conversation ("Write to the seller") -------------------------------------------------------------------

def _topic_store(db: Session, kind: TopicKind, topic_id: int, store_id: int | None) -> tuple[Store, int]:
    if kind == TopicKind.offer:
        offer = db.get(Offer, topic_id)
        if offer is None:
            raise ChatError("not_found", 404)
        return offer.store, topic_id
    if kind == TopicKind.build:
        build = db.get(Build, topic_id)
        if build is None:
            raise ChatError("not_found", 404)
        return build.store, topic_id
    if kind == TopicKind.reservation:  # made together with the reservation, not by "Write"
        raise ChatError("bad_topic")
    store = db.get(Store, store_id) if store_id else None
    if store is None:
        raise ChatError("not_found", 404)
    return store, 0


def open_conversation(db: Session, user: User, kind: str, topic_id: int = 0, store_id: int | None = None) -> Conversation:
    """The existing conversation of this buyer + store + topic, or a new one (without messages yet)."""
    if user.role != UserRole.buyer:
        raise ChatError("buyers_only", 403)
    try:
        topic = TopicKind(kind)
    except ValueError:
        raise ChatError("bad_topic")
    store, topic_id = _topic_store(db, topic, topic_id, store_id)
    # A Telegram channel is not a store (only "Open the post"); an archive price list has nobody to answer
    if store.kind == StoreKind.telegram or store.is_archive:
        raise ChatError("not_a_store")
    same = select(Conversation).where(
        Conversation.buyer_id == user.id, Conversation.store_id == store.id,
        Conversation.topic_kind == topic, Conversation.topic_id == topic_id)
    conv = db.scalar(same)
    if conv is not None:
        return conv
    if is_blocked(db, store.id, user.id):
        raise ChatError("blocked", 403)
    if store.blocked_at is not None:  # phase 13: no new conversations with a blocked store (old ones stay)
        raise ChatError("store_blocked", 403)
    day_ago = utcnow() - timedelta(days=1)
    started = db.scalar(select(func.count(Conversation.id)).where(
        Conversation.buyer_id == user.id, Conversation.created_at >= day_ago))
    if started >= NEW_PER_DAY:
        raise ChatError("rate_new", 429)
    conv = Conversation(buyer_id=user.id, store_id=store.id, topic_kind=topic, topic_id=topic_id)
    db.add(conv)
    try:
        db.commit()
    except IntegrityError:  # two clicks at once: the other request has just made it
        db.rollback()
        conv = db.scalar(same)
    return conv


# --- Messages ---------------------------------------------------------------------------------------------------------

def message_out(m: Message) -> dict:
    out = {"id": m.id, "author": m.author.value, "text": m.text, "is_read": m.is_read, "created_at": _aware(m.created_at)}
    if m.author == MessageAuthor.system:  # a reservation status line: key + params, the text is in ru.json
        try:
            line = json.loads(m.text)
            out.update(text="", key=line["key"], params=line.get("params") or {})
        except (ValueError, KeyError, TypeError):
            pass
    return out


def send_message(db: Session, user: User, conv_id: int, text: str) -> Message:
    side, conv = get_conversation(db, user, conv_id)
    text = (text or "").strip()
    if not text:
        raise ChatError("empty")
    if len(text) > MAX_TEXT:
        raise ChatError("too_long")
    if side == "buyer" and is_blocked(db, conv.store_id, user.id):
        raise ChatError("blocked", 403)
    now = utcnow()
    mine = and_(Message.sender_id == user.id, Message.author != MessageAuthor.system)
    if db.scalar(select(func.count(Message.id)).where(mine, Message.created_at >= now - timedelta(minutes=1))) >= PER_MINUTE:
        raise ChatError("rate_minute", 429)
    if db.scalar(select(func.count(Message.id)).where(mine, Message.created_at >= now - timedelta(days=1))) >= PER_DAY:
        raise ChatError("rate_day", 429)
    msg = Message(conversation_id=conv.id, author=MessageAuthor(side), sender_id=user.id, text=text, created_at=now)
    conv.last_message_at = now
    db.add(msg)
    db.commit()
    return msg


def read_messages(db: Session, user: User, conv_id: int, after_id: int = 0) -> tuple[str, Conversation, list[Message]]:
    """Messages after `after_id` (0 = all); what the other side wrote becomes read."""
    side, conv = get_conversation(db, user, conv_id)
    db.query(Message).filter(Message.conversation_id == conv.id, _unread_q(side, user.id)).update(
        {"is_read": True}, synchronize_session="fetch")
    db.commit()
    msgs = db.scalars(select(Message).where(Message.conversation_id == conv.id, Message.id > after_id)
                      .order_by(Message.id)).all()
    return side, conv, list(msgs)


# --- Lists and counters -----------------------------------------------------------------------------------------------

def _unread_q(side: str, user_id: int | None = None):
    """Not mine and not read. A system line (reservation status) is for the other side of the one who changed it."""
    cond = and_(Message.author != MessageAuthor(side), Message.is_read.is_(False))
    if user_id is None:
        return cond
    return and_(cond, or_(Message.author != MessageAuthor.system, Message.sender_id.is_(None),
                          Message.sender_id != user_id))


def unread_count(db: Session, user: User) -> int:
    side, mine = _mine(db, user)
    return db.scalar(select(func.count(Message.id)).join(Message.conversation).where(mine, _unread_q(side, user.id))) or 0


def list_conversations(db: Session, user: User, usd_rate: float | None, filter_: str = "all") -> list[dict]:
    """Newest first. Seller filters: unread, offer (about products), build (about builds).
    A conversation without messages yet is shown only to the buyer who opened it."""
    side, mine = _mine(db, user)
    q = select(Conversation).where(mine)
    if side == "store":
        q = q.where(Conversation.messages.any())
    if filter_ in ("offer", "build"):
        q = q.where(Conversation.topic_kind == TopicKind(filter_))
    convs = db.scalars(q.order_by(Conversation.last_message_at.desc())).all()
    unread = dict(db.execute(
        select(Message.conversation_id, func.count(Message.id))
        .where(Message.conversation_id.in_([c.id for c in convs]), _unread_q(side, user.id))
        .group_by(Message.conversation_id)).all())
    blocked = {b for (b,) in db.execute(select(StoreBlock.user_id).where(
        StoreBlock.store_id.in_({c.store_id for c in convs})))} if side == "store" else set()
    out = []
    for c in convs:
        if filter_ == "unread" and not unread.get(c.id):
            continue
        last = c.messages[-1] if c.messages else None
        out.append({**conversation_head(db, c, side, usd_rate, c.buyer_id in blocked),
                    "last": message_out(last) if last else None, "unread": unread.get(c.id, 0)})
    return out


def conversation_head(db: Session, c: Conversation, side: str, usd_rate: float | None, blocked: bool | None = None) -> dict:
    """The other side as this side may see it: a store by name; a buyer only by number (never the email)."""
    if blocked is None:
        blocked = is_blocked(db, c.store_id, c.buyer_id)
    return {"id": c.id, "topic": topic_card(db, c, usd_rate), "store": {"id": c.store_id, "name": c.store.name},
            "buyer_no": c.buyer_id, "is_demo": c.is_demo, "blocked": blocked, "last_message_at": _aware(c.last_message_at),
            "side": side}


def overview_counts(db: Session, store: Store) -> dict:
    """For the cabinet overview: new messages and conversations where the buyer waits longer than a day."""
    new = db.scalar(select(func.count(Message.id)).join(Message.conversation).where(
        Conversation.store_id == store.id, _unread_q("store", store.user_id))) or 0
    waiting = 0
    since = utcnow() - timedelta(hours=NO_ANSWER_HOURS)
    for conv in db.scalars(select(Conversation).where(Conversation.store_id == store.id,
                                                      Conversation.last_message_at < since)):
        last = next((m for m in reversed(conv.messages) if m.author != MessageAuthor.system), None)
        if last is not None and last.author == MessageAuthor.buyer and _aware(last.created_at) < since:
            waiting += 1
    return {"new_messages": new, "waiting_day": waiting}


# --- Report and block -------------------------------------------------------------------------------------------------

def report(db: Session, user: User, conv_id: int, reason: str, comment: str | None) -> ChatReport:
    _, conv = get_conversation(db, user, conv_id)
    if reason not in REPORT_REASONS:
        raise ChatError("bad_reason")
    item = ChatReport(conversation_id=conv.id, reporter_id=user.id, reason=reason,
                      comment=(comment or "").strip()[:MAX_TEXT] or None)
    db.add(item)
    db.commit()
    return item


def set_block(db: Session, user: User, conv_id: int, blocked: bool) -> None:
    """The seller blocks the buyer of this conversation in the whole store (all topics)."""
    side, conv = get_conversation(db, user, conv_id)
    if side != "store":
        raise ChatError("sellers_only", 403)
    row = db.scalar(select(StoreBlock).where(StoreBlock.store_id == conv.store_id, StoreBlock.user_id == conv.buyer_id))
    if blocked and row is None:
        db.add(StoreBlock(store_id=conv.store_id, user_id=conv.buyer_id))
    elif not blocked and row is not None:
        db.delete(row)
    db.commit()
