"""Phase 12.2: "Склад" of the seller's cabinet — the store's mode, receipt / sale / adjustment, the journal,
Excel export of "My goods" and of the journal, stock back from Excel. Only the seller; never the storefront."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.seller import MAX_FILE_SIZE, _require_store, seller_only
from app.db.database import get_db
from app.db.models import Offer, Product, User
from app.schemas.seller import OfferFilter
from app.services import cabinet, stock, stock_excel
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
    reason: str | None = None  # adjust: inventory / defect / loss / other
    comment: str | None = Field(default=None, max_length=300)


class OperationIn(BaseModel):
    kind: Literal["receipt", "sale", "adjust"]
    lines: list[LineIn] = Field(min_length=1, max_length=200)


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


@router.post("/operations")
def operate(data: OperationIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """A receipt, a sale or an adjustment document: all lines or none."""
    try:
        return stock.operate(db, _require_store(db, user), user, data.kind, [line.model_dump() for line in data.lines])
    except stock.StockError as e:
        _err(e)


@router.get("/search")
def search(q: str = Query("", max_length=200), user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """The goods input of the operations: by name, the seller's line or the code (12.3 adds the barcode here)."""
    store = _require_store(db, user)
    q = q.strip()
    if not q:
        return []
    cond = [Product.normalized_name.ilike(f"%{q}%"), Offer.raw_name.ilike(f"%{q}%")]
    if q.isdigit():
        cond.append(Offer.id == int(q))
    offers = db.scalars(select(Offer).join(Product, Offer.product_id == Product.id).where(
        Offer.store_id == store.id, Offer.removed_at.is_(None), or_(*cond)).order_by(Product.normalized_name)
        .limit(15)).all()
    if q.isdigit():
        offers.sort(key=lambda o: o.id != int(q))
    return [{"id": o.id, "name": o.product.normalized_name, "raw_name": o.raw_name, "price": o.price,
             "currency": o.currency.value, "cost_last": o.cost_last, "stocks": seller_stocks(o)} for o in offers]


@router.get("/journal")
def journal(offer_id: int | None = None, branch_id: int | None = None, kind: str | None = Query(None, max_length=100),
            date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1),
            user: User = Depends(seller_only), db: Session = Depends(get_db)):
    f = {"offer_id": offer_id, "branch_id": branch_id, "kind": kind, "date_from": date_from, "date_to": date_to}
    return stock.list_journal(db, _require_store(db, user), f, page)


def _xlsx(content: bytes, name: str) -> Response:
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/journal.xlsx")
def journal_xlsx(offer_id: int | None = None, branch_id: int | None = None,
                 kind: str | None = Query(None, max_length=100), date_from: date | None = None,
                 date_to: date | None = None, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    f = {"offer_id": offer_id, "branch_id": branch_id, "kind": kind, "date_from": date_from, "date_to": date_to}
    rows = stock.all_movements(db, _require_store(db, user), f)
    return _xlsx(stock_excel.export_journal(rows), f"journal_{stock_excel.stamp()}.xlsx")


@router.get("/offers.xlsx")
def offers_xlsx(f: OfferFilter = Depends(), cost: bool = False, user: User = Depends(seller_only),
                db: Session = Depends(get_db)):
    """"Скачать в Excel" of "My goods" with the current filters; the same columns load back as stock."""
    store = _require_store(db, user)
    offers = [o for o, _ in cabinet.filtered_offers(db, store, f.model_dump())]
    offers.sort(key=lambda o: o.product.normalized_name.lower())
    return _xlsx(stock_excel.export_offers(db, store, offers, cost), f"goods_{stock_excel.stamp()}.xlsx")


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
