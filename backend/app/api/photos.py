"""Phase 14: photos — the seller's uploader (cards, offers, builds) and the admin section «Фото»."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import admin_only
from app.api.seller import _require_store, seller_only
from app.core import photo_standard as S
from app.db.database import get_db
from app.db.models import Photo, User
from app.services import photos as svc
from app.services.imaging import PhotoError

router = APIRouter(tags=["photos"])

OwnerType = str


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PhotoError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code in ("not_yours", "not_found") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code, {"code": f"photo_{e.code}", **e.params})


def _own_photo(db: Session, store, photo_id: int) -> Photo:
    p = db.get(Photo, photo_id)
    if p is None or p.store_id != store.id or p.owner_type not in svc.OWNERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {"code": "photo_not_found"})
    if p.owner_type == "product" and p.status == "published" and not svc.is_sole(db, store, p.owner_id):
        # A published card photo seen by other stores changes only through the admin ("Предложить другое фото")
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "photo_locked"})
    return p


@router.get("/seller/photos")
def list_photos(owner_type: OwnerType, owner_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _run(svc.check_owner, db, store, owner_type, owner_id)
    return svc.seller_view(db, store, owner_type, owner_id)


@router.post("/seller/photos", status_code=status.HTTP_201_CREATED)
async def upload_photo(owner_type: OwnerType = Form(...), owner_id: int = Form(...), file: UploadFile = File(...),
                       orig_w: int | None = Form(None), orig_h: int | None = Form(None),
                       user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """One file -> a draft in the standard (the seller sees it before "Сохранить"). The file name is not used."""
    store = _require_store(db, user)
    data = await file.read(S.MAX_BYTES + 1)
    p = _run(svc.upload, db, store, owner_type, owner_id, data, orig_w, orig_h)
    return svc.seller_out(p, store.id)


class AdjustIn(BaseModel):
    mode: str | None = Field(None, pattern="^(white|blur)$")
    zoom: float | None = Field(None, ge=0.3, le=4)
    ox: float | None = Field(None, ge=-0.5, le=0.5)
    oy: float | None = Field(None, ge=-0.5, le=0.5)
    rotate: int = Field(0, ge=0, le=3)  # quarter turns clockwise


@router.patch("/seller/photos/{photo_id}")
def adjust_photo(photo_id: int, data: AdjustIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    p = _own_photo(db, store, photo_id)
    return svc.seller_out(_run(svc.adjust, db, p, **data.model_dump()), store.id)


class SetIn(BaseModel):
    owner_type: OwnerType
    owner_id: int
    ids: list[int] = Field(default_factory=list, max_length=20)
    main_id: int | None = None
    rights: bool = False


@router.put("/seller/photos")
def save_photos(data: SetIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    return _run(svc.save_set, db, store, user, data.owner_type, data.owner_id, data.ids, data.main_id, data.rights)


# --- admin ---------------------------------------------------------------------------------------------------------------

@router.get("/admin/photos")
def review(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"items": svc.review_queue(db)}


class DecideIn(BaseModel):
    accept: bool
    reason: str | None = Field(None, max_length=300)
    main: bool = False


@router.post("/admin/photos/{photo_id}")
def decide(photo_id: int, data: DecideIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.decide, db, admin, photo_id, data.accept, data.reason, data.main)


@router.post("/admin/photos/{photo_id}/main")
def main_photo(photo_id: int, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.make_main, db, admin, photo_id)
