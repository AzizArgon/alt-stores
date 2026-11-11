"""The store's point in Yandex Maps (phase 12): only a link check, no own map, no keys, no requests from the server.

Accepted: yandex.uz/maps, yandex.ru/maps, yandex.com/maps (also with www. or maps.yandex.*) and the short links
yandex.*/maps/-/... that "Share" -> "Copy link" gives. Coordinates are kept when the link has them (ll / pt /
whatshere[point] = "longitude,latitude"); a link without them is fine too.
"""

import re
from urllib.parse import parse_qs, unquote, urlsplit

HOSTS = re.compile(r"^(?:www\.|maps\.)?yandex\.(?:uz|ru|com)$")
COORD_PARAMS = ("pt", "ll", "whatshere[point]")


class MapLinkError(ValueError):
    """Not a Yandex Maps link: the code goes to the client (texts in ru.json store.mapError)."""


def _coords(query: str) -> tuple[float | None, float | None]:
    params = parse_qs(query)
    for name in COORD_PARAMS:
        for value in params.get(name, []):
            m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", unquote(value))
            if m:
                lon, lat = float(m.group(1)), float(m.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
    return None, None


def parse_map_url(url: str | None) -> tuple[str | None, float | None, float | None]:
    """(link, latitude, longitude); an empty link is (None, None, None). Raises MapLinkError for other sites."""
    url = (url or "").strip()
    if not url:
        return None, None, None
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not HOSTS.match(host):
        raise MapLinkError("map_url")
    if not host.startswith("maps.") and not (parts.path == "/maps" or parts.path.startswith("/maps/")):
        raise MapLinkError("map_url")
    lat, lon = _coords(parts.query)
    return url, lat, lon
