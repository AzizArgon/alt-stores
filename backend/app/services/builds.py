"""Ready PCs of stores (phase B4): a build is not a component, it lives apart from cards and offers.

The problem of the ready-PC market is a "lottery": "RTX 3060, 16GB, SSD 512GB, PSU 650W" and nobody knows what is
inside. Writing vaguely is allowed, but every part shows its precision level honestly:
- "exact": a reference card (a link to it);
- "specs": values by the category dictionary, without a card ("RTX 3060, 12 GB, the maker not said");
- "integrated": integrated graphics instead of a GPU (an office PC) — a precise statement too;
- "none": only the seller's words, or nothing.
A build price is the store's own: builds of different stores are never compared, other stores' prices are never
used. The only hint is inside one store: when every part is exact and the same store sells each of them, the page
says neutrally what these parts cost there separately. A build never counts in the market price, the indexes, the
component catalog or the "full price list / append" modes of a price list upload.
Checks: Anti-Fraud of exact parts (the same rules as offers), "the name says one, the parts say another", "the PSU
maker is not said" (info); soft compatibility by known values of both exact and specs parts.
"""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Build, BuildComponent, BuildPriceHistory, BuildPurpose, BuildSlot, Category, Condition, Currency, Offer, Product,
    Store, utcnow,
)
from app.services.antifraud import LEVEL_ORDER, check_offer
from app.services.catalog import search_filter
from app.services.exchange import get_usd_rate, to_usd, to_uzs
from app.services.manual import product_brief, seller_specs
from app.services.price_cleaner import CleanRow
from app.services.spec_dictionary import BOARD_SIZES, spec_map
from app.services.spec_normalizer import GPU_CHIP, _chip, canonical_brand, written_specs
from app.services.text_import import clean_lines, condition_of, find_price, has_model

PAGE_SIZE = 24
SLOTS = [s.value for s in BuildSlot]
# Which cards fit a slot (the form searches only there); a card of these categories goes to that slot
SLOT_CATEGORIES = {
    "cpu": ("cpu",), "motherboard": ("motherboard",), "ram": ("ram",), "gpu": ("gpu",), "storage": ("ssd", "hdd"),
    "psu": ("psu",), "case": ("case",), "cooling": ("cooling",),
}
SLOT_OF = {c: slot for slot, cats in SLOT_CATEGORIES.items() for c in cats}
KEY_SLOTS = ("cpu", "gpu", "ram", "storage")  # parts shown on a build tile
PRECISE = ("exact", "integrated")

# "Процессор: Ryzen 5 5600": the key of a line says the slot (Russian and Uzbek)
_SLOT_WORDS = [
    ("cpu", r"процессор|проц\b|cpu|protsessor"),
    ("motherboard", r"материнск|мат\.?\s*плат|мать|motherboard|\bmb\b|ona\s*plata|она\s*плата"),
    ("ram", r"оперативн|\bозу\b|\bram\b|\bopera"),
    ("gpu", r"видеокарт|видюх|\bgpu\b|videokarta|графика"),
    ("storage", r"накопител|\bssd\b|\bhdd\b|диск|nvme|жестк|жёстк"),
    ("psu", r"блок\s*питания|\bбп\b|\bpsu\b|питани|quvvat"),
    ("case", r"корпус|\bcase\b|korpus"),
    ("cooling", r"охлажден|кулер|cooler|\bсво\b|sovutish"),
]
_SLOT_KEY = re.compile(r"^(?P<key>[^\W\d_][^:\d]{0,28}):\s*(?P<value>\S.*)$")
# One line of parts: "Ryzen 5 5600 / B550M / 16GB DDR4" (a slash between spaces, not inside "1TB/2TB")
_SPLIT = re.compile(r"\s+[/|]\s+|\s*[|;]\s*|\s+\+\s*|\s*\+\s+")
_QUANTITY = re.compile(r"^(?P<n>[1-8])\s*(?:x|х|×|шт\.?)\s+(?=\S)|\s+(?:x|х|×)\s*(?P<m>[1-8])$|\s*\((?P<k>[1-8])\s*шт\.?\)$", re.I)
_PURPOSE_WORDS = [
    ("gaming", r"игров|gaming|геймер|для игр|o'yin|ўйин"),
    ("work", r"монтаж|рендер|дизайн|рабоч|для работы|стрим|3d|workstation|ish uchun"),
    ("office", r"офис|office|для учеб|для дома|ofis"),
]
_INTEGRATED = re.compile(r"встро[её]н|встройк|интегрир|integrated|\bigpu\b|без\s+видеокарт|vega\s*\d|uhd\s*graphics"
                         r"|iris|radeon\s+graphics|o'rnatilgan", re.I)
