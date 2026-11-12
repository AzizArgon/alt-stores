"""Phase 15: the server answers keys and params, the interface translates them (frontend/src/locales/*.json).

The only texts the server writes itself are files: the Excel of "My goods" and of the stock journal. Their words
are here, in the reader's language: the profile's choice (users.lang), else the browser's Accept-Language, else ru.
Words typed by people (names, price list lines, branch names) are never translated.
"""
from fastapi import Request

LANGS = ("ru", "uz", "en")


def user_lang(user=None, request: Request | None = None) -> str:
    if user is not None and getattr(user, "lang", None) in LANGS:
        return user.lang
    header = request.headers.get("accept-language", "") if request is not None else ""
    for part in header.split(","):
        base = part.split(";")[0].strip().lower().split("-")[0]
        if base in LANGS:
            return base
    return "ru"


# Headers of "My goods": the ALT code and the name are recognized back in any language (stock import)
EXPORT = {
    "ru": {
        "id": "Код ALT", "name": "Товар", "category": "Категория", "brand": "Бренд", "model": "Модель",
        "condition": "Состояние", "price": "Цена", "currency": "Валюта", "barcode": "Штрихкод",
        "reserved": "Резерв", "in_stock": "Наличие", "cost": "Закупка", "markup": "Наценка, %",
        "yes": "да", "no": "нет", "goods_sheet": "Мои товары",
        "date": "Дата", "kind": "Тип", "branch": "Филиал", "before": "Было", "change": "Изменение", "after": "Стало",
        "reserved_after": "Резерв после", "sale_price": "Цена продажи", "reason": "Причина", "comment": "Комментарий",
        "doc": "Документ", "reservation": "Бронь", "upload": "Загрузка", "journal_sheet": "Журнал",
        "warehouse": "Склад",
    },
    "uz": {
        "id": "ALT kodi", "name": "Mahsulot", "category": "Kategoriya", "brand": "Brend", "model": "Model",
        "condition": "Holati", "price": "Narx", "currency": "Valyuta", "barcode": "Shtrix-kod",
        "reserved": "Rezerv", "in_stock": "Mavjudligi", "cost": "Xarid narxi", "markup": "Ustama, %",
        "yes": "ha", "no": "yoʻq", "goods_sheet": "Mahsulotlarim",
        "date": "Sana", "kind": "Turi", "branch": "Filial", "before": "Edi", "change": "Oʻzgarish", "after": "Boʻldi",
        "reserved_after": "Keyingi rezerv", "sale_price": "Sotish narxi", "reason": "Sabab", "comment": "Izoh",
        "doc": "Hujjat", "reservation": "Bron", "upload": "Yuklash", "journal_sheet": "Jurnal",
        "warehouse": "Ombor",
    },
    "en": {
        "id": "ALT code", "name": "Product", "category": "Category", "brand": "Brand", "model": "Model",
        "condition": "Condition", "price": "Price", "currency": "Currency", "barcode": "Barcode",
        "reserved": "Reserved", "in_stock": "In stock", "cost": "Cost", "markup": "Markup, %",
        "yes": "yes", "no": "no", "goods_sheet": "My products",
        "date": "Date", "kind": "Type", "branch": "Branch", "before": "Was", "change": "Change", "after": "Now",
        "reserved_after": "Reserved after", "sale_price": "Sale price", "reason": "Reason", "comment": "Comment",
        "doc": "Document", "reservation": "Reservation", "upload": "Upload", "journal_sheet": "Journal",
        "warehouse": "Warehouse",
    },
}

CONDITIONS = {
    "ru": {"new": "новый", "used": "б/у", "refurbished": "восстановленный", "new_openbox": "новый, вскрыт",
           "unknown": "не указано"},
    "uz": {"new": "yangi", "used": "b/u", "refurbished": "qayta tiklangan", "new_openbox": "yangi, qadogʻi ochilgan",
           "unknown": "koʻrsatilmagan"},
    "en": {"new": "new", "used": "used", "refurbished": "refurbished", "new_openbox": "new, open box",
           "unknown": "not given"},
}

