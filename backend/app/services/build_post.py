"""Phase 17.2: a build post -> name, price, condition, description and parts, by rules of code only.

The text of a ready-PC post is split here; the parts then go to the same pipeline as goods (cache -> rules -> AI,
`builds.parse_build_text`). Rules first:
- a line with a label ("CPU:", "Видеокарта —", "🔸 MB: ...", "Protsessor:") is a part of that slot; markers (🔸 • - ✅)
  and emojis are dropped; one labeled line may hold several parts ("SSD: 256 GB + 1 TB");
- a line without labels is a part only when the code recognizes it (a CPU model, a GPU chip, "16GB DDR4", "650W"…)
  and the post has no labeled parts, or it starts with a slot word ("SSD Samsung 980"); otherwise it is description
  (the "Преимущества" block repeats parts in words: "Мощный процессор Ryzen 7 9800X3D");
- a bracket tail with words ("(панорамное стекло, …)") is not part of the model: it goes to the description;
- the price is read by code only ("769$", "$769", "769 у.е.", "8 500 000 сум", "8.5 млн"); "торг" is a flag;
- contacts (phones, @nicks, links) are cut out of every line and never kept.
"""

import re
import unicodedata

from app.services.spec_normalizer import BRAND_CASE, GPU_CHIP
from app.services.text_import import _strip_symbols, condition_of, find_price, has_model

# The label of a line says the slot: Russian, Uzbek (Latin and Cyrillic), English and the usual abbreviations
SLOT_WORDS = [
    ("cpu", r"процессор|\bпроц\b|\bcpu\b|protsessor|processor|\bцп\b"),
    ("motherboard", r"материнск|материнка|мат\.?\s*плат|\bмать\b|motherboard|\bmb\b|\bmobo\b|\bм/?п\b|ona\s*plata"
                    r"|она\s*плата|\bплата\b"),
    ("ram", r"оперативн|оперативка|\bозу\b|\bram\b|\bopera\w*|\bпамять\b|\bmemory\b|xotira"),
    ("gpu", r"видеокарт|видюх|\bgpu\b|videokarta|video\s*karta|графика|\bvga\b|graphics"),
    ("storage", r"накопител|\bssd\b|\bhdd\b|\bдиск\b|nvme|\bm\.2\b|ж[её]стк|storage|nakopitel|\bdisk\b"),
    ("psu", r"блок\s*питания|\bбп\b|\bpsu\b|питани|quvvat|power\s*supply|\bpower\b"),
    ("case", r"корпус|\bcase\b|korpus"),
    ("cooling", r"охлажден|кулер|cooler|cooling|\bсво\b|водянка|sovutish|kuler"),
]
# "CPU: …", "Видеокарта — …", "MB - …": a label is a few words without digits before ":" or a dash with spaces
_LABEL = re.compile(r"^(?P<key>[^\W\d_][^:\d]{0,30}?)\s*(?::|\s[-–—]\s|[–—])\s*(?P<value>\S.*)$")
_MARKER = re.compile(r"^[\s\-–—•*·▪►→>✓✔+]+|^\d{1,2}[.)]\s+")
# Parts in one line: "Ryzen 5 5600 / B550M | 16GB", "i5-12400F + RTX 3060"; not "1TB/2TB", not "80+ Bronze"
_SPLIT = re.compile(r"\s+[/|]\s+|\s*[|;]\s*|(?<!\b80)\s*\+\s*(?!\s*(?:bronze|silver|gold|platinum|titanium|white)\b)",
                    re.I)
# A bracket with words is a note of the seller, not the model: "(панорамное стекло, отличная продуваемость)"
_NOTE = re.compile(r"\s*\((?=[^)]*[а-яёўқғҳ]{4})([^)]*)\)", re.I)
_HEADER = re.compile(r"^[^\W\d_][^:\d]{1,40}:$")  # "Характеристики:", "Преимущества:"
_QUANTITY = re.compile(r"^(?P<n>[1-8])\s*(?:x|х|×|шт\.?)\s*(?=\S)|\s+(?:x|х|×)\s*(?P<m>[1-8])$"
                       r"|\s*\((?P<k>[1-8])\s*шт\.?\)$", re.I)