# A CPU named at least by its model: "Ryzen 5 5600", "i5-12400F", "Core Ultra 7 265K", "Xeon E5-2680"
CPU_MODEL = re.compile(r"\b(?:core\s*)?(?:i[3579]|ryzen\s*(?:ai\s*)?[3579]|ultra\s*[579]|pentium|celeron|athlon|xeon"
                       r"|threadripper)\b[\s-]*[\w-]*?\d{3,5}", re.I)
_CPU_SERIES = re.compile(r"\b(?:core\s*)?(i[3579])[\s-]*\d{3,5}|\bryzen\s*([3579])\b|\bcore\s*(i[3579])\b", re.I)
_INTEL = re.compile(r"\bintel\b|\bcore\s*i[3579]|\bi[3579][\s-]*\d{4,5}|\bpentium\b|\bceleron\b|\bxeon\b|\bcore\s*ultra", re.I)
_AMD = re.compile(r"\bamd\b|\bryzen\b|\bathlon\b|\bthreadripper\b", re.I)


def slot_of_key(key: str) -> str | None:
    low = key.lower()
    return next((slot for slot, pattern in _SLOT_WORDS if re.search(pattern, low)), None)


def guess_purpose(text: str) -> str:
    low = text.lower()
    return next((p for p, pattern in _PURPOSE_WORDS if re.search(pattern, low)), "other")


def _quantity(text: str) -> tuple[int, str]:
    m = _QUANTITY.search(text)
    if not m:
        return 1, text
    return int(m["n"] or m["m"] or m["k"]), (text[: m.start()] + text[m.end():]).strip()


def split_post(text: str) -> dict:
    """A build post -> name, price, currency, condition, description and part texts (with a slot from "Key:").

    Code reads the price and the condition (as for posts of goods); the parts go to the parse pipeline later."""
    price = currency = None
    check = False
    name, parts, notes = "", [], []
    for line in (line for line in clean_lines(text) if line):
        found, cur, chk, rest = find_price(line)
        if found is not None:
            if price is not None:
                continue
            price, currency, check = found, cur, chk
            rest = rest.strip(" :—-–=")
            if not re.search(r"[^\W\d_]", rest) or re.fullmatch(r"(?i)(цена|narxi|price|нархи|стоимость)\s*:?", rest):
                continue
            line = rest
        kv = _SLOT_KEY.match(line)
        slot = slot_of_key(kv["key"]) if kv else None
        pieces = [p.strip(" -–—•,.") for p in _SPLIT.split(kv["value"] if slot else line)]
        pieces = [p for p in pieces if p]
        if slot:
            parts += [{"text": p, "slot": slot} for p in pieces]
        elif len(pieces) >= 2:
            parts += [{"text": p, "slot": None} for p in pieces]
        elif kv and not has_model(kv["value"]):
            notes.append(line)  # "Состояние: новый", "Гарантия: 1 год"
        elif not name and not parts:
            name = line
        elif has_model(line) or _INTEGRATED.search(line):
            parts.append({"text": line, "slot": None})
        else:
            notes.append(line)
    return {
        "name": name, "price": price, "currency": currency, "currency_check": check,
        "condition": condition_of(text), "purpose": guess_purpose(text),
        "description": "\n".join(notes) or None, "parts": parts,
    }


def _search(db: Session, q: str, slot: str | None, limit: int) -> list[Product]:
    if len(q.strip()) < 2:
        return []
    query = select(Product).outerjoin(Product.category).options(selectinload(Product.category))
    if slot in SLOT_CATEGORIES:
        query = query.where(Category.slug.in_(SLOT_CATEGORIES[slot]))
    products = db.scalars(search_filter(query, q.strip()).order_by(Product.normalized_name).limit(limit * 4)).all()
    # Cards that stores sell first: the seller picks among real goods
    sold = {pid for (pid,) in db.execute(select(Offer.product_id).where(
        Offer.product_id.in_([p.id for p in products]), Offer.price.is_not(None)))}
    return sorted(products, key=lambda p: p.id not in sold)[:limit]


