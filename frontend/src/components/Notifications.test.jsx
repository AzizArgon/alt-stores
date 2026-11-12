import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { TYPES_FOR, notifyText, timeAgo } from './Notifications'
import { ScannerStatus } from './Warehouse'
import { scannerReady, setSound, soundOn } from '../services/barcode'

const store = {}
globalThis.localStorage ??= { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v }, removeItem: (k) => { delete store[k] } }
const t = i18n.t.bind(i18n)

describe('notifications (phase 12.5)', () => {
  it('a text from the key and its params, with the number of joined messages', () => {
    expect(notifyText(t, { kind: 'message', count: 1, params: { text: 'Есть?' } })).toContain('«Есть?»')
    expect(notifyText(t, { kind: 'message', count: 3, params: { text: 'Ау' } })).toMatch(/^3 новых сообщения/)
    expect(notifyText(t, { kind: 'message', count: 1, params: { store: 'Byte', text: 'Да' } })).toContain('«Byte» ответил')
    expect(notifyText(t, { kind: 'reservation_new', params: { title: 'RTX 4060', qty: 1 } })).toContain('RTX 4060')
    expect(notifyText(t, { kind: 'admin_flag', params: { decision: 'dismissed', name: 'X' } })).toContain('снял')
    expect(notifyText(t, { kind: 'admin_store', params: { blocked: false } })).toBe('Блокировка магазина снята')
    // Every kind the server makes has a text
    for (const kind of ['reservation_cancelled', 'reservation_expired', 'reservation_confirmed', 'reservation_ready',
      'reservation_cancelled_store', 'reservation_branch', 'reservation_expiring', 'low_stock', 'oversold', 'import_ready',
      'import_failed', 'report', 'flag_disputed', 'fix_suggested', 'barcode_conflict']) {
      expect(notifyText(t, { kind, params: {} })).not.toContain('notify.text')
    }
  })

  it('"5 мин" style times', () => {
    const now = Date.parse('2026-11-11T10:00:00Z')
    expect(timeAgo(t, '2026-11-11T09:59:40Z', now)).toBe('только что')
    expect(timeAgo(t, '2026-11-11T09:55:00Z', now)).toBe('5 мин назад')
    expect(timeAgo(t, '2026-11-11T07:00:00Z', now)).toBe('3 ч назад')
    expect(timeAgo(t, '2026-11-09T10:00:00Z', now)).toBe('2 дн назад')
  })

  it('a buyer filters only his types, the seller all of his', () => {
    expect(TYPES_FOR.buyer).toEqual(['messages', 'reservations'])
    expect(TYPES_FOR.seller).toContain('stock')
  })
})

describe('the scanner indicator (phase 12.5)', () => {
  it('ready when the goods field or nobody has the focus; not when another field has it', () => {
    const field = { tagName: 'INPUT' }
    expect(scannerReady(null, field)).toBe(true)
    expect(scannerReady(field, field)).toBe(true)
    expect(scannerReady({ tagName: 'BUTTON' }, field)).toBe(true)
    expect(scannerReady({ tagName: 'INPUT' }, field)).toBe(false)
    expect(scannerReady({ tagName: 'SELECT' }, field)).toBe(false)
  })

  it('shows "Сканер готов" and the sound switch, which is remembered', () => {
    const html = renderToStaticMarkup(<MemoryRouter><ScannerStatus field={{ current: null }} /></MemoryRouter>)
    expect(html).toContain('Сканер готов')
    expect(html).toContain('Звук пика включён')
    setSound(false)
    expect(soundOn()).toBe(false)
    setSound(true)
    expect(soundOn()).toBe(true)
  })
})
