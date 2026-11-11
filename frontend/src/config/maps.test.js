import { describe, expect, it } from 'vitest'
import { isYandexMapsUrl, mapsLink, routeLink } from './maps'

describe('Yandex Maps link (phase 12)', () => {
  it('accepts only Yandex Maps', () => {
    for (const ok of ['https://yandex.uz/maps/10335/tashkent/?ll=69.27%2C41.31', 'https://yandex.ru/maps/-/CDqXbG~a',
      'yandex.com/maps/org/alt/1/', 'https://maps.yandex.ru/?text=x', '']) expect(isYandexMapsUrl(ok)).toBe(true)
    for (const bad of ['https://google.com/maps/place/x', 'https://yandex.uz/search/?text=x', 'https://evil.com/yandex.uz/maps',
      'https://yandex.uz.evil.com/maps/', 'javascript:alert(1)', 'https://2gis.uz']) expect(isYandexMapsUrl(bad)).toBe(false)
  })
  it('without a link: a search of the address in its city', () => {
    const store = { address: 'ул. Навои, 12' }
    expect(mapsLink(store, 'Ташкент')).toBe(`https://yandex.uz/maps/?text=${encodeURIComponent('Ташкент, ул. Навои, 12')}`)
    expect(mapsLink({ ...store, map_url: 'https://yandex.uz/maps/-/abc' }, 'Ташкент')).toBe('https://yandex.uz/maps/-/abc')
    expect(mapsLink({}, 'Ташкент')).toBeNull()
  })
  it('route: to the coordinates when known, else to the address', () => {
    expect(routeLink({ address: 'x', map_lat: 41.31, map_lon: 69.28 }, 'Ташкент')).toBe('https://yandex.uz/maps/?rtext=~41.31,69.28&rtt=auto')
    expect(routeLink({ address: 'ул. Навои, 12' }, 'Ташкент')).toContain('rtext=~' + encodeURIComponent('Ташкент, ул. Навои, 12'))
  })
})