# Contacts are cut out of a line; a line of only contact words then goes away
_CONTACT = re.compile(
    r"(?:https?://|www\.)\S+|\b(?:t|telegram)\.me/\S*|(?<![\w.])@[a-z0-9_]{3,}"
    r"|\+?\d[\d\s()\-]{7,}\d", re.I)
_CONTACT_WORDS = re.compile(
    r"^(?:тел\w*|телефон\w*|звоните|звонить|пишите|писать|в\s+лс|в\s+личку|контакт\w*|связь|для\s+связи|админ\w*"
    r"|aloqa|murojaat|tel|phone|contacts?|whats\s*app|telegram|телеграм|инстаграм|instagram|по\s+вопросам"
    r"|[\s:,.;—–\-+/|()])*$", re.I)

# Content rules: what a part is without a label
CPU_MODEL = re.compile(
    r"\b(?:core\s*)?(?:i[3579]|ryzen\s*(?:ai\s*)?[3579]|ultra\s*[579]|pentium|celeron|athlon|xeon|threadripper)\b"
    r"[\s-]*(?:[a-z]{1,2}\d?-?)?\d{3,5}[a-z0-9]{0,4}\b", re.I)
_GPU = re.compile(GPU_CHIP[0][0] + r"|\b(?:geforce|radeon)\b", re.I)
_INTEGRATED = re.compile(r"встро[её]н|встройк|интегрир|integrated|\bigpu\b|без\s+видеокарт|o'rnatilgan", re.I)
_CHIPSET = re.compile(r"\b[abhxz]\d{3}[a-z]{0,2}\b", re.I)
_RAM = re.compile(r"\bddr[345]\b|\b\d{1,3}\s*(?:gb|гб)\b.*\b(?:fury|vengeance|ripjaws|trident|dominator|xpg|t-?force"
                  r"|\d{4}\s*(?:mhz|мгц))|\b\d{4}\s*(?:mhz|мгц)\b", re.I)
_STORAGE = re.compile(r"\b(?:ssd|hdd|nvme|m\.2|sata)\b|\b\d+(?:[.,]\d+)?\s*(?:tb|тб)\b", re.I)
_PSU = re.compile(r"\b\d{3,4}\s*(?:w|вт|ватт?)\b|80\s*\+|80\s*plus", re.I)
_CASE = re.compile(r"корпус|\bcase\b|\btower\b|aquarium|аквариум", re.I)
_COOLING = re.compile(r"кулер|cooler|\baio\b|водян|liquid|жидкост|охлажд", re.I)
CONTENT_RULES = [("cpu", CPU_MODEL), ("gpu", _GPU), ("gpu", _INTEGRATED), ("cooling", _COOLING),
                 ("motherboard", _CHIPSET), ("ram", _RAM), ("storage", _STORAGE), ("psu", _PSU), ("case", _CASE)]

_PURPOSE_WORDS = [
    ("gaming", r"игров|gaming|геймер|для игр|o'yin|ўйин"),
    ("work", r"монтаж|рендер|дизайн|рабоч|для работы|стрим|3d|workstation|ish uchun"),
    ("office", r"офис|office|для учеб|для дома|ofis"),
]
# Words of a used PC: the condition is offered as "б/у", the seller confirms it in the preview
_USED_HINTS = re.compile(
    r"обслужен|был\w*\s+в\s+(?:использ|эксплуат)|использовал|после\s+майнинг|состояни\w*\s+\d+\s*/\s*10"
    r"|гаранти\w*(?:\s+магазина)?\s+(?:нет|уже\s+нет|закончил)|без\s+гаранти|отличн\w+\s+состояни"
    r"|ishlatilgan|почищен|чистк\w+\s+(?:сделан|проведен)|замен\w+\s+термопаст|продаю\s+свой", re.I)
_BARGAIN = re.compile(r"(?:небольшой\s+|уместен\s+|возможен\s+|есть\s+|разумный\s+)?торг\w*(?:\s+уместен)?"
                      r"|kelishamiz|kelishiladi", re.I)
