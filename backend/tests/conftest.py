import pytest

from app.services import importer


@pytest.fixture(autouse=True)
def no_cbu_requests(monkeypatch):
    """Tests never ask cbu.uz: the USD rate is unknown, USD prices need no conversion."""
    monkeypatch.setattr(importer, "get_usd_rate", lambda db: None)


@pytest.fixture(autouse=True)
def photo_storage(tmp_path):
    """Phase 14: photos made by tests (demo seeding too) go to a temporary folder, never to _local/media."""
    from app.services import storage

    storage.set_storage(storage.LocalStorage(tmp_path / "media", "/media"))
    yield
    storage.set_storage(None)
