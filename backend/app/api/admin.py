"""The admin panel API (phase 13): every route needs the admin role; a seller or a buyer gets 403.

There is no admin registration on the site: scripts/create_admin.py makes one (the password only in a terminal).
"""

from datetime import date

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, blocked_error
from app.core.limits import SlidingWindow, client_ip, too_many
from app.core.security import create_access_token, verify_password
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import TokenResponse, UserOut
from app.services import admin as svc
from app.services.admin import AdminError

router = APIRouter(prefix="/admin", tags=["admin"])
public = APIRouter(prefix="/admin", tags=["admin"])

# Login attempts of the admin entrance: always limited (also locally), by IP and by email
ADMIN_MAX_FAILURES, ADMIN_WINDOW_MINUTES = 5, 15
admin_failures = SlidingWindow()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


def admin_door_check(ip: str, email: str) -> None:
    """The admin limit (phase 13), kept by the one login (phase 16.3): 5 failures per IP or email = locked 15 min."""
    window = ADMIN_WINDOW_MINUTES * 60
    if max(admin_failures.count(f"ip:{ip}", window), admin_failures.count(f"email:{email}", window)) >= ADMIN_MAX_FAILURES:
        raise too_many("too_many_logins", minutes=ADMIN_WINDOW_MINUTES)


def admin_door_failed(db: Session, user: User | None, ip: str, email: str) -> None:
    admin_failures.hit(f"ip:{ip}")
    admin_failures.hit(f"email:{email}")
    if user is not None and user.role == UserRole.admin:
        svc.log(db, user, "login_failed", "user", user.id, user.email, ip=ip)
        db.commit()


def admin_door_passed(db: Session, user: User, ip: str) -> None:
    svc.log(db, user, "login_admin", "user", user.id, user.email, ip=ip)
    db.commit()


@public.post("/login", response_model=TokenResponse)
def admin_login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip, email = client_ip(request), data.email.lower()
    admin_door_check(ip, email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(data.password, user.password_hash):
        admin_door_failed(db, user, ip, email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "not_admin"})
    if user.blocked_at is not None:
        raise blocked_error(user)
    admin_door_passed(db, user, ip)
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=UserOut.model_validate(user))


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AdminError as e:
        raise HTTPException(e.status, {"code": e.code, **e.params})


# --- overview and journal ---------------------------------------------------------------------------------------------

