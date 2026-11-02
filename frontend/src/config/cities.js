// City choice in the header: 'all' + the regional centres of Uzbekistan. Names are in ru.json (cities.*)
export const CITIES = [
  'all', 'tashkent', 'samarkand', 'bukhara', 'andijan', 'fergana', 'namangan',
  'nukus', 'urgench', 'karshi', 'termez', 'navoi', 'jizzakh', 'gulistan', 'nurafshan',
]
// A store is in one city (the same list on the server: backend/app/db/seed.py CITIES)
export const STORE_CITIES = CITIES.filter((c) => c !== 'all')

// The city for API requests: none = all of Uzbekistan
export const cityParam = (city) => (city && city !== 'all' ? city : undefined)
