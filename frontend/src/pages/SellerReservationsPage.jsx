// Phase 11: "Reservations" of the seller cabinet - filters by status, search by name or phone, the next status in
// order, cancel with a reason, the chat, and a hint to take the item off sale (the site changes nothing itself).
import { CalendarCheck, MessageSquare, PackageX, Phone, Search, Send, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import { Modal, useToast } from '../components/overlays'
import Price from '../components/Price'
import { Badge, Button, Card, EmptyState, Input, Select, Skeleton, Tabs, inputClass } from '../components/ui'
import api from '../services/api'
import { notifyChanged } from '../services/chat'
import { formatDate, formatDayMonth, telegramUrl } from '../services/format'
import { CANCEL_REASONS, STORE_FILTERS, formatPhone, reservationErrorKey } from '../services/reservations'
import { CancelReasonText, StatusBadge, pickupText } from './ReservationsPage'

function CancelModal({ r, onClose, onDone }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const submit = async () => {
    setError('')
    try {
      await api.post(`/reservations/${r.id}/cancel`, { reason, text })
      onDone()
    } catch (err) {
      setError(t(reservationErrorKey(err)))
    }
  }
  return (
    <Modal open onClose={onClose} title={t('reservation.storeCancelTitle')} footer={<>
      <Button variant="secondary" onClick={onClose}>{t('reservation.keep')}</Button>
      <Button variant="danger" onClick={submit} disabled={!reason}>{t('reservation.storeCancel')}</Button>
    </>}>
      <div className="grid gap-3">
        <Select label={t('reservation.reason.label')} value={reason} onChange={(e) => setReason(e.target.value)}>
          <option value="" disabled>—</option>
          {CANCEL_REASONS.map((c) => <option key={c} value={c}>{t(`reservation.reason.${c}`)}</option>)}
        </Select>
        <Input label={t('reservation.reasonText')} value={text} maxLength={200} onChange={(e) => setText(e.target.value)}
          required={reason === 'other'} />
        <ErrorText>{error}</ErrorText>
      </div>
    </Modal>
  )
}

function Row({ label, children }) {
  return <p className="text-sm"><span className="text-muted">{label}: </span>{children}</p>
}

function StoreCard({ r, usdRate, highlight, onMoved, onCancel }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const editPath = r.build_id ? `/seller/builds/${r.build_id}` : r.offer_id ? `/seller/goods?edit=${r.offer_id}` : null
  const advance = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post(`/reservations/${r.id}/advance`)
      toast(t('reservation.moved'))
      onMoved()
    } catch (err) {
      setError(t(reservationErrorKey(err)))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card as="li" className={`min-w-0 ${highlight ? 'ring-2 ring-primary' : ''}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <StatusBadge status={r.status} />
            {r.is_demo && <Badge>{t('reservation.demo')}</Badge>}
            <span className="text-xs text-muted">{t('reservation.created', { date: formatDate(r.created_at) })}</span>
          </p>
          {editPath ? <Link to={editPath} className="mt-1.5 block text-h3 break-words hover:text-primary">{r.title}</Link>
            : <p className="mt-1.5 text-h3 break-words">{r.title}</p>}
          <p className="text-sm text-muted">
            {t(`condition.${r.condition}`)} · {t('reservation.qty', { count: r.quantity })}
            {!r.current.exists ? <> · <span className="text-danger">{t('reservation.itemGone')}</span></>
              : !r.current.on_sale && <> · <span className="text-warning">{t('reservation.notOnSale')}</span></>}
          </p>
        </div>
        <div className="shrink-0 sm:text-right">
          <Price price={r.price} currency={r.currency} usdRate={usdRate} size="text-lg" />
          <p className="text-xs text-muted">{t('reservation.priceAt')}</p>
          {r.price_changed && (
            <p className="mt-1 text-xs font-medium text-warning">
              {t('reservation.priceChanged')}: <Price price={r.current.price} currency={r.current.currency} usdRate={usdRate} size="text-sm" />
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 grid gap-1 border-t border-line pt-3">
        <p className="text-sm font-semibold">{r.name} <span className="font-normal text-muted">· {t('reservation.buyerNo', { no: r.buyer_no })}</span></p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <a href={`tel:${r.phone}`} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
            <Phone className="size-4" aria-hidden />{formatPhone(r.phone)}
          </a>
          {r.telegram && (
            <a href={telegramUrl(r.telegram)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              <Send className="size-4" aria-hidden />{r.telegram}
            </a>
          )}
        </p>
        <Row label={t('reservation.contact')}>{t(`reservation.contactKind.${r.contact}`)}</Row>
        {pickupText(r) && <Row label={t('reservation.pickupDate')}>{pickupText(r)}</Row>}
        {r.comment && <Row label={t('reservation.comment')}><span className="break-words whitespace-pre-wrap">{r.comment}</span></Row>}
        {r.expires_at && ['confirmed', 'ready'].includes(r.status) && (
          <p className="text-sm font-medium text-primary">{t('reservation.until', { date: formatDayMonth(r.expires_at) })}</p>
        )}
        <CancelReasonText r={r} side="store" />
        <details className="mt-1 text-sm">
          <summary className="cursor-pointer text-muted">{t('reservation.history')}</summary>
          <ul className="mt-1 grid gap-0.5 text-xs text-muted">
            {r.history.map((h, i) => (
              <li key={i}>{formatDate(h.at)} — {t(`reservation.status.${h.status}`)} ({t(`reservation.by.${h.by}`)})</li>
            ))}
          </ul>
        </details>
      </div>

      <ErrorText>{error}</ErrorText>
      <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap sm:justify-end">
        {r.next && <Button onClick={advance} disabled={busy} className="w-full sm:w-auto">{t(`reservation.next.${r.next}`)}</Button>}
        {r.conversation_id && (
          <Button to={`/seller/messages/${r.conversation_id}`} variant="secondary" className="w-full sm:w-auto">
            <MessageSquare className="size-4" aria-hidden />{t('reservation.openChat')}
          </Button>
        )}
        {editPath && r.current.on_sale && (
          <Button to={editPath} variant="text" className="w-full sm:w-auto" title={t('reservation.takeOffHint')}>
            <PackageX className="size-4" aria-hidden />{t('reservation.takeOff')}
          </Button>
        )}
        {r.can_cancel && (
          <Button variant="text" className="w-full !text-danger hover:!bg-danger-soft sm:w-auto" onClick={() => onCancel(r)}>
            <X className="size-4" aria-hidden />{t('reservation.storeCancel')}
          </Button>
        )}
      </div>
    </Card>
  )
}

export default function SellerReservationsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [params] = useSearchParams()
  const highlight = Number(params.get('id')) || null
  const [status, setStatus] = useState(highlight ? 'all' : 'active')
  const [q, setQ] = useState('')
  const [items, setItems] = useState(null)
  const [rate, setRate] = useState(null)
  const [cancelling, setCancelling] = useState(null)

  const load = () => api.get('/reservations/store', { params: { status, q } })
    .then((res) => { setItems(res.data); notifyChanged() }).catch(() => setItems([]))
  useEffect(() => {
    const timer = setTimeout(load, q ? 300 : 0)
    return () => clearTimeout(timer)
  }, [status, q]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.get('/rates/usd').then((res) => setRate(res.data?.rate ?? null)).catch(() => {}) }, [])

  return (
    <section className="grid gap-4">
      <h1 className="text-h1">{t('cabinet.nav.reservations')}</h1>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" aria-hidden />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('reservation.search')}
          aria-label={t('reservation.search')} className={`${inputClass} pl-9`} />
      </div>
      <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
        <Tabs label={t('reservation.filters')} value={status} onChange={setStatus} className="w-max"
          tabs={STORE_FILTERS.map((f) => ({ value: f, label: t(`reservation.filter.${f}`) }))} />
      </div>
      {items === null ? (
        <div className="grid gap-3">{[0, 1].map((i) => <Skeleton key={i} className="h-48" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={CalendarCheck} title={t('reservation.empty')} hint={t('reservation.emptyStore')} />
      ) : (
        <ul className="grid gap-3">
          {items.map((r) => (
            <StoreCard key={r.id} r={r} usdRate={rate} highlight={highlight === r.id} onMoved={load} onCancel={setCancelling} />
          ))}
        </ul>
      )}
      {cancelling && (
        <CancelModal r={cancelling} onClose={() => setCancelling(null)}
          onDone={() => { setCancelling(null); toast(t('reservation.cancelled')); load() }} />
      )}
    </section>
  )
}
