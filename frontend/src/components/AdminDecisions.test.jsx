import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { ToastProvider } from './overlays'
import { BlockedNotice, SellerFlags } from './AdminDecisions'
import { ADMIN_SECTIONS, NoAccessPage } from '../pages/AdminPage'
import { BLOCK_ACTION, reportSides } from '../pages/AdminModeration'
import { AuthProvider } from '../services/auth.jsx'
import { actionGroup, adminErrorKey, cleanParams } from '../services/admin'

// AuthProvider reads a saved token: none here (node has no localStorage)
globalThis.localStorage ??= { getItem: () => null, setItem: () => {}, removeItem: () => {} }

const html = (el) => renderToStaticMarkup(<MemoryRouter><AuthProvider><ToastProvider>{el}</ToastProvider></AuthProvider></MemoryRouter>)
const FLAG = { id: 5, type: 'price_below_market', level: 'warning', reason_key: 'below_market', source: 'rule',
  params: { percent: 30, median: 100, count: 3 } }

describe('the seller sees the admin decisions (phase 13)', () => {
  it('an active flag has "Оспорить"', () => {
    expect(html(<SellerFlags offer={{ flags: [FLAG] }} onChanged={() => {}} />)).toContain('Оспорить')
  })
  it('an upheld flag shows the answer and cannot be disputed again', () => {
    const out = html(<SellerFlags offer={{ flags: [{ ...FLAG, resolution: 'upheld', admin_answer: 'Цена ниже рынка' }] }} onChanged={() => {}} />)
    expect(out).toContain('Ответ администратора: Цена ниже рынка')
    expect(out).not.toContain('Оспорить</button>')
  })
  it('a disputed flag shows its status and the comment', () => {
    const out = html(<SellerFlags offer={{ flags: [], disputed_flags: [{ ...FLAG, status: 'disputed', dispute_comment: 'Акция' }] }} onChanged={() => {}} />)
    expect(out).toContain('ждёт решения администратора')
    expect(out).toContain('Ваш комментарий: Акция')
  })
  it('a blocked store sees the reason in the cabinet', () => {
    expect(html(<BlockedNotice store={{ blocked_at: '2026-11-10', block_reason: 'Обман' }} />)).toContain('Причина: Обман')
    expect(html(<BlockedNotice store={{}} />)).not.toContain('role="alert"')
  })
})

describe('the admin panel', () => {
  it('a seller or a buyer on /admin sees "Нет доступа"', () => {
    expect(html(<NoAccessPage />)).toContain('Нет доступа')
  })
  it('every section is in the menu, six fit the phone bar', () => {
    expect(ADMIN_SECTIONS.map((s) => s.key)).toEqual(['overview', 'stores', 'reports', 'flags', 'fixes', 'barcodes', 'photos', 'channels', 'users', 'log'])
    expect(ADMIN_SECTIONS.filter((s) => s.tab)).toHaveLength(6)
  })
  it('helpers: the error text, the journal group, empty filters', () => {
    expect(adminErrorKey({ response: { status: 400, data: { detail: { code: 'reason_required' } } } })).toBe('admin.error.reason_required')
    expect(adminErrorKey({ response: { status: 429, data: { detail: { code: 'too_many_logins' } } } })).toBe('errors.too_many_logins')
    expect(actionGroup('store_block')).toBe('store')
    expect(cleanParams({ q: '', verified: 'false', city: null })).toEqual({ verified: 'false' })
  })
})

describe('a report: who complained about whom (one main block button)', () => {
  it('the store complained -> the main action blocks the buyer, the store is in "more"', () => {
    const { from, target } = reportSides({ reporter_side: 'store' })
    expect([from, target]).toEqual(['store', 'buyer'])
    expect(BLOCK_ACTION[target]).toBe('block_user')
  })
  it('the buyer complained -> the main action blocks the store', () => {
    const { target } = reportSides({ reporter_side: 'buyer' })
    expect(BLOCK_ACTION[target]).toBe('block_store')
  })
})
