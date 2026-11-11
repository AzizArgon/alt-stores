"""Phase 12.5: the bell — the same routes for a buyer, a seller and the admin (each sees only his own)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(type: str | None = None, limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_for(db, user, type, limit, offset)


@router.get("/unread")
def unread(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": svc.unread_count(db, user)}


@router.post("/{notification_id}/read")
def read_one(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not svc.mark_read(db, user, notification_id):
        raise HTTPException(404, detail={"code": "not_found"})
    return {"ok": True}


@router.post("/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": svc.mark_all(db, user)}
