"""Phase 16.1: category rules by the words of the row — code first, the AI's category is only a guess.

Ink, toner and printheads are not printers (a 15 $ ink bottle at the top of "Принтеры" sorted by price);
bags, mouse pads, adapters, webcams and microphones are not "Прочее". A rule moves a row only out of the
categories where such goods get lost (its sources), so "Наушники с микрофоном" stay headphones.
"""

import re

# Words that only say what the item goes with: "Камера с массивом микрофонов", "Принтер + картридж"
_WITH = re.compile(r"(?:\b(?:с|со|with)\s+|\+\s*)(?:массивом\s+)?"
                   r"(?:микрофон|спикерфон|картридж|чернил|подставк|коврик|сумк|рюкзак|адаптер)\w*", re.I)
# A printer or an MFP names itself; its scanner or its ink is a part of it
_DEVICE = r"^(?:принтер|мфу|printer|mfp)\b|копир|\bмфу\b|\bmfp\b|\bkfq\b"

# (category, pattern, categories it takes rows from[, a pattern that keeps the row where it is]). First match wins
RULES: tuple[tuple, ...] = (
    ("consumables",
     r"чернил|картридж|тонер|\btoner\b|cartridge|ink\s*bottle|\bink\b(?!\s*tank)|печатающ\w*\s+головк|printhead"
     r"|заправочн\w*\s+комплект|reload\s+kit|фотобарабан|\bdrum\b|бумага\s+для\s+принтер|фотобумаг|photo\s*paper"
     r"|siyoh|kartrij",
     ("printer", "other"), _DEVICE),
    ("bags", r"рюкзак|сумк|чехол\s+для\s+ноутбук|backpack|\bsleeve\b|\bbag\b|top\s*-?load|\bsling\b|ryukzak|sumka",
     ("other", "laptop")),
    ("webcams", r"веб-?камер|webcam|\bptz\b|^камера\b|\bкамера\s+(?:aver|logitech|teleset|twc)|veb-?kamera", ("other",)),
    ("microphones", r"микрофон|microphone|mikrofon|поп-?фильтр|pop\s+filter", ("other",)),
    ("scanners", r"сканер|scanner|scanjet|imageformula|\bczur\b|\bkv-s\w*|\blide\s*\d|skaner", ("other", "printer"),
     _DEVICE),
    ("screens", r"проекционн\w*\s+экран|^экран\b|хромакей|projection\s+screen|\bekran\b", ("other", "projector")),
    # A mouse pad or a wrist rest a store put under "Мыши" / "Клавиатуры"
    ("accessories", r"коврик|mouse\s*pad|mousepad|\bmat\b|подставк|wrist\s+rest|kovrik", ("other", "mouse", "keyboard")),
    ("accessories",
     r"кабел|\bcable\b|переходник|адаптер|adapter|\bхаб|\bhub\b|док-станц|\bdock\b|сетев\w*\s+фильтр|стилус|stylus"
     r"|\bpen\b|кронштейн|bracket|креплени|\bстенд\b|прижимн\w*\s+рамк|riser|райзер|контроллер\s+(?:pwm|argb|подсвет)"
     r"|^стойки\b|лоток|kabel",
     ("other",)),
    ("panels", r"интерактивн\w*\s+(?:дисплей|панел|инфокиоск|сенсорн)|видеостен|инфокиоск|сенсорн\w*\s+стол"
               r"|led\s+постер|лифтов\w*\s+дисплей|interactive\s+(?:display|panel)", ("other", "monitor")),
)
_COMPILED = tuple((r[0], re.compile(r[1], re.I), r[2], re.compile(r[3], re.I) if len(r) > 3 else None) for r in RULES)
NEW_CATEGORIES = tuple(dict.fromkeys(r[0] for r in RULES))


def refine_category(category: str | None, text: str) -> str:
    """The category by the rules, or the given one: refine_category("printer", "Чернила HP GT52") -> "consumables"."""
    category = category or "other"
    text = _WITH.sub(" ", text.replace("ё", "е")).strip()
    for slug, pattern, sources, keep in _COMPILED:
        if category in sources and pattern.search(text) and not (keep and keep.search(text)):
            return slug
    return category
