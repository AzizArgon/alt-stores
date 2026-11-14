import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { MessageBubble } from '../components/Chat'
import { returnTo } from './roles'
import { canReserve, checkForm, formatPhone, normalizePhone, reservePath, systemText, todayIso } from './reservations'

const t = i18n.t.bind(i18n)
const FORM = { name: 'Азиз', phone: '+998 90 123-45-67', contact: 'call', telegram: '', quantity: 1, pickup_date: '', pickup_time: '', comment: '' }
const ITEM = { kind: 'offer', id: 5, inStock: true, price: 120 }

describe('reservation form', () => {
  it('phone: +998 XX XXX-XX-XX in any spacing, other countries refused', () => {
    expect(normalizePhone('+998 90 123-45-67')).toBe('+998901234567')
    expect(normalizePhone('998901234567')).toBe('+998901234567')
    expect(normalizePhone('+7 900 123 45 67')).toBeNull()
    expect(normalizePhone('90 123 45 67')).toBeNull()
    expect(formatPhone('+998901234567')).toBe('+998 90 123-45-67')
  })
  it('required fields, Telegram nick when chosen, date not before today', () => {
    expect(checkForm(FORM)).toEqual({})
    expect(checkForm({ ...FORM, name: ' ', phone: '123' })).toEqual({ name: 'name', phone: 'phone' })
    expect(checkForm({ ...FORM, contact: 'telegram' })).toEqual({ telegram: 'telegram' })
    expect(checkForm({ ...FORM, contact: 'telegram', telegram: '@aziz_dev' })).toEqual({})
    expect(checkForm({ ...FORM, pickup_date: '2020-01-01' })).toEqual({ pickup_date: 'pickup_date' })
    expect(checkForm({ ...FORM, pickup_date: todayIso() })).toEqual({})
    expect(checkForm({ ...FORM, comment: 'x'.repeat(501) })).toEqual({ comment: 'comment' })
  })
  it('no "Reserve" for Telegram ads, sellers and what is not on sale', () => {
    const shop = { kind: 'shop' }
    expect(canReserve(shop, null, ITEM)).toBe(true)
    expect(canReserve(shop, { role: 'buyer' }, ITEM)).toBe(true)
    expect(canReserve({ kind: 'telegram' }, { role: 'buyer' }, ITEM)).toBe(false)
    expect(canReserve(shop, { role: 'seller' }, ITEM)).toBe(false)
    expect(canReserve(shop, null, { ...ITEM, inStock: false })).toBe(false)
  })
  it('a guest comes back to the same page with the form open', () => {
    const from = reservePath('/products/7', '?tab=used', 'offer', 5)
    expect(from).toBe('/products/7?tab=used&reserve=offer%3A5')
    expect(returnTo({ role: 'buyer' }, from)).toBe(from)
    expect(returnTo({ role: 'buyer' }, '/reservations')).toBe('/reservations')
    // Phase 16.3: a buyer returns to any storefront page he came from ("Вход" in the header remembers it)
    expect(returnTo({ role: 'buyer' }, '/products/7')).toBe('/products/7')
  })
})

describe('system lines of a reservation in the chat', () => {
  it('a key with params becomes the text of ru.json', () => {
    expect(systemText(t, { key: 'confirmed', params: { until: '14.11' } })).toBe('Магазин подтвердил бронь. Товар ждёт вас до 14.11')
    expect(systemText(t, { key: 'cancelled_store', params: { reason: 'other', text: 'Продан' } })).toBe('Магазин отменил бронь: Другое — Продан')
    expect(systemText(t, { text: 'обычное' })).toBe('обычное')
  })
  it('the bubble shows the system line centred, as text', () => {
    const html = renderToStaticMarkup(<MessageBubble message={{ id: 1, author: 'system', text: '', key: 'issued', params: {}, created_at: '2026-11-09T10:00:00Z' }} />)
    expect(html).toContain('Товар выдан')
  })
})
