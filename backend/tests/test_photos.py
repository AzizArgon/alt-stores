"""Phase 14: photos — the storage module, checks, the 1500×1500 standard (white / blurred background), card photos with
rights and moderation, offer and build photos, the daily limit, deletion with the offer, Telegram pictures, storefront."""

import asyncio
import re
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core import photo_standard as S
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import AdminAction, Build, Notification, Offer, Photo, TgChannel
from app.services import catalog, imaging, photos, storage, telegram
from app.services.cabinet import list_offers, remove_offer
from app.services.imaging import Layout, PhotoError
from main import app
from scripts.create_admin import create_admin
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)


class MemoryStorage:
    """Another implementation of the same interface (as S3 would be): the code must not notice the difference."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def save(self, key, data, content_type="image/webp"):
        self.files[storage.check_key(key)] = data

    def url(self, key):
        return f"https://cdn.example.com/{key}"

    def delete(self, key):
        self.files.pop(key, None)

    def read(self, key):
        return self.files[key]


@pytest.fixture(autouse=True)
def mem():
    s = MemoryStorage()
    storage.set_storage(s)
    yield s
    storage.set_storage(None)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def _bytes(img, fmt="PNG", **kw):
    out = BytesIO()
    img.save(out, fmt, **kw)
    return out.getvalue()


def white_photo(size=(1200, 900), box=(500, 300, 700, 600)):
    img = Image.new("RGB", size, "white")
    ImageDraw.Draw(img).rectangle(box, fill=(200, 30, 30))
    return img


def busy_photo(size=(1600, 1200)):
    img = Image.new("RGB", size, (90, 60, 40))  # a table
    ImageDraw.Draw(img).rectangle((600, 400, 1000, 800), fill=(20, 40, 200))
    return img


def _dark_box(img, level=160):
    return img.convert("L").point(lambda v: 255 if v < level else 0).getbbox()


# --- storage ---------------------------------------------------------------------------------------------------------

def test_local_storage_save_url_delete(tmp_path):
    s = storage.LocalStorage(tmp_path, "/media/")
    key = storage.new_key("t")
    s.save(key, b"abc")
    assert s.read(key) == b"abc" and (tmp_path / key[:2] / key).exists()
    assert s.url(key) == f"/media/{key[:2]}/{key}"
    s.delete(key)
    assert not (tmp_path / key[:2] / key).exists()
    s.delete(key)  # twice is fine


def test_keys_are_random_and_user_paths_are_refused(tmp_path):
    s = storage.LocalStorage(tmp_path, "/media")
    assert storage.new_key() != storage.new_key()
    for bad in ("../../etc/passwd", "photo.webp", "a" * 32 + "/../x.webp", "Мой товар.jpg"):
        with pytest.raises(ValueError):
            s.save(bad, b"x")


def test_storage_is_swappable(db, mem):
    shop = _store(db, "shop@example.com")
    cpu = _card(db, "cpu", "AMD Ryzen 5 5600")
    _offer(db, shop, cpu, 100)
    offer = db.scalar(select(Offer))
    p = photos.upload(db, shop, "offer", offer.id, _bytes(white_photo()))
    assert {p.key, p.thumb_key, p.src_key} <= set(mem.files)
    assert photos.out(p)["url"].startswith("https://cdn.example.com/")


# --- checks ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("data, code", [
    (b"%PDF-1.4 not a picture", "not_image"),
    (b"x" * (S.MAX_BYTES + 1), "too_heavy"),
], ids=["pdf", "heavy"])
def test_not_pictures_and_heavy_files_are_refused(data, code):
    with pytest.raises(PhotoError) as e:
        imaging.load(data)
    assert e.value.code == code


def test_formats_and_pixel_limits():
    with pytest.raises(PhotoError) as e:
        imaging.load(_bytes(Image.new("RGB", (800, 800), "white"), "GIF"))
    assert e.value.code == "format"
    with pytest.raises(PhotoError) as e:
        imaging.load(_bytes(Image.new("L", (S.MAX_SIDE + 1, 500)), "PNG"))
    assert e.value.code == "too_big"
    with pytest.raises(PhotoError) as e:
        imaging.load(_bytes(Image.new("RGB", (1000, S.MIN_SIDE - 1), "white"), "JPEG"))
    assert e.value.code == "too_small"
    for fmt in ("JPEG", "PNG", "WEBP"):
        assert imaging.load(_bytes(Image.new("RGB", (600, 500), "white"), fmt)).size == (600, 500)


def test_exif_is_removed_and_the_photo_turned_upright(db, mem):
    img = Image.new("RGB", (900, 600), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: turned 90°
    exif[0x8825] = {2: (41.0, 18.0, 0.0)}  # GPS
    data = _bytes(img, "JPEG", exif=exif)
    loaded = imaging.load(data)
    assert loaded.size == (600, 900)
    shop = _store(db, "shop@example.com")
    _offer(db, shop, _card(db, "cpu", "AMD Ryzen 5 5600"), 100)
    p = photos.upload(db, shop, "offer", db.scalar(select(Offer.id)), data)
    for key in (p.key, p.thumb_key, p.src_key):
        out = Image.open(BytesIO(mem.files[key]))
        assert out.format == "WEBP" and not out.getexif() and "exif" not in out.info
    assert Image.open(BytesIO(mem.files[p.key])).size == (S.CANVAS, S.CANVAS)
    assert Image.open(BytesIO(mem.files[p.thumb_key])).size == (S.THUMB, S.THUMB)
    assert (p.orig_w, p.orig_h) == (600, 900)


# --- the standard ------------------------------------------------------------------------------------------------------

def test_white_edges_give_a_white_background_and_the_product_in_the_safe_zone():
    src = imaging.load(_bytes(white_photo(size=(2000, 1500), box=(400, 300, 1600, 1200))))
    assert imaging.auto_mode(src) == "white"
    out = imaging.render(src, Layout("white"), trim=True)
    assert out.size == (S.CANVAS, S.CANVAS) and out.getpixel((3, 3)) == (255, 255, 255)
    x0, y0, x1, y1 = _dark_box(out)
    zone = S.CANVAS * S.SAFE_ZONE
    margin = (S.CANVAS - zone) / 2
    assert max(x1 - x0, y1 - y0) == pytest.approx(zone, abs=3)  # trimmed and fitted into the zone
    assert x0 >= margin - 2 and y0 >= margin - 2 and x1 <= S.CANVAS - margin + 2 and y1 <= S.CANVAS - margin + 2
    assert (x0 + x1) / 2 == pytest.approx(S.CANVAS / 2, abs=2)


def test_transparent_png_gets_a_white_background():
    img = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((300, 300, 700, 700), fill=(10, 120, 10, 255))
    src = imaging.load(_bytes(img))
    assert src.mode == "RGBA" and imaging.auto_mode(src) == "white"
    out = imaging.render(src, Layout("white"), trim=True)
    assert out.getpixel((5, 5)) == (255, 255, 255) and out.getpixel((750, 750))[1] > 100


def test_busy_background_gives_a_blurred_background_and_the_photo_is_whole():
    src = imaging.load(_bytes(busy_photo(), "JPEG"))
    assert imaging.auto_mode(src) == "blur"
    out = imaging.render(src, Layout("blur"), trim=True)
    corner = out.getpixel((5, 5))
    assert corner != (255, 255, 255) and sum(corner) < sum((90, 60, 40)) + 30  # the darker blurred copy
    # The whole photo (4:3) lies on top: its width is the zone, its height 3/4 of it — nothing cut
    _, (nw, nh), (x, y) = imaging.placement(src.size)
    assert nw == pytest.approx(S.CANVAS * S.SAFE_ZONE, abs=2) and nh == pytest.approx(nw * 3 / 4, abs=2)
    assert out.getpixel((x + 3, y + 3)) == pytest.approx((90, 60, 40), abs=12)  # the photo's own corner is there


def test_a_small_photo_is_never_enlarged_more_than_twice_and_warns():
    src = imaging.load(_bytes(white_photo(size=(500, 450), box=(150, 150, 350, 300))))
    out = imaging.render(src, Layout("white"), trim=True)
    x0, y0, x1, y1 = _dark_box(out)
    assert (x1 - x0) <= 201 * S.MAX_UPSCALE + 2  # 2× of the 201 px product, smaller than the zone
    assert (x1 - x0) < S.CANVAS * S.SAFE_ZONE and (x0 + x1) / 2 == pytest.approx(S.CANVAS / 2, abs=2)
    assert imaging.is_small(500, 450) and not imaging.is_small(1200, 900)


def test_offer_photos_are_not_trimmed():
    src = imaging.load(_bytes(white_photo(size=(1500, 1000), box=(700, 450, 800, 550))))
    card = _dark_box(imaging.render(src, Layout("white"), trim=True))
    offer = _dark_box(imaging.render(src, Layout("white"), trim=False))
    assert card[2] - card[0] > 2 * (offer[2] - offer[0])  # the card zoomed in on the product, the offer kept it all
    assert offer[2] - offer[0] == pytest.approx(101 * S.CANVAS * S.SAFE_ZONE / 1500, abs=3)


def test_cropper_layout_keeps_the_photo_inside_the_canvas():
    scale, (nw, nh), (x, y) = imaging.placement((1000, 1000), zoom=4, ox=0.5, oy=-0.5)
    assert scale <= S.MAX_UPSCALE and nw <= S.CANVAS and x + nw <= S.CANVAS and y >= 0


def test_frontend_keeps_the_same_numbers():
    js = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "photo.js").read_text(encoding="utf-8")
    for name in ("CANVAS", "SAFE_ZONE", "MAX_UPSCALE", "MIN_SIDE", "WARN_SIDE", "MAX_SIDE", "SOURCE_MAX"):
        m = re.search(rf"\b{name}: ([\d.]+)", js)
        assert m and float(m.group(1)) == float(getattr(S, name)), name


# --- card photos: rights and moderation ----------------------------------------------------------------------------------

@pytest.fixture
def world(db):
    admin, _ = create_admin(db, "admin@example.com", "admin12345")
    shop, other = _store(db, "shop@example.com"), _store(db, "other@example.com")
    alone = _card(db, "cpu", "AMD Ryzen 5 5600")
    shared = _card(db, "gpu", "MSI RTX 4060 Ventus 2X 8GB")
    _offer(db, shop, alone, 100)
    _offer(db, shop, shared, 300)
    _offer(db, other, shared, 310)
    return {"admin": admin, "shop": shop, "other": other, "alone": alone, "shared": shared}


def _upload(client, user, owner_type, owner_id, img=None, **extra):
    data = {"owner_type": owner_type, "owner_id": str(owner_id), **{k: str(v) for k, v in extra.items()}}
    return client.post("/api/seller/photos", headers=_h(user), data=data,
                       files={"file": ("../../evil name.png", _bytes(img or white_photo()), "image/png")})


def _save(client, user, owner_type, owner_id, ids, **extra):
    return client.put("/api/seller/photos", headers=_h(user),
                      json={"owner_type": owner_type, "owner_id": owner_id, "ids": ids, **extra})


def test_card_photo_needs_the_rights_tick(client, db, world):
    seller = world["shop"].owner
    r = _upload(client, seller, "product", world["alone"].id)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    pid = r.json()["id"]
    r = _save(client, seller, "product", world["alone"].id, [pid])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "photo_rights"
    r = _save(client, seller, "product", world["alone"].id, [pid], rights=True)
    assert r.status_code == 200 and r.json()["items"][0]["status"] == "published"
    p = db.get(Photo, pid)
    assert p.rights_at is not None and p.rights_user_id == seller.id
    assert "evil" not in p.key and ".." not in p.key


def test_only_a_seller_of_the_card_uploads(client, world):
    from app.db.models import Product
    from tests.test_builds import _card as card

    r = _upload(client, world["other"].owner, "product", world["alone"].id)
    assert r.status_code == 404


def test_sole_seller_publishes_at_once_several_sellers_go_to_the_admin(client, db, world):
    seller, admin = world["shop"].owner, world["admin"]
    a = _upload(client, seller, "product", world["alone"].id).json()["id"]
    _save(client, seller, "product", world["alone"].id, [a], rights=True)
    assert db.get(Photo, a).status == "published"
    small = _upload(client, seller, "product", world["shared"].id, white_photo(size=(800, 600))).json()["id"]
    big = _upload(client, seller, "product", world["shared"].id, white_photo(size=(1800, 1400))).json()["id"]
    r = _save(client, seller, "product", world["shared"].id, [small, big], rights=True, main_id=small)
    assert {i["status"] for i in r.json()["items"]} == {"pending"} and r.json()["sole"] is False
    assert db.scalar(select(Notification).where(Notification.user_id == admin.id)).kind == "photo_review"
    # The storefront shows nothing new while it waits
    card = catalog.product_card(db, world["shared"].id, None)
    assert card["photos"] == [] and card["image"] is None
    queue = client.get("/api/admin/photos", headers=_h(admin)).json()["items"]
    assert len(queue) == 1 and queue[0]["suggested_main"] == big  # the largest by default
    assert {(p["w"], p["h"]) for p in queue[0]["pending"]} == {(800, 600), (1800, 1400)}  # resolution is shown
    assert client.post(f"/api/admin/photos/{big}", headers=_h(admin), json={"accept": True, "main": True}).status_code == 200
    r = client.post(f"/api/admin/photos/{small}", headers=_h(admin), json={"accept": False})
    assert r.json()["detail"]["code"] == "photo_reason"
    client.post(f"/api/admin/photos/{small}", headers=_h(admin), json={"accept": False, "reason": "Чужой водяной знак"})
    kinds = [(n.kind, n.params.get("reason")) for n in db.scalars(select(Notification).where(
        Notification.user_id == seller.id).order_by(Notification.id))]
    assert kinds == [("photo_approved", None), ("photo_rejected", "Чужой водяной знак")]
    card = catalog.product_card(db, world["shared"].id, None)
    assert [p["id"] for p in card["photos"]] == [big] and card["photos"][0]["main"]
    assert {"photo_accept", "photo_reject"} <= set(db.scalars(select(AdminAction.action)))
    assert client.get("/api/admin/photos", headers=_h(admin)).json()["items"] == []


def test_a_published_card_photo_of_a_shared_card_is_locked(client, db, world):
    seller = world["shop"].owner
    pid = _upload(client, seller, "product", world["shared"].id).json()["id"]
    _save(client, seller, "product", world["shared"].id, [pid], rights=True)
    client.post(f"/api/admin/photos/{pid}", headers=_h(world["admin"]), json={"accept": True})
    r = client.patch(f"/api/seller/photos/{pid}", headers=_h(seller), json={"mode": "blur"})
    assert r.status_code == 403


def test_card_photos_are_at_most_five(client, world):
    seller = world["shop"].owner
    ids = [_upload(client, seller, "product", world["alone"].id).json()["id"] for _ in range(S.CARD_MAX)]
    r = _upload(client, seller, "product", world["alone"].id)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "photo_too_many"
    assert _save(client, seller, "product", world["alone"].id, ids, rights=True).status_code == 200


# --- offers, builds, limits, deletion ----------------------------------------------------------------------------------

def test_offer_photos_order_main_rotate_and_no_rights(client, db, world):
    seller = world["shop"].owner
    offer = db.scalar(select(Offer).where(Offer.store_id == world["shop"].id, Offer.product_id == world["alone"].id))
    a = _upload(client, seller, "offer", offer.id).json()
    b = _upload(client, seller, "offer", offer.id, busy_photo()).json()
    assert b["mode"] == "blur" and a["mode"] == "white" and not a["small"]
    turned = client.patch(f"/api/seller/photos/{b['id']}", headers=_h(seller), json={"rotate": 1}).json()
    assert (turned["src_w"], turned["src_h"]) == (b["src_h"], b["src_w"]) and turned["url"] != b["url"]
    r = _save(client, seller, "offer", offer.id, [b["id"], a["id"]], main_id=a["id"])
    assert [i["id"] for i in r.json()["items"]] == [a["id"], b["id"]]  # the main first, then the order
    assert all(i["status"] == "published" for i in r.json()["items"])
    card = catalog.product_card(db, world["alone"].id, None)
    assert [p["id"] for p in card["offers"][0]["photos"]] == [a["id"], b["id"]]


def test_small_photo_warning(client, db, world):
    offer = db.scalar(select(Offer).where(Offer.store_id == world["shop"].id))
    r = _upload(client, world["shop"].owner, "offer", offer.id, white_photo(size=(700, 600), box=(200, 200, 400, 400)))
    assert r.json()["small"] is True


def test_the_browser_tells_the_original_resolution(client, db, world):
    offer = db.scalar(select(Offer).where(Offer.store_id == world["shop"].id))
    r = _upload(client, world["shop"].owner, "offer", offer.id, white_photo(size=(2000, 1500)), orig_w=4000, orig_h=3000)
    assert (r.json()["w"], r.json()["h"]) == (4000, 3000)
    r = _upload(client, world["shop"].owner, "offer", offer.id, white_photo(size=(2000, 1500)), orig_w=100, orig_h=9000)
    assert (r.json()["w"], r.json()["h"]) == (2000, 1500)  # not believed


def test_daily_upload_limit(client, db, world, monkeypatch):
    monkeypatch.setattr(S, "DAILY_UPLOADS", 2)
    offer = db.scalar(select(Offer).where(Offer.store_id == world["shop"].id))
    seller = world["shop"].owner
    assert _upload(client, seller, "offer", offer.id).status_code == 201
    assert _upload(client, seller, "offer", offer.id).status_code == 201
    r = _upload(client, seller, "offer", offer.id)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "photo_limit"


def test_photos_go_with_a_deleted_offer_and_with_a_left_out_photo(db, mem, world):
    shop = world["shop"]
    offer = db.scalar(select(Offer).where(Offer.store_id == shop.id))
    a = photos.upload(db, shop, "offer", offer.id, _bytes(white_photo()))
    b = photos.upload(db, shop, "offer", offer.id, _bytes(white_photo()))
    photos.save_set(db, shop, shop.owner, "offer", offer.id, [a.id])  # b left out — deleted with its files
    assert db.get(Photo, b.id) is None and b.key not in mem.files and a.key in mem.files
    remove_offer(db, offer)
    assert db.scalar(select(Photo)) is None and not mem.files
    # A hard delete (undo of an upload, a deleted Telegram ad) too
    other = db.scalar(select(Offer).where(Offer.store_id == world["other"].id))
    c = photos.upload(db, world["other"], "offer", other.id, _bytes(white_photo()))
    db.delete(other)
    db.commit()
    assert db.scalar(select(Photo.id).where(Photo.id == c.id)) is None and c.key not in mem.files


def test_build_photos(client, db, world):
    build = Build(store=world["shop"], name="Игровой ПК", price=900)
    db.add(build)
    db.commit()
    seller = world["shop"].owner
    pid = _upload(client, seller, "build", build.id, busy_photo()).json()["id"]
    _save(client, seller, "build", build.id, [pid])
    from app.services.builds import build_summary

    s = build_summary(build, None)
    assert s["image"] and s["photos"][0]["id"] == pid
    assert _upload(client, world["other"].owner, "build", build.id).status_code == 404


def test_goods_filter_without_photo(db, world):
    shop = world["shop"]
    offer = db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.product_id == world["alone"].id))
    p = photos.upload(db, shop, "offer", offer.id, _bytes(white_photo()))
    photos.save_set(db, shop, shop.owner, "offer", offer.id, [p.id])
    rows = list_offers(db, shop, {"no_photo": True})["items"]
    assert [r["product_id"] for r in rows] == [world["shared"].id]
    full = {r["product_id"]: r for r in list_offers(db, shop, {})["items"]}
    assert full[world["alone"].id]["photo"] and full[world["alone"].id]["photos"] == {"own": 1, "card": 0}


# --- storefront ----------------------------------------------------------------------------------------------------------

def test_storefront_gives_the_photo_or_falls_back_to_the_icon(db, world):
    shop = world["shop"]
    p = photos.upload(db, shop, "product", world["alone"].id, _bytes(white_photo()))
    photos.save_set(db, shop, shop.owner, "product", world["alone"].id, [p.id], rights=True)
    items = {i["id"]: i for i in catalog.search_products(db, None)["items"]}
    assert items[world["alone"].id]["image"] == photos.out(p)["thumb"]
    assert items[world["shared"].id]["image"] is None  # the page draws the category icon


def test_used_section_prefers_the_item_photo_then_the_card(db, world):
    from app.db.models import Condition

    shop = world["shop"]
    offer = db.scalar(select(Offer).where(Offer.store_id == shop.id, Offer.product_id == world["alone"].id))
    offer.condition = Condition.used
    db.commit()
    card = photos.upload(db, shop, "product", world["alone"].id, _bytes(white_photo()))
    photos.save_set(db, shop, shop.owner, "product", world["alone"].id, [card.id], rights=True)
    item = catalog.used_offers(db, None)["items"][0]
    assert item["image"] == photos.out(card)["thumb"] and item["photos"] == []
    own = photos.upload(db, shop, "offer", offer.id, _bytes(busy_photo()))
    photos.save_set(db, shop, shop.owner, "offer", offer.id, [own.id])
    item = catalog.used_offers(db, None)["items"][0]
    assert item["image"] == photos.out(own)["thumb"] and len(item["photos"]) == 1


# --- Telegram ------------------------------------------------------------------------------------------------------------

def test_telegram_post_picture_is_downloaded_and_attached(db):
    from tests.test_telegram import PAGE1, fake_parse

    channel = telegram.add_channel(db, "@test_parts", "Б/у (тест)", "tashkent")
    asked = []

    def fetch_photo(url):
        asked.append(url)
        if url.endswith("y.jpg"):
            return _bytes(Image.new("RGB", (300, 300), "white"))  # under 400 px — the ad stays without a photo
        return _bytes(busy_photo(), "JPEG")

    asyncio.run(telegram.run_channel(db, db.scalar(select(TgChannel)), 50, fetch=lambda *_: PAGE1, parse=fake_parse,
                                     pause=lambda: None, fetch_photo=fetch_photo))
    assert "https://cdn4.telesco.pe/file/x.jpg" in asked
    with_photo = db.scalars(select(Photo).where(Photo.owner_type == "offer")).all()
    assert with_photo and all(p.source == "telegram" and p.status == "published" and p.mode == "blur" for p in with_photo)
    offers = {o.id: o for o in db.scalars(select(Offer).where(Offer.store_id == channel.store_id))}
    urls = {offers[p.owner_id].post_url for p in with_photo}
    assert all(u.endswith("/101") for u in urls)


def test_telegram_picture_hosts_are_checked():
    assert photos.tg_image_ok("https://cdn4.telesco.pe/file/x.jpg")
    assert not photos.tg_image_ok("http://cdn4.telesco.pe/file/x.jpg")
    assert not photos.tg_image_ok("https://127.0.0.1/x.jpg") and not photos.tg_image_ok("https://evil.pe/x.jpg")
