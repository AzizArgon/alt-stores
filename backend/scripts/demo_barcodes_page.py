"""Phase 12.3: samples/demo/barcodes.html — the demo barcodes as pictures, to scan from a screen with a phone camera.

  cd backend
  .venv/Scripts/python.exe scripts/demo_barcodes_page.py

Reads the demo codes of Silicon Plus and Byte Market from the database (after seed_demo) and draws EAN-13 in SVG
by itself (no libraries, works offline). Adds a valid code bound nowhere ("Привязать штрихкод") and a misread one.
"""

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.models import Barcode, BarcodeCode, Offer, Store  # noqa: E402
from scripts.seed_demo import DEMO_UNKNOWN_CODE, demo_code  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "samples" / "demo" / "barcodes.html"
L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_bits(code: str) -> str:
    d = [int(c) for c in code]
    left = "".join((L if p == "L" else G)[x] for p, x in zip(PARITY[d[0]], d[1:7]))
    return "101" + left + "01010" + "".join(R[x] for x in d[7:]) + "101"


def svg(code: str) -> str:
    bits, w, h, quiet = ean13_bits(code), 2, 70, 11
    bars = "".join(f'<rect x="{(quiet + i) * w}" y="0" width="{w}" height="{h + (6 if i < 3 or 45 <= i < 50 or i >= 92 else 0)}"/>'
                   for i, b in enumerate(bits) if b == "1")
    width = (len(bits) + quiet * 2) * w
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h + 22}" width="{width}" height="{h + 22}">'
            f'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{bars}</g>'
            f'<text x="{width / 2}" y="{h + 19}" font-family="monospace" font-size="14" text-anchor="middle">{code}</text></svg>')


def main() -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        rows = db.execute(select(Barcode.code, Store.name, Offer.raw_name, Offer.product_id)
                          .join(Store, Barcode.store_id == Store.id).join(Offer, Barcode.offer_id == Offer.id)
                          .where(Barcode.is_demo.is_(True)).order_by(Barcode.code, Store.name)).all()
        status = {c.code: c.status for c in db.scalars(select(BarcodeCode))}
        from app.db.models import Product

        names = {p.id: p.normalized_name for p in db.scalars(select(Product).where(Product.id.in_({r[3] for r in rows})))}
    by_code: dict[str, list] = {}
    for code, store, _, pid in rows:
        by_code.setdefault(code, []).append((store, names.get(pid, "")))
    label = {"confirmed": "подтверждён (2 магазина)", "pending": "не подтверждён (1 магазин)", "conflict": "конфликт"}
    cards = []
    for code, items in by_code.items():
        who = "<br>".join(f"{html.escape(s)}: {html.escape(n)}" for s, n in items)
        cards.append(f'<figure class="c {status.get(code, "")}">{svg(code)}<figcaption><b>{label.get(status.get(code), "")}</b><br>{who}</figcaption></figure>')
    unknown = demo_code(DEMO_UNKNOWN_CODE)
    cards.append(f'<figure class="c">{svg(unknown)}<figcaption><b>не привязан нигде</b><br>для сцены «Привязать штрихкод»</figcaption></figure>')
    bad = unknown[:-1] + str((int(unknown[-1]) + 1) % 10)
    cards.append(f'<figure class="c"><p class="bad">{bad}</p><figcaption><b>ошибка контрольной цифры</b><br>ввести вручную: «код считан с ошибкой»</figcaption></figure>')
    OUT.write_text(f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Демо-штрихкоды ALT STORES</title>
<style>
body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#111}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}}
.c{{margin:0;padding:12px;border:1px solid #ddd;border-radius:8px}} .c svg{{max-width:100%;height:auto}}
.confirmed{{border-color:#0f7a55}} .conflict{{border-color:#c62828}} figcaption{{font-size:13px;margin-top:6px}}
.bad{{font:20px monospace;padding:28px 0;text-align:center}}
</style></head><body>
<h1>Демо-штрихкоды (только внутренние коды 290…, не совпадают с настоящими товарами)</h1>
<p>Откройте страницу на компьютере и наведите камеру телефона: «Кабинет → Сканирование → Сканировать камерой».</p>
<div class="g">{"".join(cards)}</div></body></html>
""", encoding="utf-8")
    print(f"{OUT} — {len(by_code)} codes")


if __name__ == "__main__":
    main()