def search_parts(db: Session, q: str, slot: str | None) -> list[dict]:
    """"Choose the exact model" for one slot of the form: only cards of that slot's categories."""
    return [product_brief(p) for p in _search(db, q, slot, 8)]


def _part_specs(slot: str, category: str, row: dict, words: str) -> dict:
    """"Only specs" of a parsed part: values read from the seller's words by the normalizer. AI guesses never
    become specs (they are kept apart in the preview row), and the brand only when the seller wrote it."""
    if slot == "gpu" and _INTEGRATED.search(words):
        return {"integrated": True}
    specs = written_specs(row.get("specs") or {}) if row else {}
    brand = canonical_brand(row.get("brand") or "") if row else None
    if brand and brand.lower() in words.lower() and "brand" in spec_map(category):
        specs["brand"] = brand
    if slot == "cpu" and (m := CPU_MODEL.search(words)):
        specs["model"] = m[0].strip()
    return specs


async def parse_build_text(db: Session, text: str) -> dict:
    """"Paste as text": parts through the same pipeline as goods (cache -> rules -> AI -> normalizer).

    A part whose card key matches exactly is an "exact model"; one with only values read ("16GB DDR4 3200",
    "650W") stays "only specs" and is never tied to a random card; the rest is "not specified" with its text."""
    from app.services.importer import _Matcher, parse_clean_rows  # the importer imports half the app

    post = split_post(text)
    rows = []
    for i, part in enumerate(post["parts"], 1):
        part["quantity"], part["words"] = _quantity(part["text"])
        hint = SLOT_CATEGORIES.get(part["slot"], (None,))[0]
        rows.append(CleanRow(row=i, sheet="", section="", cells=[part["words"]], name=part["words"],
                             ai_text=part["words"], is_in_stock=True, category_hint=hint))
    parsed = {r["row"]: r for r in await parse_clean_rows(db, rows, {})} if rows else {}
    matcher = _Matcher(db)
    components = []
    for i, part in enumerate(post["parts"], 1):
        row = parsed.get(i)
        if row and row["source"] == "failed":
            row = None
        category = row["category"] if row and row["category"] != "other" else None
        slot = part["slot"] or SLOT_OF.get(category) or ("gpu" if _INTEGRATED.search(part["words"]) else "other")
        if category not in SLOT_CATEGORIES.get(slot, ()):
            category = SLOT_CATEGORIES.get(slot, (None,))[0]  # "Видеокарта: ..." the seller named the slot
        product = matcher.match({**row, "category": category})[3] if row and category else None
        if product is not None and SLOT_OF.get(product.category.slug if product.category else None) != slot:
            product = None
        specs = {} if product else _part_specs(slot, category, row, part["words"]) if category or slot == "gpu" else {}
        components.append({
            "slot": slot, "quantity": part["quantity"], "raw_text": part["text"],
            "product": product_brief(product) if product else None,
            "category": None if product else category, "specs": specs,
            "level": "exact" if product else level_of(None, specs),
        })
    order = {s: i for i, s in enumerate(SLOTS)}
    components.sort(key=lambda c: order[c["slot"]])
    draft = {k: post[k] for k in ("name", "price", "currency", "currency_check", "condition", "purpose", "description")}
    return {**draft, "components": components, "missing": missing_required(components)}


# --- Precision and the required minimum ------------------------------------------------------------------------------

def level_of(product_id: int | None, specs: dict | None) -> str:
    if product_id:
        return "exact"
    specs = specs or {}
    if specs.get("integrated"):
        return "integrated"
    return "specs" if any(v not in (None, "") for k, v in specs.items() if not k.startswith("_")) else "none"


def _level(c: BuildComponent) -> str:
    return level_of(c.product_id, c.specs)


def precision(build: Build) -> dict:
    return {"exact": sum(_level(c) in PRECISE for c in build.components), "total": len(build.components)}


