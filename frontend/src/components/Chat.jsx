import { ArrowLeft, Ban, Flag, MessageSquare, MoreVertical, SendHorizontal, Store } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { storeUrl } from '../config/sites'
import api from '../services/api'
import {
  MAX_TEXT, THREAD_POLL_MS, UNREAD_POLL_MS, canWrite, chatErrorKey, formatChatTime, notifyChanged, usePolling, writePath,
} from '../services/chat'
import { useAuth } from '../services/auth.jsx'
import { systemText } from '../services/reservations'
import { StatusBadge } from '../pages/ReservationsPage'
import { ErrorText } from './AuthForm'
import { CategoryIcon } from './CategoryIcon'
import { Dropdown, DropdownItem, Modal, useToast } from './overlays'
import Price from './Price'
import { Badge, Button, EmptyState, Select, Skeleton, Tabs, inputClass } from './ui'

const PUBLIC_DEMO = import.meta.env.VITE_PUBLIC_DEMO === '1'
const REASONS = ['spam', 'abuse', 'fraud', 'other']
const TEMPLATES = ['inStock', 'comeSee', 'finalPrice', 'reserve']
const FILTERS = ['all', 'unread', 'offer', 'build']

// "Write to the seller" next to "Contact". Not for Telegram ads (only "Open the post") and not for sellers
export function WriteButton({ kind, id, store, className = '', size = 'lg' }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  if (!canWrite(store) || user?.role === 'seller') return null
  return (
    <Button to={writePath(kind, id)} variant="secondary" size={size} className={className}>
      <MessageSquare className="size-4" aria-hidden />{t('chat.write')}
    </Button>
  )
}

function TopicIcon({ topic, className = 'size-10' }) {
  const box = `flex shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted ${className}`
  if (topic.kind === 'store') return <span className={box}><Store className="size-1/2" aria-hidden /></span>
  return <span className={box}><CategoryIcon category={topic.kind === 'build' || topic.category === 'build' ? 'desktop' : topic.category} className="size-1/2" /></span>
}

// The other side: a store by name; a buyer only by number (the seller never sees the email)
function useOtherName(side) {
  const { t } = useTranslation()
  return (c) => (side === 'store' ? t('chat.buyerNo', { no: c.buyer_no }) : c.store.name)
}

function topicTitle(t, topic) {
  if (topic.missing) return t('chat.topicGone')
  return topic.kind === 'store' ? t('chat.storeQuestion') : topic.title
}

