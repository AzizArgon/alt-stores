import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import '../i18n'
import StoreWhere, { StoreName } from './StoreWhere'

const html = (el) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>)
const SHOP = { id: 3, kind: 'shop', name: 'Alt', city: 'tashkent', address: 'ул. Навои, 12', hours: 'Пн–Сб 10:00–19:00' }

describe('store address and name (phase 12)', () => {
  it('the name of a shop leads to its page, a Telegram channel is plain text', () => {
    expect(html(<StoreName store={SHOP} />)).toContain('href="/store/3"')
    expect(html(<StoreName store={{ ...SHOP, kind: 'telegram' }} />)).not.toContain('href')
  })
  it('address, hours, map and route buttons (search by the address without a link)', () => {
    const out = html(<StoreWhere store={SHOP} route />)
    expect(out).toContain('Ташкент, ул. Навои, 12')
    expect(out).toContain('Пн–Сб 10:00–19:00')
    expect(out).toContain('Открыть в Яндекс Картах')
    expect(out).toContain('Маршрут')
    expect(out).toContain('https://yandex.uz/maps/?text=')
    expect(html(<StoreWhere store={{ ...SHOP, kind: 'telegram' }} />)).toBe('')
  })
})
