// Phase 17.5: "Мой магазин" has only the general fields, where to go is only in "Филиалы"
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import i18n from './i18n'
import { STORE_FIELDS } from './pages/SellerPage'
import BranchesBlock from './components/Branches'
import SellerCode from './pages/SellerPage.jsx?raw'
import BranchesCode from './components/Branches.jsx?raw'
import { errorKey } from './services/api'

const html = (store) => renderToStaticMarkup(<MemoryRouter><BranchesBlock store={store} onChanged={() => {}} /></MemoryRouter>)
const branch = { id: 1, name: null, city: 'tashkent', address: 'ул. Навои, 7', landmark: 'ЦУМ', hours: null, phone: null, is_main: true }

describe('the store profile (phase 17.5)', () => {
  it('"Мой магазин" — only name, INN, phone, Telegram and reservation days', () => {
    expect(STORE_FIELDS).toEqual(['name', 'inn_stir', 'phone', 'telegram', 'reservation_days'])
    for (const f of ['city', 'district', 'address', 'hours', 'map_url']) expect(STORE_FIELDS).not.toContain(f)
    expect(SellerCode).not.toContain('LOCATION_FIELDS')
    expect(SellerCode).toContain("t('store.placesHint')")
    // "Филиалы" right under "Мой магазин"
    const profile = SellerCode.slice(SellerCode.indexOf('export function ProfileSection'))
    expect(profile.indexOf('<StoreForm')).toBeLessThan(profile.indexOf('<BranchesBlock'))
    expect(profile.indexOf('<BranchesBlock')).toBeLessThan(profile.indexOf('<StockModeBlock'))
  })

  it('a store without branches sees the hint and "Добавить филиал"', () => {
    const out = html({ id: 1, branches: [] })
    expect(out).toContain('data-testid="branches-empty"')
    expect(out).toContain(i18n.t('branches.emptyTitle'))
    expect(out).toContain(i18n.t('branches.add'))
  })

  it('a branch error is never shown as "Сервер недоступен" when the server did answer', () => {
    expect(BranchesCode).not.toContain("'errors.network'")
    expect(BranchesCode.match(/errorKey\(err\)/g).length).toBe(2)
    expect(errorKey({ response: { status: 500, data: {} } })).toBe('errors.unknown')
    expect(errorKey({ response: { status: 422, data: { detail: [] } } })).toBe('errors.validation')
    expect(errorKey({})).toBe('errors.network') // only when there is no answer at all
  })

  it('a store with branches sees the list, without the hint', () => {
    const out = html({ id: 1, branches: [branch] })
    expect(out).not.toContain('branches-empty')
    expect(out).toContain('ул. Навои, 7')
  })
})
