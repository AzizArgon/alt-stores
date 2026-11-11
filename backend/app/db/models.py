import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, WriteOnlyMapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def str_enum(enum_cls):
    # Store enum values as plain strings so the DB stays readable
    return Enum(enum_cls, native_enum=False, values_callable=lambda e: [m.value for m in e])


class UserRole(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    master = "master"
    admin = "admin"


class Condition(str, enum.Enum):
    new = "new"
    used = "used"
    refurbished = "refurbished"
    new_openbox = "new_openbox"  # new, the box was opened
    unknown = "unknown"  # a post did not say: the seller is asked to choose


# Groups the buyer sees (phase 9): new and used goods are never mixed in one list or price.
# "Not said" is in the used group: it is more honest not to pass it off as new
NEW_GROUP = (Condition.new, Condition.new_openbox)
USED_GROUP = (Condition.used, Condition.refurbished, Condition.unknown)


class StoreKind(str, enum.Enum):
    shop = "shop"
    telegram = "telegram"  # a public Telegram channel (phase 9): no cabinet, never verified, ads not checked


class Currency(str, enum.Enum):
    USD = "USD"
    UZS = "UZS"


class ImportStatus(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"
    published = "published"
    undone = "undone"  # "Undo this upload" (phase 12): can be neither undone nor published again


class FlagLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    danger = "danger"


class FlagSource(str, enum.Enum):
    rule = "rule"
    ai = "ai"


class FlagStatus(str, enum.Enum):
    active = "active"
    disputed = "disputed"
    dismissed = "dismissed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole), default=UserRole.buyer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Contacts of the last reservation (phase 11): filled in the next form, the buyer may change them
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(16))
    contact_telegram: Mapped[str | None] = mapped_column(String(33))
    # Phase 13: blocked on the whole site by the admin (no login, messages or reservations); the reason is shown
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_reason: Mapped[str | None] = mapped_column(String(300))

    stores: Mapped[list["Store"]] = relationship(back_populates="owner")


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    inn_stir: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(255))
    district: Mapped[str | None] = mapped_column(String(128))
    # City slug from app.db.seed.CITIES (the same list as the city choice of the site header)
    city: Mapped[str] = mapped_column(String(32), default="tashkent", server_default="tashkent", index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Archive source (an old price list of a shop, e.g. Gshop, Dec 2022): its prices go only to the price history
    is_archive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Invented store of the demo (scripts/seed_demo.py, live upload store); a real store is kept by demo_reset.py
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    kind: Mapped[StoreKind] = mapped_column(str_enum(StoreKind), default=StoreKind.shop, server_default="shop")
    # How many days a confirmed reservation waits for the buyer (phase 11), 1-7
    reservation_days: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    # Where to go (phase 12): opening hours as the store writes them, its point in Yandex Maps (optional; without it
    # the site searches the address), coordinates only when the link has them
    hours: Mapped[str | None] = mapped_column(String(100))
    map_url: Mapped[str | None] = mapped_column(String(500))
    map_lat: Mapped[float | None] = mapped_column(Float)
    map_lon: Mapped[float | None] = mapped_column(Float)
    # Phase 12.2: "price" = stock from price lists and hand edits; "stock" = only operations change quantities
    stock_mode: Mapped[str] = mapped_column(String(8), default="price", server_default="price")
    low_stock: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # "заканчивается": available <= it
    # Phase 13: blocked by the admin — its goods, builds and branches are off the storefront, the market and the
    # "Stores" list, no new reservations; nothing is deleted, the seller sees the reason in the cabinet
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_reason: Mapped[str | None] = mapped_column(String(300))
    # Phase 12.4: "Есть отдельный склад" — receipts go to the warehouse (a Branch with is_warehouse), branches get
    # goods by "Выкладка"; off = receipts straight into a branch. The warehouse row stays when it is switched off
    has_warehouse: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    owner: Mapped[User] = relationship(back_populates="stores")
    offers: Mapped[list["Offer"]] = relationship(back_populates="store")
    # The buyer's points only: the warehouse (phase 12.4) is never shown on the storefront
    branches: Mapped[list["Branch"]] = relationship(
        primaryjoin=lambda: (Store.id == Branch.store_id) & Branch.is_warehouse.is_(False),
        order_by=lambda: (Branch.is_main.desc(), Branch.id), viewonly=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    mxik_code: Mapped[str | None] = mapped_column(String(32), index=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    """Reference product: one card that groups offers from many stores."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    brand: Mapped[str | None] = mapped_column(String(128), index=True)
    model: Mapped[str | None] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(512), index=True)
    # Lowercased brand+model used to merge the same product from different stores
    match_key: Mapped[str] = mapped_column(String(512), index=True)
    specs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Set when a seller created the card by hand (not from a price list): to be moderated later
    manual_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))

    category: Mapped[Category | None] = relationship(back_populates="products")
    offers: Mapped[list["Offer"]] = relationship(back_populates="product")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    raw_name: Mapped[str] = mapped_column(Text)
    # Price is kept in the seller's original currency
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.USD)
    is_in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    condition: Mapped[Condition] = mapped_column(str_enum(Condition), default=Condition.new)
    # The seller's own words next to the price: "Подписчикам 13$", "(только в сборках)"
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # "Delete my offer": the row stays (its price history is kept), without a price it is out of the catalog.
    # The next price list with the same item brings it back
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # An ad of a Telegram channel (phase 9): the link to its post and when it was posted (older than 30 days = hidden)
    post_url: Mapped[str | None] = mapped_column(String(255))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 12.2, only the seller sees them: the last purchase price and the average over receipts (offer currency)
    cost_last: Mapped[float | None] = mapped_column(Float)
    cost_avg: Mapped[float | None] = mapped_column(Float)
    # Phase 12.4: sold more than the books had — "проверьте при ревизии" (cleared by a stocktake or an adjustment)
    oversold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="offers")
    store: Mapped[Store] = relationship(back_populates="offers")
    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    fraud_flags: Mapped[list["FraudFlag"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    events: Mapped[list["OfferEvent"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    stocks: Mapped[list["OfferStock"]] = relationship(cascade="all, delete-orphan")
    movements: WriteOnlyMapped["StockMovement"] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    barcodes: Mapped[list["Barcode"]] = relationship(cascade="all, delete-orphan", order_by="Barcode.id")  # 12.3


class OfferEvent(Base):
    """A change of an offer other than its price (prices are in price_history): stock, condition, removal."""

    __tablename__ = "offer_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(16))  # stock / condition / removed / product
    value: Mapped[str] = mapped_column(String(64))
    # import (a price list), edit (the seller in the cabinet), bulk (a bulk action)
    source: Mapped[str] = mapped_column(String(16))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    offer: Mapped[Offer] = relationship(back_populates="events")


class ProductFix(Base):
    """A seller's correction of a card that other stores sell too: waits for the admin (phase 12)."""

    __tablename__ = "product_fixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    # The card as it was and as the seller wants it: {name, brand, model, category, specs}
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / accepted / rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Phase 13: the admin's decision — why rejected, when, and the card it was merged into (accepted, same key)
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into: Mapped[int | None] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.USD)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # Invented history of the demo stores (scripts/seed_demo.py): deleted with one query
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)

    offer: Mapped[Offer] = relationship(back_populates="price_history")


class ArchivePrice(Base):
    """One row of an old price list (archive source): only history, never a current offer or a catalog card.

    Matched to a reference card when the model is the same; unmatched rows stay here as they were.
    """

    __tablename__ = "archive_prices"
    __table_args__ = (UniqueConstraint("store_id", "sheet", "raw_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    sheet: Mapped[str] = mapped_column(String(128))
    section: Mapped[str | None] = mapped_column(String(255))
    raw_name: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.USD)
    condition: Mapped[Condition] = mapped_column(str_enum(Condition), default=Condition.new)
    # A note that makes the price not comparable ("only in a PC build")
    note: Mapped[str | None] = mapped_column(String(64))
    price_date: Mapped[date] = mapped_column(Date)


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    level: Mapped[FlagLevel] = mapped_column(str_enum(FlagLevel))
    # Translation key (flags.reason.<key> in the frontend) + its parameters: texts stay out of the DB
    reason_key: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[FlagSource] = mapped_column(str_enum(FlagSource))
    status: Mapped[FlagStatus] = mapped_column(str_enum(FlagStatus), default=FlagStatus.active)
    # Phase 13: "Оспорить" by the seller and the admin's answer. upheld = "the flag is right" (active again, the
    # seller sees the answer); dismissed = taken off for good (never raised again by the next uploads)
    dispute_comment: Mapped[str | None] = mapped_column(String(500))
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(10))
    admin_answer: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    offer: Mapped[Offer] = relationship(back_populates="fraud_flags")


class PriceImport(Base):
    """One uploaded price list: parsed rows wait here until the seller publishes them."""

    __tablename__ = "price_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Where the rows came from: a price list file, a pasted text (Telegram post) or one offer added by hand.
    # Only a file is the full price list: missing items become "out of stock" only after a file
    source: Mapped[str] = mapped_column(String(16), default="file", server_default="file")
    # A file is "full" (missing items become out of stock) or "append" (only the listed items change);
    # pasted text and manual adding are always "append"
    mode: Mapped[str] = mapped_column(String(8), default="full", server_default="full")
    # Pasted text as the seller sent it: to see later why a post was parsed the way it was
    text: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency))
    status: Mapped[ImportStatus] = mapped_column(str_enum(ImportStatus), default=ImportStatus.processing)
    chunks_total: Mapped[int] = mapped_column(Integer, default=0)
    chunks_done: Mapped[int] = mapped_column(Integer, default=0)
    rows_json: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    # How the rows were parsed: counts by source, AI requests, seconds (for the parser experiment)
    stats_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # "Undo this upload" (phase 12): what the publication changed (app.services.undo), when it was published/undone
    undo_json: Mapped[dict | None] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 12.1: the price list of one branch (None = the whole store) and the confirmed branch columns
    # {column header: branch id or None = not a branch}; None = not confirmed yet
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    columns_json: Mapped[dict | None] = mapped_column(JSON)


