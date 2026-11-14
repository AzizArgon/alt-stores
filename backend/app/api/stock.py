"""Phase 12.2: "Склад" of the seller's cabinet — the store's mode, receipt / sale / adjustment, the journal,
Excel export of "My goods" and of the journal, stock back from Excel. Only the seller; never the storefront."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.seller import MAX_FILE_SIZE, _require_store, seller_only
from app.core.i18n import user_lang
from app.db.database import get_db
from app.db.models import Offer, Product, User
from app.schemas.seller import OfferFilter
from app.services import barcodes, cabinet, stock, stock_excel, warehouse
from app.services.branches import seller_stocks

router = APIRouter(prefix="/seller/stock", tags=["stock"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ModeIn(BaseModel):
    mode: Literal["price", "stock"]


class LineIn(BaseModel):
    offer_id: int
    branch_id: int
    qty: int = Field(ge=0, le=1_000_000)
    cost: float | None = Field(default=None, ge=0)  # receipt: purchase price (offer currency)
    price: float | None = Field(default=None, ge=0)  # sale: the price (default the current one)
    reason: str | None = None  # adjust: inventory / defect / loss / other; return: defect / changed_mind / other
    comment: str | None = Field(default=None, max_length=300)
    restock: bool = True  # return: False = a defective item is not put back into the stock


class OperationIn(BaseModel):
    kind: Literal["receipt", "sale", "adjust", "move", "return"]
    lines: list[LineIn] = Field(min_length=1, max_length=200)
    scan: bool = False  # a price-only store changes its stock as a hand edit (12.3)
    confirm: bool = False  # sale: "товар забронирован — продать всё равно?" answered yes (12.4)


def _err(e: stock.StockError):
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": e.code, **e.params})


@router.get("/mode")
def mode_preview(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    return {"mode": store.stock_mode, "low_stock": store.low_stock, **stock.mode_preview(db, store)}


@router.post("/mode")
def set_mode(data: ModeIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Учёт остатков": the current quantities become the opening balance; back to "Только прайс" any time."""
    try:
        return stock.set_mode(db, _require_store(db, user), data.mode, user)
    except stock.StockError as e:
        _err(e)


class SettingsIn(BaseModel):
    low_stock: int = Field(ge=0, le=1000)


