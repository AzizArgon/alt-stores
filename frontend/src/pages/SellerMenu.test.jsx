import { describe, expect, it } from 'vitest'
import '../i18n'
import { scanTarget } from '../App'
import { pageActive } from '../layouts/Workspace'
import { placeFor, placeLabel, placesOf } from '../services/place'
import { sellerSections } from './SellerPage'
import { stockTabs } from './WarehousePage'

globalThis.localStorage ??= { getItem: () => null, setItem: () => {}, removeItem: () => {} }

const t = (k) => ({ 'place.warehouse': 'Склад' }[k] || k)
const STORE = { stock_mode: 'stock', branches: [{ id: 1, name: 'Чиланзар' }, { id: 2, name: 'Юнусабад' }] }
const WITH_WH = { ...STORE, warehouse: { id: 9 } }
const at = (path) => { const [pathname, q] = path.split('?'); return { pathname, search: q ? `?${q}` : '' } }

describe('the cabinet menu (phase 12.4)', () => {
  it('five sections instead of thirteen items, the profile is not among them', () => {
    const s = sellerSections(STORE)
    expect(s.map((x) => x.key)).toEqual(['overview', 'goodsGroup', 'stock', 'buyers', 'analyticsGroup'])
    expect(s.every((x) => x.tab)).toBe(true)
    expect(JSON.stringify(s)).not.toContain('profile')
    expect(s[1].children.map((c) => c.key)).toEqual(['goods', 'add', 'builds', 'imports'])
    expect(s[4].children.map((c) => c.key)).toEqual(['analytics', 'reports'])
  })

  it('"Склад" has its modes; "Выкладка" only with a warehouse; a price-only store has one page', () => {
    expect(stockTabs(STORE)).toEqual(['receipt', 'sale', 'return', 'stocktake', 'journal'])
    expect(stockTabs(WITH_WH)).toEqual(['receipt', 'move', 'sale', 'return', 'stocktake', 'journal'])
    expect(sellerSections({ ...STORE, stock_mode: 'price' })[2].children).toEqual([{ to: '/seller/stock', key: 'stock_about' }])
  })

  it('the counters of messages and reservations are on the "Покупатели" section', () => {
    const buyers = sellerSections(STORE, { messages: 2, reservations: 3 })[3]
    expect(buyers.badge).toBe(5)
    expect(buyers.children.map((c) => c.badge)).toEqual([2, 3])
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
