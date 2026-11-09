"""Phase 10: chat of a buyer with a store. One set of routes for both sides: a seller speaks for the store."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.services import chat as svc
from app.services.exchange import get_usd_rate

router = APIRouter(prefix="/chat", tags=["chat"])


class OpenIn(BaseModel):
    topic_kind: str = Field(pattern="^(offer|build|store)$")
    topic_id: int = 0
    store_id: int | None = None


class MessageIn(BaseModel):
    # Longer texts are refused with a clear code (chat.error.too_long), not cut
    text: str = Field(max_length=svc.MAX_TEXT * 2)


class ReportIn(BaseModel):
    reason: str
    comment: str | None = Field(None, max_length=svc.MAX_TEXT)


class BlockIn(BaseModel):
    blocked: bool = True


def _rate(db: Session) -> float | None:
    rate = get_usd_rate(db)
    return rate.rate if rate else None


def _do(fn, *args):
    try:
        return fn(*args)
    except svc.ChatError as e:
        raise HTTPException(e.status, {"code": e.code})


def _detail(db: Session, side: str, conv, msgs) -> dict:
    return {**svc.conversation_head(db, conv, side, _rate(db)), "messages": [svc.message_out(m) for m in msgs]}


@router.get("/unread")
def unread(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": _do(svc.unread_count, db, user)}


@router.get("/conversations")
def conversations(filter: str = Query("all", pattern="^(all|unread|offer|build)$"),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _do(svc.list_conversations, db, user, _rate(db), filter)


@router.post("/conversations")
def open_conversation(data: OpenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """"Write to the seller": the existing conversation of this topic, or a new empty one."""
    conv = _do(svc.open_conversation, db, user, data.topic_kind, data.topic_id, data.store_id)
    return {"id": conv.id}


@router.get("/conversations/{conv_id}")
def conversation(conv_id: int, after: int = Query(0, ge=0),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """`after` = the last message id the page has: polling gets only the new ones."""
    side, conv, msgs = _do(svc.read_messages, db, user, conv_id, after)
    return _detail(db, side, conv, msgs)


@router.post("/conversations/{conv_id}/messages", status_code=201)
def send(conv_id: int, data: MessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.message_out(_do(svc.send_message, db, user, conv_id, data.text))


@router.post("/conversations/{conv_id}/report", status_code=201)
def report(conv_id: int, data: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _do(svc.report, db, user, conv_id, data.reason, data.comment)
    return {"ok": True}


@router.post("/conversations/{conv_id}/block")
def block(conv_id: int, data: BlockIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _do(svc.set_block, db, user, conv_id, data.blocked)
    return {"blocked": data.blocked}
