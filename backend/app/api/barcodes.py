"""Phase 12.3: barcodes of the seller's cabinet — a scan (lookup), binding a code to an offer, removing it."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.seller import _require_store, seller_only
from app.api.stock import scan_offer
from app.db.database import get_db
from app.db.models import Offer, User
from app.services import barcodes

router = APIRouter(prefix="/seller/barcodes", tags=["barcodes"])


def _err(e: barcodes.BarcodeError, code=status.HTTP_422_UNPROCESSABLE_ENTITY):
    raise HTTPException(status.HTTP_409_CONFLICT if e.code == "taken" else code, {"code": e.code, **e.params})


@router.get("/lookup")
def lookup(code: str = Query(..., max_length=64), user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """A scanned code: {status: found, offer} / {status: unknown, suggestion}; a wrong code — 422 checksum/format."""
    store = _require_store(db, user)
    try:
        res = barcodes.lookup(db, store, code)
    except barcodes.BarcodeError as e:
        _err(e)
    if res["status"] == "found":
        res["offer"] = scan_offer(db.get(Offer, res.pop("offer_id")))
    return res


class BindIn(BaseModel):
    code: str = Field(max_length=64)
    offer_id: int
    source: str = "manual"  # manual (the editor) / scan ("Привязать штрихкод")


@router.post("", status_code=status.HTTP_201_CREATED)
def bind(data: BindIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    offer = db.get(Offer, data.offer_id)
    try:
        b = barcodes.bind(db, store, offer, data.code, user_id=user.id, source=data.source)
    except barcodes.BarcodeError as e:
        _err(e)
    db.refresh(offer)
    return {"id": b.id, "code": b.code, "offer": scan_offer(offer), "barcodes": barcodes.codes(offer)}


@router.delete("/{barcode_id}")
def unbind(barcode_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    try:
        barcodes.unbind(db, _require_store(db, user), barcode_id)
    except barcodes.BarcodeError as e:
        _err(e, status.HTTP_404_NOT_FOUND)
    return {"ok": True}
