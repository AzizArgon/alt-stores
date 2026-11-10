"""Stock by branch from a price list (phase 12.1).

Two ways:
- branch columns: the cleaner finds stock columns of branches ("Чиланзар | Юнусабад"); the seller confirms once
  which column is which branch, the match is remembered (Branch.columns_json) and offered next time;
- the price list of one branch (PriceImport.branch_id): only that branch's stock changes; "full / append" work
  inside it. In "full" a tracked offer missing from the file is "нет" in this branch only; offers the store does
  not track by branch are not touched (another branch may have them).
A price list without branch info works as before; for an offer tracked by branch "sold out" = "нет" everywhere,
"in stock" with no branch available = "есть" in the main branch (the list says it is there, it does not say where).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Branch, Offer, PriceImport, Store
from app.services.branches import available, main_branch, recompute_offer, set_stock, store_branches


class ColumnsError(ValueError):
    pass


def known_branch_columns(db: Session, store_id: int) -> set[str]:
    return {h.lower() for b in store_branches(db, store_id) for h in (b.columns_json or [])}


def _suggest(branches: list[Branch], header: str) -> int | None:
    low = header.lower().strip()
    for b in branches:
        if low in {h.lower() for h in (b.columns_json or [])}:
            return b.id
    for b in branches:
        for word in filter(None, ((b.name or "").lower(), (b.address or "").lower())):
            if low and (low in word or word in low):
                return b.id
    return None


def branch_info(db: Session, imp: PriceImport) -> dict:
    """For the preview: the branch columns found, their match (confirmed or suggested) and the branch scope."""
    headers = (imp.stats_json or {}).get("branch_columns") or []
    branches = store_branches(db, imp.store_id)
    mapping = imp.columns_json if imp.columns_json is not None else {h: _suggest(branches, h) for h in headers}
    return {"headers": headers, "mapping": mapping, "confirmed": imp.columns_json is not None or not headers,
            "branch_id": imp.branch_id}


def confirm_columns(db: Session, store: Store, imp: PriceImport, mapping: dict[str, int | None]) -> None:
    """The seller's match: saved on the upload and remembered on the branches for the next price list."""
    headers = (imp.stats_json or {}).get("branch_columns") or []
    branches = {b.id: b for b in store_branches(db, store.id)}
    clean = {}
    for h in headers:
        bid = mapping.get(h)
        if bid is not None and bid not in branches:
            raise ColumnsError("branch")
        clean[h] = bid
    used = [b for b in clean.values() if b is not None]
    if len(used) != len(set(used)):
        raise ColumnsError("twice")  # two columns for one branch
    imp.columns_json = clean
    for b in branches.values():
        kept = [h for h in (b.columns_json or []) if h.lower() not in {x.lower() for x in clean}]
        b.columns_json = kept + [h for h, bid in clean.items() if bid == b.id]
    db.flush()


def _mapped(imp: PriceImport) -> dict[str, int]:
    return {h: bid for h, bid in (imp.columns_json or {}).items() if bid is not None}


def _value_stock(value) -> tuple[int | None, bool | None]:
    """A cell value -> (quantity, present): 5 -> (5, None); True -> (None, True); False / None (empty) -> (0, None)."""
    if value is True:
        return None, True
    if type(value) is int:
        return max(0, value), None
    return 0, None


def row_targets(imp: PriceImport, r: dict, in_stock: bool) -> dict[int, tuple[int | None, bool | None]] | None:
    """What the row sets per branch: {branch_id: (quantity, present)}; None = no branch info (the general flag)."""
    if imp.branch_id:
        cells = r.get("branches") or {}
        if in_stock and len(cells) == 1:
            q, present = _value_stock(next(iter(cells.values())))
            return {imp.branch_id: (q, present)}
        return {imp.branch_id: (None, True) if in_stock else (0, None)}
    mapped = _mapped(imp)
    cells = r.get("branches") or {}
    if mapped and cells:
        return {bid: _value_stock(cells.get(h)) if r.get("price") is not None else (0, None) for h, bid in mapped.items()}
    return None


