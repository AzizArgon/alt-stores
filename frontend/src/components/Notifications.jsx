import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Bell, Boxes, CalendarCheck, FileSpreadsheet, MessageSquare, ShieldCheck } from 'lucide-react'
import api from '../services/api'
import { CHANGED, UNREAD_POLL_MS, usePolling } from '../services/chat'
import { Button, Card, EmptyState, Skeleton } from './ui'

// Phase 12.5: the bell of the cabinet, the storefront (a logged-in buyer) and the admin. The counter asks the server
// with the same 30-second poll as the chat counters (stopped while the tab is hidden); no WebSocket.

export const NOTIFY_CHANGED = 'notify:changed'
const ICONS = { messages: MessageSquare, reservations: CalendarCheck, stock: Boxes, imports: FileSpreadsheet, admin: ShieldCheck }
// The filter of "Все уведомления": the types each side can get
export const TYPES_FOR = {
  seller: ['messages', 'reservations', 'stock', 'imports', 'admin'],
  buyer: ['messages', 'reservations'],
  admin: ['admin'],
}

// The text of a notification: a key + params; some kinds have variants (the admin's decision, a blocked store)
export function notifyText(t, n) {
  const p = n.params || {}
  let key = n.kind
  if (n.kind === 'message' && p.store) key = 'reply'
  else if (n.kind === 'admin_flag') key += `_${p.decision}`
  else if (n.kind === 'admin_fix' || n.kind === 'admin_barcode') key += `_${p.status}`
  else if (n.kind === 'admin_store') key += p.blocked ? '_on' : '_off'
  return t(`notify.text.${key}`, { ...p, count: n.count || p.count || 1 })
}

// "5 мин", "3 ч", "2 дн"
export function timeAgo(t, iso, now = Date.now()) {
  const min = Math.floor((now - new Date(iso).getTime()) / 60000)
  if (min < 1) return t('notify.ago.now')
  if (min < 60) return t('notify.ago.min', { count: min })
  if (min < 60 * 24) return t('notify.ago.hour', { count: Math.floor(min / 60) })
  return t('notify.ago.day', { count: Math.floor(min / 1440) })
}

export function useNotifyCount(enabled) {
  const [count, setCount] = useState(0)
  const load = () => api.get('/notifications/unread').then((r) => setCount(r.data.count)).catch(() => {})
  useEffect(() => {
    if (!enabled) { setCount(0); return undefined }
    load()
    // A message read or sent (chat) and a notification read change the counter at once
    window.addEventListener(CHANGED, load)
    window.addEventListener(NOTIFY_CHANGED, load)
    return () => { window.removeEventListener(CHANGED, load); window.removeEventListener(NOTIFY_CHANGED, load) }
  }, [enabled])
  usePolling(load, UNREAD_POLL_MS, enabled)
  return count
}

const changed = () => window.dispatchEvent(new Event(NOTIFY_CHANGED))

function useOpen(n, onDone) {
  const navigate = useNavigate()
  return () => {
    if (!n.is_read) api.post(`/notifications/${n.id}/read`).then(changed).catch(() => {})
    onDone?.()
    navigate(n.link)
  }
}

