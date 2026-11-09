"""Phase 11: reservations. The buyer makes and cancels them; the store moves them on and cancels with a reason."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services import reservations as svc
from app.services.exchange import get_usd_rate

router = APIRouter(prefix="/reservations", tags=["reservations"])


class ReservationIn(BaseModel):
    kind: str = Field(pattern="^(offer|build)$")
    item_id: int
    name: str = Field("", max_length=200)
    phone: str = Field("", max_length=40)
    contact: str = "call"
    telegram: str | None = Field(None, max_length=64)
    quantity: int = 1
    pickup_date: str | None = Field(None, max_length=10)
    pickup_time: str | None = Field(None, max_length=5)
    # Longer comments are refused with a clear code (reservation.error.comment), not cut
    comment: str | None = Field(None, max_length=svc.MAX_COMMENT * 2)


class CancelIn(BaseModel):
    reason: str | None = None
    text: str | None = Field(None, max_length=400)


def _rate(db: Session) -> float | None:
    rate = get_usd_rate(db)
    return rate.rate if rate else None


def _do(fn, *args):
    try:
        return fn(*args)
    except svc.ReservationError as e:
        raise HTTPException(e.status, {"code": e.code})


@router.get("/contacts")
def contacts(user: User = Depends(get_current_user)):
    """The buyer's name, phone and Telegram from the last reservation: filled in the next form."""
    return svc.contacts_of(user)


@router.get("/unseen")
def unseen(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": svc.unseen_count(db, user)}


@router.get("")
def my_reservations(done: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The buyer's own: active (new, confirmed, ready) or finished."""
    return svc.list_for_buyer(db, user, _rate(db), done)


@router.post("", status_code=201)
def create(data: ReservationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _do(svc.create, db, user, data.model_dump())
    return svc.out(db, r, "buyer", _rate(db))


@router.get("/store")
def store_reservations(status: str = Query("all", max_length=16), q: str = Query("", max_length=100),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _do(svc.list_for_store, db, user, _rate(db), status, q)


@router.get("/store/counts")
def store_counts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The cabinet's counter: new reservations and the ones ending today."""
    return svc.store_counts(db, _do(svc._store_of, db, user))


@router.get("/{res_id}")
def one(res_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    side, r = _do(svc.get_for, db, user, res_id)
    return svc.out(db, r, side, _rate(db))


@router.post("/{res_id}/advance")
def advance(res_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _do(svc.advance, db, user, res_id)
    return svc.out(db, r, "store", _rate(db))


@router.post("/{res_id}/cancel")
def cancel(res_id: int, data: CancelIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _do(svc.cancel, db, user, res_id, data.reason, data.text)
    return svc.out(db, r, r.cancelled_by, _rate(db))
