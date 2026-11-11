"""Phase 14: photos of cards, offers and builds.

- A card photo (owner "product") is the model's photo, one set for all stores. A store that sells the card uploads
  it with the tick "У меня есть право использовать это фото"; when it is the only seller the photo is published at
  once, otherwise it waits for the admin (section «Фото»). Up to 5, one main.
- An offer photo is the store's own item (used goods above all): up to 6, no moderation, never trimmed.
- A build photo: up to 6, as offer photos.

Upload -> draft (the seller sees the standard result, may adjust it in the cropper) -> "Сохранить" -> published /
pending. Every file goes through app/services/storage.py; deleted photos are deleted from it after the commit.
"""

import logging
from datetime import timedelta

from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from app.core import photo_standard as S
from app.core.limits import spend, too_many, used_today
from app.db.models import Build, Offer, Photo, Product, Store, User, utcnow
from app.services import imaging
from app.services.imaging import Layout, PhotoError
from app.services.storage import get_storage, new_key

log = logging.getLogger(__name__)

OWNERS = ("product", "offer", "build")
LIMITS = {"product": S.CARD_MAX, "offer": S.OFFER_MAX, "build": S.BUILD_MAX}
LIVE = ("published", "pending", "draft")


# --- files are deleted after the commit (a rolled back delete keeps them) ---------------------------------------------

def _trash(db: Session, *keys: str) -> None:
    db.info.setdefault("photo_trash", []).extend(k for k in keys if k)


@event.listens_for(Session, "after_commit")
def _empty_trash(session: Session) -> None:
    keys = session.info.pop("photo_trash", None)
    if keys:
        storage = get_storage()
        for key in keys:
            try:
                storage.delete(key)
            except Exception:  # a missing file must not break the request
                log.warning("photo file %s not deleted", key)


@event.listens_for(Session, "after_rollback")
def _keep_trash(session: Session) -> None:
    session.info.pop("photo_trash", None)


def _files(p: Photo) -> tuple[str, str, str]:
    return p.key, p.thumb_key, p.src_key


def delete_photo(db: Session, p: Photo) -> None:
    _trash(db, *_files(p))
    db.delete(p)


def delete_owner(db: Session, owner_type: str, owner_id: int) -> int:
    """All photos of an offer / build / card (the offer was deleted)."""
    rows = db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id)).all()
    for p in rows:
        delete_photo(db, p)
    return len(rows)


def _on_owner_delete(owner_type: str):
    def handler(_mapper, connection, target):
        rows = connection.execute(select(Photo.key, Photo.thumb_key, Photo.src_key).where(
            Photo.owner_type == owner_type, Photo.owner_id == target.id)).all()
        if not rows:
            return
        connection.execute(delete(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == target.id))
        from sqlalchemy.orm import object_session
        session = object_session(target)
        if session is not None:
            _trash(session, *[k for r in rows for k in r])
    return handler


event.listen(Offer, "after_delete", _on_owner_delete("offer"))
event.listen(Build, "after_delete", _on_owner_delete("build"))
event.listen(Product, "after_delete", _on_owner_delete("product"))


def move_owner(db: Session, owner_type: str, from_id: int, to_id: int) -> None:
    """Cards or offers merged by the admin: the photos go with them (the target keeps its main photo)."""
    has_main = db.scalar(select(Photo.id).where(Photo.owner_type == owner_type, Photo.owner_id == to_id,
                                                Photo.is_main.is_(True)).limit(1)) is not None
    for p in db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == from_id)):
        p.owner_id = to_id
        if has_main:
            p.is_main = False


def purge_drafts(db: Session) -> int:
    old = db.scalars(select(Photo).where(Photo.status == "draft",
                                         Photo.created_at < utcnow() - timedelta(hours=S.DRAFT_HOURS))).all()
    for p in old:
        delete_photo(db, p)
    db.commit()
    return len(old)


# --- access ------------------------------------------------------------------------------------------------------------

