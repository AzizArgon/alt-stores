"""Phase 9, part B: ads of Telegram channels from the recorded t.me/s pages (no network, no AI)."""

import asyncio
import re
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.db.models import Offer, Store, StoreKind, TgChannel, TgPost, User, utcnow
from app.services import telegram
from app.services.catalog import product_card, search_products, used_offers
from app.services.importer import _preview_row
from app.services.market import market_data, product_market
from tests.test_publish import _import, _row, _store, db  # noqa: F401  (db is a fixture)

PAGE1 = (Path(__file__).parent / "fixtures" / "telegram" / "page1.html").read_text(encoding="utf-8")
GUESS = [  # what the cache/rules/AI would say about the names of the fixture posts
    (r"rtx 3060", {"category": "gpu", "brand": "MSI", "name": "MSI RTX 3060 Ventus 12GB"}),
    (r"kingston", {"category": "ram", "brand": "Kingston", "name": "Kingston Fury Beast DDR4 16GB 3200MHz"}),
    (r"ryzen", {"category": "cpu", "brand": "AMD", "name": "AMD Ryzen 5 5600"}),
]
PHONE_OR_NICK = re.compile(r"@\w|\+998|\d{2}-\d{3}-\d{2}-\d{2}|\d{3} \d{2} \d{2}|alisher", re.IGNORECASE)


async def fake_parse(db, rows, stats, *args, **kwargs):
    result = []
    for r in rows:
        guess = next((g for pattern, g in GUESS if re.search(pattern, r.raw_name, re.IGNORECASE)), None)
        result.append(_preview_row(r, guess, "rule" if guess else "failed"))
    return result


def _page(*changes, drop=()):
    """PAGE1 with edits: (old text, new text) pairs and posts removed from the feed."""
    html = PAGE1
    for old, new in changes:
        html = html.replace(old, new)
    for post_id in drop:
        html = re.sub(rf'<div class="tgme_widget_message_wrap[^>]*>\s*<div[^>]*data-post="test_parts/{post_id}".*?</div>\s*</div>\s*</div>\s*</div>\s*</div>',
                      "", html, flags=re.DOTALL)
    return html


def _run(db, html, budget=50):
    channel = db.scalar(select(TgChannel))
    return asyncio.run(telegram.run_channel(db, channel, budget, fetch=lambda *_: html, parse=fake_parse,
                                            pause=lambda: None))


@pytest.fixture
def channel(db, monkeypatch):
    # Recorded posts are from early November: "now" is right after them, so none is older than 30 days
    return telegram.add_channel(db, "@test_parts", "Б/у комплектующие (тест)", "tashkent")


def test_feed_parsing():
    posts = telegram.parse_feed(PAGE1)
    assert [p.id for p in posts] == [101, 102, 103, 104, 105]  # the service message is not a post
    first = posts[0]
    assert first.has_media and first.posted_at.isoformat() == "2026-11-05T10:15:00+00:00"
    assert first.text.splitlines()[0].strip().endswith("MSI RTX 3060 Ventus 12GB")
    assert "i9-14900K" not in posts[2].text  # the quoted reply is not the post's own text


def test_scrub_removes_phones_nicks_links_and_contact_lines():
    text = ("MSI RTX 3060 12GB 210$\nТел: +998 90 123 45 67 Алишер\nзвонить 90-765-43-21\n"
            "Цена 2 500 000 сум, пишите @alisher_pc или t.me/alisher_pc\nAdmin: Jasur")
    clean = telegram.scrub(text)
    assert "2 500 000" in clean and "210$" in clean
    assert not PHONE_OR_NICK.search(clean) and "Jasur" not in clean and "Алишер" not in clean


def test_sold_words_and_kits():
    assert telegram.SOLD.search("Сотилди✅") and telegram.SOLD.search("❌ПРОДАНО❌") and not telegram.SOLD.search("продаю")
    assert telegram.kit_reason("Asus B550M-K Argb\nR5 2600\n90 y.e", 1) == "bundle"
    assert telegram.kit_reason("CPU: i5-3470\nRAM: DDR3 8GB\nSSD 512GB\nGPU: GT 730\n104$", 1) == "build"
    assert telegram.kit_reason("Colorfire ddr5 16*2 6000 cl36\n420 y.e", 1) is None
    assert telegram.kit_reason("RTX 3060 200$\nRTX 3070 300$\ni5-12400F 100$", 3) is None  # a price list


def test_channel_store_is_a_telegram_seller_nobody_logs_in(db, channel):
    store = db.get(Store, channel.store_id)
    assert store.kind == StoreKind.telegram and not store.is_verified and store.city == "tashkent"
    assert not verify_password("anything", db.get(User, store.user_id).password_hash)
    with pytest.raises(ValueError):
        telegram.add_channel(db, "test_parts")


