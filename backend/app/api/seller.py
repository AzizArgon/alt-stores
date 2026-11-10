from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.limits import spend_import
from app.db.database import get_db
from app.db.models import Branch, Category, Condition, Currency, ImportStatus, Offer, PriceImport, Product, Store, User
from app.schemas.seller import (
    BranchIn, BulkIn, CheckResult, ColumnsIn, StockIn, ImportDetail, ImportOut, OfferFilter, OfferIn, OfferPatch, PreviewRow, ProductIn,
    PublishRequest, PublishResult, RelinkIn, StoreIn, StoreOut, TextImportIn,
)
from app.services import branch_stock, branches, cabinet
from app.services.cabinet import EditError
from app.services.importer import (
    ALLOWED_EXTENSIONS, flag_rows, plan_import, publish_import, reparse_row, retry_failed_rows, run_import, run_text_import,
)
from app.services.market import PERIODS, index_table, market_data, missing_popular, seller_position
from app.services import undo
from app.services.maps import MapLinkError, parse_map_url
from app.services.manual import create_product, product_brief, save_offer, store_offer, suggest_products

router = APIRouter(tags=["seller"])

MAX_FILE_SIZE = 10 * 1024 * 1024
seller_only = require_role("seller")


def _my_store(db: Session, user: User) -> Store | None:
    return db.scalar(select(Store).where(Store.user_id == user.id))


def _require_store(db: Session, user: User) -> Store:
    store = _my_store(db, user)
    if store is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Store not created")
    return store


def _my_import(db: Session, user: User, import_id: int) -> tuple[Store, PriceImport]:
    store = _require_store(db, user)
    imp = db.get(PriceImport, import_id)
    if imp is None or imp.store_id != store.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    return store, imp


def _store_out(db: Session, store: Store) -> dict:
    out = StoreOut.model_validate({c.name: getattr(store, c.name) for c in Store.__table__.columns}).model_dump()
    out["branches"] = [branches.branch_seller(b, store) for b in branches.store_branches(db, store.id)]
    return out


