"""Phase 16.1: consumables are not printers, "Прочее" is split into categories, "3 в 1" / "4 в 1" instead of "МФУ"."""

from sqlalchemy import func, select

from app.db.models import Category, Offer, Product, Store
from app.services import recategorize
from app.services.categorize import refine_category
from app.services.spec_normalizer import normalize_specs
from tests.test_builds import _card, _offer, _store, db  # noqa: F401  (db is a fixture)


def test_consumables_leave_printers():
    for name in ("Чернила HP GT52 Cyan Original Ink Bottle", "Картридж HP 205A Black LaserJet Toner Cartridge",
                 "Печатающая головка HP Tri-color", "Заправочный комплект HP Neverstop Toner Reload kit 103AD",
                 "Фотобарабан Pantum DL-420", "Бумага для принтера A4 SvetoCopy"):
        assert refine_category("printer", name) == "consumables", name
        assert refine_category("other", name) == "consumables", name


def test_printers_stay_printers():
    for name in ("HP Ink Tank 315 AiO Z4B04A", "МФУ Epson L3210 (с чернилами)", "Принтер HP Smart Tank 580 + картридж",
                 "Epson L3250", "МФУ Canon PIXMA G3410 принтер/сканер/копир"):
        assert refine_category("printer", name) == "printer", name


def test_other_is_split_and_other_categories_keep_their_goods():
    cases = {
        "Коврик для мыши HyperX Pulsefire Mat XL": "accessories", "USB хаб Lenovo USB-C to 4 Port USB-A Hub": "accessories",
        "Адаптер HP USB-C to HDMI 2.0 Adapter": "accessories", "Gembird SPG6-B-10PPB Сетевой фильтр 3m": "accessories",
        "Рюкзак HP Campus XL Marble Stone": "bags", "Чехол для ноутбука Lenovo 14\" Urban Sleeve Case": "bags",
        "Веб-камера Lenovo 510 FHD": "webcams", "Камера TWC-2AFH с массивом микрофонов 1080p": "webcams",
        "Микрофон HyperX QuadCast 2": "microphones", "Audio-Technica AT2020USBX Микрофон": "microphones",
        "HP ScanJet Pro 2000 s2 Scanner": "scanners", "Проекционный экран EMRSM-HD-100D 100\"": "screens",
        "Интерактивный дисплей e-SURF E6514 65\" 4K UHD": "panels",
        "Мобильный стенд для интерактивной панели": "accessories",
        "Планшет Lenovo Tab M10": "other",
    }
    for name, slug in cases.items():
        assert refine_category("other", name) == slug, name
    assert refine_category("headphones", "Наушники HyperX Cloud II с микрофоном") == "headphones"
    assert refine_category("keyboard", "Игровой набор (клавиатура+мышь+коврик)") == "keyboard"
    assert refine_category("mouse", "Коврик для мыши Redragon Flick L") == "accessories"
    assert refine_category("laptop", "Ноутбук HP 15 + сумка") == "laptop"


def test_mfp_is_3_in_1_or_4_in_1():
    def kind(text, given=None):
        return normalize_specs("printer", text, given).get("type")
    assert kind("МФУ Epson L3210") == "3in1"
    assert kind("HP Laser MFP 137fnw 4ZB84A") == "4in1"
    assert kind("Pantum BM5100FDN") == "4in1"
    assert kind("Canon i-SENSYS MF275dw МФУ с факсом") == "4in1"
    assert kind("Canon PIXMA G2416", {"type": "mfp"}) == "3in1"  # the old value
    assert kind("Принтер HP LaserJet M111a") == "printer"
    assert kind("Epson L121") == "printer"  # no MFP word: a plain printer (rule)
    assert kind("HP LaserJet Pro MFP 4103dw") == "3in1"


def test_recategorize_moves_cards_keeps_offers_and_counts_add_up(db):
    store = _store(db, "a@example.com")
    ink = _card(db, "printer", "Чернила HP GT52 Cyan Original Ink Bottle", brand="HP")
    mfp = _card(db, "printer", "МФУ Epson L3210", {"type": "mfp"}, "Epson")
    pad = _card(db, "other", "Коврик для мыши HyperX Pulsefire Mat XL", brand="HyperX")
    tablet = _card(db, "other", "Планшет Lenovo Tab M10", brand="Lenovo")
    for card, price in ((ink, 12), (mfp, 180), (pad, 20), (tablet, 150)):
        _offer(db, store, card, price)
    offers = db.scalar(select(func.count(Offer.id)).where(Offer.store_id == store.id))
    assert {m["to"] for m in recategorize.report(db)["moves"]} == {"consumables", "accessories"}
    result = recategorize.apply(db)
    assert result["moved"] == 2
    db.expire_all()
    slug = lambda p: db.get(Product, p.id).category.slug  # noqa: E731
    assert (slug(ink), slug(mfp), slug(pad), slug(tablet)) == ("consumables", "printer", "accessories", "other")
    assert db.get(Product, ink.id).match_key.startswith("consumables:")
    assert db.get(Product, mfp.id).specs_json["type"] == "3in1"
    assert db.scalar(select(func.count(Offer.id)).where(Offer.store_id == store.id)) == offers
    assert db.scalar(select(func.count(Category.id)).where(Category.slug == "consumables")) == 1
    assert recategorize.report(db)["moves"] == []  # a second run moves nothing
    assert db.get(Store, store.id) is not None