def missing_required(components: list[dict]) -> list[str]:
    """CPU at least by its model, GPU at least by its chip or "integrated graphics": otherwise not published."""
    def ok(slot, test):
        return any(c["slot"] == slot and test(c) for c in components)

    def card_of(c, slug):
        return (c.get("product") or {}).get("category") == slug or c.get("product_category") == slug

    specs = lambda c: c.get("specs") or {}  # noqa: E731
    missing = []
    if not ok("cpu", lambda c: card_of(c, "cpu") or CPU_MODEL.search(str(specs(c).get("model") or ""))):
        missing.append("cpu")
    if not ok("gpu", lambda c: card_of(c, "gpu") or specs(c).get("chip") or specs(c).get("integrated")):
        missing.append("gpu")
    return missing


# --- Saving ---------------------------------------------------------------------------------------------------------

class BuildError(ValueError):
    def __init__(self, code: str, **params):
        super().__init__(code)
        self.params = params


def _clean_specs(slot: str, category: str | None, given: dict) -> tuple[str | None, dict]:
    """Form values through the dictionary of the category; extra keys: the CPU model, integrated graphics."""
    if slot == "gpu" and given.get("integrated"):
        return "gpu", {"integrated": True}
    if category not in SLOT_CATEGORIES.get(slot, ()):
        category = SLOT_CATEGORIES.get(slot, (None,))[0]
    if category is None:
        return None, {}
    specs = seller_specs(category, given)
    if "brand" in specs:
        specs["brand"] = canonical_brand(str(specs["brand"])) or specs["brand"]
    if slot == "cpu" and str(given.get("model") or "").strip():
        specs["model"] = str(given["model"]).strip()[:80]
    return category, specs


def _set_components(db: Session, build: Build, components: list[dict]) -> None:
    ids = [c["product_id"] for c in components if c.get("product_id")]
    cards = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)).options(
        selectinload(Product.category)))} if ids else {}
    if set(ids) - set(cards):
        raise BuildError("product_not_found")
    rows = []
    for c in components:
        product = cards.get(c.get("product_id"))
        category, specs = (None, {}) if product else _clean_specs(c["slot"], c.get("category"), c.get("specs") or {})
        rows.append({**c, "category": category, "specs": specs,
                     "product_category": product.category.slug if product and product.category else None})
    missing = missing_required(rows)
    if missing:
        raise BuildError("build_required", missing=missing)
    build.components = [
        BuildComponent(position=i, slot=BuildSlot(c["slot"]), product_id=c.get("product_id"),
                       quantity=max(1, min(int(c.get("quantity") or 1), 8)), raw_text=(c.get("raw_text") or "").strip(),
                       category=c["category"], specs=c["specs"])
        for i, c in enumerate(rows)
    ]


def save_build(db: Session, store: Store, data: dict, build: Build | None = None) -> Build:
    """Creates a build or changes it (the editor); a new price or currency goes to its price history."""
    created = build is None
    if created:
        build = Build(store=store, text=data.get("text"))
    price_changed = created or build.price != data["price"] or build.currency != Currency(data["currency"])
    if "components" in data:
        _set_components(db, build, data["components"])  # checked before anything is saved
    build.name = data["name"].strip()
    build.price, build.currency = data["price"], Currency(data["currency"])
    build.condition = Condition(data.get("condition") or "new")
    build.purpose = BuildPurpose(data.get("purpose") or "other")
    build.is_in_stock = data.get("is_in_stock", True)
    build.description = (data.get("description") or "").strip() or None
    build.updated_at = utcnow()
    if price_changed:
        build.price_history.append(BuildPriceHistory(price=build.price, currency=build.currency))
    if created:
        db.add(build)
    db.commit()
    return build


def set_on_sale(db: Session, build: Build, on_sale: bool) -> None:
    build.is_in_stock = on_sale
    build.updated_at = utcnow()
    db.commit()


# --- Checks ---------------------------------------------------------------------------------------------------------

def _values(c: BuildComponent) -> dict:
    """Known values of a part: the card's (without service maps) or the seller's "only specs"."""
    source = c.product.specs_json if c.product is not None else c.specs
    return {k: v for k, v in (source or {}).items() if not k.startswith("_")}