_PRICE_WORD = re.compile(r"^(?:цена|стоимость|price|narxi|narx|нарх\w*)\b\s*[:—–\-=]?\s*", re.I)


def slot_of_key(key: str) -> str | None:
    low = key.lower()
    return next((slot for slot, pattern in SLOT_WORDS if re.search(pattern, low)), None)


def slot_by_content(text: str) -> str | None:
    """What part a text is without a label, or None. A CPU model first: "i5-12400F" has no chipset."""
    return next((slot for slot, pattern in CONTENT_RULES if pattern.search(text)), None)


def guess_purpose(text: str) -> str:
    low = text.lower()
    return next((p for p, pattern in _PURPOSE_WORDS if re.search(pattern, low)), "other")


def quantity(text: str) -> tuple[int, str]:
    m = _QUANTITY.search(text)
    if not m:
        return 1, text
    return int(m["n"] or m["m"] or m["k"]), (text[: m.start()] + text[m.end():]).strip()


def _cut_contact(m: re.Match) -> str:
    """A number is a phone with "+" or 9+ digits; a price has fewer ("8 500 000")."""
    found = m[0]
    if found[0].isdigit() and sum(ch.isdigit() for ch in found) < 9:
        return found
    return " "


def strip_contacts(text: str) -> str:
    """The post without phones, @nicks and links; lines of only "Тел:" / "Пишите" go away too."""
    out = []
    for line in text.splitlines():
        cleaned = _CONTACT.sub(_cut_contact, line)
        if cleaned != line:
            cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
            if _CONTACT_WORDS.fullmatch(_strip_symbols(cleaned).strip()):
                continue
        out.append(cleaned)
    return "\n".join(out).strip()


def _clean_line(raw: str) -> str:
    line = _strip_symbols(unicodedata.normalize("NFC", raw))
    line = re.sub(r"#\w+", " ", line)
    line = _MARKER.sub("", re.sub(r"\s+", " ", line)).strip()
    return line.strip(" ,;")


def _split_note(piece: str) -> tuple[str, str | None]:
    """"Zalman P30 (панорамное стекло, …)" -> ("Zalman P30", "панорамное стекло, …")."""
    notes = [m[1].strip() for m in _NOTE.finditer(piece)]
    return _NOTE.sub("", piece).strip(" ,-–—"), ", ".join(notes) or None


def _pieces(value: str) -> list[str]:
    return [p.strip(" -–—•,.") for p in _SPLIT.split(value) if p and p.strip(" -–—•,.")]


def _content_parts(line: str) -> list[str] | None:
    """An unlabeled line as parts: every piece of "Ryzen 5 5600 / B550M / 16GB" (or of "…, …, …") must be one."""
    for pieces in (_pieces(line), [p.strip() for p in line.split(",") if p.strip()]):
        if len(pieces) >= 2 and all(slot_by_content(p) for p in pieces):
            return pieces
    if slot_by_content(line) and len(line.split()) <= 8:
        return [line]
    return None


def _title(line: str) -> str:
    """"Игровой ПК | RTX 3070 Ti + i5-12400F | Корпус-аквариум" -> "Игровой ПК RTX 3070 Ti + i5-12400F": the first
    segment and the segments that name models; slogans without models are left out."""
    segments = [s.strip(" -–—,.") for s in re.split(r"\s*\|\s*", line) if s.strip(" -–—,.")]
    kept = [s for i, s in enumerate(segments) if i == 0 or has_model(s)]
    return " ".join(kept)[:200]


