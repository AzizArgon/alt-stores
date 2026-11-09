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
    saved = client.put("/api/stores/me", json=body, headers=h).json()
    assert saved["map_lat"] == 41.31 and saved["map_lon"] == 69.28 and saved["hours"] == "Пн–Сб 10–19"
    bad = client.put("/api/stores/me", json={**body, "map_url": "https://google.com/maps"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "map_url"
    assert client.put("/api/stores/me", json={**body, "address": ""}, headers=h).status_code == 422
    # Without a link the coordinates are cleared
    assert client.put("/api/stores/me", json={**body, "map_url": None}, headers=h).json()["map_lat"] is None
    assert db.scalar(select(Store).where(Store.id == a.id)).address.startswith("ул. Навои")
