"""Phase 14: the photo standard — every number of it in one place (docs/defense.md, «Стандарт фото»).

The browser keeps a copy of the numbers it needs in frontend/src/config/photo.js (a test checks they match)."""

CANVAS = 1500  # every photo becomes a 1500×1500 square
SAFE_ZONE = 0.80  # the product fits into 80% of the side: ~10% margin on every edge, centered
MAX_UPSCALE = 2.0  # a small photo is never enlarged more than 2×; if that is not enough it stays smaller, centered
THUMB = 400  # the preview of tiles and lists
QUALITY_BIG, QUALITY_THUMB = 85, 80  # WebP quality
SOURCE_MAX = 2000  # the kept source (to re-render after the cropper or a turn) and the browser's downscale

MIN_SIDE = 400  # shorter side below this — not accepted
WARN_SIDE = 1000  # longer side below this — "Фото маленькое — на витрине может выглядеть мутно"
MAX_SIDE = 6000  # either side above this — not accepted
MAX_BYTES = 8 * 1024 * 1024
FORMATS = ("JPEG", "PNG", "WEBP")

# The edges decide the background: "almost white" channels and "transparent" alpha
WHITE_LEVEL = 235  # every channel at least this = almost white
CLEAR_ALPHA = 16  # alpha below this = transparent
WHITE_EDGES = 0.92  # share of edge pixels that must be white/transparent for the white background
BLUR_DARKEN = 0.82  # the blurred background is a bit darker so the photo itself stands out

CARD_MAX, OFFER_MAX, BUILD_MAX = 5, 6, 6  # photos per card / per offer of a store / per build
DAILY_UPLOADS = 50  # per store per day
DRAFT_HOURS = 24  # uploaded but never saved — deleted after this