@router.get("/overview")
def overview(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.overview(db)


@router.get("/counts")
def counts(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.counts(db)


@router.get("/log")
def journal(action: str | None = None, date_from: date | None = None, date_to: date | None = None,
            user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.journal(db, action, date_from, date_to)


# --- stores -----------------------------------------------------------------------------------------------------------

class VerifyIn(BaseModel):
    verified: bool
    comment: str | None = Field(default=None, max_length=500)


class BlockIn(BaseModel):
    blocked: bool
    reason: str | None = Field(default=None, max_length=300)


@router.get("/stores")
def stores(city: str | None = None, verified: bool | None = None, demo: bool | None = None, mode: str | None = None,
           blocked: bool | None = None, q: str | None = None, user: User = Depends(admin_only),
           db: Session = Depends(get_db)):
    return svc.list_stores(db, {"city": city, "verified": verified, "demo": demo, "mode": mode, "blocked": blocked,
                                "q": q})


@router.get("/stores/{store_id}")
def store(store_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.store_card(db, _run(svc.get_store, db, store_id))


@router.post("/stores/{store_id}/verify")
def verify(store_id: int, data: VerifyIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = _run(svc.get_store, db, store_id)
    svc.set_verified(db, user, s, data.verified, data.comment)
    return svc.store_card(db, s)


@router.post("/stores/{store_id}/block")
def block_store(store_id: int, data: BlockIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = _run(svc.get_store, db, store_id)
    _run(svc.set_store_blocked, db, user, s, data.blocked, data.reason)
    return svc.store_card(db, s)


# --- users ------------------------------------------------------------------------------------------------------------

@router.get("/users")
def users(q: str | None = None, role: str | None = None, blocked: bool | None = None,
          user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.list_users(db, q, role, blocked)


@router.post("/users/{user_id}/block")
def block_user(user_id: int, data: BlockIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {"code": "not_found"})
    _run(svc.set_user_blocked, db, user, target, data.blocked, data.reason)
    return svc._user_row(target)


# --- chat reports -----------------------------------------------------------------------------------------------------

class ResolveReportIn(BaseModel):
    action: str
    comment: str | None = Field(default=None, max_length=500)


@router.get("/reports")
def reports(status_: str | None = Query(None, alias="status"), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.list_reports(db, status_)


@router.get("/reports/{report_id}")
def report(report_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.report_detail, db, report_id)


@router.post("/reports/{report_id}")
def resolve_report(report_id: int, data: ResolveReportIn, user: User = Depends(admin_only),
                   db: Session = Depends(get_db)):
    _run(svc.resolve_report, db, user, report_id, data.action, data.comment)
    return svc.report_detail(db, report_id)


# --- disputed flags ---------------------------------------------------------------------------------------------------

class FlagDecisionIn(BaseModel):
    decision: str
    answer: str | None = Field(default=None, max_length=500)


@router.get("/flags")
def flags(status_: str = Query("disputed", alias="status"), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.list_flags(db, status_)


@router.post("/flags/{flag_id}")
def resolve_flag(flag_id: int, data: FlagDecisionIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    _run(svc.resolve_flag, db, user, flag_id, data.decision, data.answer)
    return {"ok": True}


# --- card fixes -------------------------------------------------------------------------------------------------------

class CommentIn(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class ReasonIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.get("/fixes")
def fixes(status_: str = Query("pending", alias="status"), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.list_fixes(db, status_)


@router.post("/fixes/{fix_id}/accept")
def accept_fix(fix_id: int, data: CommentIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.accept_fix, db, user, fix_id, data.comment)


@router.post("/fixes/{fix_id}/reject")
def reject_fix(fix_id: int, data: ReasonIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    _run(svc.reject_fix, db, user, fix_id, data.reason)
    return {"ok": True}


# --- barcodes ---------------------------------------------------------------------------------------------------------

class BarcodeDecisionIn(BaseModel):
    product_id: int | None = None  # None = "Отклонить все"
    comment: str | None = Field(default=None, max_length=500)


@router.get("/barcodes/conflicts")
def barcode_conflicts(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.barcode_conflicts(db)


@router.get("/barcodes/lookup")
def barcode_lookup(code: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.barcode_lookup, db, code)


@router.post("/barcodes/{code}")
def resolve_barcode(code: str, data: BarcodeDecisionIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.resolve_barcode, db, user, code, data.product_id, data.comment)


# --- Telegram channels ------------------------------------------------------------------------------------------------

class ChannelIn(BaseModel):
    username: str = Field(max_length=100)
    title: str | None = Field(default=None, max_length=255)
    city: str = "tashkent"


class ChannelEditIn(BaseModel):
    city: str | None = None
    enabled: bool | None = None


@router.get("/channels")
def channels(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return svc.list_channels(db)


@router.post("/channels", status_code=status.HTTP_201_CREATED)
def add_channel(data: ChannelIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.add_channel, db, user, data.username, data.title, data.city)


@router.patch("/channels/{channel_id}")
def edit_channel(channel_id: int, data: ChannelEditIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _run(svc.edit_channel, db, user, _run(svc.get_channel, db, channel_id), data.city, data.enabled)


@router.delete("/channels/{channel_id}")
def delete_channel(channel_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    svc.delete_channel(db, user, _run(svc.get_channel, db, channel_id))
    return {"ok": True}


@router.post("/channels/{channel_id}/fetch")
def fetch_channel(channel_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    # A worker thread with its own loop: the collection (t.me pages, pauses, the AI) does not stop the server
    return asyncio.run(svc.fetch_channel(db, user, _run(svc.get_channel, db, channel_id)))
