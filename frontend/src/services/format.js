import i18n from '../i18n'
import { intlLocale, UZ_MONTHS } from './lang'

// Prices: "$1 234.50" for USD, "1 234 567 сум" for UZS (currency word comes from the translations)
export function formatPrice(value, currency) {
  if (value == null) return '—'
  const locale = intlLocale(i18n.language)
  if (currency === 'USD') {
    return '$' + new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value)
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)} ${i18n.t('currency.UZS')}`
}

export function formatDate(iso) {
  return new Intl.DateTimeFormat(intlLocale(i18n.language)).format(new Date(iso))
}

// "@store", "t.me/store" or "https://t.me/store" -> https://t.me/store
export function telegramUrl(handle) {
  const name = handle.trim().replace(/^(https?:\/\/)?(t\.me\/)?@?/, '')
  return `https://t.me/${name}`
}

// "25.10" for "by the CBU rate on 25.10"
export function formatDayMonth(iso) {
  return new Intl.DateTimeFormat(intlLocale(i18n.language), { day: '2-digit', month: '2-digit' }).format(new Date(iso))
}

// "декабрь 2022" for an old price list date
export function formatMonthYear(iso) {
  const d = new Date(iso)
  if (i18n.language === 'uz') return `${UZ_MONTHS[d.getMonth()]} ${d.getFullYear()}`
  const text = new Intl.DateTimeFormat(intlLocale(i18n.language), { month: 'long', year: 'numeric' }).format(new Date(iso))
  return text.replace(/\s*г\.$/, '')
}

// Converted amounts are approximate: sums rounded to 1 000, dollars to whole dollars
export const roundSum = (value) => Math.round(value / 1000) * 1000
export const roundUsd = (value) => Math.round(value)

// Import history name: a file is called by its name, a pasted text by its time ("Текст от 25.10, 14:30")
export function importTitle(imp) {
  if (imp.source !== 'text' || imp.filename) return imp.filename
  const d = new Date(imp.created_at)
  const time = new Intl.DateTimeFormat(intlLocale(i18n.language), { hour: '2-digit', minute: '2-digit' }).format(d)
  return i18n.t('manual.textTitle', { date: formatDayMonth(imp.created_at), time })
}
