"""Barcodes (phase 12.3): a code on a box -> the store's offer -> the reference card of the common base.

Check of a code: EAN-13, EAN-8 and UPC-A (12 digits) — by the check digit; UPC-A is kept as EAN-13 with a leading 0
(a scanner may read the same box either way). Other formats (Code 128, a store's own labels) — text of 4–32
characters without spaces.

Bindings: a store binds a code to its offer (`barcodes`) and it works for this store at once. The common base
(`barcode_codes`) is recomputed from all stores' bindings of the code: one store — "pending" (only that store uses
it); two different stores bound it to the same card — "confirmed" (other stores get the card offered, the buyer
finds the card by the code); stores bound it to different cards — "conflict" (no card; kept for the admin).
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Barcode, BarcodeCode, Offer, Product, Store, utcnow

_TEXT = re.compile(r"^[\x21-\x7e]{4,32}$")  # printable ASCII, no spaces
SOURCES = ("manual", "scan", "import", "demo")


class BarcodeError(ValueError):
    """code: format / checksum / taken / offer / not_found (texts in ru.json barcode.error.*)."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code, self.params = code, params


def check_digit(digits: str) -> int:
    """The GTIN check digit of the digits before it (EAN-8, UPC-A, EAN-13): weights 3,1,3,... from the right."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def kind(code: str) -> str:
    if code.isdigit() and len(code) in (8, 12, 13):
        return {8: "ean8", 12: "upca", 13: "ean13"}[len(code)]
    return "text"


def normalize(raw) -> str:
    """The code as it is stored, or BarcodeError: "checksum" (read with an error — scan again) / "format"."""
    code = str(raw if raw is not None else "").strip()
    if isinstance(raw, float) and raw.is_integer():  # a number cell of Excel: 4600000000017.0
        code = str(int(raw))
    if kind(code) != "text":
        if check_digit(code[:-1]) != int(code[-1]):
            raise BarcodeError("checksum")
        return "0" + code if len(code) == 12 else code
    if not _TEXT.match(code):
        raise BarcodeError("format")
    return code


def make_ean13(first12: str) -> str:
    """The demo data: 12 digits + the right check digit."""
    return first12 + str(check_digit(first12))


# --- the common base ------------------------------------------------------------------------------------------------

def refresh_common(db: Session, code: str) -> BarcodeCode | None:
    """Recomputes the common record of one code from every store's binding of it."""
    db.flush()
    rows = db.execute(select(Barcode.store_id, Offer.product_id).join(Offer, Barcode.offer_id == Offer.id)
                      .where(Barcode.code == code)).all()
    common = db.scalar(select(BarcodeCode).where(BarcodeCode.code == code))
    if not rows:
        if common is not None:
            db.delete(common)
        return None
    by_product: dict[int, set[int]] = {}
    for store_id, product_id in rows:
        by_product.setdefault(product_id, set()).add(store_id)
    if common is None:
        common = BarcodeCode(code=code)
        db.add(common)
    if len(by_product) > 1:
        common.status, common.product_id, common.stores = "conflict", None, 0
        common.conflict_json = [{"product_id": p, "stores": sorted(s)} for p, s in sorted(by_product.items())]
    else:
        (product_id, stores), = by_product.items()
        common.product_id, common.stores, common.conflict_json = product_id, len(stores), []
        common.status = "confirmed" if len(stores) >= 2 else "pending"
    common.updated_at = utcnow()
    return common


def confirmed_product(db: Session, raw) -> Product | None:
    """The card of a code in the confirmed common base (the buyer's search, other stores' suggestion)."""
    try:
        code = normalize(raw)
    except BarcodeError:
        return None
    common = db.scalar(select(BarcodeCode).where(BarcodeCode.code == code, BarcodeCode.status == "confirmed"))
    return db.get(Product, common.product_id) if common is not None and common.product_id else None


# --- a store's bindings ---------------------------------------------------------------------------------------------

def store_binding(db: Session, store: Store, code: str) -> Barcode | None:
    return db.scalar(select(Barcode).where(Barcode.store_id == store.id, Barcode.code == code))


def bind(db: Session, store: Store, offer: Offer, raw, *, user_id: int | None = None, source: str = "manual",
         is_demo: bool = False, commit: bool = True) -> Barcode:
    """Binds a code to the store's offer. The same code on another offer of the store -> "taken" (with its name)."""
    if offer is None or offer.store_id != store.id:
        raise BarcodeError("offer")
    code = normalize(raw)
    existing = store_binding(db, store, code)
    if existing is not None:
        if existing.offer_id != offer.id:
            other = db.get(Offer, existing.offer_id)
            raise BarcodeError("taken", name=other.product.normalized_name if other else "", offer_id=existing.offer_id)
        return existing
    b = Barcode(store_id=store.id, code=code, source=source if source in SOURCES else "manual", user_id=user_id,
                is_demo=is_demo)
    offer.barcodes.append(b)
    refresh_common(db, code)
    if commit:
        db.commit()
    return b


def unbind(db: Session, store: Store, barcode_id: int) -> None:
    b = db.get(Barcode, barcode_id)
    if b is None or b.store_id != store.id:
        raise BarcodeError("not_found")
    code = b.code
    offer = db.get(Offer, b.offer_id)
    if offer is not None and b in offer.barcodes:
        offer.barcodes.remove(b)  # delete-orphan: the row goes, the loaded list follows
    else:
        db.delete(b)
    refresh_common(db, code)
    db.commit()


def refresh_offer(db: Session, offer: Offer) -> None:
    """The offer moved to another card ("not this product"): its codes' common records follow."""
    for b in offer.barcodes:
        refresh_common(db, b.code)


def bind_many(db: Session, store: Store, pairs: list[tuple[Offer, object]], *, user_id: int | None = None,
              source: str = "import") -> dict:
    """A price list or a stock file with a barcode column: wrong codes and codes of another offer are skipped.
    A cell may hold several codes: "4600000000017, 4600000000024"."""
    stats = {"bound": 0, "skipped": 0}
    for offer, cell in pairs:
        for raw in re.split(r"[,;\s]+", str(int(cell)) if isinstance(cell, float) and cell.is_integer() else str(cell)):
            if not raw:
                continue
            try:
                code = normalize(raw)
                if store_binding(db, store, code) is None:
                    bind(db, store, offer, code, user_id=user_id, source=source, commit=False)
                    stats["bound"] += 1
                elif store_binding(db, store, code).offer_id != offer.id:
                    stats["skipped"] += 1
            except BarcodeError:
                stats["skipped"] += 1
    db.commit()
    return stats


def codes(offer: Offer) -> list[dict]:
    return [{"id": b.id, "code": b.code} for b in offer.barcodes]


def lookup(db: Session, store: Store, raw) -> dict:
    """A scan in the cabinet: the store's own binding -> the offer; otherwise "unknown" with the card of the
    confirmed common base (and the store's offer on it, if any) as a suggestion. A wrong code -> BarcodeError."""
    code = normalize(raw)
    own = store_binding(db, store, code)
    if own is not None:
        return {"status": "found", "code": code, "offer_id": own.offer_id}
    suggestion = None
    product = confirmed_product(db, code)
    if product is not None:
        mine = db.scalar(select(Offer).where(Offer.store_id == store.id, Offer.product_id == product.id))
        suggestion = {"product_id": product.id, "name": product.normalized_name,
                      "category": product.category.slug if product.category else "other",
                      "my_offer_id": mine.id if mine is not None else None}
    return {"status": "unknown", "code": code, "suggestion": suggestion}
