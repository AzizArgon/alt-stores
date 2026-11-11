"""Phase 14 demo: placeholder "photos" in one style — the category's silhouette, the model's name and the mark «демо».

No photos from the internet: every picture is drawn here with Pillow. Half of the card pictures are on a white
background, half on a "busy" one (a desk), so both branches of the photo standard are visible. 2–3 used demo offers get
their own "photo" of the same kind with another caption, the used demo build — one too.

Everything is marked is_demo; a rerun (also --builds-only) skips what is there already — no duplicates. The real store is
never touched: no photo of its offers. The demo assortment is taken from the real
price list, so a demo card may be one the real store sells too: a demo placeholder gives way by itself — it is deleted as
soon as a real photo of the card is published (app/services/photos.py `drop_demo`).
"""

import random
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Build, Category, Condition, Offer, Photo, Product, Store, StoreKind
from app.services import photos

CATEGORIES = ("gpu", "cpu", "motherboard", "ram", "ssd", "psu", "case", "cooling", "monitor", "laptop", "mouse",
              "keyboard", "hdd", "headphones")
CARDS = 12
USED_OFFERS = 3
FONT_PATHS = ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
INK, PART, ACCENT = (45, 62, 92), (88, 108, 140), (220, 84, 60)


def _font(size: int):
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _silhouette(d: ImageDraw.ImageDraw, slug: str, x: int, y: int, w: int, h: int) -> None:
    """A flat silhouette of the category inside the box (x, y, w, h)."""
    r = min(w, h)
    cx, cy = x + w // 2, y + h // 2
    if slug == "gpu":
        d.rounded_rectangle((x, y + h * .2, x + w, y + h * .8), 30, fill=PART)
        for fx in (x + w * .3, x + w * .7):
            d.ellipse((fx - r * .2, cy - r * .2, fx + r * .2, cy + r * .2), fill=INK)
            d.ellipse((fx - r * .05, cy - r * .05, fx + r * .05, cy + r * .05), fill=PART)
        d.rectangle((x + w * .15, y + h * .8, x + w * .6, y + h * .86), fill=(190, 160, 60))
    elif slug in ("cpu", "motherboard"):
        d.rounded_rectangle((cx - r * .45, cy - r * .45, cx + r * .45, cy + r * .45), 20, fill=PART)
        d.rectangle((cx - r * .25, cy - r * .25, cx + r * .25, cy + r * .25), fill=INK)
        if slug == "motherboard":
            for i in range(3):
                d.rectangle((cx - r * .4, cy + r * (.3 + i * .04), cx + r * .4, cy + r * (.32 + i * .04)), fill=INK)
        else:
            for i in range(9):
                t = cx - r * .4 + i * r * .1
                d.rectangle((t, cy - r * .5, t + 6, cy - r * .45), fill=(190, 160, 60))
                d.rectangle((t, cy + r * .45, t + 6, cy + r * .5), fill=(190, 160, 60))
    elif slug == "ram":
        d.rounded_rectangle((x, cy - h * .15, x + w, cy + h * .15), 12, fill=PART)
        for i in range(8):
            t = x + w * .06 + i * w * .115
            d.rectangle((t, cy - h * .08, t + w * .08, cy + h * .06), fill=INK)
        d.rectangle((x + w * .05, cy + h * .15, x + w * .95, cy + h * .2), fill=(190, 160, 60))
    elif slug in ("ssd", "hdd"):
        d.rounded_rectangle((cx - r * .35, cy - r * .45, cx + r * .35, cy + r * .45), 24, fill=PART)
        if slug == "hdd":
            d.ellipse((cx - r * .25, cy - r * .3, cx + r * .25, cy + r * .2), fill=INK)
        else:
            d.rectangle((cx - r * .25, cy - r * .3, cx + r * .25, cy), fill=INK)
    elif slug in ("psu", "cooling"):
        if slug == "psu":
            d.rounded_rectangle((x + w * .1, cy - r * .35, x + w * .9, cy + r * .35), 16, fill=PART)
        d.ellipse((cx - r * .3, cy - r * .3, cx + r * .3, cy + r * .3), fill=INK)
        for a in range(0, 360, 60):
            d.pieslice((cx - r * .26, cy - r * .26, cx + r * .26, cy + r * .26), a, a + 30, fill=PART)
    elif slug == "case":
        d.rounded_rectangle((cx - r * .28, y, cx + r * .28, y + h), 20, fill=PART)
        d.rectangle((cx - r * .2, y + h * .1, cx + r * .2, y + h * .6), fill=INK)
        d.ellipse((cx - 14, y + h * .8, cx + 14, y + h * .8 + 28), fill=ACCENT)
    elif slug in ("monitor", "laptop"):
        d.rounded_rectangle((x, y + h * .05, x + w, y + h * .7), 16, fill=INK)
        d.rectangle((x + 18, y + h * .05 + 18, x + w - 18, y + h * .7 - 18), fill=PART)
        if slug == "laptop":
            d.polygon([(x - w * .05, y + h * .8), (x + w * 1.05, y + h * .8), (x + w, y + h * .7), (x, y + h * .7)], fill=INK)
        else:
            d.rectangle((cx - 20, y + h * .7, cx + 20, y + h * .85), fill=INK)
            d.rounded_rectangle((cx - w * .2, y + h * .85, cx + w * .2, y + h * .9), 8, fill=INK)
    elif slug == "mouse":
        d.rounded_rectangle((cx - r * .22, cy - r * .38, cx + r * .22, cy + r * .38), int(r * .22), fill=PART)
        d.line((cx, cy - r * .38, cx, cy - r * .1), fill=INK, width=8)
    elif slug == "keyboard":
        d.rounded_rectangle((x, cy - h * .2, x + w, cy + h * .2), 16, fill=PART)
        for row in range(3):
            for col in range(10):
                kx, ky = x + w * .05 + col * w * .09, cy - h * .14 + row * h * .1
                d.rectangle((kx, ky, kx + w * .07, ky + h * .07), fill=INK)
    elif slug == "headphones":
        d.arc((cx - r * .35, cy - r * .4, cx + r * .35, cy + r * .3), 180, 360, fill=INK, width=24)
        for sx in (cx - r * .35, cx + r * .35):
            d.rounded_rectangle((sx - r * .08, cy - r * .05, sx + r * .08, cy + r * .25), 16, fill=PART)
    else:
        d.rounded_rectangle((cx - r * .4, cy - r * .3, cx + r * .4, cy + r * .3), 16, fill=PART)