def apply_row_stock(db: Session, imp: PriceImport, store: Store, offer: Offer, r: dict, in_stock: bool) -> bool:
    """Sets the offer's stock from one row; returns the general "в наличии" after it."""
    targets = row_targets(imp, r, in_stock)
    if targets is not None:
        for bid, (q, present) in targets.items():
            set_stock(offer, bid, quantity=q, present=present)
    elif offer.stocks:
        if not in_stock:
            for s in list(offer.stocks):
                set_stock(offer, s.branch_id, quantity=0)
        elif not any(available(s) for s in offer.stocks):
            main = main_branch(db, store.id)
            set_stock(offer, main.id if main else offer.stocks[0].branch_id, present=True)
    else:
        offer.is_in_stock = in_stock
    if offer.stocks:
        recompute_offer(offer)
    if r.get("price") is None:
        offer.is_in_stock = False
    return offer.is_in_stock


def take_off_sale(imp: PriceImport, offer: Offer) -> bool:
    """A full price list without this offer. Returns True when something changed (to remember it for undo first)."""
    if imp.branch_id:
        row = next((s for s in offer.stocks if s.branch_id == imp.branch_id), None)
        if row is None or not available(row):
            return False  # not tracked by branch here: another branch may have it
        return True
    return offer.is_in_stock


def do_take_off_sale(imp: PriceImport, offer: Offer) -> None:
    if imp.branch_id:
        set_stock(offer, imp.branch_id, quantity=0)
        return
    for s in list(offer.stocks):
        set_stock(offer, s.branch_id, quantity=0)
    offer.is_in_stock = False


def _avail_after(q, present) -> bool:
    return bool(present) if q is None else q > 0


def plan_branch_stock(db: Session, imp: PriceImport, store: Store, matched: list[tuple[Offer | None, dict, bool]],
                      unseen: list[Offer], mode: str) -> dict:
    """"What will change" by branch: per branch how many goods appear ("есть") and run out ("нет"); and the
    general "в наличии" after the upload for tracked offers {offer id: bool}."""
    if imp.columns_json is None and (imp.stats_json or {}).get("branch_columns"):
        # Not confirmed yet: the summary follows the suggested match (publishing waits for the confirmation)
        suggested = branch_info(db, imp)["mapping"]
        imp.columns_json = suggested
        try:
            return plan_branch_stock(db, imp, store, matched, unseen, mode)
        finally:
            imp.columns_json = None
    branches = {b.id: b for b in store_branches(db, store.id)}
    counts = {bid: {"appear": 0, "run_out": 0} for bid in branches}
    general: dict[int, bool] = {}
    for offer, r, in_stock in matched:
        targets = row_targets(imp, r, in_stock)
        rows = {s.branch_id: available(s) for s in (offer.stocks if offer is not None else [])}
        after = dict(rows)
        if targets is not None:
            for bid, (q, present) in targets.items():
                after[bid] = _avail_after(q, present)
        elif rows:
            if not in_stock:
                after = {b: False for b in rows}
        for bid in set(after) | set(rows):
            if bid in counts and rows.get(bid, False) != after.get(bid, False):
                counts[bid]["appear" if after.get(bid) else "run_out"] += 1
        if offer is not None and after:
            general[offer.id] = (any(after.values()) or (targets is None and in_stock)) and r.get("price") is not None
    if mode == "full":
        for offer in unseen:
            if take_off_sale(imp, offer):
                for s in offer.stocks:
                    if (not imp.branch_id or s.branch_id == imp.branch_id) and available(s) and s.branch_id in counts:
                        counts[s.branch_id]["run_out"] += 1
                if offer.stocks:
                    general[offer.id] = any(available(s) for s in offer.stocks
                                            if imp.branch_id and s.branch_id != imp.branch_id)
    items = [{"branch_id": bid, "name": b.name, "address": b.address, "city": b.city, **counts[bid]}
             for bid, b in branches.items() if counts[bid]["appear"] or counts[bid]["run_out"]]
    return {"branches": items, "general": general}


def stocked_offers(db: Session, store_id: int) -> list[Offer]:
    return list(db.scalars(select(Offer).where(Offer.store_id == store_id)))