def _part_text(c: BuildComponent) -> str:
    return " ".join(filter(None, [c.raw_text, c.product.normalized_name if c.product else None,
                                  str((c.specs or {}).get("model") or "")]))


def _chips(text: str) -> set[str]:
    return {_chip(m) for m in re.finditer(GPU_CHIP[0][0], text or "", re.IGNORECASE)}


def _series(text: str) -> set[str]:
    return {(m[1] or m[3]).lower() if (m[1] or m[3]) else f"Ryzen {m[2]}" for m in _CPU_SERIES.finditer(text or "")}


def _name_mismatch(build: Build) -> list[dict]:
    """"RTX 4060" in the name, an RTX 3050 among the parts: the buyer is told to ask the seller."""
    said_text = " ".join(filter(None, [build.name, build.description]))
    flags = []
    for slot, extract in (("gpu", _chips), ("cpu", _series)):
        said, actual = extract(said_text), set()
        for c in build.components:
            if c.slot.value == slot:
                chip = _values(c).get("chip") if slot == "gpu" else None
                actual |= {chip} if chip else extract(_part_text(c))
        if said and actual and not said & actual:
            flags.append({"type": "build_name_mismatch", "level": "warning", "reason_key": "build_name_mismatch",
                          "params": {"said": ", ".join(sorted(said)), "actual": ", ".join(sorted(actual))},
                          "source": "rule"})
    return flags


def _psu_maker(build: Build) -> list[dict]:
    """The PSU decides how long the PC lives: an unknown maker is worth asking about (info, not a warning)."""
    psus = [c for c in build.components if c.slot.value == "psu"]
    if any(c.product_id or (c.specs or {}).get("brand") for c in psus):
        return []
    return [{"type": "build_psu_brand", "level": "info", "reason_key": "build_psu_brand", "params": {},
             "source": "rule"}]


def build_flags(build: Build) -> list[dict]:
    """Anti-Fraud of a build: the offer rules on exact parts (Xeon as i9, mining cards, used as new), the name
    check and the PSU maker. Only the seller's words and card values count; AI guesses are never stored."""
    flags = []
    for c in build.components:
        if c.product is None:
            continue
        row = {"raw_name": _part_text(c), "brand": c.product.brand,
               "category": c.product.category.slug if c.product.category else "other",
               "specs": written_specs(c.product.specs_json), "condition": build.condition.value, "price": None}
        for f in check_offer(row):
            if f["source"] == "rule":
                flags.append({**f, "params": {**f["params"], "component": c.product.normalized_name}})
    flags += _name_mismatch(build) + _psu_maker(build)
    return sorted(flags, key=lambda f: -LEVEL_ORDER[f["level"]])


def _board_rank(size: str | None) -> int | None:
    return BOARD_SIZES.index(size) if size in BOARD_SIZES else None  # 0 = E-ATX, the largest


def compatibility(build: Build) -> list[dict]:
    """Soft checks by known values (exact and "only specs" parts); nothing known = nothing checked."""
    by_slot: dict[str, list[dict]] = {}
    for c in build.components:
        by_slot.setdefault(c.slot.value, []).append(_values(c))
    cpu, board = (by_slot.get("cpu") or [{}])[0], (by_slot.get("motherboard") or [{}])[0]
    case = (by_slot.get("case") or [{}])[0]
    issues = []
    if cpu.get("socket") and board.get("socket") and cpu["socket"] != board["socket"]:
        issues.append({"key": "socket", "params": {"cpu": cpu["socket"], "board": board["socket"]}})
    ram_types = {ram["type"] for ram in by_slot.get("ram", []) if ram.get("type")}
    if board.get("memory_type") and ram_types - {board["memory_type"]}:
        issues.append({"key": "memory", "params": {"ram": ", ".join(sorted(ram_types)), "board": board["memory_type"]}})
    rank_board, rank_case = _board_rank(board.get("form_factor")), _board_rank(case.get("board"))
    if rank_board is not None and rank_case is not None and rank_board < rank_case:
        issues.append({"key": "form_factor", "params": {"board": board["form_factor"], "case": case["board"]}})
    return issues