@router.put("/settings")
def save_settings(data: SettingsIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    store.low_stock = data.low_stock
    db.commit()
    return {"low_stock": store.low_stock}


class WarehouseIn(BaseModel):
    on: bool
    action: Literal["move", "write_off"] | None = None  # switched off with stock: to a branch or written off
    branch_id: int | None = None


@router.get("/warehouse")
def warehouse_state(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Before switching the warehouse off: how much stock is there."""
    store = _require_store(db, user)
    rows = warehouse.warehouse_rows(db, store)
    return {"has_warehouse": store.has_warehouse, "positions": len(rows), "units": sum(r.quantity for r, _ in rows)}


@router.post("/warehouse")
def set_warehouse(data: WarehouseIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Phase 12.4: "Есть отдельный склад" on / off (the stock of the warehouse goes through the journal)."""
    try:
        return warehouse.set_warehouse(db, _require_store(db, user), data.on, user, data.action, data.branch_id)
    except stock.StockError as e:
        db.rollback()
        _err(e)


class StocktakeIn(BaseModel):
    branch_id: int
    categories: list[str] = Field(default_factory=list, max_length=50)


class CountIn(BaseModel):
    offer_id: int
    delta: int | None = Field(default=1, ge=-1000, le=1000)
    set: int | None = Field(default=None, ge=0, le=1_000_000)


class ExcludeIn(BaseModel):
    offer_id: int
    excluded: bool = True


def _st(fn, *args):
    try:
        return fn(*args)
    except stock.StockError as e:
        db = args[0]
        db.rollback()
        _err(e)


@router.get("/stocktakes")
def stocktakes(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Phase 12.4 "Ревизия": the unfinished ones and the history with results."""
    return warehouse.list_stocktakes(db, _require_store(db, user))


@router.post("/stocktakes", status_code=status.HTTP_201_CREATED)
def start_stocktake(data: StocktakeIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    st = _st(warehouse.start, db, store, user, data.branch_id, data.categories)
    return warehouse.stocktake_out(db, store, st)


@router.get("/stocktakes/{stocktake_id}")
def get_stocktake(stocktake_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    return warehouse.stocktake_out(db, store, _st(warehouse.get, db, store, stocktake_id))


@router.post("/stocktakes/{stocktake_id}/count")
def count_stocktake(stocktake_id: int, data: CountIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    st = _st(warehouse.get, db, store, stocktake_id)
    st = _st(warehouse.count, db, store, st, data.offer_id, data.delta, data.set)
    return warehouse.stocktake_out(db, store, st)


@router.post("/stocktakes/{stocktake_id}/{action}")
def stocktake_action(stocktake_id: int, action: Literal["finish", "resume", "apply"], user: User = Depends(seller_only),
                     db: Session = Depends(get_db)):
    store = _require_store(db, user)
    st = _st(warehouse.get, db, store, stocktake_id)
    if action == "finish":
        st = _st(warehouse.finish, db, store, st)
    elif action == "resume":
        st = _st(warehouse.resume, db, st)
    else:
        st = _st(warehouse.apply, db, store, st, user)
    return warehouse.stocktake_out(db, store, st)


@router.put("/stocktakes/{stocktake_id}/exclude")
def stocktake_exclude(stocktake_id: int, data: ExcludeIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    st = _st(warehouse.get, db, store, stocktake_id)
    return warehouse.stocktake_out(db, store, _st(warehouse.exclude, db, st, data.offer_id, data.excluded))


@router.delete("/stocktakes/{stocktake_id}")
def cancel_stocktake(stocktake_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _st(warehouse.cancel, db, _st(warehouse.get, db, store, stocktake_id))
    return {"ok": True}


@router.post("/operations")
def operate(data: OperationIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """A receipt, a sale or an adjustment document: all lines or none."""
    try:
        return stock.operate(db, _require_store(db, user), user, data.kind, [line.model_dump() for line in data.lines],
                             data.scan, data.confirm)
    except stock.StockError as e:
        _err(e)


def scan_offer(o: Offer) -> dict:
    """An offer as the goods input, "Сканирование" and "Найти" show it (only the seller)."""
    return {"id": o.id, "name": o.product.normalized_name, "raw_name": o.raw_name, "price": o.price,
            "currency": o.currency.value, "cost_last": o.cost_last, "cost_avg": o.cost_avg,
            "category": o.product.category.slug if o.product.category else "other", "product_id": o.product_id,
            "is_in_stock": o.is_in_stock, "stocks": seller_stocks(o), "barcodes": [b.code for b in o.barcodes]}


@router.get("/search")
def search(q: str = Query("", max_length=200), user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """The goods input of the operations: by name, the seller's line, the code or the store's barcode (12.3)."""
    store = _require_store(db, user)
    q = q.strip()
    if not q:
        return []
    cond = [Product.normalized_name.ilike(f"%{q}%"), Offer.raw_name.ilike(f"%{q}%")]
    if q.isdigit():
        cond.append(Offer.id == int(q))
    try:
        own = barcodes.store_binding(db, store, barcodes.normalize(q))
    except barcodes.BarcodeError:
        own = None
    if own is not None:
        cond.append(Offer.id == own.offer_id)
    offers = db.scalars(select(Offer).join(Product, Offer.product_id == Product.id).where(
        Offer.store_id == store.id, Offer.removed_at.is_(None), or_(*cond)).order_by(Product.normalized_name)
        .limit(15)).all()
    first = own.offer_id if own is not None else (int(q) if q.isdigit() else None)
    if first is not None:
        offers.sort(key=lambda o: o.id != first)
    return [scan_offer(o) for o in offers]


@router.get("/journal")
def journal(offer_id: int | None = None, branch_id: int | None = None, kind: str | None = Query(None, max_length=100),
            date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1),
            doc: str | None = Query(None, max_length=24), user: User = Depends(seller_only), db: Session = Depends(get_db)):
    f = {"offer_id": offer_id, "branch_id": branch_id, "kind": kind, "date_from": date_from, "date_to": date_to,
         "doc": doc}
    return stock.list_journal(db, _require_store(db, user), f, page)


def _xlsx(content: bytes, name: str) -> Response:
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/journal.xlsx")
def journal_xlsx(request: Request, offer_id: int | None = None, branch_id: int | None = None,
                 kind: str | None = Query(None, max_length=100), date_from: date | None = None,
                 date_to: date | None = None, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    f = {"offer_id": offer_id, "branch_id": branch_id, "kind": kind, "date_from": date_from, "date_to": date_to}
    rows = stock.all_movements(db, _require_store(db, user), f)
    return _xlsx(stock_excel.export_journal(rows, user_lang(user, request)), f"journal_{stock_excel.stamp()}.xlsx")


@router.get("/offers.xlsx")
def offers_xlsx(request: Request, f: OfferFilter = Depends(), cost: bool = False, user: User = Depends(seller_only),
                db: Session = Depends(get_db)):
    """"Скачать в Excel" of "My goods" with the current filters; the same columns load back as stock."""
    store = _require_store(db, user)
    offers = [o for o, _ in cabinet.filtered_offers(db, store, f.model_dump())]
    offers.sort(key=lambda o: o.product.normalized_name.lower())
    return _xlsx(stock_excel.export_offers(db, store, offers, cost, user_lang(user, request)), f"goods_{stock_excel.stamp()}.xlsx")


@router.post("/import")
async def import_stock(file: UploadFile = File(...), apply: bool = Form(False), user: User = Depends(seller_only),
                       db: Session = Depends(get_db)):
    """"Загрузить остатки из Excel": only quantities; apply=false — "что изменится" by branch."""
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"code": "too_big"})
    try:
        return stock_excel.stock_import(db, _require_store(db, user), user, content, file.filename or "", apply)
    except stock.StockError as e:
        _err(e)
