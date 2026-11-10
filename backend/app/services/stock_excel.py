"""Excel both ways (phase 12.2): "My goods" and the journal to a plain .xlsx, stock back from the same file.

The export of "My goods" is the format of the stock import: the column "Код ALT" (offer id) finds the offer exactly,
the branch columns are named as the branches (a remembered column header of 12.1 is understood too). A number in a
branch column sets that quantity; "+", text and empty cells change nothing. So an exported file uploaded back
changes nothing. The file loads as a price list too (the columns have the usual headers: Товар, Цена, Наличие).
"""

import io
import re
from datetime import datetime, timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Offer, Store, User
from app.services.branches import store_branches
from app.services.stock import StockError, journal, move

ID_HEADER = "Код ALT"
BARCODE_HEADERS = ("штрихкод", "штрих-код", "штрихкоды", "barcode", "ean")
CONDITIONS = {"new": "новый", "used": "б/у", "refurbished": "восстановленный", "new_openbox": "новый, вскрыт",
              "unknown": "не указано"}
KIND_TEXT = {
    "initial": "Начальный остаток", "receipt": "Приход", "sale": "Продажа", "adjust": "Корректировка",
    "reserve": "Резерв брони", "unreserve": "Снятие резерва", "res_sale": "Продажа по брони",
    "import": "Импорт остатков", "undo": "Отмена загрузки", "manual": "Ручная правка",
}
REASON_TEXT = {"inventory": "инвентаризация", "defect": "брак", "loss": "потеря", "other": "другое"}


def _branch_title(b) -> str:
    return b.name or b.address


def _book(headers: list[str], rows: list[list], title: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(r)
    for i, h in enumerate(headers, 1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:200] if r[i - 1] is not None])
        ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, max(8, width + 2))
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_offers(db: Session, store: Store, offers: list[Offer], with_cost: bool) -> bytes:
    from app.services.cabinet import markup

    branches = store_branches(db, store.id)
    headers = [ID_HEADER, "Товар", "Категория", "Бренд", "Модель", "Состояние", "Цена", "Валюта", "Штрихкод"]
    headers += [_branch_title(b) for b in branches] + ["Резерв", "Наличие"]
    if with_cost:
        headers += ["Закупка", "Наценка, %"]
    rows = []
    for o in offers:
        p = o.product
        stocks = {s.branch_id: s for s in o.stocks}
        row = [o.id, p.normalized_name, p.category.name if p.category else None, p.brand, p.model,
               CONDITIONS.get(o.condition.value, o.condition.value), o.price, o.currency.value,
               ", ".join(b.code for b in o.barcodes) or None]
        for b in branches:
            s = stocks.get(b.id)
            row.append(None if s is None else (s.quantity if s.quantity is not None else ("+" if s.in_stock else 0)))
        row += [sum(s.reserved or 0 for s in o.stocks), "да" if o.is_in_stock else "нет"]
        if with_cost:
            row += [o.cost_avg, markup(o)]
        rows.append(row)
    return _book(headers, rows, "Мои товары")


def export_journal(movements: list[dict]) -> bytes:
    headers = ["Дата", "Тип", "Товар", "Филиал", "Было", "Изменение", "Стало", "Резерв после", "Закупка",
               "Цена продажи", "Валюта", "Причина", "Комментарий", "Документ", "Бронь", "Загрузка"]
    rows = []
    for m in movements:
        at = m["at"].astimezone(timezone.utc).replace(tzinfo=None) if m["at"] else None
        change = m["delta"] if m["kind"] not in ("reserve", "unreserve") else m["reserved_delta"]
        rows.append([at, KIND_TEXT.get(m["kind"], m["kind"]), m["name"], m["branch"], m["before"], change,
                     m["after"], m["reserved_after"], m["cost"], m["price"], m["currency"],
                     REASON_TEXT.get(m["reason"]) if m["reason"] else None, m["comment"], m["doc"],
                     m["reservation_id"], m["import_id"]])
    return _book(headers, rows, "Журнал")


# --- stock back from Excel ------------------------------------------------------------------------------------------

def _norm(v) -> str:
    return str(v).strip().lower() if v is not None else ""


