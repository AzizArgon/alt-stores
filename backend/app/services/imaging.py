"""Phase 14: checking and light processing of photos — Pillow only, no AI (the server is shared and has little memory).

load() checks a file (format, weight, pixels) and turns it upright by EXIF; nothing of the metadata survives, because
every output is re-encoded as WebP without it (EXIF may hold the place where the photo was taken).
render() makes the standard square (app/core/photo_standard.py, docs/defense.md «Стандарт фото»):
- edges almost white or transparent -> white background; for a card photo the white margins are trimmed, the product
  is fitted into the safe zone;
- otherwise (a table, a box, a phone photo) -> a strongly blurred, slightly darker copy of the same photo fills the
  square, the photo itself lies on top, whole, in the safe zone.
The background is never cut out, the product is never cropped, and it is never enlarged more than 2×.
"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

from app.core import photo_standard as S


class PhotoError(ValueError):
    """A file that is not accepted: `code` is the i18n key `photo.err.<code>`."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code, self.params = code, params


def load(data: bytes) -> Image.Image:
    """The checked picture, upright, RGB or RGBA (only when it has transparency)."""
    if len(data) > S.MAX_BYTES:
        raise PhotoError("too_heavy", mb=S.MAX_BYTES // (1024 * 1024))
    try:
        img = Image.open(BytesIO(data))
        fmt = img.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise PhotoError("not_image")
    if fmt not in S.FORMATS:
        raise PhotoError("format")
    w, h = img.size
    if max(w, h) > S.MAX_SIDE:
        raise PhotoError("too_big", px=S.MAX_SIDE)
    if min(w, h) < S.MIN_SIDE:
        raise PhotoError("too_small", px=S.MIN_SIDE)
    try:
        img.load()
        img = ImageOps.exif_transpose(img)
    except (OSError, ValueError, SyntaxError):
        raise PhotoError("not_image")
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    return img.convert("RGBA" if has_alpha else "RGB")


def shrink(img: Image.Image, longest: int = S.SOURCE_MAX) -> Image.Image:
    if max(img.size) <= longest:
        return img
    img = img.copy()
    img.thumbnail((longest, longest), Image.LANCZOS)
    return img


def _is_white(px) -> bool:
    if len(px) == 4 and px[3] < S.CLEAR_ALPHA:
        return True
    return min(px[:3]) >= S.WHITE_LEVEL


def edges_white(img: Image.Image) -> bool:
    """Are the edges almost white or transparent? Looks at a 3% band around a small copy."""
    small = img.convert("RGBA")
    small.thumbnail((200, 200))
    w, h = small.size
    band = max(2, round(min(w, h) * 0.03))
    pixels = []
    for box in ((0, 0, w, band), (0, h - band, w, h), (0, band, band, h - band), (w - band, band, w, h - band)):
        raw = small.crop(box).tobytes()
        pixels.extend(raw[i:i + 4] for i in range(0, len(raw), 4))
    white = sum(1 for p in pixels if _is_white(p))
    return white >= len(pixels) * S.WHITE_EDGES


def on_white(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        return img.convert("RGB")
    bg = Image.new("RGB", img.size, "white")
    bg.paste(img, mask=img.getchannel("A"))
    return bg


def product_box(img: Image.Image) -> tuple[int, int, int, int]:
    """The borders of the product: the picture without its white and transparent margins."""
    flat = on_white(img)
    diff = ImageChops.difference(flat, Image.new("RGB", flat.size, "white"))
    r, g, b = diff.split()
    mask = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > 255 - S.WHITE_LEVEL else 0)
    return mask.getbbox() or (0, 0, *img.size)


@dataclass
class Layout:
    mode: str  # white / blur
    zoom: float = 1.0  # 1 = the automatic fit into the safe zone
    ox: float = 0.0  # center offset, share of the canvas side
    oy: float = 0.0


def auto_mode(img: Image.Image) -> str:
    return "white" if edges_white(img) else "blur"


def placement(size: tuple[int, int], zoom: float = 1.0, ox: float = 0.0, oy: float = 0.0):
    """Scale and top-left corner of a `size` picture on the canvas. The same formula is in PhotoCropper.jsx."""
    w, h = size
    zone = S.CANVAS * S.SAFE_ZONE
    fit = min(zone / w, zone / h, S.MAX_UPSCALE)
    # Never more than 2×, never larger than the canvas: the product is always whole
    scale = min(fit * max(zoom, 0.3), S.MAX_UPSCALE, S.CANVAS / w, S.CANVAS / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    cx = min(max(S.CANVAS / 2 + ox * S.CANVAS, nw / 2), S.CANVAS - nw / 2)
    cy = min(max(S.CANVAS / 2 + oy * S.CANVAS, nh / 2), S.CANVAS - nh / 2)
    return scale, (nw, nh), (round(cx - nw / 2), round(cy - nh / 2))


def _blurred(img: Image.Image) -> Image.Image:
    # Blur a small copy and stretch it: strong blur at a fraction of the memory and time
    small = ImageOps.fit(on_white(img), (120, 120), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(6))
    big = small.resize((S.CANVAS, S.CANVAS), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
    return ImageEnhance.Brightness(big).enhance(S.BLUR_DARKEN)


def render(src: Image.Image, layout: Layout, trim: bool) -> Image.Image:
    """The 1500×1500 square. `trim` (card photos, white background only) cuts the white margins around the product;
    an offer photo is a real item and is only fitted whole."""
    fg = src.crop(product_box(src)) if trim and layout.mode == "white" else src
    _, (nw, nh), (x, y) = placement(fg.size, layout.zoom, layout.ox, layout.oy)
    fg = fg.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (S.CANVAS, S.CANVAS), "white") if layout.mode == "white" else _blurred(src)
    canvas.paste(fg, (x, y), fg.getchannel("A") if fg.mode == "RGBA" else None)
    return canvas


def webp(img: Image.Image, quality: int) -> bytes:
    out = BytesIO()
    img.save(out, "WEBP", quality=quality, method=4)  # no exif= : nothing of the metadata is written
    return out.getvalue()


def thumb(img: Image.Image) -> Image.Image:
    return img.resize((S.THUMB, S.THUMB), Image.LANCZOS)


def is_small(width: int, height: int) -> bool:
    return max(width, height) < S.WARN_SIDE
