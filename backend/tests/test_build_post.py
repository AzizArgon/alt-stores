"""Phase 17.2: a build post is split by code (labels, markers, price, bargain, contacts), parts go cache -> rules ->
one AI request for the rest; the AI may be away (the draft has what the rules read)."""

import asyncio

import pytest
from sqlalchemy import select

from app.db.models import Build, ParseCache
from app.services import build_post, builds, importer
from tests.test_builds import _card, _store, db, no_rate  # noqa: F401  (db and no_rate are fixtures)

POST = """⚡️ Игровой ПК | RTX 3070 Ti + i5-12400F | Корпус-аквариум
Красивая и производительная сборка. Тянет CS2, Dota 2, Warzone, Cyberpunk 2077 и любые тяжелые проекты без фризов.
🔸 CPU: Intel Core i5-12400F
🔸 GPU: RTX 3070 Ti Galax Duo
🔸 RAM: 16GB Kingston Fury (3600 MHz)
🔸 SSD: Samsung PM991 NVMe 512GB
🔸 MB: MSI H610
🔸 PSU: DeepCool 750W 80+ Bronze
🔸 Case: Zalman P30 (панорамное стекло, отличная продуваемость)
ПК обслужен, работает тихо и холодно. Готов к любым тестам при покупке.
Цена — 769$ небольшой торг
Тел: +998 90 123 45 67, пишите @age_computers
https://t.me/age_computers"""


@pytest.fixture
def cpu(db):
    return _card(db, "cpu", "Intel Core i5-12400F, 2.7 GHz, 18MB, OEM, LGA1700", {"socket": "LGA1700"}, "Intel")


@pytest.fixture
def ai(monkeypatch):
    """The AI answers recorded rows; every call is one request with all its rows."""
    calls, answers = [], {}

    async def parse_rows(rows, stats):
        calls.append([r.name for r in rows])
        return [{"row": r.row, "condition": "new", "specs": {}, "risks": [], **answers[r.name]}
                for r in rows if r.name in answers]

    monkeypatch.setattr(importer, "parse_rows", parse_rows)
    monkeypatch.setattr(builds, "ai_ready", lambda: True)
    return calls, answers


def _parse(db, text, ai=True):
    return asyncio.run(builds.parse_build_text(db, text, ai=ai))


def test_the_post_gives_seven_parts_price_name_and_no_contacts(db, cpu, ai):
    calls, _ = ai
    draft = _parse(db, POST)
    assert draft["name"] == "Игровой ПК RTX 3070 Ti + i5-12400F"
    assert (draft["price"], draft["currency"], draft["currency_check"], draft["bargain"]) == (769, "USD", False, True)
    assert (draft["condition"], draft["condition_check"], draft["purpose"]) == ("used", True, "gaming")
    got = {c["slot"]: c for c in draft["components"]}
    assert [c["slot"] for c in draft["components"]] == ["cpu", "motherboard", "ram", "gpu", "storage", "psu", "case"]
    assert got["cpu"]["level"] == "exact" and got["cpu"]["product"]["id"] == cpu.id
    assert got["gpu"]["specs"] == {"chip": "RTX 3070 Ti", "brand": "Galax"}
    assert got["ram"]["specs"] == {"capacity": 16, "frequency": 3600, "brand": "Kingston"}
    assert got["storage"]["specs"] == {"capacity": 512, "interface": "NVMe", "brand": "Samsung"}
    assert got["motherboard"]["specs"] == {"chipset": "H610", "brand": "MSI"}
    assert got["psu"]["specs"] == {"power": 750, "certification": "Bronze", "brand": "Deepcool"}
    assert got["case"]["raw_text"] == "Zalman P30" and got["case"]["specs"] == {"brand": "Zalman"}
    assert all("🔸" not in c["raw_text"] and "CPU" not in c["raw_text"] for c in draft["components"])
    assert calls == [] and draft["ai"] == "none" and draft["missing"] == []  # the rules read everything
    text = draft["description"]
    assert "панорамное стекло" in text and "Небольшой торг" in text and "обслужен" in text
    assert "769" not in text and "Цена" not in text and "CPU" not in text
    for contact in ("998", "@age", "t.me", "Тел"):
        assert contact not in text
    # The pasted post is kept without contacts
    components = [{"slot": c["slot"], "product_id": c["product"]["id"] if c["product"] else None,
                   "raw_text": c["raw_text"], "quantity": 1, "category": c["category"], "specs": c["specs"]}
                  for c in draft["components"]]
    build = builds.save_build(db, _store(db, "s@example.com"), {
        "name": draft["name"], "price": 769, "currency": "USD", "condition": "used", "purpose": "gaming",
        "description": text, "components": components, "text": POST})
    saved = db.get(Build, build.id)
    assert "Zalman P30" in saved.text and all(c not in saved.text for c in ("998", "@age", "t.me"))


@pytest.mark.parametrize("line, price, currency", [
    ("Цена: 769$", 769, "USD"), ("$769", 769, "USD"), ("769 у.е.", 769, "USD"), ("Narxi: 650 $, kelishamiz", 650, "USD"),
    ("8 500 000 сум", 8_500_000, "UZS"), ("Цена 8.5 млн, торг уместен", 8_500_000, "UZS"),
])
def test_price_by_code_only(line, price, currency):
    post = build_post.split_post(f"ПК\nCPU: Ryzen 5 5600\n{line}")
    assert (post["price"], post["currency"]) == (price, currency)
    assert post["bargain"] == ("торг" in line or "kelish" in line)
    assert [p["text"] for p in post["parts"]] == ["Ryzen 5 5600"]