def check_owner(db: Session, store: Store, owner_type: str, owner_id: int) -> None:
    if owner_type == "offer":
        o = db.get(Offer, owner_id)
        ok = o is not None and o.store_id == store.id and o.removed_at is None
    elif owner_type == "build":
        b = db.get(Build, owner_id)
        ok = b is not None and b.store_id == store.id
    elif owner_type == "product":
        ok = db.scalar(select(Offer.id).where(Offer.product_id == owner_id, Offer.store_id == store.id,
                                              Offer.removed_at.is_(None)).limit(1)) is not None
    else:
        ok = False
    if not ok:
        raise PhotoError("not_yours")


def sellers(db: Session, product_id: int) -> set[int]:
    return set(db.scalars(select(Offer.store_id).where(Offer.product_id == product_id, Offer.removed_at.is_(None))))


def is_sole(db: Session, store: Store, product_id: int) -> bool:
    return sellers(db, product_id) <= {store.id}


# --- upload and render -------------------------------------------------------------------------------------------------

def _orig(claimed_w, claimed_h, w: int, h: int) -> tuple[int, int]:
    """The resolution the seller's file had before the browser shrank it: believed only when it is consistent."""
    try:
        cw, ch = int(claimed_w or 0), int(claimed_h or 0)
    except (TypeError, ValueError):
        return w, h
    if cw < w or ch < h or max(cw, ch) > S.MAX_SIDE or abs(cw / ch - w / h) > 0.03 * (w / h):
        return w, h
    return cw, ch


def _render(p: Photo, src) -> None:
    """(Re)makes the 1500 and 400 files from the source with new keys (the long browser cache never shows an old one)."""
    big = imaging.render(src, Layout(p.mode, p.zoom, p.ox, p.oy), trim=p.owner_type == "product")
    storage = get_storage()
    old = (p.key, p.thumb_key) if p.key else ()
    p.key, p.thumb_key = new_key(), new_key("t")
    storage.save(p.key, imaging.webp(big, S.QUALITY_BIG))
    storage.save(p.thumb_key, imaging.webp(imaging.thumb(big), S.QUALITY_THUMB))
    return old


def _source(img):
    src = imaging.shrink(img)
    key = new_key("s")
    get_storage().save(key, imaging.webp(src, 92))
    return src, key


def create(db: Session, owner_type: str, owner_id: int, data: bytes, store_id: int | None, status: str = "draft",
           orig_w=None, orig_h=None, source: str = "upload", mode: str | None = None) -> Photo:
    img = imaging.load(data)
    src, src_key = _source(img)
    ow, oh = _orig(orig_w, orig_h, *img.size)
    auto = imaging.auto_mode(src)
    box = list(imaging.product_box(src)) if owner_type == "product" else None
    p = Photo(box=box, owner_type=owner_type, owner_id=owner_id, store_id=store_id, status=status, src_key=src_key,
              src_w=src.width, src_h=src.height, orig_w=ow, orig_h=oh, mode=mode or auto, auto_mode=auto,
              source=source, key="", thumb_key="", position=10_000, zoom=1.0, ox=0.0, oy=0.0,
              is_main=False)
    _render(p, src)
    db.add(p)
    return p


def upload(db: Session, store: Store, owner_type: str, owner_id: int, data: bytes, orig_w=None, orig_h=None) -> Photo:
    if owner_type not in OWNERS:
        raise PhotoError("not_yours")
    check_owner(db, store, owner_type, owner_id)
    key = f"photos:store:{store.id}"
    if used_today(db, key) >= S.DAILY_UPLOADS:
        raise too_many("photo_limit", limit=S.DAILY_UPLOADS)
    own = db.scalar(select(func.count(Photo.id)).where(
        Photo.owner_type == owner_type, Photo.owner_id == owner_id, Photo.store_id == store.id,
        Photo.status.in_(LIVE))) or 0
    if own >= LIMITS[owner_type]:
        raise PhotoError("too_many", max=LIMITS[owner_type])
    p = create(db, owner_type, owner_id, data, store.id, orig_w=orig_w, orig_h=orig_h)
    spend(db, key)
    db.commit()
    return p


