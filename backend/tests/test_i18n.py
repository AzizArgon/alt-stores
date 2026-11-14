"""Phase 15: languages — the profile keeps the choice, files are in the reader's language, the server answers keys."""

import io
import re

from openpyxl import load_workbook
from sqlalchemy import select

from app.core.i18n import user_lang
from app.db.models import Notification
from app.services import cabinet, chat, stock_excel
from tests.test_notifications import _of
from tests.test_reservations import _auth, client, no_rate, world  # noqa: F401  (fixtures)
from tests.test_builds import db  # noqa: F401
from tests.test_stock import _op, _world

CYRILLIC = re.compile("[А-Яа-яЁё]")


def _headers(content: bytes) -> tuple[str, list[str]]:
    ws = load_workbook(io.BytesIO(content)).active
    return ws.title, [c.value for c in ws[1]]


def test_the_profile_keeps_the_language(client, db, world):
    b1 = world["b1"]
    h = _auth(b1)
    assert client.get("/api/auth/me", headers=h).json()["lang"] is None  # not chosen yet: the browser's one
    assert client.put("/api/auth/me/lang", json={"lang": "uz"}, headers=h).json()["lang"] == "uz"
    # Another device logs in: the same language comes with the user
    assert client.get("/api/auth/me", headers=h).json()["lang"] == "uz"
    assert client.put("/api/auth/me/lang", json={"lang": "de"}, headers=h).status_code == 422
    assert client.put("/api/auth/me/lang", json={"lang": "en"}).status_code == 401


def test_language_of_a_file_profile_then_browser_then_ru():
    class U:
        lang = None

    class R:
        def __init__(self, value):
            self.headers = {"accept-language": value}

    u = U()
    assert user_lang(u, R("uz-Latn-UZ,uz;q=0.9,ru;q=0.8")) == "uz"
    assert user_lang(u, R("de-DE,de;q=0.9")) == "ru"
    assert user_lang(None, None) == "ru"
    u.lang = "en"
    assert user_lang(u, R("uz")) == "en"


def test_my_goods_excel_in_the_users_language_loads_back(db):
    store, chil, yunus, a, b = _world(db)
    offers = cabinet.store_offers(db, store)
    title, ru = _headers(stock_excel.export_offers(db, store, offers, with_cost=True))
    base = stock_excel.stock_import(db, store, store.owner, stock_excel.export_offers(db, store, offers, True),
                                    "goods.xlsx", False)
    assert title == "Мои товары" and ru[:3] == ["Код ALT", "Товар", "Категория"] and ru[-2:] == ["Закупка", "Наценка, %"]
    for lang, sheet, first in (("uz", "Mahsulotlarim", ["ALT kodi", "Mahsulot", "Kategoriya"]),
                               ("en", "My products", ["ALT code", "Product", "Category"])):
        content = stock_excel.export_offers(db, store, offers, with_cost=True, lang=lang)
        title, head = _headers(content)
        assert title == sheet and head[:3] == first
        # Words of the file are translated; branch names (typed by the seller) stay as they are
        assert not any(CYRILLIC.search(h) for h in head if h not in ("Чиланзар", "Юнусабад"))
        ws = load_workbook(io.BytesIO(content)).active
        row = [c.value for c in ws[2]]
        assert row[2] and not CYRILLIC.search(row[2])  # the category in the reader's language
        # The same file loads back as stock in any language: nothing changes
        plan = stock_excel.stock_import(db, store, store.owner, content, "goods.xlsx", False)
        assert plan["total"] == 0 and plan["unknown"] == 0 and plan["rows"] == base["rows"] > 0


def test_journal_excel_by_accept_language(client, db):
    store, chil, yunus, a, b = _world(db)
    _op(db, store, "receipt", {"offer_id": a.id, "branch_id": chil.id, "qty": 1})
    h = _auth(store.owner)
    r = client.get("/api/seller/stock/journal.xlsx", headers={**h, "Accept-Language": "en-US,en;q=0.9"})
    title, head = _headers(r.content)
    assert title == "Journal" and head[:3] == ["Date", "Type", "Product"]
    kinds = [c.value for c in load_workbook(io.BytesIO(r.content)).active["B"][1:]]
    assert "Receipt" in kinds
    # The profile's language wins over the browser's
    client.put("/api/auth/me/lang", json={"lang": "uz"}, headers=h)
    title, head = _headers(client.get("/api/seller/stock/journal.xlsx", headers={**h, "Accept-Language": "en"}).content)
    assert title == "Jurnal" and head[0] == "Sana"


def test_notifications_are_keys_and_params_not_sentences(client, db, world):
    """The reader's interface writes the text in the reader's language — not the language of who caused it."""
    shop, b1 = world["shop"], world["b1"]
    client.put("/api/auth/me/lang", json={"lang": "en"}, headers=_auth(b1))  # the buyer writes in English
    conv = chat.open_conversation(db, b1, "offer", world["offer"].id)
    chat.send_message(db, b1, conv.id, "Hello")
    n = _of(db, shop.owner)[0]
    assert n.kind == "message" and n.params["count"] == 1
    db.expire_all()
    item = client.get("/api/notifications", headers=_auth(shop.owner)).json()["items"][0]
    assert item["kind"] == "message"
    # No stored sentence in any language: only the key's parameters (the message text is the buyer's own)
    assert not any(isinstance(v, str) and CYRILLIC.search(v) for k, v in item["params"].items() if k != "text")
    assert db.scalar(select(Notification.id).where(Notification.user_id == b1.id)) is None