def _int(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and float(v).is_integer() and v >= 0:
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def read_stock_file(db: Session, store: Store, content: bytes) -> dict:
    """The rows of the file: {offer, branch: quantity}; the branch columns by name or remembered header."""
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise StockError("file")
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    branches = store_branches(db, store.id)
    by_header = {}
    for b in branches:
        for h in [_branch_title(b), b.name, *(b.columns_json or [])]:
            if h:
                by_header.setdefault(_norm(h), b.id)
    head_i = next((i for i, r in enumerate(rows[:30])
                   if any(_norm(c) in (_norm(ID_HEADER), "товар", "наименование", "название") for c in r)), None)
    if head_i is None:
        raise StockError("no_header")
    header = [_norm(c) for c in rows[head_i]]
    id_col = header.index(_norm(ID_HEADER)) if _norm(ID_HEADER) in header else None
    name_col = next((i for i, h in enumerate(header) if h in ("товар", "наименование", "название")), None)
    code_col = next((i for i, h in enumerate(header) if h in BARCODE_HEADERS), None)  # phase 12.3
    cols = {i: by_header[h] for i, h in enumerate(header) if h in by_header}
    if not cols and code_col is None:
        raise StockError("no_branches")
    offers = list(db.scalars(select(Offer).where(Offer.store_id == store.id)))
    by_id = {o.id: o for o in offers}
    by_name = {}
    for o in offers:
        for n in (o.product.normalized_name, o.raw_name):
            by_name.setdefault(_norm(n), o)
    from app.services.barcodes import BarcodeError, normalize, store_binding

    items, unknown, codes = [], 0, []
    for r in rows[head_i + 1:]:
        if not any(c is not None and str(c).strip() for c in r):
            continue
        offer = None
        if id_col is not None and id_col < len(r):
            offer = by_id.get(_int(r[id_col]))
        if offer is None and name_col is not None and name_col < len(r):
            offer = by_name.get(_norm(r[name_col]))
        cell = r[code_col] if code_col is not None and code_col < len(r) else None
        if offer is None and cell is not None:  # a file of the warehouse with only barcodes and quantities
            try:
                own = store_binding(db, store, normalize(cell))
                offer = by_id.get(own.offer_id) if own is not None else None
            except BarcodeError:
                pass
        if offer is None:
            unknown += 1
            continue
        if cell is not None and str(cell).strip():
            codes.append((offer, cell))
        values = {bid: _int(r[i]) for i, bid in cols.items() if i < len(r) and _int(r[i]) is not None}
        if values:
            items.append((offer, values))
    return {"items": items, "unknown": unknown, "columns": sorted({bid for bid in cols.values()}), "codes": codes}


def stock_import(db: Session, store: Store, user: User, content: bytes, filename: str, apply: bool) -> dict:
    """"Загрузить остатки из Excel": only quantities (no prices). apply=False — the summary by branch."""
    if store.stock_mode != "stock":
        raise StockError("mode_off")
    data = read_stock_file(db, store, content)
    branches = {b.id: b for b in store_branches(db, store.id)}
    summary = {bid: {"branch_id": bid, "name": _branch_title(branches[bid]), "changed": 0, "plus": 0, "minus": 0}
               for bid in data["columns"]}
    changes = []
    for offer, values in data["items"]:
        stocks = {s.branch_id: s for s in offer.stocks}
        for bid, q in values.items():
            old = stocks[bid].quantity if bid in stocks else None
            if old == q:
                continue
            summary[bid]["changed"] += 1
            diff = q - (old or 0)
            summary[bid]["plus" if diff > 0 else "minus"] += abs(diff)
            changes.append({"offer_id": offer.id, "name": offer.product.normalized_name, "branch_id": bid,
                            "branch": summary[bid]["name"], "before": old, "after": q})
    if apply and changes:
        with journal("import", user_id=user.id, comment=filename[:300]):
            for c in changes:
                move(db.get(Offer, c["offer_id"]), c["branch_id"], "import", set_to=c["after"])
        db.commit()
    new_codes = _new_codes(db, store, data["codes"])
    if apply and new_codes:
        from app.services.barcodes import bind_many

        bind_many(db, store, new_codes, user_id=user.id, source="import")
    return {"barcodes": len(new_codes), "branches": list(summary.values()), "changes": changes[:100], "total": len(changes),
            "rows": len(data["items"]), "unknown": data["unknown"], "applied": apply and bool(changes or new_codes)}


def _new_codes(db: Session, store: Store, pairs: list) -> list:
    """The barcode cells that would bind something new (a valid code not yet bound in this store)."""
    from app.services.barcodes import BarcodeError, normalize, store_binding

    out = []
    for offer, cell in pairs:
        for raw in re.split(r"[,;\s]+", str(int(cell)) if isinstance(cell, float) and cell.is_integer() else str(cell)):
            try:
                if raw and store_binding(db, store, normalize(raw)) is None:
                    out.append((offer, raw))
            except BarcodeError:
                pass
    return out


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