def test_variations_without_labels_slash_line_sums_and_plus(db, cpu, ai):
    calls, _ = ai
    # Without labels, one part per line
    draft = _parse(db, "Офисный ПК\n• i5-12400F\n• 16GB DDR4 3200\n• SSD 512GB\n• 500W\n• Встроенная графика\n"
                       "Цена: 4 200 000 сум")
    assert [(c["slot"], c["level"]) for c in draft["components"]] == [
        ("cpu", "exact"), ("ram", "specs"), ("gpu", "integrated"), ("storage", "specs"), ("psu", "specs")]
    assert (draft["price"], draft["currency"], draft["purpose"], draft["name"]) == (4_200_000, "UZS", "office", "Офисный ПК")
    # Everything in one line through "/"
    draft = _parse(db, "Игровой ПК\nRyzen 5 5600 / B550M / 16GB DDR4 / RTX 3060 12GB / SSD 1TB / 650W\n650$")
    assert [c["slot"] for c in draft["components"]] == ["cpu", "motherboard", "ram", "gpu", "storage", "psu"]
    # "+" between parts, in the title line; "80+ Gold" is not split
    draft = _parse(db, "ПК i5-12400F + RTX 4060 + 32GB DDR5 — 900$\nБлок питания: 650W 80+ Gold")
    assert [c["raw_text"] for c in draft["components"]] == ["650W 80+ Gold"]
    post = build_post.split_post("i5-12400F + RTX 4060 + 32GB DDR5 + 1TB NVMe\n900$")
    assert [p["text"] for p in post["parts"]] == ["i5-12400F", "RTX 4060", "32GB DDR5", "1TB NVMe"]
    # A labeled part with two drives; the "advantages" block repeating parts in words is description
    post = build_post.split_post("ПК\n• Процессор: Ryzen 7 9800X3D\n• SSD: Lexar NM620 256 GB + Lexar NM610 1 TB\n"
                                 "Преимущества:\n• Мощный игровой процессор Ryzen 7 9800X3D\n1000$")
    assert [(p["slot"], p["text"]) for p in post["parts"]] == [
        ("cpu", "Ryzen 7 9800X3D"), ("storage", "Lexar NM620 256 GB"), ("storage", "Lexar NM610 1 TB")]
    assert post["description"] == "Мощный игровой процессор Ryzen 7 9800X3D"
    # Uzbek labels and a quantity
    post = build_post.split_post("Kompyuter\nProtsessor: i3-12100F\nVideokarta - GTX 1650\nOperativ xotira: 2x8GB DDR4\n"
                                 "Narxi 3 900 000 so'm")
    assert [(p["slot"], p["quantity"]) for p in post["parts"]] == [("cpu", 1), ("gpu", 1), ("ram", 2)]
    assert calls == []


def test_parts_rules_did_not_read_go_to_the_ai_in_one_request(db, cpu, ai):
    calls, answers = ai
    answers["Huananzhi QD4"] = {"category": "motherboard", "brand": "Huananzhi", "model": "QD4", "name": "Huananzhi QD4"}
    answers["Fractal North"] = {"category": "case", "brand": "Fractal", "model": "North", "name": "Fractal North"}
    text = "ПК\nCPU: i5-12400F\nМатеринка: Huananzhi QD4\nКорпус: Fractal North\nGPU: RTX 4060\n700$"
    rules_only = _parse(db, text, ai=False)
    assert rules_only["ai"] == "skipped" and rules_only["ai_pending"] == 2 and rules_only["parts_total"] == 4
    assert calls == []
    draft = _parse(db, text)
    assert calls == [["Huananzhi QD4", "Fractal North"]]  # one request for the whole build, not one per part
    got = {c["slot"]: c for c in draft["components"]}
    assert got["motherboard"]["specs"] == {"brand": "Huananzhi"} and got["motherboard"]["source"] == "ai"
    assert got["cpu"]["source"] == "rule" and draft["ai"] == "done"
    # Next time the answers come from the cache: no request at all
    assert db.scalar(select(ParseCache).where(ParseCache.key == "huananzhi qd4")) is not None
    draft = _parse(db, text)
    assert len(calls) == 1 and {c["source"] for c in draft["components"]} == {"rule", "cache"}


def test_without_the_ai_the_rules_result_comes_at_once(db, cpu, ai, monkeypatch):
    calls, _ = ai
    text = "ПК\nCPU: i5-12400F\nМатеринка: Huananzhi QD4\nGPU: RTX 4060\n700$"

    async def broken(rows, stats):
        calls.append([r.name for r in rows])
        raise RuntimeError("quota")

    monkeypatch.setattr(importer, "parse_rows", broken)
    draft = _parse(db, text)
    assert draft["ai"] == "failed" and len(draft["components"]) == 3
    assert {c["slot"]: c["level"] for c in draft["components"]} == {"cpu": "exact", "motherboard": "none", "gpu": "specs"}

    async def slow(rows, stats):
        await asyncio.sleep(5)

    monkeypatch.setattr(importer, "parse_rows", slow)
    monkeypatch.setattr(builds.settings, "build_ai_seconds", 0.05)
    assert _parse(db, text)["ai"] == "failed"  # the time limit, not minutes of retries
    monkeypatch.setattr(builds, "ai_ready", lambda: False)
    assert _parse(db, text)["ai"] == "off"


def test_contacts_are_cut_out_prices_stay():
    text = build_post.strip_contacts("Цена 8 500 000 сум\nЗвоните: +998 (90) 123-45-67\nпишите @shop_uz\n"
                                     "Канал t.me/shop_uz https://instagram.com/x\nRTX 3060 12GB")
    assert text == "Цена 8 500 000 сум\nКанал\nRTX 3060 12GB"
