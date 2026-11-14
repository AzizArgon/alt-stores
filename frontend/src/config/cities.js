// City choice in the header: 'all' + the regional centres of Uzbekistan. Names are in ru.json (cities.*)
export const CITIES = [
  'all', 'tashkent', 'samarkand', 'bukhara', 'andijan', 'fergana', 'namangan',
  'nukus', 'urgench', 'karshi', 'termez', 'navoi', 'jizzakh', 'gulistan', 'nurafshan',
]
// A store is in one city (the same list on the server: backend/app/db/seed.py CITIES)
export const STORE_CITIES = CITIES.filter((c) => c !== 'all')

// The city for API requests: none = all of Uzbekistan
export const cityParam = (city) => (city && city !== 'all' ? city : undefined)

// Phase 16.2: "Определить" — the browser gives coordinates, the city is the nearest of ours (no outside services).
// Centres of the regional cities [latitude, longitude]
export const CITY_COORDS = {
  tashkent: [41.2995, 69.2401], samarkand: [39.6542, 66.9597], bukhara: [39.7747, 64.4286],
  andijan: [40.7821, 72.3442], fergana: [40.3864, 71.7864], namangan: [40.9983, 71.6726],
  nukus: [42.4531, 59.6103], urgench: [41.55, 60.6333], karshi: [38.8606, 65.7891],
  termez: [37.2242, 67.2783], navoi: [40.0844, 65.3792], jizzakh: [40.1158, 67.8422],
  gulistan: [40.4897, 68.7842], nurafshan: [41.0167, 69.3417],
}
// Farther than this from every city of the list = not "ours": all of Uzbekistan
export const NEAR_KM = 80

const km = ([lat1, lon1], [lat2, lon2]) => {
  const rad = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(a))
}

export function nearestCity(lat, lon) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return 'all'
  let best = 'all'
  let bestKm = NEAR_KM
  for (const [city, point] of Object.entries(CITY_COORDS)) {
    const d = km([lat, lon], point)
    if (d <= bestKm) { best = city; bestKm = d }
  }
  return best
}

// Asks the browser once (only on a click); a refusal, an error or no geolocation = all of Uzbekistan
export function detectCity(geo = globalThis.navigator?.geolocation) {
  return new Promise((resolve) => {
    if (!geo) { resolve('all'); return }
    geo.getCurrentPosition(
      (pos) => resolve(nearestCity(pos.coords.latitude, pos.coords.longitude)),
      () => resolve('all'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    )
  })
}