def test_run_publishes_ads_skips_the_rest_and_keeps_no_personal_data(db, channel):
    log = _run(db, PAGE1)
    assert (log.fetched, log.new, log.parsed) == (5, 5, 2)
    assert log.skipped == {"image_price": 1, "ad": 1, "sold": 1}
    assert channel.last_post_id == 105
    # Each ad post points at its own offer only (not at the offers of the posts before it)
    parsed = db.scalars(select(TgPost).where(TgPost.status == "parsed").order_by(TgPost.post_id)).all()
    assert [len(p.offer_ids) for p in parsed] == [1, 1] and parsed[0].offer_ids != parsed[1].offer_ids
    offers = {o.product.normalized_name: o for o in db.scalars(select(Offer))}
    gpu, ram = offers["MSI RTX 3060 Ventus 12GB"], offers["Kingston Fury Beast DDR4 16GB 3200MHz"]
    assert gpu.post_url == "https://t.me/test_parts/101" and gpu.condition.value == "used" and gpu.price == 210
    assert ram.condition.value == "new" and ram.currency.value == "UZS"
    # Privacy: nothing stored has a phone, a @name or the seller's name
    stored = [p.text for p in db.scalars(select(TgPost))] + [o.raw_name for o in offers.values()] + \
             [o.note or "" for o in offers.values()]
    assert not any(PHONE_OR_NICK.search(t) for t in stored)
    # The buyer sees the ad with "Open the post" and without contacts
    item = used_offers(db, 12_000)["items"][0]
    assert item["store"]["kind"] == "telegram" and item["store"]["phone"] is None and item["post_url"]


def test_second_run_takes_only_new_posts_and_does_not_duplicate(db, channel):
    _run(db, PAGE1)
    again = _run(db, PAGE1)
    assert again.new == 0 and again.parsed == 0
    assert db.scalar(select(TgPost).where(TgPost.post_id == 101)) is not None
    assert len(db.scalars(select(TgPost)).all()) == 5 and len(db.scalars(select(Offer)).all()) == 2


def test_republished_product_updates_the_ad(db, channel):
    _run(db, PAGE1)
    repost = PAGE1.replace("</section>", '''<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="test_parts/107">
    <div class="tgme_widget_message_text js-message_text">MSI RTX 3060 Ventus 12GB б/у — 195$</div>
    <span class="tgme_widget_message_meta"><a class="tgme_widget_message_date" href="https://t.me/test_parts/107"><time datetime="2026-11-08T09:00:00+00:00">09:00</time></a></span>
  </div>
</div></section>''')
    log = _run(db, repost)
    assert log.new == 1 and log.parsed == 1
    gpus = [o for o in db.scalars(select(Offer)) if "3060" in o.product.normalized_name]
    assert len(gpus) == 1 and gpus[0].price == 195 and gpus[0].post_url.endswith("/107")
    # The old post is gone now, but the ad belongs to the newer post: it stays
    _run(db, _page(drop=[101]).replace("</section>", repost[repost.index('<div class="tgme_widget_message_wrap js-widget_message_wrap">\n  <div class="tgme_widget_message js-widget_message" data-post="test_parts/107">'):]))
    assert gpus[0].removed_at is None


def test_edited_to_sold_and_gone_posts_take_the_ad_off(db, channel):
    _run(db, PAGE1)
    log = _run(db, _page(("Состояние: б/у, не майнила", "ПРОДАНО"), drop=[104]))
    assert (log.sold, log.gone) == (1, 1)
    assert used_offers(db, 12_000)["total"] == 0
    assert search_products(db, 12_000)["total"] == 0  # the new RAM ad is gone too
    assert {p.status for p in db.scalars(select(TgPost).where(TgPost.post_id.in_([101, 104])))} == {"sold", "gone"}


def test_old_posts_are_skipped_and_old_ads_expire(db, channel):
    long_ago = PAGE1.replace("2026-11-05T10:15:00+00:00", (utcnow() - timedelta(days=40)).isoformat())
    log = _run(db, long_ago)
    assert log.skipped.get("old") == 1 and log.parsed == 1
    ram = db.scalar(select(Offer))
    ram.posted_at = utcnow() - timedelta(days=31)
    db.commit()
    assert telegram.expire_old(db) == 1 and not ram.is_in_stock
    assert product_card(db, ram.product_id, 12_000)["offers"] == []


def test_budget_limits_posts_per_run(db, channel):
    log = _run(db, PAGE1, budget=2)
    assert log.new == 2 and channel.last_post_id == 102
    assert _run(db, PAGE1, budget=50).new == 3


def test_failed_ai_posts_are_retried(db, channel, monkeypatch):
    monkeypatch.setattr(telegram, "condition_of", telegram.condition_of)
    no_guess = GUESS.copy()
    GUESS.clear()
    try:
        log = _run(db, PAGE1)
    finally:
        GUESS.extend(no_guess)
    assert log.skipped.get("ai_failed") == 2 and db.scalar(select(Offer)) is None
    again = _run(db, PAGE1)
    assert again.parsed == 2 and len(db.scalars(select(Offer)).all()) == 2


def test_telegram_used_ads_are_not_in_the_new_market(db, channel):
    a, b = _store(db, "a@example.com"), _store(db, "b@example.com")
    from app.services.importer import publish_import

    gpu = {**_row(1, "MSI RTX 3060 Ventus 12GB", 300), "category": "gpu", "brand": "MSI"}
    publish_import(db, _import(db, a), a, [gpu])
    publish_import(db, _import(db, b), b, [{**gpu, "price": 320}])
    _run(db, PAGE1)
    pid = db.scalar(select(Offer).where(Offer.store_id == channel.store_id, Offer.post_url.like("%/101"))).product_id
    market = product_market(db, pid)
    assert market["conditions"]["new"]["stores"] == 2 and market["conditions"]["new"]["ads"] == 0
    assert market["conditions"]["used"]["ads"] == 1
    md = market_data(db)
    assert md.now((pid, "new")) == 310
