"""Phase 12: the store address and Yandex Maps link, the store page and the "Stores" list."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import Store, StoreKind, User
from app.services.importer import publish_import
from app.services.maps import MapLinkError, parse_map_url
from tests.test_import_modes import FIRST, _imp, db  # noqa: F401  (the db fixture)
from tests.test_publish import _row


@pytest.mark.parametrize("url", [
    "https://yandex.uz/maps/10335/tashkent/?ll=69.279737%2C41.311151&z=17",
    "https://yandex.ru/maps/-/CDqXbG~a",
    "yandex.com/maps/org/alt/12345/",
    "https://www.yandex.uz/maps/?pt=69.28,41.31",
    "https://maps.yandex.ru/?text=Tashkent",
])
def test_yandex_maps_links_are_accepted(url):
    assert parse_map_url(url)[0].startswith("https://")


@pytest.mark.parametrize("url", [
    "https://google.com/maps/place/x", "https://yandex.uz/search/?text=x", "https://evil.com/yandex.uz/maps",
    "https://yandex.uz.evil.com/maps/", "https://2gis.uz/tashkent", "javascript:alert(1)",
])
def test_other_links_are_refused(url):
    with pytest.raises(MapLinkError):
        parse_map_url(url)


def test_coordinates_are_kept_only_when_present():
    _, lat, lon = parse_map_url("https://yandex.uz/maps/10335/tashkent/?ll=69.279737%2C41.311151&z=17")
    assert (lat, lon) == (41.311151, 69.279737)
    assert parse_map_url("https://yandex.ru/maps/-/CDqXbG~a")[1:] == (None, None)
    assert parse_map_url("") == (None, None, None)


def _shop(db, email, city="tashkent", kind=StoreKind.shop, verified=False):
    store = Store(owner=User(email=email, password_hash="x"), name=email.split("@")[0], city=city, kind=kind,
                  is_verified=verified, address="ул. Навои, 12", hours="Пн–Сб 10:00–19:00")
    db.add(store)
    db.commit()
    return store


@pytest.fixture
def client(db):
    from main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_store_list_by_city_without_telegram_channels(db, client):
    a = _shop(db, "a@example.com", verified=True)
    _shop(db, "b@example.com", city="samarkand")
    _shop(db, "tg@example.com", kind=StoreKind.telegram)
    publish_import(db, _imp(db, a), a, FIRST)
    items = client.get("/api/catalog/stores").json()["items"]
    assert [s["name"] for s in items] == ["a", "b"]
    assert items[0]["in_stock"] == 4 and items[0]["hours"] == "Пн–Сб 10:00–19:00"
    assert [s["name"] for s in client.get("/api/catalog/stores?city=samarkand").json()["items"]] == ["b"]
    assert [s["name"] for s in client.get("/api/catalog/stores?city=all").json()["items"]] == ["a", "b"]


def test_store_page_and_its_goods(db, client):
    a = _shop(db, "a@example.com")
    publish_import(db, _imp(db, a), a, FIRST + [_row(9, "Samsung DDR4 4GB", None)])
    page = client.get(f"/api/catalog/stores/{a.id}").json()
    assert page["address"] == "ул. Навои, 12" and page["counts"] == {"new": 4, "used": 0} and page["builds"] == []
    goods = client.get(f"/api/catalog/stores/{a.id}/offers?group=new").json()
    assert goods["total"] == 4 and all(i["own"] for i in goods["items"])
    tg = _shop(db, "tg@example.com", kind=StoreKind.telegram)
    assert client.get(f"/api/catalog/stores/{tg.id}").status_code == 404


def test_profile_saves_address_hours_and_map_link(db, client):
    from app.core.security import create_access_token
    from app.db.models import UserRole

    a = _shop(db, "a@example.com")
    a.owner.role = UserRole.seller
    db.commit()
    h = {"Authorization": f"Bearer {create_access_token(a.owner.id, 'seller')}"}
    body = {"name": "Alt", "city": "tashkent", "address": "ул. Навои, 12, ориентир — ЦУМ", "hours": "Пн–Сб 10–19",
            "map_url": "https://yandex.uz/maps/?ll=69.28%2C41.31&z=16"}
    bad = client.put("/api/stores/me", json={**body, "map_url": "https://google.com/maps"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "map_url"
    saved = client.put("/api/stores/me", json=body, headers=h).json()
    assert saved["map_lat"] == 41.31 and saved["map_lon"] == 69.28 and saved["hours"] == "Пн–Сб 10–19"
    # Phase 12.1: the address now lives in the main branch; without a link the coordinates are cleared
    main = saved["branches"][0]
    assert main["is_main"] and main["map_lat"] == 41.31
    edit = {"city": "tashkent", "address": main["address"], "landmark": "ЦУМ", "map_url": None}
    assert client.put(f"/api/stores/me/branches/{main['id']}", json={**edit, "address": ""}, headers=h).status_code == 422
    assert client.put(f"/api/stores/me/branches/{main['id']}", json=edit, headers=h).json()["map_lat"] is None
    assert db.scalar(select(Store).where(Store.id == a.id)).address.startswith("ул. Навои")


# --- Phase 17.5: the profile has only the general fields; where to go lives in the branches --------------------------

def _seller(db, client, email):
    from app.core.security import create_access_token
    from app.db.models import UserRole

    a = _shop(db, email)
    a.owner.role = UserRole.seller
    db.commit()
    return a, {"Authorization": f"Bearer {create_access_token(a.owner.id, 'seller')}"}


def test_profile_without_address_saves_general_fields_and_has_no_branches(db, client):
    a, h = _seller(db, client, "noaddr@example.com")
    a.address, a.district, a.hours = None, "Чиланзар", "Пн–Сб 10–19"  # old fields of the top block, no address
    db.commit()
    r = client.put("/api/stores/me", json={"name": "Без адреса", "phone": "+998 90 000 00 00", "reservation_days": 3}, headers=h)
    assert r.status_code == 200
    out = r.json()
    assert out["name"] == "Без адреса" and out["reservation_days"] == 3 and out["branches"] == []
    db.refresh(a)
    assert a.district == "Чиланзар" and a.hours == "Пн–Сб 10–19"  # the old values are kept in the base


def test_profile_ignores_location_once_there_are_branches(db, client):
    a, h = _seller(db, client, "withbr@example.com")
    first = client.post("/api/stores/me/branches", headers=h, json={"city": "samarkand", "address": "ул. Регистан, 5",
                                                                    "landmark": "у площади", "hours": "9–18"}).json()
    assert len(first["branches"]) == 1 and first["city"] == "samarkand" and first["address"] == "ул. Регистан, 5"
    out = client.put("/api/stores/me", json={"name": "Новое имя", "city": "tashkent", "address": "другой адрес"},
                     headers=h).json()
    assert out["name"] == "Новое имя" and out["city"] == "samarkand" and out["address"] == "ул. Регистан, 5"
    assert len(out["branches"]) == 1


def test_old_top_address_becomes_the_first_branch(db):
    from app.services.branches import migrate_branches, store_branches

    old = _shop(db, "old@example.com")
    old.city, old.district, old.address, old.hours = "bukhara", "Старый город", "ул. Накшбанди, 41", "Пн–Пт 9–18"
    old.map_url = "https://yandex.uz/maps/-/CDabc"
    empty = _shop(db, "empty@example.com")  # no address: nothing to move, stays without branches
    empty.address = None
    db.commit()
    assert migrate_branches(db) >= 1
    (b,) = store_branches(db, old.id)
    assert (b.city, b.landmark, b.address, b.hours, b.map_url, b.is_main) == (
        "bukhara", "Старый город", "ул. Накшбанди, 41", "Пн–Пт 9–18", "https://yandex.uz/maps/-/CDabc", True)
    assert store_branches(db, empty.id) == []
    assert migrate_branches(db) == 0  # once: a second start makes nothing new


def test_storefront_shows_the_address_of_the_branches(db, client):
    from app.services.catalog import store_brief

    a, h = _seller(db, client, "front@example.com")
    client.post("/api/stores/me/branches", headers=h, json={"city": "fergana", "address": "ул. Мустакиллик, 25",
                                                            "landmark": "у базара"})
    client.post("/api/stores/me/branches", headers=h, json={"city": "tashkent", "address": "ул. Навои, 7",
                                                            "landmark": "ЦУМ"})
    db.expire_all()
    store = db.get(Store, a.id)
    brief = store_brief(store)
    assert (brief["city"], brief["address"], brief["district"]) == ("fergana", "ул. Мустакиллик, 25", "у базара")
    page = client.get(f"/api/catalog/stores/{a.id}").json()
    assert "branches" in page, page
    assert {b["address"] for b in page["branches"]} == {"ул. Мустакиллик, 25", "ул. Навои, 7"}


def test_startup_with_only_a_warehouse_and_no_branch(db):
    """Age on the server, 17.11: stock mode, "Склад" on, no branch and no address — the startup must not fail."""
    from app.db.models import Branch
    from app.services.branches import ensure_main_branch, migrate_branches, store_branches, warehouse_of

    a = _shop(db, "wh@example.com")
    a.address = None
    db.add(Branch(store_id=a.id, city="tashkent", address="", is_warehouse=True))
    b = _shop(db, "wh2@example.com")  # an address and only a warehouse: the address still becomes the first branch
    db.add(Branch(store_id=b.id, city="tashkent", address="", is_warehouse=True))
    db.commit()
    migrate_branches(db)
    assert ensure_main_branch(db, a) is None and store_branches(db, a.id) == [] and warehouse_of(db, a.id) is not None
    (main,) = store_branches(db, b.id)
    assert main.is_main and main.address == "ул. Навои, 12" and not warehouse_of(db, b.id).is_main


def test_add_branch_to_a_store_like_age(db, client):
    """Age on the server, 18.11: stock mode, the warehouse switched off but its row kept, no branch, no address.
    An empty landmark answered a bare 422 that the form showed as "Сервер недоступен"; now a code, then it works."""
    from app.db.models import Branch
    from app.services.branches import store_branches, warehouse_of

    a, h = _seller(db, client, "agelike@example.com")
    a.address, a.district, a.stock_mode, a.has_warehouse = None, "Чиланзар", "stock", False
    db.add(Branch(store_id=a.id, city="tashkent", address="", is_warehouse=True))
    db.commit()
    for body, code in [({"city": "tashkent", "address": "ул. Бунёдкор, 1", "landmark": None}, "landmark"),
                       ({"city": "tashkent", "address": "", "landmark": "ЦУМ"}, "address"),
                       ({"address": "ул. Бунёдкор, 1", "landmark": "ЦУМ"}, "city")]:
        res = client.post("/api/stores/me/branches", json=body, headers=h)
        assert res.status_code == 422 and res.json()["detail"] == {"code": code}
    res = client.post("/api/stores/me/branches", json={"city": "tashkent", "address": "ул. Бунёдкор, 1", "landmark": "ЦУМ"},
                      headers=h)
    assert res.status_code == 201, res.text
    (b,) = store_branches(db, a.id)
    assert b.is_main and b.address == "ул. Бунёдкор, 1" and not warehouse_of(db, a.id).is_main
    assert [x["address"] for x in res.json()["branches"]] == ["ул. Бунёдкор, 1"]
    assert client.get(f"/api/catalog/stores/{a.id}").status_code == 200