class ParseCache(Base):
    """Already parsed names: the same row is never sent to the AI twice.

    Seller corrections from the preview overwrite AI answers (source = "seller").
    """

    __tablename__ = "parse_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExchangeRate(Base):
    """Official CBU rate: how many UZS one unit of the currency costs on a given day."""

    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("currency", "rate_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[float] = mapped_column(Float)
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    # When we last asked cbu.uz: on weekends rate_date lags behind, so it can't tell freshness
    fetched_on: Mapped[date] = mapped_column(Date, default=date.today)


class UsageCounter(Base):
    """Daily usage for the limits of the public server; key: "imports", "imports:store:5" or "ai"."""

    __tablename__ = "usage_counters"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class BuildPurpose(str, enum.Enum):
    gaming = "gaming"
    office = "office"
    work = "work"  # video editing, design, work
    other = "other"


class BuildSlot(str, enum.Enum):
    cpu = "cpu"
    motherboard = "motherboard"
    ram = "ram"
    gpu = "gpu"
    storage = "storage"
    psu = "psu"
    case = "case"
    cooling = "cooling"
    other = "other"


class Build(Base):
    """A ready PC of a store (phase B4): not a component, so it lives apart from cards and offers.

    Its price is the store's own; builds of different stores are never compared, and a build never counts in the
    market price, the indexes or the component catalog."""

    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.USD)
    condition: Mapped[Condition] = mapped_column(str_enum(Condition), default=Condition.new)
    is_in_stock: Mapped[bool] = mapped_column(Boolean, default=True)  # False = taken off sale by the seller
    purpose: Mapped[BuildPurpose] = mapped_column(str_enum(BuildPurpose), default=BuildPurpose.other)
    description: Mapped[str | None] = mapped_column(Text)
    # Pasted post as the seller sent it ("Paste as text"): to see later why it was parsed the way it was
    text: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    store: Mapped[Store] = relationship()
    components: Mapped[list["BuildComponent"]] = relationship(
        back_populates="build", cascade="all, delete-orphan", order_by="BuildComponent.position")
    price_history: Mapped[list["BuildPriceHistory"]] = relationship(
        back_populates="build", cascade="all, delete-orphan")


