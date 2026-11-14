import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { detectCity, nearestCity } from '../config/cities'
import { groupLayout, groupSections, lastTileSpan, packGroups, sideRows, sideTileClass } from '../config/homeGroups'
import ForSellersPage from '../pages/ForSellersPage'
import { CityProvider } from '../services/city.jsx'
import Footer, { FOOTER_COLUMNS } from './Footer'
import { MARKET_LINK, NAV_LINKS } from './Header'
import Price from './Price'
import SearchBar, { CityMenu, HERO_PATH, SEARCH_ROW_PATHS, catalogSearch } from './SearchBar'
import { Hero } from '../pages/HomePage'
import StoreLayoutCode from '../layouts/StoreLayout.jsx?raw'
import { cityParam } from '../config/cities'

globalThis.localStorage ??= { getItem: () => null, setItem: () => {}, removeItem: () => {} }

const html = (el, path = '/') => renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><CityProvider>{el}</CityProvider></MemoryRouter>)
const geo = (result) => ({ getCurrentPosition: (ok, fail) => (result ? ok({ coords: result }) : fail(new Error('denied'))) })

describe('storefront header (phase 16.2)', () => {
  it('sections only: no stores, no search field, no city; the market is a separate icon', () => {
    expect(NAV_LINKS.map((l) => l.to)).toEqual(['/catalog', '/used', '/builds'])
    expect(MARKET_LINK.to).toBe('/market')
  })
})

describe('search row (phase 16.2)', () => {
  it('lives on the home page and in the catalog', () => {
    expect(SEARCH_ROW_PATHS).toEqual(['/', '/catalog'])
  })
  it('passes the words to the catalog, keeps its filters and starts from the first page', () => {
    expect(catalogSearch('rtx 4060')).toEqual({ pathname: '/catalog', search: 'q=rtx+4060' })
    const next = new URLSearchParams(catalogSearch('ssd', '?category=ssd&page=3').search)
    expect(next.get('q')).toBe('ssd')
    expect(next.get('category')).toBe('ssd')
    expect(next.get('page')).toBeNull()
    expect(catalogSearch('', '?q=old').search).toBe('')
  })
  it('one row: field, city, "Найти"', () => {
    const out = html(<SearchBar />)
    expect(out).toContain('Что ищете?')
    expect(out).toContain('Весь Узбекистан')
    expect(out).toContain('Найти')
    expect(out.indexOf('Что ищете?')).toBeLessThan(out.indexOf('Весь Узбекистан'))
    expect(out.indexOf('Весь Узбекистан')).toBeLessThan(out.indexOf('Найти'))
  })
})

describe('city choice (phase 17.1)', () => {
  it('the row does not cut off the list: no overflow-hidden on the form', () => {
    const form = html(<SearchBar />).match(/<form[^>]*>/)[0]
    expect(form).not.toContain('overflow-hidden')
  })
  it('the list opens: "Определить" first, then all of Uzbekistan and the cities', () => {
    const out = html(<CityMenu initialOpen />)
    expect(out).toContain('role="menu"')
    expect(out.indexOf('Определить')).toBeLessThan(out.indexOf('Ташкент'))
    expect(out).toContain('aria-expanded="true"')
  })
  it('the choice is remembered and reaches the catalog requests', () => {
    expect(cityParam('samarkand')).toBe('samarkand')
    expect(cityParam('all')).toBeUndefined()
  })
})

describe('blue banner and the compact row (phase 17.1)', () => {
  it('the banner: title, hint, city → words → "Найти"', () => {
    const out = html(<Hero />)
    expect(out).toContain('bg-gradient-to-br')
    expect(out).toContain('Цены на компьютерную технику во всех магазинах Узбекистана')
    expect(out).toContain('один товар — одна карточка')
    expect(out).toContain('data-variant="hero"')
    expect(out.indexOf('Весь Узбекистан')).toBeLessThan(out.indexOf('Модель, бренд или тип товара'))
  })
  it('the banner only on the home page: the layout draws the row everywhere else', () => {
    expect(HERO_PATH).toBe('/')
    expect(StoreLayoutCode).toContain('pathname !== HERO_PATH && SEARCH_ROW_PATHS.includes(pathname)')
  })
  it('the other pages: compact — 40 px high, limited width, full width on a phone', () => {
    const form = html(<SearchBar />, '/catalog').match(/<form[^>]*>/)[0]
    expect(form).toContain('data-variant="compact"')
    expect(form).toContain('h-10')
    expect(form).toContain('md:max-w-[680px]')
    expect(form).toContain('w-full')
  })
})

describe('"Определить" (phase 16.2)', () => {
  it('the nearest of our cities', () => {
    expect(nearestCity(41.31, 69.28)).toBe('tashkent')
    expect(nearestCity(39.66, 66.93)).toBe('samarkand')
    expect(nearestCity(40.39, 71.78)).toBe('fergana')
    expect(nearestCity(42.45, 59.6)).toBe('nukus')
  })
  it('far from every city or no coordinates: all of Uzbekistan', () => {
    expect(nearestCity(55.75, 37.62)).toBe('all') // Moscow
    expect(nearestCity(43.6, 63.5)).toBe('all') // the desert, far from the regional centres
    expect(nearestCity(NaN, 69)).toBe('all')
  })
  it('a refusal, an error or no geolocation: all of Uzbekistan', async () => {
    expect(await detectCity(geo({ latitude: 39.77, longitude: 64.43 }))).toBe('bukhara')
    expect(await detectCity(geo(null))).toBe('all')
    expect(await detectCity(undefined)).toBe('all')
  })
})

