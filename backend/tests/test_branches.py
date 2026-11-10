"""Phase 12.1: branches of a store and stock by branch."""

import pytest
from sqlalchemy import select

from app.db.models import Branch, Offer, Reservation, Store, StoreKind, User
from app.services import branches as br
from app.services.importer import publish_import
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row


def _shop(db, email="a@example.com", city="tashkent", address="ул. Навои, 12"):
    store = Store(owner=User(email=email, password_hash="x"), name=email.split("@")[0], city=city, address=address,
                  district="ЦУМ", hours="Пн–Сб 10–19", map_url="https://yandex.uz/maps/?ll=69.28%2C41.31",
                  map_lat=41.31, map_lon=69.28)
    db.add(store)
    db.commit()
    return store


def _data(city="tashkent", address="ул. Бабура, 5", landmark="рынок", **kw):
    return {"city": city, "address": address, "landmark": landmark, **kw}


def test_store_address_moves_to_its_main_branch_without_losses(db):
    store = _shop(db)
    no_address = _shop(db, "b@example.com", address=None)
    channel = Store(owner=User(email="c@example.com", password_hash="x"), name="@ch", kind=StoreKind.telegram)
    db.add(channel)
    db.commit()
    assert br.migrate_branches(db) == 1
    main = br.main_branch(db, store.id)
    assert (main.city, main.address, main.landmark, main.hours, main.map_url, main.map_lat, main.map_lon) == (
        "tashkent", "ул. Навои, 12", "ЦУМ", "Пн–Сб 10–19", store.map_url, 41.31, 69.28)
    assert br.main_branch(db, no_address.id) is None and br.main_branch(db, channel.id) is None
    assert br.migrate_branches(db) == 0  # once
    assert len(br.store_branches(db, store.id)) == 1


def test_old_reservations_go_to_the_main_branch(db):
    store = _shop(db)
    r = Reservation(buyer=User(email="buyer@example.com", password_hash="x"), store=store, title="x", price=1,
                    currency="USD", name="A", phone="+998901234567", contact="call")
    db.add(r)
    db.commit()
    br.migrate_branches(db)
    assert r.branch_id == br.main_branch(db, store.id).id


def test_exactly_one_main_branch_and_it_is_the_store_address(db):
    store = _shop(db)
    br.migrate_branches(db)
    second = br.save_branch(db, store, _data(city="samarkand", address="ул. Регистан, 1"))
    assert not second.is_main
    br.make_main(db, store, second)
    assert [b.id for b in db.scalars(select(Branch).where(Branch.is_main.is_(True)))] == [second.id]
    assert (store.city, store.address, store.district) == ("samarkand", "ул. Регистан, 1", "рынок")


def test_main_and_last_branch_cannot_be_deleted(db):
    store = _shop(db)
    br.migrate_branches(db)
    main = br.main_branch(db, store.id)
    with pytest.raises(br.BranchError, match="delete_main"):
        br.delete_branch(db, store, main)
    other = br.save_branch(db, store, _data())
    br.delete_branch(db, store, other)
    assert len(br.store_branches(db, store.id)) == 1


@pytest.mark.parametrize("bad, code", [({"address": ""}, "address"), ({"landmark": " "}, "landmark"),
                                       ({"city": "moscow"}, "city"), ({"map_url": "https://google.com/maps"}, "map_url")])
def test_branch_needs_address_landmark_known_city_and_yandex_link(db, bad, code):
    store = _shop(db)
    with pytest.raises(br.BranchError, match=code):
        br.save_branch(db, store, {**_data(), **bad})


def test_in_stock_means_available_above_zero(db):
    store = _shop(db)
    br.migrate_branches(db)
    a, b = br.main_branch(db, store.id), br.save_branch(db, store, _data())
    publish_import(db, _imp(db, store), store, FIRST[:1])
    offer = db.scalar(select(Offer))
    br.set_stock(offer, a.id, quantity=2)
    assert offer.is_in_stock
    row = br.set_stock(offer, a.id, quantity=0)
    assert not br.available(row) and not offer.is_in_stock
    row.quantity, row.reserved = 3, 3  # all reserved (12.2): nothing available
    assert not br.available(row)
    br.set_stock(offer, b.id, present=True)  # "есть, количество не указано"
    assert offer.is_in_stock and next(s for s in offer.stocks if s.branch_id == b.id).quantity is None