def adjust(db: Session, p: Photo, mode: str | None = None, zoom: float | None = None, ox: float | None = None,
           oy: float | None = None, rotate: int = 0) -> Photo:
    """The cropper (move, scale, background) and "повернуть": the square is made again from the kept source."""
    from PIL import Image
    from io import BytesIO

    storage = get_storage()
    src = Image.open(BytesIO(storage.read(p.src_key)))
    src.load()
    if rotate % 4:
        src = src.rotate(-90 * (rotate % 4), expand=True)
        old_src = p.src_key
        p.src_key = new_key("s")
        storage.save(p.src_key, imaging.webp(src, 92))
        p.src_w, p.src_h = src.size
        if (rotate % 2) == 1:
            p.orig_w, p.orig_h = p.orig_h, p.orig_w
        _trash(db, old_src)
        p.zoom, p.ox, p.oy = 1.0, 0.0, 0.0
        if p.owner_type == "product":
            p.box = list(imaging.product_box(src))
    if mode in ("white", "blur"):
        p.mode = mode
    if zoom is not None:
        p.zoom = min(max(float(zoom), 0.3), 4.0)
    if ox is not None:
        p.ox = min(max(float(ox), -0.5), 0.5)
    if oy is not None:
        p.oy = min(max(float(oy), -0.5), 0.5)
    old = _render(p, src)
    _trash(db, *old)
    db.commit()
    return p


# --- saving a set --------------------------------------------------------------------------------------------------------

def _set_main(db: Session, owner_type: str, owner_id: int, main: Photo | None) -> None:
    rows = db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id)).all()
    for p in rows:
        p.is_main = main is not None and p.id == main.id


def ensure_main(db: Session, owner_type: str, owner_id: int) -> None:
    """A set with published photos always has one main: the first by order (for cards — the largest)."""
    db.flush()
    pub = db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id,
                                         Photo.status == "published")).all()
    if not pub or any(p.is_main for p in pub):
        return
    if owner_type == "product":
        best = max(pub, key=lambda p: (p.orig_w * p.orig_h, -p.id))
    else:
        best = min(pub, key=lambda p: (p.position, p.id))
    best.is_main = True


def save_set(db: Session, store: Store, user: User, owner_type: str, owner_id: int, ids: list[int],
             main_id: int | None = None, rights: bool = False) -> dict:
    """The seller's "Сохранить": order and main of the store's own photos; drafts become published (or pending for
    a card sold by several stores); own photos left out of `ids` are deleted."""
    from app.services.notifications import notify_admins

    check_owner(db, store, owner_type, owner_id)
    own = {p.id: p for p in db.scalars(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id,
                                                           Photo.store_id == store.id))}
    keep = [own[i] for i in ids if i in own]
    drafts = [p for p in keep if p.status == "draft"]
    if owner_type == "product" and drafts and not rights:
        raise PhotoError("rights")
    for p in own.values():
        if p not in keep:
            delete_photo(db, p)
    sole = owner_type != "product" or is_sole(db, store, owner_id)
    if owner_type == "product" and sole:
        published = db.scalar(select(func.count(Photo.id)).where(
            Photo.owner_type == "product", Photo.owner_id == owner_id, Photo.status == "published",
            Photo.store_id != store.id)) or 0
        if published + len([p for p in keep if p.status in ("draft", "published")]) > S.CARD_MAX:
            raise PhotoError("too_many", max=S.CARD_MAX)
    now = utcnow()
    for pos, p in enumerate(keep):
        p.position = pos
        if p.status == "draft":
            p.status = "published" if sole else "pending"
            if owner_type == "product":
                p.rights_at, p.rights_user_id = now, user.id
    if owner_type == "product" and drafts and not sole:
        product = db.get(Product, owner_id)
        notify_admins(db, "photo_review", "/admin/photos", group="photo_review",
                      name=product.normalized_name if product else "", store=store.name)
    main = own.get(main_id) if main_id else None
    if owner_type == "product" and sole and main_id:
        # The only seller chooses the main photo of the card among all published ones
        main = db.get(Photo, main_id)
        if main is None or main.owner_type != "product" or main.owner_id != owner_id:
            main = None
    if main is not None and main.status == "published":
        _set_main(db, owner_type, owner_id, main)
    elif owner_type != "product":
        _set_main(db, owner_type, owner_id, keep[0] if keep else None)
    ensure_main(db, owner_type, owner_id)
    db.commit()
    return seller_view(db, store, owner_type, owner_id)


