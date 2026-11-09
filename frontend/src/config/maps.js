// The store's point in Yandex Maps (phase 12): no own map, no keys. The same check as backend/app/services/maps.py
const HOST = /^(?:www\.|maps\.)?yandex\.(?:uz|ru|com)$/i
const BASE = 'https://yandex.uz/maps/'

// Only Yandex Maps: yandex.uz|ru|com/maps/..., short links /maps/-/..., maps.yandex.*; empty is fine (optional)
export function isYandexMapsUrl(value) {
  const raw = (value || '').trim()
  if (!raw) return true
  let url
  try {
    url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`)
  } catch {
    return false
  }
  if (!['http:', 'https:'].includes(url.protocol) || !HOST.test(url.hostname)) return false
  return url.hostname.toLowerCase().startsWith('maps.') || url.pathname === '/maps' || url.pathname.startsWith('/maps/')
}

const hasPoint = (store) => store?.map_lat != null && store?.map_lon != null
// "Tashkent, Navoi st. 12": the search text when the store gave no link
export const addressText = (store, cityName) => [cityName, store?.address].filter(Boolean).join(', ')

// "Open in Yandex Maps": the store's own link, else a search of the address in its city
export function mapsLink(store, cityName) {
  if (store?.map_url) return store.map_url
  if (!store?.address) return null
  return `${BASE}?text=${encodeURIComponent(addressText(store, cityName))}`
}

// "Route": Yandex Maps builds it from where the buyer is to the store (coordinates when known, else the address)
export function routeLink(store, cityName) {
  if (hasPoint(store)) return `${BASE}?rtext=~${store.map_lat},${store.map_lon}&rtt=auto`
  if (!store?.address) return null
  return `${BASE}?rtext=~${encodeURIComponent(addressText(store, cityName))}&rtt=auto`
}