@router.get("/stores/me", response_model=StoreOut)
def get_my_store(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    return _store_out(db, _require_store(db, user))


@router.put("/stores/me", response_model=StoreOut)
def save_my_store(data: StoreIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Create the store (its address becomes the main branch) or change its own fields. Once the store has
    branches, the address, hours and map are edited in the branches (phase 12.1): those fields are ignored here."""
    store = _my_store(db, user)
    has_branches = store is not None and bool(branches.store_branches(db, store.id))
    if not has_branches and (not data.address or not data.city):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "address"})
    try:
        map_url, lat, lon = parse_map_url(data.map_url)
    except MapLinkError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": str(e)})
    store = store or Store(user_id=user.id)
    location = {"address", "district", "city", "hours", "map_url"}
    for field, value in data.model_dump().items():
        if has_branches and field in location or field == "low_stock" and value is None:
            continue
        if isinstance(value, str):
            value = value.strip() or None
        setattr(store, field, value)
    if not has_branches:
        store.map_url, store.map_lat, store.map_lon = map_url, lat, lon
    db.add(store)
    db.flush()
    branches.ensure_main_branch(db, store)
    db.commit()
    db.refresh(store)
    return _store_out(db, store)


def _my_branch(db: Session, store: Store, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or branch.store_id != store.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Branch not found")
    return branch


def _branch_edit(db: Session, fn, *args):
    try:
        fn(db, *args)
    except branches.BranchError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": str(e)})
    db.commit()


@router.post("/stores/me/branches", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def add_branch(data: BranchIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _branch_edit(db, branches.save_branch, store, data.model_dump())
    return _store_out(db, store)


@router.put("/stores/me/branches/{branch_id}", response_model=StoreOut)
def edit_branch(branch_id: int, data: BranchIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _branch_edit(db, branches.save_branch, store, data.model_dump(), _my_branch(db, store, branch_id))
    return _store_out(db, store)


@router.post("/stores/me/branches/{branch_id}/main", response_model=StoreOut)
def set_main_branch(branch_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _branch_edit(db, branches.make_main, store, _my_branch(db, store, branch_id))
    return _store_out(db, store)


@router.delete("/stores/me/branches/{branch_id}", response_model=StoreOut)
def remove_branch(branch_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    _branch_edit(db, branches.delete_branch, store, _my_branch(db, store, branch_id))
    return _store_out(db, store)


@router.post("/imports", response_model=ImportOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_price(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    currency: Currency = Form(...),
    # No default: the seller chooses "full price list" or "addition" every time
    mode: str = Form(..., pattern="^(full|append)$"),
    branch_id: int | None = Form(None),  # phase 12.1: the price list of one branch; none = the whole store
    user: User = Depends(seller_only),
    db: Session = Depends(get_db),
):
    store = _require_store(db, user)
    if branch_id is not None:
        _my_branch(db, store, branch_id)
    filename = file.filename or "price"
    if not any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")

    spend_import(db, store.id)
    imp = PriceImport(store_id=store.id, filename=filename, currency=currency, mode=mode, branch_id=branch_id)
    db.add(imp)
    db.commit()
    db.refresh(imp)
    # Parsing takes minutes: the client polls GET /imports/{id} for progress
    background.add_task(run_import, imp.id, data, filename)
    return imp


@router.post("/imports/text", response_model=ImportOut, status_code=status.HTTP_202_ACCEPTED)
def paste_text(data: TextImportIn, background: BackgroundTasks, user: User = Depends(seller_only),
               db: Session = Depends(get_db)):
    """"Paste as text": a Telegram post goes through the same pipeline and preview as a file."""
    store = _require_store(db, user)
    spend_import(db, store.id)
    # No file name: the page calls it "Текст от 25.10, 14:30" by the creation time
    imp = PriceImport(store_id=store.id, filename="", source="text", mode="append", text=data.text, currency=Currency(data.currency))
    db.add(imp)
    db.commit()
    db.refresh(imp)
    background.add_task(run_text_import, imp.id, data.text, imp.currency)
    return imp


@router.get("/imports", response_model=list[ImportOut])
def list_imports(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    undoable = undo.undoable_id(db, store)
    imports = db.scalars(
        select(PriceImport).where(PriceImport.store_id == store.id).order_by(PriceImport.id.desc()).limit(20)
    ).all()
    return [ImportOut.model_validate(i).model_copy(update={"can_undo": i.id == undoable}) for i in imports]


def _undoable(db: Session, imp: PriceImport) -> None:
    reason = undo.can_undo(db, imp)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": reason})


@router.get("/imports/{import_id}/undo")
def undo_summary(import_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"What will come back" before undoing the upload: nothing is written."""
    imp = _my_import(db, user, import_id)[1]
    _undoable(db, imp)
    return undo.plan_undo(db, imp)


@router.post("/imports/{import_id}/undo")
def undo_upload(import_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    imp = _my_import(db, user, import_id)[1]
    _undoable(db, imp)
    return undo.undo_import(db, imp)


@router.get("/imports/{import_id}", response_model=ImportDetail)
def get_import(import_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    imp = _my_import(db, user, import_id)[1]
    out = ImportDetail.model_validate(imp)
    out.branch_info = branch_stock.branch_info(db, imp)
    return out


@router.post("/imports/{import_id}/columns", response_model=ImportDetail)
def confirm_import_columns(import_id: int, data: ColumnsIn, user: User = Depends(seller_only),
                           db: Session = Depends(get_db)):
    """"Сопоставление столбцов": which branch each stock column is; remembered for the next price list."""
    store, imp = _my_import(db, user, import_id)
    try:
        branch_stock.confirm_columns(db, store, imp, data.mapping)
    except branch_stock.ColumnsError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": str(e)})
    db.commit()
    return get_import(import_id, user, db)


@router.post("/imports/{import_id}/publish", response_model=PublishResult)
def publish(import_id: int, data: PublishRequest, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store, imp = _my_import(db, user, import_id)
    if imp.status != ImportStatus.ready:
        raise HTTPException(status.HTTP_409_CONFLICT, "Import is not ready to publish")
    rows = [r.model_dump() for r in data.rows]
    if not branch_stock.branch_info(db, imp)["confirmed"]:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "columns"})  # match the branch columns first
    if not data.confirm_drop and plan_import(db, imp, store, rows, data.mode)["large_drop"]:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "large_drop"})
    return publish_import(db, imp, store, rows, data.mode)


@router.post("/imports/{import_id}/summary")
def import_summary(import_id: int, data: PublishRequest, user: User = Depends(seller_only),
                   db: Session = Depends(get_db)):
    """"What will change" for the rows as the seller edited them: nothing is written."""
    store, imp = _my_import(db, user, import_id)
    if imp.status != ImportStatus.ready:
        raise HTTPException(status.HTTP_409_CONFLICT, "Import is not ready")
    return plan_import(db, imp, store, [r.model_dump() for r in data.rows], data.mode)


@router.post("/imports/{import_id}/check", response_model=CheckResult)
def check_rows(import_id: int, data: PublishRequest, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Anti-Fraud for rows the seller just edited in the preview (rules only, no AI request)."""
    store, imp = _my_import(db, user, import_id)
    rows = [r.model_dump() for r in data.rows]
    flag_rows(db, rows, store.id, imp.currency)
    return {"flags": [r["flags"] for r in rows]}


@router.post("/imports/{import_id}/retry", response_model=ImportOut, status_code=status.HTTP_202_ACCEPTED)
def retry_import(
    import_id: int, background: BackgroundTasks, user: User = Depends(seller_only), db: Session = Depends(get_db)
):
    """Parses again the rows that failed, e.g. the next day when the AI quota is back."""
    store, imp = _my_import(db, user, import_id)
    if imp.status != ImportStatus.ready or not any(r.get("source") == "failed" for r in imp.rows_json):
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing to retry")
    spend_import(db, store.id)
    imp.status = ImportStatus.processing
    imp.chunks_done = 0
    db.commit()
    background.add_task(retry_failed_rows, imp.id)
    return imp


@router.post("/imports/{import_id}/rows/{row}/reparse", response_model=PreviewRow)
async def reparse_import_row(import_id: int, row: int, user: User = Depends(seller_only),
                             db: Session = Depends(get_db)):
    """"Re-parse without the cache": the AI reads this row again; a wrong cached answer is forgotten."""
    store, imp = _my_import(db, user, import_id)
    if imp.status != ImportStatus.ready:
        raise HTTPException(status.HTTP_409_CONFLICT, "Import is not ready")
    old = next((r for r in imp.rows_json if r["row"] == row), None)
    if old is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Row not found")
    spend_import(db, store.id)
    db.commit()
    new = await reparse_row(db, imp, old)
    if new is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "not_a_product"})
    return new


@router.get("/seller/catalog-search")
def catalog_search(q: str = Query("", max_length=200), user: User = Depends(seller_only),
                   db: Session = Depends(get_db)):
    """"Find in the catalog": suggestions with key specs and the store's own offer on the card, if any."""
    return suggest_products(db, _require_store(db, user), q)


@router.post("/seller/offers", status_code=status.HTTP_201_CREATED)
def add_offer(data: OfferIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"I have it too, here is my price". An existing offer is never duplicated: 409 unless `replace`."""
    store = _require_store(db, user)
    product = db.get(Product, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    existing = store_offer(db, store, product)
    if existing is not None and not data.replace:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "offer_exists", "product": product_brief(product, existing)})
    return save_offer(db, store, product, data.price, Currency(data.currency), Condition(data.condition),
                      data.is_in_stock)


@router.post("/seller/products", status_code=status.HTTP_201_CREATED)
def add_product(data: ProductIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Not in the catalog": a new card by the dictionary. The same card already exists -> 409 with it."""
    store = _require_store(db, user)
    category = db.scalar(select(Category).where(Category.slug == data.category))
    if category is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    if not (data.name or data.model or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name or model required")
    product, created = create_product(db, store, category, data.brand, data.model, data.name, data.specs)
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "code": "product_exists", "product": product_brief(product, store_offer(db, store, product))})
    return product_brief(product)


@router.get("/seller/analytics")
def market_analytics(period: str = Query("quarter", pattern=f"^({'|'.join(PERIODS)})$"),
                     user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Market analytics": category indices, the seller's prices against the market, what competitors sell more."""
    from app.api.market import usd_rate_info

    store = _require_store(db, user)
    md = market_data(db)
    return {"indices": index_table(md, period), "position": seller_position(db, md, store.id),
            "missing": missing_popular(db, md, store.id), "includes_demo": bool(md.demo_stores), **usd_rate_info(db)}


# --- Seller cabinet (phase B3): the store's own offers after publishing ---

def _my_offer(db: Session, store: Store, offer_id: int) -> Offer:
    offer = db.get(Offer, offer_id)
    if offer is None or offer.store_id != store.id or offer.removed_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return offer


def _edit(fn, *args):
    try:
        return fn(*args)
    except EditError as e:
        raise HTTPException(status.HTTP_409_CONFLICT if str(e) == "offer_exists" else status.HTTP_422_UNPROCESSABLE_ENTITY,
                            {"code": str(e)})


@router.get("/seller/overview")
def seller_overview(user: User = Depends(seller_only), db: Session = Depends(get_db)):
    return cabinet.overview(db, _require_store(db, user))


@router.get("/seller/offers")
def my_offers(f: OfferFilter = Depends(), sort: str = Query("updated", pattern=f"^({'|'.join(cabinet.SORTS)})$"),
              desc: bool = True, page: int = Query(1, ge=1), user: User = Depends(seller_only),
              db: Session = Depends(get_db)):
    """"My goods": the store's offers with search, filters and sorting, 50 a page."""
    return cabinet.list_offers(db, _require_store(db, user), f.model_dump(), sort, desc, page)


@router.get("/seller/offers/{offer_id}")
def my_offer(offer_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    store = _require_store(db, user)
    return cabinet.offer_detail(db, store, _my_offer(db, store, offer_id))


@router.patch("/seller/offers/{offer_id}")
def edit_offer(offer_id: int, data: OfferPatch, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Price, stock, condition, the seller's line, note: at once, with price history and Anti-Fraud."""
    store = _require_store(db, user)
    return _edit(cabinet.update_offer, db, store, _my_offer(db, store, offer_id), data.model_dump(exclude_unset=True))


@router.put("/seller/offers/{offer_id}/stocks")
def edit_offer_stocks(offer_id: int, data: list[StockIn], user: User = Depends(seller_only),
                      db: Session = Depends(get_db)):
    """Stock by branch (phase 12.1): a quantity, "есть / нет" (quantity unknown) or clear = not tracked there."""
    store = _require_store(db, user)
    return _edit(cabinet.set_branch_stock, db, store, _my_offer(db, store, offer_id), [d.model_dump() for d in data])


@router.delete("/seller/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer(offer_id: int, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Only the store's offer: the card and the price history stay."""
    store = _require_store(db, user)
    cabinet.remove_offer(db, _my_offer(db, store, offer_id))


@router.put("/seller/offers/{offer_id}/card")
def edit_offer_card(offer_id: int, data: ProductIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """The shared card: changed at once if only this store sells it, otherwise a suggestion for the admin."""
    store = _require_store(db, user)
    return _edit(cabinet.edit_card, db, store, _my_offer(db, store, offer_id), data.model_dump())


@router.post("/seller/offers/{offer_id}/relink")
def relink_offer(offer_id: int, data: RelinkIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """"Not this product": the offer moves to another card."""
    store = _require_store(db, user)
    offer = _my_offer(db, store, offer_id)
    product = db.get(Product, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return _edit(cabinet.relink, db, store, offer, product)


@router.post("/seller/offers/bulk")
def bulk_offers(data: BulkIn, user: User = Depends(seller_only), db: Session = Depends(get_db)):
    """Bulk actions over chosen rows or all rows by the filter; apply=False returns the preview."""
    store = _require_store(db, user)
    if data.action == "price" and not data.percent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "percent_required"})
    if data.ids is not None:
        wanted = set(data.ids)
        offers = [o for o in cabinet.store_offers(db, store) if o.id in wanted]
    else:
        offers = [o for o, _ in cabinet.filtered_offers(db, store, (data.filter or OfferFilter()).model_dump())]
    if data.action in ("branch_on", "branch_off"):
        if data.branch_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "branch_required"})
        _my_branch(db, store, data.branch_id)
    return cabinet.bulk(db, store, offers, data.action, data.percent, data.apply, data.branch_id)