# --- reading -------------------------------------------------------------------------------------------------------------

def out(p: Photo) -> dict:
    storage = get_storage()
    return {"id": p.id, "url": storage.url(p.key), "thumb": storage.url(p.thumb_key), "w": p.orig_w, "h": p.orig_h,
            "main": p.is_main}


def seller_out(p: Photo, store_id: int) -> dict:
    return {**out(p), "status": p.status, "own": p.store_id == store_id, "mode": p.mode, "auto_mode": p.auto_mode,
            "zoom": p.zoom, "ox": p.ox, "oy": p.oy, "src": get_storage().url(p.src_key), "src_w": p.src_w,
            "src_h": p.src_h, "small": imaging.is_small(p.orig_w, p.orig_h), "reason": p.reject_reason,
            "box": p.box, "trim": p.owner_type == "product", "demo": p.is_demo}


def _ordered(q):
    return q.order_by(Photo.is_main.desc(), Photo.position, Photo.id)


def seller_view(db: Session, store: Store, owner_type: str, owner_id: int) -> dict:
    """What the uploader shows: own photos of any status; for a card also the published photos of other stores."""
    q = select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id)
    if owner_type == "product":
        q = q.where((Photo.store_id == store.id) | (Photo.status == "published"))
    else:
        q = q.where(Photo.store_id == store.id)
    rows = db.scalars(_ordered(q)).all()
    view = {"items": [seller_out(p, store.id) for p in rows], "max": LIMITS[owner_type]}
    if owner_type == "product":
        view["sole"] = is_sole(db, store, owner_id)
    return view


def published(db: Session, owner_type: str, owner_ids) -> dict[int, list[dict]]:
    ids = list(owner_ids)
    if not ids:
        return {}
    rows = db.scalars(_ordered(select(Photo).where(Photo.owner_type == owner_type, Photo.owner_id.in_(ids),
                                                   Photo.status == "published"))).all()
    res: dict[int, list[dict]] = {}
    for p in rows:
        res.setdefault(p.owner_id, []).append(out(p))
    return res


def main_thumbs(db: Session, owner_type: str, owner_ids) -> dict[int, str]:
    return {k: v[0]["thumb"] for k, v in published(db, owner_type, owner_ids).items()}


def has_photo_ids(db: Session, owner_type: str) -> set[int]:
    return set(db.scalars(select(Photo.owner_id).where(Photo.owner_type == owner_type, Photo.status == "published")))


# --- Telegram (phase 9 ads): the first picture of a post -----------------------------------------------------------------

TG_HOSTS = ("telesco.pe", "telegram.org", "t.me")


def tg_image_ok(url: str | None) -> bool:
    from urllib.parse import urlparse

    if not url:
        return False
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in TG_HOSTS)