class BuildComponent(Base):
    """One part of a build at one of the precision levels the buyer sees:
    - "exact model": a reference card (product_id);
    - "only specs": no card, values by the category dictionary ("RTX 3060, 12 GB", the maker not said);
      a GPU may be {"integrated": true} — integrated graphics of an office PC;
    - "not specified": only the seller's text, or nothing."""

    __tablename__ = "build_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("builds.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    slot: Mapped[BuildSlot] = mapped_column(str_enum(BuildSlot))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    # "Only specs": the dictionary category (a storage slot is ssd or hdd) and its values; a CPU adds "model"
    category: Mapped[str | None] = mapped_column(String(32))
    specs: Mapped[dict] = mapped_column(JSON, default=dict)

    build: Mapped[Build] = relationship(back_populates="components")
    product: Mapped[Product | None] = relationship()


class BuildPriceHistory(Base):
    __tablename__ = "build_price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("builds.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency), default=Currency.USD)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    build: Mapped[Build] = relationship(back_populates="price_history")


class TgChannel(Base):
    """A public Telegram channel whose posts are collected from t.me/s/<username> (phase 9); added by hand."""

    __tablename__ = "tg_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(32), default="tashkent")  # its ads have no shop city
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_id: Mapped[int] = mapped_column(Integer, default=0)
    # The seller of its ads: a store of kind "telegram" (no owner can log in)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    # Phase 13: the admin's "Удалить" hides the channel and its ads (the store is blocked), nothing is erased;
    # the last run's log ({fetched, new, parsed, offers, skipped, error}) and its error for the channel list
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_log: Mapped[dict | None] = mapped_column(JSON)
    last_error: Mapped[str | None] = mapped_column(String(200))

    store: Mapped[Store] = relationship()


