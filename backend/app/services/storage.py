"""Phase 14: all work with stored files goes through this module — save, url, delete.

Now the files are on disk (`<ALT_LOCAL_DIR>/media`, on the server `data/media`, mounted into the containers; the web
container serves them with a long cache). An S3-compatible storage (Cloudflare R2, Backblaze B2) is added later as one
more class with the same three methods and chosen by STORAGE_BACKEND in .env (docs/deploy.md).

Keys are made here, never taken from the user: random hex + a fixed suffix, so no path from outside reaches the disk.
"""

import re
import secrets
from pathlib import Path
from typing import Protocol

from app.core.config import LOCAL_DIR, settings

KEY_RE = re.compile(r"^[0-9a-f]{32}(_[a-z]{1,8})?\.(webp|jpg|png)$")


def new_key(suffix: str = "", ext: str = "webp") -> str:
    return f"{secrets.token_hex(16)}{'_' + suffix if suffix else ''}.{ext}"


def check_key(key: str) -> str:
    if not KEY_RE.match(key or ""):
        raise ValueError(f"bad storage key: {key!r}")
    return key


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str = "image/webp") -> None: ...
    def url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...
    def read(self, key: str) -> bytes: ...


class LocalStorage:
    """Files in one folder; the URL is `media_url` + key (the backend serves /media locally, nginx on the server)."""

    def __init__(self, root: Path, base_url: str):
        self.root = Path(root)
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        # Two-letter subfolders so one folder never holds tens of thousands of files
        key = check_key(key)
        return self.root / key[:2] / key

    def save(self, key: str, data: bytes, content_type: str = "image/webp") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def url(self, key: str) -> str:
        key = check_key(key)
        return f"{self.base_url}/{key[:2]}/{key}"

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except ValueError:
            pass

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()


def media_root() -> Path:
    return Path(settings.media_dir) if settings.media_dir else LOCAL_DIR / "media"


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.storage_backend != "local":
            # S3 is described in docs/deploy.md; not connected in the diploma version
            raise RuntimeError(f"storage backend {settings.storage_backend!r} is not available")
        _storage = LocalStorage(media_root(), settings.media_url)
    return _storage


def set_storage(storage: Storage | None) -> None:
    """Tests (and a future S3 class) swap the implementation here."""
    global _storage
    _storage = storage