function Row({ n, onDone, big = false }) {
  const { t } = useTranslation()
  const open = useOpen(n, onDone)
  const Icon = ICONS[n.type] || Bell
  return (
    <li>
      <button type="button" onClick={open}
        className={`flex w-full items-start gap-3 rounded-md px-2.5 py-2.5 text-left outline-none hover:bg-surface-2 focus-visible:bg-surface-2 ${big ? 'sm:px-3' : ''}`}>
        <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-full ${n.is_read ? 'bg-surface-2 text-muted' : 'bg-primary-soft text-primary'}`}>
          <Icon className="size-4" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className={`block text-sm break-words ${n.is_read ? 'text-muted' : 'font-medium text-ink'}`}>{notifyText(t, n)}</span>
          <span className="mt-0.5 block text-xs text-faint">{timeAgo(t, n.created_at)}</span>
        </span>
        {!n.is_read && <span className="mt-2 size-2 shrink-0 rounded-full bg-primary" role="img" aria-label={t('notify.unreadDot')} />}
      </button>
    </li>
  )
}

// The bell with the counter; a click opens the last 10. On a phone the window takes the whole width of the screen.
export function NotificationBell({ allPath, enabled = true }) {
  const { t } = useTranslation()
  const count = useNotifyCount(enabled)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const box = useRef(null)
  const load = () => api.get('/notifications', { params: { limit: 10 } }).then((r) => setItems(r.data.items)).catch(() => setItems([]))
  useEffect(() => {
    if (!open) return undefined
    load()
    const onDown = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  const markAll = () => api.post('/notifications/read-all').then(() => { changed(); load() }).catch(() => {})
  const navigate = useNavigate()
  if (!enabled) return null
  return (
    <div ref={box} className="sm:relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="dialog"
        aria-label={count ? t('notify.bellUnread', { count }) : t('notify.bell')} title={t('notify.bell')}
        className="relative grid size-10 shrink-0 place-items-center rounded-full text-muted outline-none hover:bg-surface-2 hover:text-ink focus-visible:ring-2 focus-visible:ring-primary">
        <Bell className="size-5" aria-hidden />
        {count > 0 && (
          <span className="absolute top-0.5 right-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 text-[11px] font-semibold text-white ring-2 ring-surface">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label={t('notify.title')}
          className="fixed inset-x-0 top-14 z-40 border-y border-line bg-surface shadow-pop sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:w-96 sm:rounded-lg sm:border">
          <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
            <p className="font-semibold">{t('notify.title')}</p>
            {count > 0 && <button type="button" onClick={markAll} className="text-sm font-medium text-primary hover:underline">{t('notify.markAll')}</button>}
          </div>
          <div className="max-h-[min(70vh,28rem)] overflow-y-auto p-1.5">
            {items === null ? <Skeleton className="h-24 w-full" /> : items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted">{t('notify.empty')}</p>
            ) : (
              <ul className="grid">{items.map((n) => <Row key={n.id} n={n} onDone={() => setOpen(false)} />)}</ul>
            )}
          </div>
          <div className="border-t border-line p-1.5">
            <button type="button" onClick={() => { setOpen(false); navigate(allPath) }}
              className="min-h-10 w-full rounded-md text-sm font-medium text-primary hover:bg-surface-2">{t('notify.all')}</button>
          </div>
        </div>
      )}
    </div>
  )
}

const PAGE = 30

// "Все уведомления": the list with a filter by type
export function NotificationsPage({ side }) {
  const { t } = useTranslation()
  const [type, setType] = useState('')
  const [data, setData] = useState(null)
  const load = (offset = 0) => api.get('/notifications', { params: { type: type || undefined, limit: PAGE, offset } })
    .then((r) => setData((d) => (offset && d ? { ...r.data, items: [...d.items, ...r.data.items] } : r.data)))
    .catch(() => setData({ items: [], total: 0, unread: 0 }))
  useEffect(() => { setData(null); load() }, [type]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const again = () => load()
    window.addEventListener(NOTIFY_CHANGED, again)
    return () => window.removeEventListener(NOTIFY_CHANGED, again)
  }, [type]) // eslint-disable-line react-hooks/exhaustive-deps
  const markAll = () => api.post('/notifications/read-all').then(changed).catch(() => {})
  const types = TYPES_FOR[side] || []
  return (
    <div className="mx-auto grid w-full max-w-3xl grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-h1">{t('notify.title')}</h1>
        {data?.unread > 0 && <Button variant="secondary" size="sm" onClick={markAll}>{t('notify.markAll')}</Button>}
      </div>
      {types.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none]" role="group" aria-label={t('notify.title')}>
          {['', ...types].map((k) => (
            <button key={k || 'all'} type="button" aria-pressed={type === k} onClick={() => setType(k)}
              className={`min-h-9 shrink-0 rounded-full border px-3.5 text-sm font-medium whitespace-nowrap ${
                type === k ? 'border-primary bg-primary-soft text-primary' : 'border-line text-muted hover:text-ink'}`}>
              {t(`notify.types.${k || 'all'}`)}
            </button>
          ))}
        </div>
      )}
      {data === null ? <Skeleton className="h-48 w-full rounded-xl" /> : data.items.length === 0 ? (
        <EmptyState icon={Bell} title={t('notify.empty')} hint={t('notify.emptyHint')} />
      ) : (
        <Card className="!p-1.5">
          <ul className="grid divide-y divide-line">{data.items.map((n) => <Row key={n.id} n={n} big />)}</ul>
          {data.items.length < data.total && (
            <div className="p-2"><Button variant="secondary" className="w-full" onClick={() => load(data.items.length)}>{t('notify.more')}</Button></div>
          )}
        </Card>
      )}
      <p className="text-xs text-faint">{t('notify.keep')}</p>
    </div>
  )
}