def _busy_background(size: tuple[int, int], seed: int) -> Image.Image:
    """A "desk": warm wood stripes, a darker corner and a mug — not white edges, so the standard blurs it."""
    rnd = random.Random(seed)
    w, h = size
    img = Image.new("RGB", size, (126, 88, 58))
    d = ImageDraw.Draw(img)
    for y in range(0, h, 14):
        shade = rnd.randint(-18, 18)
        d.rectangle((0, y, w, y + 14), fill=(126 + shade, 88 + shade, 58 + shade // 2))
    d.ellipse((w * .78, h * .05, w * .98, h * .3), fill=(230, 230, 225))
    d.ellipse((w * .82, h * .09, w * .94, h * .26), fill=(80, 50, 30))
    d.rectangle((0, h * .82, w * .35, h), fill=(40, 40, 46))  # a laptop's corner
    return img.filter(ImageFilter.GaussianBlur(1.2))


def placeholder(slug: str, title: str, caption: str, busy: bool, seed: int = 0) -> bytes:
    """A demo picture: 1600×1200 (busy) or 1400×1400 (white), the silhouette, the model and the mark «демо»."""
    size = (1600, 1200) if busy else (1400, 1400)
    img = _busy_background(size, seed) if busy else Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    w, h = size
    box = (int(w * .2), int(h * .14), int(w * .6), int(h * .5)) if busy else (int(w * .22), int(h * .16), int(w * .56), int(h * .5))
    if busy:  # the product lies on a light card on the desk
        d.rounded_rectangle((box[0] - 40, box[1] - 40, box[0] + box[2] + 40, box[1] + box[3] + 220), 24, fill=(238, 238, 242))
    _silhouette(d, slug, *box)
    text_y = box[1] + box[3] + 40
    font, small = _font(54), _font(40)
    for line in _wrap(d, title, font, box[2] + 60)[:2]:
        tw = d.textlength(line, font=font)
        d.text(((w - tw) / 2 if not busy else box[0] + (box[2] - tw) / 2, text_y), line, fill=INK, font=font)
        text_y += 64
    tw = d.textlength(caption, font=small)
    d.text(((w - tw) / 2 if not busy else box[0] + (box[2] - tw) / 2, text_y + 8), caption, fill=PART, font=small)
    # The mark: a red «ДЕМО» stamp in the corner of the product area
    stamp = "ДЕМО"
    sw = d.textlength(stamp, font=small)
    sx, sy = box[0] + box[2] - sw + 10, box[1] - 30
    d.rounded_rectangle((sx - 18, sy - 8, sx + sw + 18, sy + 52), 10, fill=ACCENT)
    d.text((sx, sy), stamp, fill="white", font=small)
    out = BytesIO()
    img.save(out, "JPEG" if busy else "PNG", quality=90)
    return out.getvalue()


def _wrap(d, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        probe = f"{line} {word}".strip()
        if d.textlength(probe, font=font) <= width or not line:
            line = probe
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


# --- seeding --------------------------------------------------------------------------------------------------------------

def _has_demo(db: Session, owner_type: str, owner_id: int) -> bool:
    return db.scalar(select(Photo.id).where(Photo.owner_type == owner_type, Photo.owner_id == owner_id,
                                            Photo.is_demo.is_(True)).limit(1)) is not None


def _add(db: Session, owner_type: str, owner_id: int, store_id: int, data: bytes) -> Photo:
    p = photos.create(db, owner_type, owner_id, data, store_id, status="published", source="demo")
    p.is_demo, p.position, p.is_main = True, 0, True
    db.flush()
    return p


def demo_cards(db: Session) -> list[tuple[Product, int]]:
    """12 popular cards (the most stores first, as on the home page and the catalog), at most 2 per category, sold by
    demo stores: (card, the demo store that "uploaded" it)."""
    demo_seller = dict(db.execute(
        select(Offer.product_id, func.min(Offer.store_id)).join(Store, Store.id == Offer.store_id)
        .where(Store.is_demo.is_(True), Store.kind == StoreKind.shop, Offer.removed_at.is_(None),
               Offer.price.is_not(None), Offer.condition == Condition.new).group_by(Offer.product_id)).all())
    rows = db.execute(
        select(Product, func.count(func.distinct(Offer.store_id)).label("n")).join(Offer, Offer.product_id == Product.id)
        .where(Product.id.in_(demo_seller), Offer.removed_at.is_(None), Offer.price.is_not(None))
        .group_by(Product.id).order_by(func.count(func.distinct(Offer.store_id)).desc(), Product.normalized_name)
        .limit(400)).all()
    picked, per_cat = [], {}
    for product, _ in rows:
        slug = product.category.slug if product.category else "other"
        if slug not in CATEGORIES or per_cat.get(slug, 0) >= 2:
            continue
        per_cat[slug] = per_cat.get(slug, 0) + 1
        picked.append((product, demo_seller[product.id]))
        if len(picked) >= CARDS:
            break
    return picked


def seed_photos(db: Session) -> dict:
    made = {"cards": 0, "offers": 0, "builds": 0}
    # A full rerun reshuffles the demo assortment: cards that got photos before keep them, the total stays ≤ CARDS
    have = db.scalar(select(func.count(func.distinct(Photo.owner_id))).where(
        Photo.owner_type == "product", Photo.is_demo.is_(True))) or 0
    for i, (product, store_id) in enumerate(demo_cards(db)):
        if _has_demo(db, "product", product.id):
            continue
        if have >= CARDS:
            break
        have += 1
        slug = product.category.slug if product.category else "other"
        _add(db, "product", product.id, store_id,
             placeholder(slug, product.normalized_name, "фото модели · демо", busy=i % 2 == 1, seed=product.id))
        made["cards"] += 1
    used = db.scalars(select(Offer).join(Store, Store.id == Offer.store_id).where(
        Store.is_demo.is_(True), Store.kind == StoreKind.shop, Offer.condition == Condition.used,
        Offer.removed_at.is_(None)).order_by(Offer.id).limit(USED_OFFERS)).all()
    for o in used:
        if _has_demo(db, "offer", o.id):
            continue
        slug = o.product.category.slug if o.product.category else "other"
        _add(db, "offer", o.id, o.store_id,
             placeholder(slug, o.product.normalized_name, "фото экземпляра б/у · демо", busy=True, seed=o.id))
        made["offers"] += 1
    build = db.scalar(select(Build).where(Build.is_demo.is_(True), Build.condition == Condition.used).order_by(Build.id))
    if build is not None and not _has_demo(db, "build", build.id):
        _add(db, "build", build.id, build.store_id, placeholder("case", build.name, "фото сборки · демо", busy=True, seed=7))
        made["builds"] += 1
    db.commit()
    return made