KINDS = {
    "ru": {"initial": "Начальный остаток", "receipt": "Приход", "sale": "Продажа", "adjust": "Корректировка",
           "reserve": "Резерв брони", "unreserve": "Снятие резерва", "res_sale": "Продажа по брони",
           "import": "Импорт остатков", "undo": "Отмена загрузки", "manual": "Ручная правка",
           "move_out": "Выкладка: со склада", "move_in": "Выкладка: в филиал", "return": "Возврат",
           "inventory": "Ревизия"},
    "uz": {"initial": "Boshlangʻich qoldiq", "receipt": "Kirim", "sale": "Sotish", "adjust": "Tuzatish",
           "reserve": "Bron rezervi", "unreserve": "Rezervni olish", "res_sale": "Bron boʻyicha sotish",
           "import": "Qoldiqlar importi", "undo": "Yuklashni bekor qilish", "manual": "Qoʻlda tahrir",
           "move_out": "Chiqarish: ombordan", "move_in": "Chiqarish: filialga", "return": "Qaytarish",
           "inventory": "Reviziya"},
    "en": {"initial": "Opening balance", "receipt": "Receipt", "sale": "Sale", "adjust": "Adjustment",
           "reserve": "Reservation hold", "unreserve": "Hold released", "res_sale": "Sale by reservation",
           "import": "Stock import", "undo": "Upload undone", "manual": "Hand edit",
           "move_out": "Shelving: from the warehouse", "move_in": "Shelving: to a branch", "return": "Return",
           "inventory": "Stocktake"},
}

REASONS = {
    "ru": {"inventory": "инвентаризация", "defect": "брак", "loss": "потеря", "other": "другое",
           "wh_off": "склад выключен", "changed_mind": "передумал", "defect_out": "брак, не в наличие",
           "oversold": "продано больше, чем по учёту"},
    "uz": {"inventory": "inventarizatsiya", "defect": "brak", "loss": "yoʻqotish", "other": "boshqa",
           "wh_off": "ombor oʻchirilgan", "changed_mind": "fikridan qaytdi", "defect_out": "brak, mavjudlikka qaytmaydi",
           "oversold": "hisobdagidan koʻp sotilgan"},
    "en": {"inventory": "inventory", "defect": "defect", "loss": "loss", "other": "other",
           "wh_off": "warehouse turned off", "changed_mind": "changed their mind", "defect_out": "defect, not back in stock",
           "oversold": "sold more than the books show"},
}

# The category of a card by its slug (the same words as `categories.*` of the interface)
CATEGORIES = {
    "uz": {"cpu": "Protsessorlar", "motherboard": "Ona platalar", "gpu": "Videokartalar", "ram": "Operativ xotira",
           "ssd": "SSD disklar", "hdd": "Qattiq disklar (HDD)", "flash": "Fleshkalar va xotira kartalari",
           "psu": "Quvvat bloklari", "ups": "UPS (UBP)", "case": "Korpuslar", "cooling": "Sovutish",
           "monitor": "Monitorlar", "laptop": "Noutbuklar", "aio": "Monobloklar", "desktop": "Tizim bloklari",
           "keyboard": "Klaviaturalar", "mouse": "Sichqonchalar", "headphones": "Quloqchinlar", "speakers": "Karnaylar",
           "printer": "Printerlar va KFQ", "projector": "Proyektorlar", "chair": "Geymer kreslolari", "other": "Boshqalar"},
    "en": {"cpu": "Processors", "motherboard": "Motherboards", "gpu": "Graphics cards", "ram": "RAM", "ssd": "SSDs",
           "hdd": "Hard drives (HDD)", "flash": "Flash drives and memory cards", "psu": "Power supplies", "ups": "UPS",
           "case": "Cases", "cooling": "Cooling", "monitor": "Monitors", "laptop": "Laptops", "aio": "All-in-ones",
           "desktop": "Desktop PCs", "keyboard": "Keyboards", "mouse": "Mice", "headphones": "Headphones",
           "speakers": "Speakers", "printer": "Printers and MFPs", "projector": "Projectors", "chair": "Gaming chairs",
           "other": "Other"},
}


def category_name(category, lang: str) -> str | None:
    if category is None:
        return None
    return CATEGORIES.get(lang, {}).get(category.slug, category.name)