def store_reference(db: Session, build: Build, usd_rate: float | None) -> dict | None:
    """"These parts separately in this store: N sum" — only when every part is exact (integrated graphics needs
    no part) and the same store sells each of them in stock. Other stores' prices are never used."""
    exact = [c for c in build.components if _level(c) == "exact"]
    if not exact or any(_level(c) not in PRECISE for c in build.components):
        return None
    offers = {o.product_id: o for o in db.scalars(select(Offer).where(
        Offer.store_id == build.store_id, Offer.product_id.in_([c.product_id for c in exact]),
        Offer.is_in_stock.is_(True), Offer.price.is_not(None), Offer.removed_at.is_(None)))}
    if any(c.product_id not in offers for c in exact):
        return None
    usd = sum((to_usd(offers[c.product_id].price, offers[c.product_id].currency, usd_rate) or 0) * c.quantity
              for c in exact)
    uzs = [to_uzs(offers[c.product_id].price, offers[c.product_id].currency, usd_rate) for c in exact]
    if None in uzs:  # no CBU rate: the sum is only exact in one currency
        currencies = {offers[c.product_id].currency for c in exact}
        if len(currencies) > 1:
            return None
        currency = currencies.pop()
        return {"price": sum(offers[c.product_id].price * c.quantity for c in exact), "currency": currency.value}
    total = sum(u * c.quantity for u, c in zip(uzs, exact))
    return {"price": round(total), "currency": "UZS", "usd": round(usd, 2)}


# --- Read -----------------------------------------------------------------------------------------------------------

def load_builds(db: Session, query=None):
    query = query if query is not None else select(Build)
    return db.scalars(query.options(
        selectinload(Build.store),
        selectinload(Build.components).selectinload(BuildComponent.product).selectinload(Product.category),
    )).all()


def component_out(c: BuildComponent) -> dict:
    return {
        "id": c.id, "slot": c.slot.value, "quantity": c.quantity, "raw_text": c.raw_text, "level": _level(c),
        "product": product_brief(c.product) if c.product else None,
        "category": c.category, "specs": c.specs or {},
    }


def _cpu_brand(build: Build) -> str | None:
    for c in build.components:
        if c.slot.value == "cpu":
            brand = str(_values(c).get("brand") or (c.product.brand if c.product else "") or "").lower()
            text = _part_text(c)
            if brand == "intel" or _INTEL.search(text):
                return "intel"
            if brand == "amd" or _AMD.search(text):
                return "amd"
    return None


def _gpu_chip(build: Build) -> str | None:
    for c in build.components:
        if c.slot.value == "gpu":
            if (c.specs or {}).get("integrated"):
                return "integrated"
            chip = _values(c).get("chip") or next(iter(sorted(_chips(_part_text(c)))), None)
            if chip:
                return chip
    return None


def _ram_gb(build: Build) -> int | None:
    total = sum(int(_values(c).get("capacity") or 0) * c.quantity for c in build.components if c.slot.value == "ram")
    return total or None


def _build_photos(build: Build) -> list[dict]:
    from sqlalchemy.orm import object_session

    from app.services.photos import published

    db = object_session(build)
    return published(db, "build", [build.id]).get(build.id, []) if db is not None and build.id else []


def build_summary(build: Build, usd_rate: float | None) -> dict:
    flags = build_flags(build)
    store = build.store
    photos = _build_photos(build)  # phase 14: up to 6, the seller uploads them in «Мои сборки»
    return {
        "photos": photos, "image": photos[0]["thumb"] if photos else None,
        "id": build.id, "name": build.name, "price": build.price, "currency": build.currency.value,
        "price_usd": to_usd(build.price, build.currency, usd_rate),
        "price_uzs": to_uzs(build.price, build.currency, usd_rate),
        "condition": build.condition.value, "purpose": build.purpose.value, "is_in_stock": build.is_in_stock,
        "created_at": build.created_at, "updated_at": build.updated_at, "is_demo": build.is_demo or store.is_demo,
        "precision": precision(build),
        "key_parts": [component_out(c) for c in build.components if c.slot.value in KEY_SLOTS],
        "cpu_brand": _cpu_brand(build), "gpu_chip": _gpu_chip(build), "ram_gb": _ram_gb(build),
        "flag_level": flags[0]["level"] if flags else None,
        "warnings": sum(f["level"] != "info" for f in flags) + len(compatibility(build)),
        "store": {"id": store.id, "name": store.name, "city": store.city, "is_verified": store.is_verified},
    }


