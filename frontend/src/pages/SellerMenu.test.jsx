import { describe, expect, it } from 'vitest'
import '../i18n'
import { scanTarget } from '../App'
import { pageActive, sectionActive } from '../layouts/Workspace'
import { placeFor, placeLabel, placesOf } from '../services/place'
import { sellerSections } from './SellerPage'
import { stockTabs } from './WarehousePage'

globalThis.localStorage ??= { getItem: () => null, setItem: () => {}, removeItem: () => {} }

const t = (k) => ({ 'place.warehouse': 'Склад' }[k] || k)
const STORE = { stock_mode: 'stock', branches: [{ id: 1, name: 'Чиланзар' }, { id: 2, name: 'Юнусабад' }] }
const WITH_WH = { ...STORE, warehouse: { id: 9 } }
const at = (path) => { const [pathname, q] = path.split('?'); return { pathname, search: q ? `?${q}` : '' } }

describe('the cabinet menu (phase 12.5)', () => {
  it('four sections on the left without sub-items; "Главная" only in the phone bar; no profile', () => {
    const s = sellerSections(STORE)
    expect(s.map((x) => x.key)).toEqual(['overview', 'goodsGroup', 'stock', 'buyers', 'analyticsGroup'])
    expect(s.filter((x) => x.side !== false).map((x) => x.key)).toEqual(['goodsGroup', 'stock', 'buyers', 'analyticsGroup'])
    expect(s.every((x) => x.tab)).toBe(true)
    expect(s.some((x) => x.children)).toBe(false)
    expect(JSON.stringify(s)).not.toContain('profile')
    expect(s[1].pages.map((c) => c.key)).toEqual(['goods', 'add', 'builds', 'imports'])
    expect(s[3].pages.map((c) => c.key)).toEqual(['messages', 'reservations'])
    expect(s[4].pages.map((c) => c.key)).toEqual(['analytics', 'reports'])
  })

  it('"Склад" tabs are its modes; "Выкладка" only with a warehouse; a price-only store has one page', () => {
    expect(stockTabs(STORE)).toEqual(['receipt', 'sale', 'return', 'stocktake', 'journal'])
    expect(stockTabs(WITH_WH)).toEqual(['receipt', 'move', 'sale', 'return', 'stocktake', 'journal'])
    expect(sellerSections(WITH_WH)[2].pages.map((c) => c.to)).toContain('/seller/stock?tab=move')
    expect(sellerSections({ ...STORE, stock_mode: 'price' })[2].pages).toEqual([{ to: '/seller/stock', key: 'stock_about' }])
  })

  it('the counter of "Покупатели" is messages + new reservations', () => {
    const buyers = sellerSections(STORE, { messages: 2, reservations: 3 })[3]
    expect(buyers.badge).toBe(5)
    expect(buyers.pages.map((c) => c.badge)).toEqual([2, 3])
  })

  it('a section is open on any of its pages, "Склад" in every mode', () => {
    const [, goods, stock] = sellerSections(WITH_WH)
    expect(sectionActive(stock, at('/seller/stock?tab=journal'))).toBe(true)
    expect(sectionActive(stock, at('/seller/stock'))).toBe(true)
    expect(sectionActive(goods, at('/seller/builds/5'))).toBe(true)
    expect(sectionActive(goods, at('/seller/stock?tab=sale'))).toBe(false)
  })

  it('a page of a section is open by its path and its tab', () => {
    expect(pageActive({ to: '/seller/stock?tab=sale' }, at('/seller/stock?tab=sale'))).toBe(true)
    expect(pageActive({ to: '/seller/stock?tab=sale' }, at('/seller/stock?tab=receipt'))).toBe(false)
    expect(pageActive({ to: '/seller/builds', deep: true }, at('/seller/builds/5'))).toBe(true)
    expect(pageActive({ to: '/seller/goods' }, at('/seller/goods/x'))).toBe(false)
  })

  it('the old "Сканирование" address opens "Склад" in the same mode', () => {
    expect(scanTarget('')).toContain('tab=receipt')
    expect(scanTarget('?mode=sale')).toContain('tab=sale')
    expect(scanTarget('?mode=find')).toContain('tab=receipt')
  })
})

describe('places of the stock (phase 12.4)', () => {
  it('the warehouse is the first place of the seller, never a branch', () => {
    const places = placesOf(WITH_WH)
    expect(places.map((p) => p.id)).toEqual([9, 1, 2])
    expect(placeLabel(t, places[0])).toBe('Склад')
    expect(placeLabel(t, '@warehouse')).toBe('Склад')
    expect(placesOf(STORE).map((p) => p.id)).toEqual([1, 2])
    expect(placeFor(places, 2).id).toBe(2)
    expect(placeFor(STORE.branches, 9).id).toBe(1) // a mode that allows only branches
  })
})
