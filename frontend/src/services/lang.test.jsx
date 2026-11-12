// Phase 15: the language — first visit, the browser memory, the profile, formats, texts from keys in three languages
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import i18n from '../i18n'
import Flags from '../components/Flags'
import LangSwitch from '../components/LangSwitch'
import { notifyText, timeAgo } from '../components/Notifications'
import { AuthProvider } from './auth.jsx'
import { formatDate, formatMonthYear, formatPrice } from './format'
import { browserLang, initialLang, LANG_KEY, profileLang, rememberLang } from './lang'
import { formatSpec } from './specs'

const store = {}
globalThis.localStorage ??= { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v }, removeItem: (k) => { delete store[k] } }
const t = i18n.t.bind(i18n)
const strip = (s) => s.replace(/[  ]/g, ' ') // Intl groups thousands with a narrow no-break space

afterEach(async () => {
  await i18n.changeLanguage('ru')
  localStorage.removeItem(LANG_KEY)
})

describe('choosing the language', () => {
  it('first visit: the browser language if it is uz or en, otherwise ru', () => {
    expect(browserLang(['uz-Latn-UZ', 'ru'])).toBe('uz')
    expect(browserLang(['en-US', 'en'])).toBe('en')
    expect(browserLang(['de-DE', 'en-GB'])).toBe('en') // the first language we have
    expect(browserLang(['ru-RU', 'en'])).toBe('ru')
    expect(browserLang(['de', 'fr'])).toBe('ru')
    expect(browserLang([])).toBe('ru')
  })

  it('the browser remembers the choice; it wins over the browser language next time', async () => {
    await i18n.changeLanguage('uz')
    expect(localStorage.getItem(LANG_KEY)).toBe('uz')
    expect(initialLang()).toBe('uz')
    rememberLang('xx')
    expect(initialLang()).toBe('ru') // a broken value: the default
  })

  it('the profile keeps it: its language wins on login, an empty profile gets the current one', () => {
    expect(profileLang('en', 'ru')).toEqual({ change: 'en' })
    expect(profileLang('uz', 'uz')).toEqual({})
    expect(profileLang(null, 'uz')).toEqual({ save: 'uz' })
    expect(profileLang('de', 'en')).toEqual({ save: 'en' })
  })

  it('the switch shows RU · UZ · EN with the current one pressed', async () => {
    await i18n.changeLanguage('uz')
    const html = renderToStaticMarkup(<MemoryRouter><AuthProvider><LangSwitch /></AuthProvider></MemoryRouter>)
    expect(html).toContain('>RU<')
    expect(html).toContain('>EN<')
    expect(html).toMatch(/aria-pressed="true"[^>]*>UZ</)
    expect(html).toContain('aria-label="Til"')
  })
})

describe('formats by language', () => {
  it('prices: UZS stays the main currency — сум / soʻm / UZS', async () => {
    expect(strip(formatPrice(1250000, 'UZS'))).toBe('1 250 000 сум')
    await i18n.changeLanguage('uz')
    expect(strip(formatPrice(1250000, 'UZS'))).toBe('1 250 000 soʻm')
    await i18n.changeLanguage('en')
    expect(formatPrice(1250000, 'UZS')).toBe('1,250,000 UZS')
    expect(formatPrice(1234.5, 'USD')).toBe('$1,234.5')
  })

  it('dates and "5 min ago"', async () => {
    const now = Date.parse('2026-11-11T10:00:00Z')
    expect(timeAgo(t, '2026-11-11T09:55:00Z', now)).toBe('5 мин назад')
    await i18n.changeLanguage('uz')
    expect(timeAgo(t, '2026-11-11T09:55:00Z', now)).toBe('5 daqiqa oldin')
    // Uzbek dates as written in Uzbekistan, whatever Intl data the browser has
    expect(formatDate('2026-11-05T10:00:00Z')).toBe('05.11.2026')
    expect(formatMonthYear('2022-12-05T10:00:00Z')).toBe('dekabr 2022')
    await i18n.changeLanguage('en')
    expect(timeAgo(t, '2026-11-11T09:55:00Z', now)).toBe('5 min ago')
    expect(timeAgo(t, '2026-11-11T09:59:50Z', now)).toBe('just now')
    expect(formatDate('2026-11-05T10:00:00Z')).toBe('11/5/2026')
  })

  it('plural forms: three in ru, their own in uz and en', async () => {
    expect([1, 3, 5, 21].map((count) => t('catalog.offers', { count }))).toEqual(
      ['1 предложение', '3 предложения', '5 предложений', '21 предложение'])
    await i18n.changeLanguage('en')
    expect([1, 3].map((count) => t('catalog.offers', { count }))).toEqual(['1 offer', '3 offers'])
    await i18n.changeLanguage('uz')
    expect([1, 5].map((count) => t('catalog.offers', { count }))).toEqual(['1 ta taklif', '5 ta taklif'])
    expect(formatSpec({ key: 'capacity', kind: 'number', unit: 'GB', value: 16 })).toBe('16 GB')
    expect(formatSpec({ key: 'rgb', kind: 'yesno', value: true })).toBe('Ha')
  })
})

describe('texts from keys follow the reader', () => {
  const flag = { type: 'price_below_market', level: 'warning', source: 'rule', reason_key: 'below_market',
    params: { percent: 23, median: 310, count: 4 } }

  it('an Anti-Fraud reason in three languages', async () => {
    const html = () => renderToStaticMarkup(<Flags flags={[flag]} />)
    expect(html()).toContain('Цена на 23% ниже средней по рынку ($310 у 4 магазинов)')
    await i18n.changeLanguage('uz')
    expect(html()).toContain('Narx bozordagi oʻrtacha narxdan 23% past (4 ta doʻkonda $310)')
    await i18n.changeLanguage('en')
    expect(html()).toContain('The price is 23% below the market average ($310 at 4 stores)')
  })

  it('a notification is written in the language of who reads it', async () => {
    const n = { kind: 'reservation_new', params: { title: 'RTX 4060', qty: 2 } }
    expect(notifyText(t, n)).toBe('Новая бронь: RTX 4060 — 2 шт.')
    await i18n.changeLanguage('uz')
    expect(notifyText(t, n)).toBe('Yangi bron: RTX 4060 — 2 dona')
    await i18n.changeLanguage('en')
    expect(notifyText(t, n)).toBe('New reservation: RTX 4060 — 2 pcs')
    expect(notifyText(t, { kind: 'message', count: 3, params: { text: 'Hi' } })).toBe('3 new messages from a buyer, the last: "Hi"')
  })

  it('the Telegram ad badge and the reservation statuses', async () => {
    await i18n.changeLanguage('uz')
    expect(t('used.adBadge')).toBe('Telegramdagi eʼlon, tekshirilmagan')
    expect(t('reservation.status.ready')).toBe('Berishga tayyor')
    await i18n.changeLanguage('en')
    expect(t('warehouse.mode.stock')).toBe('Stock keeping')
  })
})
