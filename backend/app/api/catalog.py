from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Condition
from app.db.seed import CITIES
from app.services.catalog import PAGE_SIZE, category_summary, counts_demo, parse_spec_filters, product_card, search_products
from app.services.exchange import get_usd_rate
from app.services.market import product_market

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _city(city: str | None) -> str | None:
    """Unknown city or "all" = the whole country."""
    return city if city in CITIES else None


def _rate(db: Session) -> tuple[float | None, str | None]:
    """CBU USD rate and its date (the page says "by the CBU rate on 25.10")."""
    rate = get_usd_rate(db)  # cached in the DB for a day
    return (rate.rate, rate.rate_date.isoformat()) if rate else (None, None)


@router.get("/products")
def list_products(
    request: Request,
    q: str = Query("", max_length=200),
    category: str | None = None,
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    in_stock: bool = True,
    condition: Condition | None = None,
    city: str | None = None,
    sort: str = Query("popular", pattern="^(popular|price_asc|price_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=PAGE_SIZE),
    db: Session = Depends(get_db),
):
    """Catalog with search and filters. The price filter is in UZS (shown to buyers), compared in USD inside.

    Spec filters of the chosen category: `f_<key>=v1,v2` ("or" inside one filter, "and" between filters),
    e.g. `?category=ram&f_type=DDR5&f_form_factor=SODIMM`. The answer has `facets`: filters with counts.
    `condition` (new, new_openbox, used, refurbished, unknown): only offers in that condition count.
    `city` (tashkent, samarkand, ...): only offers of that city's stores; none or "all" = all of Uzbekistan.
    """
    usd_rate, rate_date = _rate(db)
    to_usd = lambda uzs: uzs / usd_rate if uzs is not None and usd_rate else None  # noqa: E731
    spec_filters = parse_spec_filters(category, dict(request.query_params))
    result = search_products(db, usd_rate, q.strip(), category, to_usd(price_min), to_usd(price_max), in_stock, page,
                             spec_filters, condition, _city(city), sort, page_size)
    return {**result, "usd_rate": usd_rate, "usd_rate_date": rate_date}


@router.get("/categories")
def list_categories(city: str | None = None, db: Session = Depends(get_db)):
    """Home page: categories with products in stock, their number of products and stores and the lowest price."""
    usd_rate, rate_date = _rate(db)
    return {"items": category_summary(db, usd_rate, _city(city)), "includes_demo": counts_demo(db, _city(city)),
            "usd_rate": usd_rate, "usd_rate_date": rate_date}


@router.get("/products/{product_id}")
def get_product(product_id: int, sort: str = Query("recommended", pattern="^(recommended|price)$"),
                db: Session = Depends(get_db)):
    """Product card with store offers: "recommended" order by default, or by price."""
    usd_rate, rate_date = _rate(db)
    card = product_card(db, product_id, usd_rate, sort)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return {**card, "usd_rate_date": rate_date, "market": product_market(db, product_id)}
