from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.seed import CITIES


class StoreIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    inn_stir: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=32)
    telegram: str | None = Field(default=None, max_length=64)
    # Street, house, landmark: the buyer must know where to go (phase 12)
    # Required when the store is created; later the address lives in the branches (phase 12.1), these stay None
    address: str | None = Field(default=None, min_length=3, max_length=255)
    district: str | None = Field(default=None, max_length=128)
    city: str | None = None
    reservation_days: int = Field(default=2, ge=1, le=7)  # how long a confirmed reservation waits (phase 11)
    hours: str | None = Field(default=None, max_length=100)  # "Mon-Sat 10:00-19:00", as the store writes it
    map_url: str | None = Field(default=None, max_length=500)  # only Yandex Maps (app.services.maps)

    @field_validator("city")
    @classmethod
    def known_city(cls, value: str | None) -> str | None:
        if value is not None and value not in CITIES:
            raise ValueError("unknown city")
        return value


class StoreOut(StoreIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_verified: bool
    address: str | None = None  # stores made before phase 12 may have none yet
    branches: list[dict] = []  # phase 12.1: the main one first
    map_lat: float | None = None
    map_lon: float | None = None


class BranchIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    city: str
    address: str = Field(max_length=255)
    landmark: str = Field(max_length=128)
    hours: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    map_url: str | None = Field(default=None, max_length=500)


class StockIn(BaseModel):
    """One branch of one offer: a quantity, or only "есть / нет", or clear = not tracked there."""

    branch_id: int
    quantity: int | None = Field(default=None, ge=0, le=1_000_000)
    present: bool | None = None
    clear: bool = False


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    mxik_code: str | None


class FlagOut(BaseModel):
    """Anti-Fraud flag: the soft text is the frontend translation flags.reason.<reason_key> with params."""

    type: str
    level: Literal["info", "warning", "danger"]
    reason_key: str
    params: dict[str, str | int | float] = {}
    source: Literal["rule", "ai"]


class PreviewRow(BaseModel):
    """One parsed row in the editable preview table."""

    row: int
    raw_name: str
    section: str = ""
    category: str
    brand: str | None = None
    model: str | None = None
    name: str = Field(min_length=1, max_length=512)
    price: float | None = Field(default=None, ge=0)
    condition: Literal["new", "new_openbox", "used", "refurbished", "unknown"] = "new"
    # Dictionary values ("DDR5", 16, true) + "_inferred": {key: rule} for values added by inference rules
    # + "_suspect": {key: number} for numbers outside their plausible range (a typo?)
    specs: dict[str, bool | int | float | str | dict[str, str | int | float]] = {}
    # AI specs not found in the row text: shown to the seller, never saved to the product
    specs_guess: dict[str, str | int | float | bool] = {}  # values inferred by rules are not always text
    is_in_stock: bool = True
    # Phase 12.1: stock by branch column header: a count, True ("+", "есть"), False ("нет") or None (empty)
    branches: dict[str, bool | int | None] = {}
    # Pasted text: the currency of this line (None = the import's one); check = not written, default was taken
    currency: Literal["USD", "UZS"] | None = None
    currency_check: bool = False
    # The seller's words next to the price: "Подписчикам 13$", "(только в сборках)"
    note: str | None = Field(default=None, max_length=500)
    # Anti-Fraud: AI hints (types only) and the resulting flags
    ai_risks: list[str] = []
    flags: list[FlagOut] = []
    # Filled by the parser: where the row came from and how to find it in the parse cache
    sheet: str = ""
    article: str | None = None
    ai_text: str | None = None
    cache_key: str | None = None
    source: Literal["cache", "rule", "ai", "failed", "seller"] = "ai"


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    source: str = "file"  # file / text / manual
    mode: str = "full"  # full / append (text and manual are always append)
    currency: str
    status: str
    chunks_total: int
    chunks_done: int
    error: str | None
    stats: dict = Field(default_factory=dict, validation_alias="stats_json")
    created_at: datetime
    published_at: datetime | None = None
    undone_at: datetime | None = None
    can_undo: bool = False  # the store's last published file or post, not older than 7 days (phase 12)
    branch_id: int | None = None  # phase 12.1: the price list of one branch

    @field_validator("created_at", "published_at", "undone_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        # SQLite drops the timezone; we always store UTC
        return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


class ImportDetail(ImportOut):
    rows: list[PreviewRow] = Field(validation_alias="rows_json")
    # Phase 12.1: branch columns found, their match to branches (confirmed or suggested)
    branch_info: dict = {}


class ColumnsIn(BaseModel):
    """Column header -> branch id (None = not a branch column)."""

    mapping: dict[str, int | None]


class PublishRequest(BaseModel):
    rows: list[PreviewRow]
    # A file may switch its mode in the preview; None = the mode chosen at the upload
    mode: Literal["full", "append"] | None = None
    # The seller saw the warning "the file looks incomplete" and still publishes
    confirm_drop: bool = False


class CheckResult(BaseModel):
    flags: list[list[FlagOut]]


class TextImportIn(BaseModel):
    """A pasted post (e.g. from Telegram); rows without a currency get `currency`."""

    text: str = Field(min_length=3, max_length=20000)
    currency: Literal["USD", "UZS"]


class OfferIn(BaseModel):
    product_id: int
    price: float = Field(gt=0)
    currency: Literal["USD", "UZS"]
    condition: Literal["new", "new_openbox", "used", "refurbished", "unknown"] = "new"
    is_in_stock: bool = True
    # The store already has an offer on this card: False -> 409 with it, True -> update its price
    replace: bool = False


class ProductIn(BaseModel):
    category: str
    brand: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=512)
    specs: dict[str, bool | int | float | str | None] = {}


CONDITIONS = Literal["new", "new_openbox", "used", "refurbished", "unknown"]


class OfferPatch(BaseModel):
    """The seller's own fields of an offer; only the given ones change."""

    price: float | None = Field(default=None, gt=0)
    currency: Literal["USD", "UZS"] | None = None
    is_in_stock: bool | None = None
    condition: CONDITIONS | None = None
    raw_name: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=500)


class OfferFilter(BaseModel):
    """Filters of "My goods" (also "all by the filter" of bulk actions)."""

    q: str = Field(default="", max_length=200)
    category: str | None = None
    stock: Literal["in", "out"] | None = None
    flagged: bool = False
    condition: CONDITIONS | None = None
    stale: bool = False
    market: Literal["above", "below", "at"] | None = None
    branch: int | None = None  # phase 12.1: the stock filter applies to this branch


class BulkIn(BaseModel):
    # Chosen rows, or every row by the filter when ids is None
    ids: list[int] | None = Field(default=None, max_length=5000)
    filter: OfferFilter | None = None
    action: Literal["off", "on", "price", "branch_on", "branch_off"]
    percent: float | None = Field(default=None, ge=-50, le=100)
    branch_id: int | None = None  # "в филиале …: есть / нет"
    apply: bool = False  # False: only the preview "N goods will change"


class RelinkIn(BaseModel):
    product_id: int


class PublishResult(BaseModel):
    created: int
    updated: int
    out_of_stock: int


class RateOut(BaseModel):
    currency: str
    rate: float
    rate_date: date