def build_detail(db: Session, build: Build, usd_rate: float | None) -> dict:
    store = build.store
    return {
        **build_summary(build, usd_rate), "description": build.description,
        "components": [component_out(c) for c in build.components],
        "flags": build_flags(build), "compatibility": compatibility(build),
        "store_reference": store_reference(db, build, usd_rate),
        "branches": _branches(store),
        "store": {"id": store.id, "name": store.name, "city": store.city, "district": store.district,
                  "address": store.address, "phone": store.phone, "telegram": store.telegram,
                  "is_verified": store.is_verified, "hours": store.hours, "map_url": store.map_url,
                  "map_lat": store.map_lat, "map_lon": store.map_lon},
    }


def _matches(s: dict, f: dict) -> bool:
    uzs = s["price_uzs"]
    if f.get("price_min") is not None and (uzs is None or uzs < f["price_min"]):
        return False
    if f.get("price_max") is not None and (uzs is None or uzs > f["price_max"]):
        return False
    if f.get("exact_only") and s["precision"]["exact"] < s["precision"]["total"]:
        return False
    for key, field in (("purpose", "purpose"), ("cpu", "cpu_brand"), ("gpu", "gpu_chip"), ("ram", "ram_gb"),
                       ("condition", "condition")):
        if f.get(key) and s[field] not in f[key]:
            return False
    return True


def _facet(items: list[dict], key: str) -> list[dict]:
    counts: dict = {}
    for s in items:
        if s[key] is not None:
            counts[s[key]] = counts.get(s[key], 0) + 1
    return [{"value": v, "count": n} for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]


def _ts(dt: datetime) -> float:
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def _branches(store: Store) -> list[dict]:
    """Phase 12.1: the build is reserved in one of the store's branches (no stock by branch for builds)."""
    from app.services.branches import branch_public

    return [branch_public(b, store) for b in store.branches]


def list_builds(db: Session, usd_rate: float | None, f: dict, city: str | None = None, sort: str = "new",
                page: int = 1, page_size: int = PAGE_SIZE) -> dict:
    """The "Ready PCs" section: builds on sale in the city (or the whole country), filters with counts.
    No market labels or ratings: builds of different stores are not compared."""
    query = select(Build).join(Build.store).where(Build.is_in_stock.is_(True), Store.blocked_at.is_(None))
    if city:
        from app.services.branches import store_in_city

        query = query.where(store_in_city(city))  # phase 12.1: a branch of the store in the city
    all_items = [build_summary(b, usd_rate) for b in load_builds(db, query)]
    items = [s for s in all_items if _matches(s, f)]
    if sort in ("price_asc", "price_desc"):
        items.sort(key=lambda s: s["price_usd"] or 0, reverse=sort == "price_desc")
    else:
        items.sort(key=lambda s: -_ts(s["created_at"]))
    return {
        "items": items[(page - 1) * page_size: page * page_size], "total": len(items), "page": page,
        "page_size": page_size, "includes_demo": any(s["is_demo"] for s in items),
        "exact_total": sum(s["precision"]["exact"] == s["precision"]["total"] for s in all_items),
        "facets": {key: _facet(all_items, field) for key, field in
                   (("purpose", "purpose"), ("cpu", "cpu_brand"), ("gpu", "gpu_chip"), ("ram", "ram_gb"),
                    ("condition", "condition"))},
    }


def store_builds(db: Session, store: Store, usd_rate: float | None) -> list[dict]:
    builds = load_builds(db, select(Build).where(Build.store_id == store.id).order_by(Build.updated_at.desc()))
    return [build_summary(b, usd_rate) for b in builds]


def counts(db: Session, store: Store) -> dict:
    builds = db.scalars(select(Build).where(Build.store_id == store.id)).all()
    return {"on_sale": sum(b.is_in_stock for b in builds), "off_sale": sum(not b.is_in_stock for b in builds)}
