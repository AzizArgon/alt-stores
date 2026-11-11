// Phase 11: reservations ("put it aside for me"). No money and no delivery: paid and picked up in the store.
import { useEffect, useState } from 'react'
import api, { errorKey } from './api'
import { CHANGED, UNREAD_POLL_MS, usePolling } from './chat'

export const CONTACTS = ['call', 'telegram', 'chat']
export const CANCEL_REASONS = ['no_stock', 'price_changed', 'no_show', 'other']
export const STORE_FILTERS = ['active', 'new', 'confirmed', 'ready', 'issued', 'cancelled', 'expired', 'all']
export const MAX_COMMENT = 500
// The field a code of the API belongs to (the error is shown under it)
export const FIELD_ERRORS = ['name', 'phone', 'telegram', 'contact', 'quantity', 'pickup_date', 'pickup_time', 'comment']

// +998 XX XXX-XX-XX in any spacing -> +998XXXXXXXXX; anything else -> null (the server checks the same)
export function normalizePhone(raw) {
  const m = /^\+?998(\d{9})$/.exec((raw || '').replace(/[\s\-()]/g, ''))
  return m ? `+998${m[1]}` : null
}

// +998901234567 -> +998 90 123-45-67
export function formatPhone(phone) {
  const m = /^\+998(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(phone || '')
  return m ? `+998 ${m[1]} ${m[2]}-${m[3]}-${m[4]}` : phone || ''
}

// Today in the buyer's browser as YYYY-MM-DD (the earliest pickup date)
export function todayIso(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// The form's own check before sending: { field: code }
export function checkForm(form) {
  const errors = {}
  if (!form.name.trim()) errors.name = 'name'
  if (!normalizePhone(form.phone)) errors.phone = 'phone'
  if (form.contact === 'telegram' && !/^@?[A-Za-z][A-Za-z0-9_]{4,31}$/.test(form.telegram.trim())) errors.telegram = 'telegram'
  if (!(form.quantity >= 1 && form.quantity <= 99)) errors.quantity = 'quantity'
  if (form.pickup_date && form.pickup_date < todayIso()) errors.pickup_date = 'pickup_date'
  if (form.comment.length > MAX_COMMENT) errors.comment = 'comment'
  return errors
}

export function reservationErrorKey(err) {
  const code = err.response?.data?.detail?.code
  return code ? `reservation.error.${code}` : errorKey(err)
}

// "Reserve" only at a store (not a Telegram ad), not for sellers, only what is on sale with a price
export const canReserve = (store, user, item) =>
  !!store && store.kind !== 'telegram' && user?.role !== 'seller' && !!item.inStock && item.price != null

export const STATUS_TONE = { new: 'info', confirmed: 'primary', ready: 'success', issued: 'neutral', cancelled: 'danger', expired: 'warning' }

// "Reserve" of a guest: login, then back to the same page with ?reserve=<kind>:<id> (the form opens again)
export function reservePath(pathname, search, kind, id) {
  const q = new URLSearchParams(search)
  q.set('reserve', `${kind}:${id}`)
  return `${pathname}?${q}`
}

// The text of a system line of a reservation (the server keeps a key and params)
export function systemText(t, m) {
  if (!m.key) return m.text
  const p = m.params || {}
  const reason = p.reason ? [t(`reservation.reason.${p.reason}`), p.text].filter(Boolean).join(' — ') : ''
  return t(`reservation.sys.${m.key}`, { ...p, reason })
}

// Reservations whose status changed and the buyer has not looked yet (the avatar badge)
export function useUnseenReservations(enabled) {
  const [count, setCount] = useState(0)
  const load = () => api.get('/reservations/unseen').then((res) => setCount(res.data.count)).catch(() => {})
  useEffect(() => {
    if (!enabled) { setCount(0); return undefined }
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [enabled])
  usePolling(load, UNREAD_POLL_MS, enabled)
  return count
}

// New reservations of the seller's store (the cabinet section badge)
export function useNewReservations(enabled) {
  const [count, setCount] = useState(0)
  const load = () => api.get('/reservations/store/counts').then((res) => setCount(res.data.new)).catch(() => {})
  useEffect(() => {
    if (!enabled) { setCount(0); return undefined }
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [enabled])
  usePolling(load, UNREAD_POLL_MS, enabled)
  return count
}