def split_post(text: str) -> dict:
    """A build post -> name, price, currency, condition (+ "check it"), purpose, bargain, description and parts."""
    text = strip_contacts(text)
    lines = [line for line in (_clean_line(raw) for raw in text.splitlines()) if line]
    price = currency = None
    check = bargain = False
    title_index, labeled, headed, loose, notes = None, [], [], [], []
    for i, line in enumerate(lines):
        found, cur, chk, rest = find_price(line)
        if found is not None and price is None and not _CHIPSET.fullmatch(line):
            price, currency, check = found, cur, chk
            line = _PRICE_WORD.sub("", rest.strip(" :—-–=")).strip(" :—-–=,.")
            if _BARGAIN.search(line):
                bargain = True
            if not re.search(r"[^\W\d_]", line):
                continue
            if _BARGAIN.fullmatch(line):
                notes.append((i, line[:1].upper() + line[1:]))
                continue
        label = _LABEL.match(line)
        slot = slot_of_key(label["key"]) if label and len(label["key"].split()) <= 3 else None
        if slot:
            for piece in _pieces(label["value"]):
                labeled.append({"text": piece, "slot": slot, "line": i})
            continue
        if title_index is None and not labeled and not loose and not headed:
            title_index = i
            continue
        if _HEADER.match(line):
            continue
        head = slot_of_key(" ".join(line.split()[:1]))
        if head and slot_by_content(line):  # "SSD Samsung 980 500GB": a slot word, then the part
            headed.append({"text": line, "slot": head, "line": i})
            continue
        found_parts = _content_parts(line)
        if found_parts:
            loose.append({"line": i, "pieces": found_parts})
            continue
        notes.append((i, line))
    title = lines[title_index] if title_index is not None else ""
    parts = sorted(labeled + headed, key=lambda p: p["line"])
    if not labeled:
        parts = sorted(headed + [{"text": p, "slot": None, "line": x["line"]} for x in loose for p in x["pieces"]],
                       key=lambda p: p["line"])
        if not parts and title:  # one line names everything: "ПК: Ryzen 5 5600 / RTX 3060 / 16GB — 500$"
            pieces = _pieces(title)
            if len(pieces) >= 2 and sum(bool(slot_by_content(p)) for p in pieces) >= 2:
                parts = [{"text": p, "slot": None, "line": title_index} for p in pieces if slot_by_content(p)]
                title = " ".join(p for p in pieces if not slot_by_content(p)) or title
    else:  # parts written in words after the labeled list are description
        notes += [(x["line"], " ".join(x["pieces"])) for x in loose]
    out = []
    for part in parts:
        words, note = _split_note(part["text"])
        if not words:
            continue
        if note:
            notes.append((part["line"], f"{words} — {note}"))
        count, words = quantity(words)
        out.append({"text": words, "slot": part["slot"], "quantity": count})
    used_hint = _USED_HINTS.search(text)
    condition = condition_of(text)
    condition_check = False
    if condition == "unknown" and used_hint:
        condition, condition_check = "used", True
    return {
        "name": _title(title), "price": price, "currency": currency, "currency_check": check,
        "condition": condition, "condition_check": condition_check, "purpose": guess_purpose(text),
        "bargain": bargain, "description": "\n".join(n for _, n in sorted(notes, key=lambda n: n[0])) or None, "parts": out,
    }


# Makers of build parts that the price lists of the catalog have not met yet (kept as written)
PART_MAKERS = {b.lower(): b for b in (
    "Galax", "Zalman", "Colorful", "Gainward", "KFA2", "PowerColor", "XFX", "FSP", "Chieftec", "NZXT", "Aerocool",
    "GameMax", "1stPlayer", "Seasonic", "Arctic", "AFOX", "Xigmatek", "Fractal Design", "be quiet!", "Ocypus",
)}
CHIP_VENDORS = {"AMD", "NVIDIA", "Intel"}


def find_brand(text: str, slot: str | None = None) -> str | None:
    """The first maker named in a part: "16GB Kingston Fury" -> Kingston. For a GPU the chip vendor is not the
    maker ("NVIDIA GeForce RTX 3060" says nothing about who made the card)."""
    low = text.lower()
    makers = {**BRAND_CASE, **PART_MAKERS}
    found = [(m.start(), makers[b]) for b in makers
             if (m := re.search(rf"(?<![\w-]){re.escape(b)}(?![\w])", low))
             and not (slot == "gpu" and makers[b] in CHIP_VENDORS)]
    return min(found)[1] if found else None
