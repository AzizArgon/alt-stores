from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.seller import _require_store
from app.core.limits import spend_import
from app.db.database import get_db
from app.db.models import Build, User
from app.db.seed import CITIES
from app.services import builds as svc
from app.services.exchange import get_usd_rate

router = APIRouter(tags=["builds"])
seller_only = require_role("seller")

Slot = Literal["cpu", "motherboard", "ram", "gpu", "storage", "psu", "case", "cooling", "other"]


class ComponentIn(BaseModel):
    slot: Slot
    product_id: int | None = None
    quantity: int = Field(1, ge=1, le=8)
    raw_text: str = Field("", max_length=300)
    # "Only specs": values by the dictionary of the category (ssd / hdd for a storage slot); a CPU adds "model",
    # a GPU may be {"integrated": true}
    category: str | None = Field(None, max_length=32)
    specs: dict = Field(default_factory=dict)


class BuildIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    price: float = Field(gt=0)
    currency: Literal["USD", "UZS"] = "USD"
    condition: Literal["new", "used"] = "new"
    purpose: Literal["gaming", "office", "work", "other"] = "other"
    is_in_stock: bool = True
    description: str | None = Field(None, max_length=3000)
    text: str | None = Field(None, max_length=5000)  # the pasted post, kept without contacts (phase 17.2)
    components: list[ComponentIn] = Field(min_length=1, max_length=30)


class BuildTextIn(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    # Phase 17.2: false = rules and cache only (instant, the form shows "5 of 7" and asks again with the AI)
    ai: bool = True


class SaleIn(BaseModel):
    on_sale: bool


def _rate(db: Session) -> tuple[float | None, str | None]:
    rate = get_usd_rate(db)
    return (rate.rate, rate.rate_date.isoformat()) if rate else (None, None)


def _list(value: str | None) -> list[str] | None:
    return [v for v in value.split(",") if v] if value else None


# --- Storefront -----------------------------------------------------------------------------------------------------

@router.get("/builds")
def list_builds(
    city: str | None = None,
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    purpose: str | None = None,
    cpu: str | None = None,
    gpu: str | None = None,
    ram: str | None = None,
    condition: str | None = None,
    exact_only: bool = False,
    sort: str = Query("new", pattern="^(new|price_asc|price_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(svc.PAGE_SIZE, ge=1, le=svc.PAGE_SIZE),
    db: Session = Depends(get_db),
):
    """"Ready PCs": builds on sale. Price in UZS; `purpose`, `cpu` (intel, amd), `gpu` (chip), `ram` (GB),
    `condition`: comma-separated values ("or" inside a filter); `exact_only`: every part is an exact model.
    `city`: none or "all" = all of Uzbekistan. No market labels: builds of different stores are not compared."""
    usd_rate, rate_date = _rate(db)
    f = {"price_min": price_min, "price_max": price_max, "purpose": _list(purpose), "cpu": _list(cpu),
         "gpu": _list(gpu), "ram": [int(v) for v in _list(ram) or [] if v.isdigit()] or None,
         "condition": _list(condition), "exact_only": exact_only}
    result = svc.list_builds(db, usd_rate, f, city if city in CITIES else None, sort, page, page_size)
    return {**result, "usd_rate": usd_rate, "usd_rate_date": rate_date}


@router.get("/builds/{build_id}")
def get_build(build_id: int, db: Session = Depends(get_db)):
    build = db.get(Build, build_id)
    if build is None or not build.is_in_stock or build.store.blocked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")
    usd_rate, rate_date = _rate(db)
    return {**svc.build_detail(db, build, usd_rate), "usd_rate": usd_rate, "usd_rate_date": rate_date}


# --- Seller cabinet: "My builds" ------------------------------------------------------------------------------------

def _my_build(db: Session, user: User, build_id: int) -> Build:
    store = _require_store(db, user)
    build = db.get(Build, build_id)
    if build is None or build.store_id != store.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")
    return build


def _save(fn, *args):
    try:
        return fn(*args)
    except svc.BuildError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": str(e), **e.params})


@router.get("/seller/builds")
def my_builds(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    usd_rate, rate_date = _rate(db)
    store = _require_store(db, user)
    return {"items": svc.store_builds(db, store, usd_rate), "usd_rate": usd_rate, "usd_rate_date": rate_date}


@router.get("/seller/builds/search")
def search_parts(q: str = Query("", max_length=200), slot: Slot | None = None,
                 user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Choose the exact model" for one slot of the build form: only cards of that slot's categories."""
    _require_store(db, user)
    return svc.search_parts(db, q, slot)


@router.post("/seller/builds/parse")
async def parse_text(data: BuildTextIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Paste as text": a build post -> a draft by slots for the preview. Nothing is saved until the seller
    publishes the draft (POST /seller/builds). ai=false: only code (cache and rules), free and instant; the AI step
    counts as an import of the day."""
    store = _require_store(db, user)
    if data.ai:
        spend_import(db, store.id)
        db.commit()
    draft = await svc.parse_build_text(db, data.text, ai=data.ai)
    if not draft["components"] and draft["price"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "build_no_parts"})
    return draft


@router.post("/seller/builds", status_code=status.HTTP_201_CREATED)
def add_build(data: BuildIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    build = _save(svc.save_build, db, store, data.model_dump())
    return svc.build_detail(db, build, _rate(db)[0])


@router.get("/seller/builds/{build_id}")
def my_build(build_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    usd_rate, rate_date = _rate(db)
    return {**svc.build_detail(db, _my_build(db, user, build_id), usd_rate), "usd_rate": usd_rate,
            "usd_rate_date": rate_date}


@router.put("/seller/builds/{build_id}")
def edit_build(build_id: int, data: BuildIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    build = _my_build(db, user, build_id)
    _save(svc.save_build, db, build.store, data.model_dump(exclude={"text"}), build)
    return svc.build_detail(db, build, _rate(db)[0])


@router.post("/seller/builds/{build_id}/sale")
def build_sale(build_id: int, data: SaleIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Take a build off sale or put it back."""
    svc.set_on_sale(db, _my_build(db, user, build_id), data.on_sale)
    return {"ok": True}


@router.delete("/seller/builds/{build_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_build(build_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    db.delete(_my_build(db, user, build_id))
    db.commit()