function ConversationList({ items, base, side, activeId, filter, setFilter }) {
  const { t } = useTranslation()
  const otherName = useOtherName(side)
  return (
    <div className="flex min-h-0 flex-col">
      {side === 'store' && (
        <Tabs className="mb-3" label={t('chat.filters')} value={filter} onChange={setFilter}
          tabs={FILTERS.map((f) => ({ value: f, label: t(`chat.filter.${f}`) }))} />
      )}
      {items === null ? (
        <div className="grid gap-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={MessageSquare} title={t('chat.empty')} hint={t(side === 'store' ? 'chat.emptyStore' : 'chat.emptyBuyer')} />
      ) : (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-1">
          {items.map((c) => (
            <li key={c.id}>
              <Link to={`${base}/${c.id}`} aria-current={String(c.id) === activeId ? 'page' : undefined}
                className={`flex min-w-0 items-center gap-3 rounded-lg p-2.5 outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  String(c.id) === activeId ? 'bg-primary-soft' : 'hover:bg-surface-2'}`}>
                <TopicIcon topic={c.topic} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-sm font-semibold">{otherName(c)}</span>
                    {c.last && <span className="shrink-0 text-xs text-faint">{formatChatTime(c.last.created_at)}</span>}
                  </span>
                  <span className="block truncate text-xs text-muted">{topicTitle(t, c.topic)}</span>
                  <span className="flex items-center justify-between gap-2">
                    <span className={`truncate text-sm ${c.unread ? 'font-medium text-ink' : 'text-muted'}`}>
                      {c.last ? systemText(t, c.last) : t('chat.noMessages')}
                    </span>
                    {c.unread > 0 && (
                      <span aria-label={t('chat.unread', { count: c.unread })}
                        className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-white">
                        {c.unread}
                      </span>
                    )}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// What the conversation is about, as it is now: price in sum (dollars grey), condition, "not in stock"
function TopicCard({ topic, usdRate, side }) {
  const { t } = useTranslation()
  const path = topic.kind === 'offer' ? `/products/${topic.product_id}` : topic.kind === 'build' ? `/builds/${topic.build_id}` : null
  // A reservation conversation leads to the reservation: "My reservations" or the cabinet section
  if (topic.kind === 'reservation' && !topic.missing) return <ReservationTopic topic={topic} usdRate={usdRate} side={side} />
  // The cabinet is apart from the storefront: there the link opens the storefront in a new tab
  const linkProps = side === 'store' ? { href: storeUrl(path), target: '_blank', rel: 'noreferrer' } : { to: path }
  const Title = path && !topic.missing ? (linkProps.to ? Link : 'a') : 'span'
  return (
    <div className="flex min-w-0 items-center gap-3 border-b border-line p-3">
      <TopicIcon topic={topic} className="size-12" />
      <div className="min-w-0 flex-1">
        <Title {...(Title === 'span' ? {} : linkProps)} className="line-clamp-2 text-sm font-semibold break-words hover:text-primary">
          {topicTitle(t, topic)}
        </Title>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          {topic.condition && <span>{t(`condition.${topic.condition}`)}</span>}
          {topic.in_stock === false && <Badge tone="warning">{t('product.outOfStock')}</Badge>}
        </p>
      </div>
      {topic.price != null && !topic.missing && (
        <div className="shrink-0 text-right"><Price price={topic.price} currency={topic.currency} usdRate={usdRate} size="text-base" /></div>
      )}
    </div>
  )
}

function ReservationTopic({ topic, usdRate, side }) {
  const { t } = useTranslation()
  const to = side === 'store' ? `/seller/reservations?id=${topic.reservation_id}` : '/reservations'
  return (
    <div className="flex min-w-0 items-center gap-3 border-b border-line p-3">
      <TopicIcon topic={topic} className="size-12" />
      <div className="min-w-0 flex-1">
        <Link to={to} className="line-clamp-2 text-sm font-semibold break-words hover:text-primary">{topic.title}</Link>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          <span>{t('reservation.formTitle')}</span><StatusBadge status={topic.status} />
        </p>
      </div>
      <div className="shrink-0 text-right"><Price price={topic.price} currency={topic.currency} usdRate={usdRate} size="text-base" /></div>
    </div>
  )
}

function ReportModal({ open, onClose, convId }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [reason, setReason] = useState('spam')
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const send = async () => {
    try {
      await api.post(`/chat/conversations/${convId}/report`, { reason, comment })
      toast(t('chat.reported'))
      onClose()
    } catch (err) {
      setError(t(chatErrorKey(err)))
    }
  }
  return (
    <Modal open={open} onClose={onClose} title={t('chat.reportTitle')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('chat.cancel')}</Button><Button variant="danger" onClick={send}>{t('chat.reportSend')}</Button></>}>
      <p className="mb-3 text-sm text-muted">{t('chat.reportHint')}</p>
      <Select label={t('chat.reportReason')} value={reason} onChange={(e) => setReason(e.target.value)}>
        {REASONS.map((r) => <option key={r} value={r}>{t(`chat.reason.${r}`)}</option>)}
      </Select>
      <label className="mt-3 block text-sm font-medium" htmlFor="report-comment">{t('chat.reportComment')}</label>
      <textarea id="report-comment" rows={3} maxLength={MAX_TEXT} value={comment} onChange={(e) => setComment(e.target.value)}
        className={`${inputClass} mt-1.5`} />
      <ErrorText>{error}</ErrorText>
    </Modal>
  )
}

function Composer({ side, disabled, onSend }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const area = useRef(null)
  const submit = async (e) => {
    e?.preventDefault()
    const value = text.trim()
    if (!value || busy) return
    if (value.length > MAX_TEXT) { setError(t('chat.error.too_long')); return }
    setBusy(true)
    setError('')
    try {
      await onSend(value)
      setText('')
    } catch (err) {
      setError(t(chatErrorKey(err)))
    } finally {
      setBusy(false)
      area.current?.focus()
    }
  }
  // A quick answer goes into the field: the seller may edit it before sending
  const applyTemplate = (key) => { setText(t(`chat.template.${key}`)); area.current?.focus() }
  return (
    <form onSubmit={submit} className="border-t border-line p-3">
      {side === 'store' && !disabled && (
        <div className="mb-2 flex gap-1.5 overflow-x-auto pb-1" aria-label={t('chat.templates')}>
          {TEMPLATES.map((key) => (
            <button key={key} type="button" onClick={() => applyTemplate(key)}
              className="min-h-9 shrink-0 rounded-full border border-line-strong px-3 text-xs font-medium whitespace-nowrap hover:bg-surface-2">
              {t(`chat.template.${key}`)}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea ref={area} rows={2} value={text} disabled={disabled} aria-label={t('chat.placeholder')}
          placeholder={t(disabled ? 'chat.blockedBuyer' : 'chat.placeholder')}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) submit(e) }}
          className={`${inputClass} max-h-40 min-h-11 resize-y`} />
        <Button type="submit" aria-label={t('chat.send')} title={t('chat.send')} disabled={disabled || busy || !text.trim()} className="shrink-0 !px-3">
          <SendHorizontal className="size-5" aria-hidden />
        </Button>
      </div>
      <div className="mt-1 flex justify-between gap-2 text-xs text-faint">
        <span>{PUBLIC_DEMO ? t('chat.demoNote') : ''}</span>
        {text.length > MAX_TEXT * 0.8 && <span className={text.length > MAX_TEXT ? 'text-danger' : ''}>{text.length}/{MAX_TEXT}</span>}
      </div>
      <ErrorText>{error}</ErrorText>
    </form>
  )
}

// Plain text only: React escapes it, so HTML is shown as text; links and phone numbers are not made clickable
export function MessageBubble({ message: m, own }) {
  const { t } = useTranslation()
  if (m.author === 'system') {
    return <li className="mx-auto max-w-[90%] rounded-lg bg-surface-2 px-3 py-1.5 text-center text-xs text-muted">{systemText(t, m)}</li>
  }
  return (
    <li className={`flex ${own ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${own ? 'rounded-br-sm bg-primary text-white' : 'rounded-bl-sm bg-surface-2 text-ink'}`}>
        <p className="break-words whitespace-pre-wrap">{m.text}</p>
        <p className={`mt-0.5 text-right text-[11px] ${own ? 'text-white/75' : 'text-faint'}`}>
          {formatChatTime(m.created_at)}{own && m.is_read ? ` · ${t('chat.read')}` : ''}
        </p>
      </div>
    </li>
  )
}

function Thread({ id, base, side, onChanged }) {
  const { t } = useTranslation()
  const otherName = useOtherName(side)
  const [conv, setConv] = useState(null)
  const [error, setError] = useState('')
  const [reporting, setReporting] = useState(false)
  const bottom = useRef(null)
  const lastId = conv?.messages.length ? conv.messages[conv.messages.length - 1].id : 0

  useEffect(() => {
    setConv(null)
    setError('')
    api.get(`/chat/conversations/${id}`)
      .then((res) => { setConv(res.data); notifyChanged() })
      .catch((err) => setError(t(chatErrorKey(err))))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Only new messages: after the last one the page already has
  usePolling(() => {
    api.get(`/chat/conversations/${id}`, { params: { after: lastId } }).then((res) => {
      setConv((prev) => {
        if (!prev || String(prev.id) !== String(id)) return prev
        const known = new Set(prev.messages.map((m) => m.id))
        const fresh = res.data.messages.filter((m) => !known.has(m.id))
        if (fresh.length) notifyChanged()
        return { ...res.data, messages: [...prev.messages, ...fresh] }
      })
    }).catch(() => {})
  }, THREAD_POLL_MS, !!conv)

  useEffect(() => { bottom.current?.scrollIntoView?.({ block: 'end' }) }, [conv?.messages.length])

  const send = async (text) => {
    const res = await api.post(`/chat/conversations/${id}/messages`, { text })
    setConv((prev) => ({ ...prev, messages: [...prev.messages, res.data] }))
    onChanged()
  }
  const setBlocked = async (blocked) => {
    await api.post(`/chat/conversations/${id}/block`, { blocked })
    setConv((prev) => ({ ...prev, blocked }))
    onChanged()
  }

  if (error) return <div className="p-4"><ErrorText>{error}</ErrorText></div>
  if (!conv) return <div className="grid gap-3 p-4"><Skeleton className="h-14" /><Skeleton className="h-24" /></div>
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-2 py-2">
        <Link to={base} aria-label={t('chat.back')} className="flex size-10 shrink-0 items-center justify-center rounded-md hover:bg-surface-2 md:hidden">
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
        <p className="min-w-0 flex-1 truncate px-1 font-semibold">{otherName(conv)}</p>
        {conv.blocked && side === 'store' && <Badge tone="danger">{t('chat.blockedBadge')}</Badge>}
        <Dropdown trigger={({ open, toggle }) => (
          <button type="button" onClick={toggle} aria-expanded={open} aria-label={t('chat.actions')}
            className="flex size-10 items-center justify-center rounded-md outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary">
            <MoreVertical className="size-5" aria-hidden />
          </button>
        )}>
          <DropdownItem icon={Flag} onClick={() => setReporting(true)}>{t('chat.report')}</DropdownItem>
          {side === 'store' && (
            <DropdownItem icon={Ban} onClick={() => setBlocked(!conv.blocked)}>{t(conv.blocked ? 'chat.unblock' : 'chat.block')}</DropdownItem>
          )}
        </Dropdown>
      </div>
      <TopicCard topic={conv.topic} usdRate={conv.usd_rate} side={side} />
      <ol className="min-h-48 flex-1 space-y-2 overflow-y-auto p-3" aria-live="polite">
        {conv.messages.length === 0 && <li className="py-6 text-center text-sm text-muted">{t('chat.start')}</li>}
        {conv.messages.map((m) => <MessageBubble key={m.id} message={m} own={m.author === side} />)}
        <li ref={bottom} aria-hidden />
      </ol>
      {conv.blocked && side === 'buyer' && <p className="border-t border-line px-3 pt-3 text-sm text-muted">{t('chat.blockedBuyer')}</p>}
      {conv.blocked && side === 'store' && <p className="border-t border-line px-3 pt-3 text-sm text-muted">{t('chat.blockedStore')}</p>}
      <Composer side={side} disabled={conv.blocked && side === 'buyer'} onSend={send} />
      <ReportModal open={reporting} onClose={() => setReporting(false)} convId={conv.id} />
    </div>
  )
}

// One view for both sides: the list of conversations on the left, the conversation on the right.
// On a phone they are two screens: the list at `base`, the conversation at `base/<id>`.
export default function ChatView({ base, side }) {
  const { t } = useTranslation()
  const { id } = useParams()
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('all')
  const load = () => api.get('/chat/conversations', { params: { filter } }).then((res) => setItems(res.data)).catch(() => setItems([]))
  useEffect(() => { load() }, [filter, id]) // eslint-disable-line react-hooks/exhaustive-deps
  usePolling(load, UNREAD_POLL_MS)
  useEffect(() => {
    window.addEventListener('chat:changed', load)
    return () => window.removeEventListener('chat:changed', load)
  }, [filter]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="grid min-w-0 gap-4">
      <h1 className={`text-h1 ${id ? 'max-md:hidden' : ''}`}>{t('chat.title')}</h1>
      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className={`min-w-0 ${id ? 'max-md:hidden' : ''}`}>
          <ConversationList items={items} base={base} side={side} activeId={id} filter={filter} setFilter={setFilter} />
        </div>
        <div className={`flex min-h-[32rem] min-w-0 flex-col rounded-xl border border-line bg-surface shadow-card md:h-[calc(100vh-12rem)] ${id ? '' : 'max-md:hidden'}`}>
          {id ? <Thread key={id} id={id} base={base} side={side} onChanged={load} />
            : <div className="m-auto p-6 text-center text-sm text-muted">{t('chat.pick')}</div>}
        </div>
      </div>
    </section>
  )
}

// /messages/new?kind=offer&id=5: opens (or finds) the conversation and goes to it
export function OpenConversation() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const asked = useRef(false)
  useEffect(() => {
    if (asked.current) return // once, also in React's development double run
    asked.current = true
    const q = new URLSearchParams(window.location.search)
    const kind = q.get('kind')
    const body = kind === 'store' ? { topic_kind: 'store', store_id: Number(q.get('store')) }
      : { topic_kind: kind, topic_id: Number(q.get('id')) }
    api.post('/chat/conversations', body)
      .then((res) => navigate(`/messages/${res.data.id}`, { replace: true }))
      .catch((err) => setError(t(chatErrorKey(err))))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return error ? <ErrorText>{error}</ErrorText> : <Skeleton className="h-40" />
}