def fetch_image(url: str) -> bytes:
    import httpx

    with httpx.stream("GET", url, timeout=15, follow_redirects=False) as res:
        res.raise_for_status()
        data = b""
        for chunk in res.iter_bytes():
            data += chunk
            if len(data) > S.MAX_BYTES:
                raise PhotoError("too_heavy", mb=S.MAX_BYTES // (1024 * 1024))
        return data


def attach_from_url(db: Session, offer: Offer, url: str | None, fetch=fetch_image) -> Photo | None:
    """The ad's photo: downloaded and standardized as an offer photo. Fails quietly — the ad stays without a photo."""
    if not tg_image_ok(url):
        return None
    if db.scalar(select(Photo.id).where(Photo.owner_type == "offer", Photo.owner_id == offer.id).limit(1)):
        return None
    try:
        p = create(db, "offer", offer.id, fetch(url), offer.store_id, status="published", source="telegram")
    except Exception as e:  # network, a picture under 400 px, not a picture
        log.info("telegram photo %s skipped: %s", url, e)
        return None
    p.position, p.is_main = 0, True
    return p


# --- the admin: section «Фото» ---------------------------------------------------------------------------------------------

def review_queue(db: Session) -> list[dict]:
    """Cards with photos waiting for a decision: the waiting ones (with the resolution and who uploaded) next to the
    published ones; the main suggested by default is the largest."""
    pending = db.scalars(select(Photo).where(Photo.owner_type == "product", Photo.status == "pending")
                         .order_by(Photo.created_at)).all()
    by_card: dict[int, list[Photo]] = {}
    for p in pending:
        by_card.setdefault(p.owner_id, []).append(p)
    stores = {s.id: s.name for s in db.scalars(select(Store).where(
        Store.id.in_({p.store_id for p in pending if p.store_id})))}
    res = []
    for pid, items in by_card.items():
        product = db.get(Product, pid)
        current = db.scalars(_ordered(select(Photo).where(Photo.owner_type == "product", Photo.owner_id == pid,
                                                          Photo.status == "published"))).all()
        everything = items + list(current)
        best = max(everything, key=lambda p: (p.orig_w * p.orig_h, -p.id))
        res.append({
            "product": {"id": pid, "name": product.normalized_name if product else "",
                        "category": product.category.slug if product and product.category else None},
            "sellers": len(sellers(db, pid)),
            "pending": [{**out(p), "store": stores.get(p.store_id), "rights_at": p.rights_at,
                         "created_at": p.created_at, "small": imaging.is_small(p.orig_w, p.orig_h)} for p in items],
            "published": [out(p) for p in current],
            "suggested_main": best.id,
        })
    return res


def pending_count(db: Session) -> int:
    return db.scalar(select(func.count(Photo.id)).where(Photo.owner_type == "product", Photo.status == "pending")) or 0


def _card_photo(db: Session, photo_id: int) -> Photo:
    p = db.get(Photo, photo_id)
    if p is None or p.owner_type != "product" or p.status == "draft":
        raise PhotoError("not_found")
    return p


def decide(db: Session, admin: User, photo_id: int, accept: bool, reason: str | None = None,
           main: bool = False) -> dict:
    from app.services.admin import log as admin_log
    from app.services.notifications import notify, owner

    p = _card_photo(db, photo_id)
    product = db.get(Product, p.owner_id)
    name = product.normalized_name if product else ""
    if accept:
        if p.status != "published":
            count = db.scalar(select(func.count(Photo.id)).where(
                Photo.owner_type == "product", Photo.owner_id == p.owner_id, Photo.status == "published")) or 0
            if count >= S.CARD_MAX:
                raise PhotoError("card_full", max=S.CARD_MAX)
            p.status, p.reject_reason = "published", None
            notify(db, owner(db, p.store_id), "photo_approved", f"/products/{p.owner_id}", name=name)
        if main:
            _set_main(db, "product", p.owner_id, p)
        ensure_main(db, "product", p.owner_id)
        admin_log(db, admin, "photo_accept", "photo", p.id, name, main=bool(main))
    else:
        reason = (reason or "").strip()[:300]
        if not reason:
            raise PhotoError("reason")
        was_main = p.is_main
        p.status, p.reject_reason, p.is_main = "rejected", reason, False
        notify(db, owner(db, p.store_id), "photo_rejected", "/seller/goods", name=name, reason=reason)
        admin_log(db, admin, "photo_reject", "photo", p.id, name, reason)
        if was_main:
            ensure_main(db, "product", p.owner_id)
    p.decided_at = utcnow()
    db.commit()
    return {"ok": True}


def make_main(db: Session, admin: User, photo_id: int) -> dict:
    from app.services.admin import log as admin_log

    p = _card_photo(db, photo_id)
    if p.status != "published":
        return decide(db, admin, photo_id, True, main=True)
    _set_main(db, "product", p.owner_id, p)
    admin_log(db, admin, "photo_main", "photo", p.id)
    db.commit()
    return {"ok": True}


def own_counts(db: Session, store: Store, offer_ids: list[int]) -> dict[int, dict]:
    """"Мои товары": per offer of the store — the number of its own published photos and the main thumb."""
    res: dict[int, dict] = {}
    for oid, items in published(db, "offer", offer_ids).items():
        res[oid] = {"count": len(items), "thumb": items[0]["thumb"]}
    return res
