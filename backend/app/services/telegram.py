"""Phase 9: ads of public Telegram channels from their web page t.me/s/<channel> (no Telegram account, no keys).

A run takes only the posts after the last processed one (at most MAX_POSTS for all channels), parses them with the
pipeline of "Paste as text" (code reads prices and currency; cache -> rules -> AI -> normalizer -> Anti-Fraud) and
publishes them as offers of the channel's own store of kind "telegram" (never verified, no cabinet).

Privacy: phones, @usernames, links and contact lines are cut out before anything is stored; the database keeps only
the cleaned text needed for the parse and the link to the post.
Freshness: a post edited to "sold" or gone from the channel takes its ad off; ads older than 30 days are hidden.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import NO_LOGIN
from app.db.models import (
    Currency, ImportStatus, Offer, OfferEvent, PriceImport, Store, StoreKind, TgChannel, TgPost, User,
    UserRole, utcnow,
)
from app.services.catalog import AD_DAYS
from app.services.importer import parse_clean_rows, publish_import
from app.services.photos import attach_from_url, delete_owner, fetch_image
from app.services.text_import import _is_ad as is_ad
from app.services.text_import import condition_of, find_price, no_rows_reason, text_to_rows

log = logging.getLogger(__name__)

MAX_POSTS = 50  # new posts per run, all channels together: the free AI limits
PAUSE_SECONDS = 3  # between channels and pages: t.me must not see a flood
MAX_PAGES = 5  # pages back in history for one channel per run
USER_AGENT = "Mozilla/5.0 (compatible; ALT-STORES-monitor/1.0)"
CHANNEL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

SOLD = re.compile(r"(?<![\w])(?:продан[оаы]?|продали|sold(?:\s*out)?|sotildi|sotilgan|сотилди|сотилган"
                  r"|sotib\s+bo['’ʻ]?ldi)(?![\w])", re.IGNORECASE)
# Parts of a PC named in a post: a whole PC or a kit ("B550M + R5 2600, 90$") has one price for several parts,
# it is not the price of one of them (ready PCs are builds of shops, phase B4)
KIT_PARTS = {
    "cpu": re.compile(r"\b(?:i[3579][\s-]?\d{4,5}\w*|ryzen|r[3579]\s?\d{4}\w*|xeon|athlon|pentium|celeron)\b|процессор|\bcpu\b"),
    "board": re.compile(r"\b[abhzx]\d{3}m?\b|материнск|\bm/b\b|motherboard"),
    "gpu": re.compile(r"\b(?:rtx|gtx|gt|rx)\s?-?\d{3,4}\b|видеокарт|\bgpu\b"),
    "ram": re.compile(r"\bddr[345]\b|\bozu\b|\bозу\b|оперативн|\bram\b"),
    "storage": re.compile(r"\bssd\b|\bnvme\b|\bhdd\b|жёстк|жестк"),
    "psu": re.compile(r"блок питания|\bpsu\b|\bбп\b"),
}
# Privacy: what is cut out of a post before it is stored or parsed
_URL = re.compile(r"(?:https?://|www\.)\S+|\bt\.me/\S+|\btelegram\.me/\S+", re.IGNORECASE)
_MENTION = re.compile(r"(?<![\w.])@[A-Za-z0-9_]{3,}")
_PHONE = re.compile(r"\+?\d[\d \-()]{7,}\d")
# A line that is about the contact person: "Тел: ...", "Звоните Алишер", "Admin: Jasur", "Aloqa uchun: ..."
_CONTACT_LINE = re.compile(
    r"^\W*(?:тел\b|тел\.|телефон|звонит|звоните|пишите|писать|обращаться|контакт|связь|для связи|админ|admin|менеджер"
    r"|manager|продавец|владелец|хозяин|имя|aloqa|murojaat|bog['’ʻ]?lanish|tel\b|tel:|phone|contact|call|whatsapp)",
    re.IGNORECASE,
)


def _is_phone(m: re.Match) -> bool:
    """+998 90 123 45 67 or 9+ digits; a price has fewer (12 500 000)."""
    return m[0].startswith("+") or sum(ch.isdigit() for ch in m[0]) >= 9


def scrub(text: str) -> str:
    """The post without phones, @usernames, links and contact lines (names live there). Prices stay."""
    lines = []
    for line in text.splitlines():
        if _CONTACT_LINE.search(line):
            continue
        line = _URL.sub(" ", line)
        line = _MENTION.sub(" ", line)
        line = _PHONE.sub(lambda m: " " if _is_phone(m) else m[0], line)
        lines.append(re.sub(r"[ \t]{2,}", " ", line).rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


@dataclass
class Post:
    id: int
    text: str = ""
    posted_at: datetime | None = None
    has_media: bool = False
    image_url: str | None = None  # phase 14: the first picture of the post (background-image of t.me/s)


class _FeedParser(HTMLParser):
    """The posts of a t.me/s page: id (data-post), text (without the quoted reply), date, whether there is a photo."""

    VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts: list[Post] = []
        self.stack: list[tuple[str, str]] = []  # (tag, class)
        self.post: Post | None = None
        self.post_depth = 0
        self.text_depth = 0  # depth of the message text element we read, 0 = not inside
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag in self.VOID:
            self._void(tag, a, cls)
            return
        self.stack.append((tag, cls))
        depth = len(self.stack)
        if self.post is None and "tgme_widget_message " in f"{cls} " and a.get("data-post"):
            post_id = a["data-post"].rsplit("/", 1)[-1]
            if post_id.isdigit() and "service_message" not in cls:
                self.post, self.post_depth, self.parts = Post(int(post_id)), depth, []
            return
        if self.post is None:
            return
        if "js-message_text" in cls and not self.text_depth and not self._in("tgme_widget_message_reply"):
            self.text_depth = depth
        if "tgme_widget_message_photo" in cls or "tgme_widget_message_video" in cls or "message_document" in cls:
            self.post.has_media = True
        if "tgme_widget_message_photo_wrap" in cls and self.post.image_url is None:
            m = re.search(r"background-image:\s*url\(['\"]?([^'\")]+)", a.get("style") or "")
            if m:
                self.post.image_url = m.group(1)
        if tag == "time" and a.get("datetime") and self._in("tgme_widget_message_date"):
            try:
                self.post.posted_at = datetime.fromisoformat(a["datetime"])
            except ValueError:
                pass

    def _void(self, tag, a, cls):
        if self.post is not None and self.text_depth and tag == "br":
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in self.VOID:
            self._void(tag, dict(attrs), dict(attrs).get("class") or "")
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID or not self.stack:
            return
        # Close up to the matching tag (t.me markup is well formed; this only guards against surprises)
        while self.stack:
            depth = len(self.stack)
            top, _ = self.stack.pop()
            if self.text_depth == depth:
                self.text_depth = 0
                self.parts.append("\n")
            if self.post is not None and depth == self.post_depth:
                self.post.text = "".join(self.parts).strip()
                self.posts.append(self.post)
                self.post = None
            if top == tag:
                break

    def handle_data(self, data):
        if self.post is not None and self.text_depth:
            self.parts.append(data)

    def _in(self, cls: str) -> bool:
        return any(cls in c for _, c in self.stack)


def parse_feed(html: str) -> list[Post]:
    parser = _FeedParser()
    parser.feed(html)
    parser.close()
    return sorted({p.id: p for p in parser.posts}.values(), key=lambda p: p.id)


def fetch_page(username: str, before: int | None = None) -> str:
    """One page of the public web view of a channel (about 20 latest posts, or those before a post id)."""
    params = {"before": before} if before else None
    res = httpx.get(f"https://t.me/s/{username}", params=params, headers={"User-Agent": USER_AGENT},
                    timeout=20, follow_redirects=True)
    res.raise_for_status()
    return res.text


def post_url(channel: TgChannel, post_id: int) -> str:
    return f"https://t.me/{channel.username}/{post_id}"


# ---------- channels ----------

def add_channel(db: Session, username: str, title: str | None = None, city: str = "tashkent") -> TgChannel:
    """A channel and its seller: a store of kind "telegram" owned by a service account nobody can log in with."""
    username = username.strip().removeprefix("https://").removeprefix("t.me/").removeprefix("s/").lstrip("@")
    if not CHANNEL_NAME.match(username):
        raise ValueError(f"not a channel name: {username!r}")
    if db.scalar(select(TgChannel).where(TgChannel.username == username)):
        raise ValueError(f"channel already added: {username}")
    user = User(email=f"telegram+{username.lower()}@alt-stores.local", password_hash=NO_LOGIN, role=UserRole.buyer)
    store = Store(owner=user, name=title or f"@{username}", kind=StoreKind.telegram, city=city, is_verified=False)
    channel = TgChannel(username=username, title=title or username, city=city, store=store)
    db.add(channel)
    db.commit()
    return channel


# ---------- a run ----------

@dataclass
class ChannelLog:
    username: str
    fetched: int = 0
    new: int = 0
    parsed: int = 0  # posts that became ads
    offers: int = 0
    skipped: dict = field(default_factory=dict)  # reason -> posts
    sold: int = 0
    gone: int = 0
    expired: int = 0
    error: str | None = None

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def _take_off(db: Session, channel: TgChannel, post: TgPost, status: str) -> int:
    """Sold or gone: its ads are hidden, unless a newer post of the channel has listed the product since."""
    url, n = post_url(channel, post.post_id), 0
    for offer in db.scalars(select(Offer).where(Offer.id.in_(post.offer_ids or []))):
        if offer.post_url == url and offer.removed_at is None:
            offer.is_in_stock, offer.removed_at = False, utcnow()
            offer.events.append(OfferEvent(field="removed", value=status, source="telegram"))
            delete_owner(db, "offer", offer.id)  # phase 14: the photo of a sold ad is not kept
            n += 1
    post.status = status
    return n


def skip_reason(text: str, has_media: bool) -> str | None:
    """Why a post is not an ad at all, before any parsing: no text, "sold", no price (only on a picture?)."""
    if not text.strip():
        return "image_price" if has_media else "no_text"
    if SOLD.search(text):
        return "sold"
    if not any(find_price(line)[0] is not None for line in text.splitlines()):
        if has_media:
            return "image_price"
        return "ad" if any(is_ad(line) for line in text.splitlines()) else "no_price"
    return None


def kit_reason(text: str, rows: int) -> str | None:
    """A whole PC ("build") or a kit of two parts with one price ("bundle"): not an ad of one part."""
    low = text.lower()
    parts = sum(bool(p.search(low)) for p in KIT_PARTS.values())
    if parts >= 3 and rows < parts:
        return "build"
    if parts == 2 and rows == 1:
        return "bundle"
    return None


def _check_known(db: Session, channel: TgChannel, visible: list[Post], log_: ChannelLog) -> None:
    """Posts seen before: edited to "sold" -> off; gone from the feed (inside the range we see) -> off."""
    if not visible:
        return
    by_id = {p.id: p for p in visible}
    lo, hi = min(by_id), max(by_id)
    known = db.scalars(select(TgPost).where(TgPost.channel_id == channel.id, TgPost.status == "parsed",
                                            TgPost.post_id >= lo, TgPost.post_id <= hi))
    for post in known:
        seen = by_id.get(post.post_id)
        if seen is None:
            _take_off(db, channel, post, "gone")
            log_.gone += 1
        elif SOLD.search(seen.text):
            _take_off(db, channel, post, "sold")
            log_.sold += 1


def expire_old(db: Session) -> int:
    """Ads older than 30 days leave the market (the pages hide them by the date anyway)."""
    old = datetime.now(timezone.utc) - timedelta(days=AD_DAYS)
    offers = db.scalars(select(Offer).join(Store, Store.id == Offer.store_id).where(
        Store.kind == StoreKind.telegram, Offer.is_in_stock.is_(True), Offer.posted_at < old)).all()
    for offer in offers:
        offer.is_in_stock = False
        offer.events.append(OfferEvent(field="stock", value="0", source="telegram"))
    db.commit()
    return len(offers)


def _new_posts(channel: TgChannel, fetch, pause) -> tuple[list[Post], list[Post]]:
    """(the latest page, the posts after the last processed one, oldest first)."""
    latest = parse_feed(fetch(channel.username))
    posts = {p.id: p for p in latest if p.id > channel.last_post_id}
    # A channel seen before with a long gap: go back page by page until the last processed post
    pages, oldest = 1, min(posts) if posts else None
    while channel.last_post_id and oldest and oldest > channel.last_post_id + 1 and pages < MAX_PAGES:
        pause()
        older = [p for p in parse_feed(fetch(channel.username, oldest)) if p.id > channel.last_post_id]
        if not older or min(p.id for p in older) >= oldest:
            break
        posts.update({p.id: p for p in older})
        oldest, pages = min(posts), pages + 1
    return latest, sorted(posts.values(), key=lambda p: p.id)


async def _publish_posts(db: Session, channel: TgChannel, items: list[tuple[Post, TgPost]], log_: ChannelLog,
                         parse, fetch_photo=None) -> None:
    """All new posts of a channel through one parse (cache -> rules -> AI), then one publication per post."""
    rows_by_post: dict[int, list] = {}
    all_rows = []
    for post, record in items:
        rows = text_to_rows(record.text)
        if not rows:
            reason = {"no_prices": "no_price"}.get(no_rows_reason(record.text), "no_model")
            if reason == "no_model" and any(is_ad(line) for line in record.text.splitlines()):
                reason = "ad"  # "Скидки! Пишите в лс" with a number, but no product
            record.status, record.reason = "skipped", reason
            log_.skip(record.reason)
            continue
        if reason := kit_reason(record.text, len(rows)):
            record.status, record.reason = "skipped", reason
            log_.skip(reason)
            continue
        for row in rows:
            row.row = len(all_rows) + 1
            all_rows.append(row)
        rows_by_post[post.id] = rows
    if not all_rows:
        db.commit()
        return
    stats: dict = {}
    parsed = {r["row"]: r for r in await parse(db, all_rows, stats)}
    imp = PriceImport(store_id=channel.store_id, filename=f"t.me/{channel.username}", source="telegram",
                      mode="append", currency=Currency.USD, status=ImportStatus.ready, stats_json=stats)
    db.add(imp)
    db.flush()
    store = channel.store
    published: list[dict] = []
    for post, record in items:
        if post.id not in rows_by_post:
            continue
        clean = {r.row: r for r in rows_by_post[post.id]}
        rows = [parsed[n] for n in clean if n in parsed]
        if any(r["source"] == "failed" for r in rows):
            record.status, record.reason = "failed", "ai_failed"  # tried again next run
            log_.skip("ai_failed")
            continue
        priced = [r for r in rows if r.get("price") is not None]
        rows = [r for r in priced if r.get("category") != "other"]
        if not rows:
            # Not a computer part the catalog has (a tablet, a phone) or no product found at all
            record.status, record.reason = "skipped", "other_category" if priced else "no_model"
            log_.skip(record.reason)
            continue
        for r in rows:
            # Only what the seller wrote: "new" counts in the market of new goods, silence is "not said" (used group)
            r["condition"] = clean[r["row"]].condition or condition_of(record.text)
        touched: list[int] = []
        publish_import(db, imp, store, rows, mode="append", touched=touched)
        changed = db.scalars(select(Offer).where(Offer.id.in_(touched))).all()
        url = post_url(channel, post.id)
        for offer in changed:
            offer.post_url, offer.posted_at = url, post.posted_at or utcnow()
            if fetch_photo is not None and post.image_url:
                attach_from_url(db, offer, post.image_url, fetch_photo)  # phase 14; no photo if it fails
        record.status, record.reason, record.offer_ids = "parsed", None, [o.id for o in changed]
        published.extend(rows)
        log_.parsed += 1
        log_.offers += len(changed)
    imp.status, imp.rows_json = ImportStatus.published, published
    db.commit()


async def run_channel(db: Session, channel: TgChannel, budget: int, fetch=fetch_page, parse=parse_clean_rows,
                      pause=lambda: time.sleep(PAUSE_SECONDS), fetch_photo=None) -> ChannelLog:
    log_ = ChannelLog(channel.username)
    if fetch_photo is None and fetch is fetch_page:
        fetch_photo = fetch_image  # live run: the picture is downloaded too (never in tests with a fake page)
    try:
        latest, new = _new_posts(channel, fetch, pause)
    except (httpx.HTTPError, ValueError) as e:
        log_.error = str(e)[:200]
        return log_
    log_.fetched = len(latest)
    _check_known(db, channel, latest, log_)
    # Posts that failed on the AI last time come back first; then the new ones, oldest first, within the budget
    retry = db.scalars(select(TgPost).where(TgPost.channel_id == channel.id, TgPost.status == "failed")).all()
    old = datetime.now(timezone.utc) - timedelta(days=AD_DAYS)
    items: list[tuple[Post, TgPost]] = [(Post(r.post_id, r.text, r.posted_at), r) for r in retry[:budget]]
    for post in new[: max(0, budget - len(items))]:
        log_.new += 1
        record = TgPost(channel_id=channel.id, post_id=post.id, posted_at=post.posted_at, text=scrub(post.text),
                        status="pending")
        db.add(record)
        channel.last_post_id = max(channel.last_post_id, post.id)
        at = post.posted_at if post.posted_at is None or post.posted_at.tzinfo else post.posted_at.replace(tzinfo=timezone.utc)
        reason = "old" if at and at < old else skip_reason(record.text, post.has_media)
        if reason:
            record.status, record.reason = "skipped", reason
            log_.skip(reason)
        else:
            items.append((post, record))
    db.flush()
    await _publish_posts(db, channel, items, log_, parse, fetch_photo)
    channel.checked_at = utcnow()
    db.commit()
    return log_


async def run_all(db: Session, fetch=fetch_page, parse=parse_clean_rows, pause=lambda: time.sleep(PAUSE_SECONDS),
                  max_posts: int = MAX_POSTS) -> list[ChannelLog]:
    """One run over the enabled channels: at most max_posts new posts in all, a pause between channels."""
    logs, budget = [], max_posts
    channels = db.scalars(select(TgChannel).where(TgChannel.enabled.is_(True)).order_by(TgChannel.checked_at.is_not(None),
                                                                                     TgChannel.checked_at)).all()
    for i, channel in enumerate(channels):
        if i:
            pause()
        result = await run_channel(db, channel, budget, fetch, parse, pause)
        budget -= result.new
        logs.append(result)
        if budget <= 0:
            break
    expired = expire_old(db)
    if logs:
        logs[0].expired = expired
    return logs