describe('home sections in groups (phase 16.2)', () => {
  const items = ['other', 'mouse', 'cpu', 'printer', 'laptop', 'gpu', 'brand_new', 'bags', 'consumables'].map((slug) => ({ slug }))
  it('groups in the fixed order, a new category goes to "Аксессуары и прочее" before "Прочее"', () => {
    const groups = groupSections(items)
    expect(groups.map((g) => g.key)).toEqual(['components', 'peripherals', 'devices', 'office', 'other'])
    expect(groups[0].items.map((i) => i.slug)).toEqual(['cpu', 'gpu'])
    expect(groups[3].items.map((i) => i.slug)).toEqual(['printer', 'consumables'])
    expect(groups[4].items.map((i) => i.slug)).toEqual(['bags', 'brand_new', 'other'])
    expect(groupSections([{ slug: 'ssd' }]).map((g) => g.key)).toEqual(['components'])
    for (const g of ['components', 'peripherals', 'devices', 'office', 'other']) expect(i18n.exists(`home.groups.${g}`)).toBe(true)
  })
  it('no empty places: the last tile takes the rest of its row', () => {
    expect(lastTileSpan(9, 2)).toBe(2)
    expect(lastTileSpan(9, 4)).toBe(4)
    expect(lastTileSpan(8, 4)).toBe(1)
    expect(lastTileSpan(9, 5, true)).toBe(4) // 4 columns beside "Готовые ПК": 4 + 4 + 1 → the last one takes 4
    expect(lastTileSpan(9, 6, true)).toBe(2) // 5 beside: 5 + 4 → the last takes 2
  })
  it('small groups share a row; a row left unfinished is closed by the group before the gap', () => {
    // wide screen, 6 columns: components (9 + tall tile), peripherals 6, devices 3 + office 3, other 2
    expect(packGroups([9, 6, 3, 3, 2], 6, true)).toEqual([
      { span: 6, last: 2 }, { span: 6, last: 1 }, { span: 3, last: 1 }, { span: 3, last: 1 }, { span: 6, last: 5 },
    ])
    // laptop, 5 columns: peripherals 6 → 5 + 1 (last takes 5); devices 3 + other 2 would fit, office 3 does not
    expect(packGroups([9, 6, 3, 3, 2], 5, true)).toEqual([
      { span: 5, last: 4 }, { span: 5, last: 5 }, { span: 5, last: 3 }, { span: 3, last: 1 }, { span: 2, last: 1 },
    ])
    for (const cols of [2, 4, 5, 6]) {
      // every row is full: the widths of small groups between full rows add up to whole rows
      const packs = packGroups([9, 6, 3, 3, 2, 1], cols, cols >= 5)
      expect(packs.reduce((n, p) => n + p.span, 0) % cols).toBe(0)
    }
    const layout = groupLayout([9, 6, 3, 3, 2])
    expect(layout[2].wrap).toBe('col-span-2 md:col-span-4 lg:col-span-5 xl:col-span-3')
    expect(layout[4].last).toBe('col-span-1 md:col-span-3 lg:col-span-1 xl:col-span-5')
  })
  it('"Готовые ПК": the last column, as high as the tiles beside it; a strip on a phone', () => {
    expect(sideRows(9, 5)).toBe(3)
    expect(sideRows(9, 6)).toBe(2)
    const cls = sideTileClass(9)
    expect(cls).toContain('col-span-full')
    expect(cls).toContain('lg:[grid-area:2/5/span_3/span_1]')
    expect(cls).toContain('xl:[grid-area:2/6/span_2/span_1]')
  })
})

describe('/for-sellers and the footer (phase 16.2)', () => {
  it('the landing leads to the seller registration and to the login', () => {
    const out = html(<ForSellersPage />, '/for-sellers')
    expect(out).toContain('href="/register?role=seller"')
    expect(out).toContain('href="/login"')
    expect(out).toContain('Почему ALT STORES')
    expect(out).toContain('Зарегистрировать магазин')
  })
  it('three columns; "Магазины" and "Для продавцов" are in the footer', () => {
    expect(FOOTER_COLUMNS.map((c) => c.title)).toEqual(['footer.buyers', 'footer.sellers', 'footer.project'])
    const out = html(<Footer />)
    for (const href of ['/catalog', '/used', '/builds', '/stores', '/reservations', '/messages', '/for-sellers', '/login', '/market']) {
      expect(out).toContain(`href="${href}"`)
    }
    expect(out).toContain('Дипломный проект, 2026')
  })
})

describe('the CBU rate is only a tooltip of "≈" (phase 16.2)', () => {
  const pages = import.meta.glob('../pages/*.jsx', { query: '?raw', import: 'default', eager: true })
  it('no rate line on the storefront pages', () => {
    expect(i18n.exists('price.rateNote')).toBe(false)
    for (const [file, code] of Object.entries(pages)) expect(code.includes('rateNote'), file).toBe(false)
  })
  it('"≈" and the dollars stay, the rate is in the tooltip', () => {
    const out = html(<Price price={100} currency="USD" usdRate={12000} rateDate="2026-11-13" />)
    expect(out).toContain('≈')
    expect(out).toContain('$')
    expect(out).toContain('role="tooltip"')
    expect(out).toMatch(/title="Пересчёт по курсу ЦБ на 13[^"]*1 \$ = 12[\s  ]000/)
  })
})