class TgPost(Base):
    """One collected post: only the cleaned text needed to parse it (no phones, @names) and what came of it."""

    __tablename__ = "tg_posts"
    __table_args__ = (UniqueConstraint("channel_id", "post_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("tg_channels.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # parsed / skipped (reason: no_price, no_model, ad, image_price) / sold / gone
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(32))
    offer_ids: Mapped[list] = mapped_column(JSON, default=list)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Phase 10: chat of a buyer with a store ---------------------------------------------------------------------------

class TopicKind(str, enum.Enum):
    """What a conversation is about."""
    offer = "offer"  # an offer of the store (a product card, new or used)
    build = "build"  # a ready PC of the store
    store = "store"  # a question to the store without a product
    reservation = "reservation"  # a reservation (phase 11): made with it, topic_id = reservations.id


class MessageAuthor(str, enum.Enum):
    buyer = "buyer"
    store = "store"
    system = "system"  # status lines of a reservation (phase 11)


class Conversation(Base):
    """One conversation per buyer + store + topic: "Write" again opens the same one."""

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("buyer_id", "store_id", "topic_kind", "topic_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    topic_kind: Mapped[TopicKind] = mapped_column(str_enum(TopicKind))
    # offers.id / builds.id; 0 for a question to the store (NULL would not be unique in SQLite)
    topic_id: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    buyer: Mapped[User] = relationship()
    store: Mapped[Store] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id")


class Message(Base):
    """Plain text only (up to 2000 characters), no files; shown as text, never as HTML."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    author: Mapped[MessageAuthor] = mapped_column(str_enum(MessageAuthor))
    # Who pressed "Send" (rate limits); empty for system lines
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ChatReport(Base):
    """"Report" on a conversation: kept for the admin panel (phase 13)."""

    __tablename__ = "chat_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(16))  # spam / abuse / fraud / other
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="new")  # new / reviewed (phase 13)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Phase 13: dismissed / block_user / block_store, the admin's comment and when
    resolution: Mapped[str | None] = mapped_column(String(16))
    admin_comment: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class StoreBlock(Base):
    """A buyer blocked by a store: no messages to this store (and, in phase 11, no reservations)."""

    __tablename__ = "store_blocks"
    __table_args__ = (UniqueConstraint("store_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Phase 11: reservations ("put it aside for me") ----------------------------------------------------------------

class ReservationStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"
    ready = "ready"  # ready to be picked up
    issued = "issued"  # the buyer took it (paid in the store)
    cancelled = "cancelled"
    expired = "expired"


class Reservation(Base):
    """A request "put it aside for me" with the buyer's contacts. No money and no delivery: paid and picked up in
    the store. It never changes the stock, the prices, the market price or the monitoring.

    The price is a snapshot at the moment of the reservation (no "it was cheaper" dispute)."""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    # The item: an offer of the store or a build (the other is NULL); the title stays if the item is deleted
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), index=True)
    build_id: Mapped[int | None] = mapped_column(ForeignKey("builds.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    condition: Mapped[Condition] = mapped_column(str_enum(Condition), default=Condition.new)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(str_enum(Currency))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(16))  # +998XXXXXXXXX
    contact: Mapped[str] = mapped_column(String(16))  # call / telegram / chat
    telegram: Mapped[str | None] = mapped_column(String(33))
    pickup_date: Mapped[date | None] = mapped_column(Date)
    pickup_time: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ReservationStatus] = mapped_column(str_enum(ReservationStatus), default=ReservationStatus.new, index=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(8))  # store / buyer
    cancel_reason: Mapped[str | None] = mapped_column(String(16))  # no_stock / price_changed / no_show / other
    cancel_text: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)  # set on confirmation
    buyer_seen: Mapped[bool] = mapped_column(Boolean, default=True)  # False: the status changed, the buyer has not looked
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    demo_key: Mapped[str | None] = mapped_column(String(32))  # constant key of a demo reservation (re-runs keep the id)
    # Where the buyer picks it up (phase 12.1); old reservations are moved to the main branch
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    # Phase 12.2 ("Учёт остатков"): how many items this reservation holds in reserve in its branch (0 = none)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Phase 12.4: the reserved item was sold at the counter — "предложите замену или отмените бронь" (the seller only)
    sold_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    buyer: Mapped[User] = relationship()
    store: Mapped[Store] = relationship()
    offer: Mapped[Offer | None] = relationship()
    build: Mapped[Build | None] = relationship()
    branch: Mapped["Branch | None"] = relationship()
    events: Mapped[list["ReservationEvent"]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan", order_by="ReservationEvent.id")


class ReservationEvent(Base):
    """The status history: who (buyer / store / system) and when."""

    __tablename__ = "reservation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), index=True)
    status: Mapped[ReservationStatus] = mapped_column(str_enum(ReservationStatus))
    by: Mapped[str] = mapped_column(String(8))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reservation: Mapped[Reservation] = relationship(back_populates="events")


# --- Phase 12.1: branches of a store and stock by branch -----------------------------------------------------------

class Branch(Base):
    """A point of the store: one store (one catalog, prices and cabinet) may have several. Exactly one is the main
    one: its city, address, hours and map are also copied to the store row (old code and the API read them there)."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(100))  # "Чиланзар", optional
    city: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(128))
    hours: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))  # empty = the store's phone
    map_url: Mapped[str | None] = mapped_column(String(500))
    map_lat: Mapped[float | None] = mapped_column(Float)
    map_lon: Mapped[float | None] = mapped_column(Float)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    demo_key: Mapped[str | None] = mapped_column(String(32))  # constant key of a demo branch (re-runs keep the id)
    # Phase 12.4: the store's warehouse — a place of storage, not a point for buyers (no storefront, no "Stores",
    # no reservations, not in "есть / нет", the city filter or the market)
    is_warehouse: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    # Price-list column header -> this branch, as the seller confirmed it once ("Чиланзар", "Склад 2")
    columns_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfferStock(Base):
    """Stock of one offer in one branch. Available = quantity - reserved; quantity None with in_stock = "есть,
    количество не указано". The buyer never sees the quantity, only "есть / нет". `reserved` is filled in 12.2."""

    __tablename__ = "offer_stocks"
    __table_args__ = (UniqueConstraint("offer_id", "branch_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int | None] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Phase 12.2: the stock journal ---------------------------------------------------------------------------------

class StockMovement(Base):
    """One change of a quantity or a reserve of an offer in a branch. Never deleted or edited: an undo is a reverse
    record. kind: initial / receipt / sale / adjust / reserve / unreserve / res_sale / import / undo / manual;
    phase 12.4: move_out / move_in ("Выкладка" warehouse -> branch, one doc), return, inventory (a stocktake)."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    delta: Mapped[int] = mapped_column(Integer, default=0)  # quantity change (unknown quantity counts as 0)
    reserved_delta: Mapped[int] = mapped_column(Integer, default=0)
    quantity_before: Mapped[int | None] = mapped_column(Integer)  # None = "есть, количество не указано" / no row
    quantity_after: Mapped[int | None] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float | None] = mapped_column(Float)  # purchase price of a receipt (offer currency)
    price: Mapped[float | None] = mapped_column(Float)  # sale price (sale / sale by a reservation)
    currency: Mapped[str | None] = mapped_column(String(3))
    reason: Mapped[str | None] = mapped_column(String(12))  # adjust: inventory / defect / loss / other
    comment: Mapped[str | None] = mapped_column(String(300))
    doc: Mapped[str | None] = mapped_column(String(24), index=True)  # lines of one receipt document share it
    units: Mapped[int | None] = mapped_column(Integer)  # 12.4: items of a line that does not change the quantity
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id", ondelete="SET NULL"))
    import_id: Mapped[int | None] = mapped_column(ForeignKey("price_imports.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# --- Phase 12.4: stocktake ------------------------------------------------------------------------------------------

class Stocktake(Base):
    """"Ревизия" of one place (a branch or the warehouse): the seller scans every item on the shelf. status:
    counting (kept on the server — a reload loses nothing) -> review (the table of differences) -> applied (the
    differences became "inventory" lines of the journal with `doc`) / cancelled. counts_json: {offer_id: counted};
    result_json: the lines at the end of the count; excluded_json: offer ids the seller left out."""

    __tablename__ = "stocktakes"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="counting", index=True)
    categories_json: Mapped[list] = mapped_column(JSON, default=list)  # category slugs; empty = everything
    counts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[list] = mapped_column(JSON, default=list)
    excluded_json: Mapped[list] = mapped_column(JSON, default=list)
    doc: Mapped[str] = mapped_column(String(24))
    positions: Mapped[int] = mapped_column(Integer, default=0)  # summary of an applied one
    shortage: Mapped[int] = mapped_column(Integer, default=0)
    surplus: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    demo_key: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Phase 12.3: barcodes -------------------------------------------------------------------------------------------

class Barcode(Base):
    """A store's binding: a code on a box -> its offer (and so the reference card). One code — one offer of a store;
    an offer may have several codes. Works for this store at once; the common base (`barcode_codes`) needs two."""

    __tablename__ = "barcodes"
    __table_args__ = (UniqueConstraint("store_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32), index=True)  # normalized: UPC-A is kept as EAN-13 with a 0
    source: Mapped[str] = mapped_column(String(12), default="manual")  # manual / scan / import / demo
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Phase 13: "disputed" = the admin chose another card for this code (the seller sees it; not counted)
    admin_status: Mapped[str | None] = mapped_column(String(10))


class BarcodeCode(Base):
    """The common base: code -> reference card, recomputed from the stores' bindings. confirmed = two different
    stores bound it to the same card (the buyer's search and other stores use only these); pending = one store;
    conflict = stores bound it to different cards — no card, `conflict_json` keeps who and where for the admin."""

    __tablename__ = "barcode_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(10), index=True)  # pending / confirmed / conflict
    stores: Mapped[int] = mapped_column(Integer, default=0)  # stores bound to the card (pending / confirmed)
    conflict_json: Mapped[list] = mapped_column(JSON, default=list)  # [{product_id, stores: [store_id]}]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Phase 13, the admin's decision on a conflict: resolved (admin_product_id is the card) / rejected (no card)
    admin_status: Mapped[str | None] = mapped_column(String(10))
    admin_product_id: Mapped[int | None] = mapped_column(Integer)


# --- Phase 13: the admin ---------------------------------------------------------------------------------------------

class AdminAction(Base):
    """The admin journal: who, when, what and with what. Written by every admin action, never edited."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    admin_email: Mapped[str] = mapped_column(String(255))  # stays readable if the account goes
    action: Mapped[str] = mapped_column(String(32), index=True)  # store_verify / user_block / fix_accept ...
    target_type: Mapped[str] = mapped_column(String(16))  # store / user / report / flag / fix / barcode / channel
    target_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))  # what it was about, as text: a store name, an email
    comment: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(Base):
    """Phase 12.5: the bell. A short text as an i18n key + params (`notify.<kind>` in ru.json), where to go, read or
    not. Made by events of the existing code; `group_key` joins repeats (several messages in one conversation — one
    notification with a number; "заканчивается" once a day per item). Older than 30 days are deleted."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # message / reservation_new / low_stock / ...
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    link: Mapped[str] = mapped_column(String(255))
    group_key: Mapped[str | None] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_key: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
