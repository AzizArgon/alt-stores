// Phase 11: "My reservations" of a buyer - active or finished, status, term, store, address, chat, cancel.
import { CalendarCheck, MapPin, MessageSquare, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { ErrorText } from '../components/AuthForm'
import { Modal, useToast } from '../components/overlays'
import Price from '../components/Price'
import { Badge, Button, Card, EmptyState, Skeleton, Tabs } from '../components/ui'
import api from '../services/api'
import { notifyChanged } from '../services/chat'
import { formatDate, formatDayMonth } from '../services/format'
import { STATUS_TONE, reservationErrorKey } from '../services/reservations'

export function StatusBadge({ status }) {
  const { t } = useTranslation()
  return <Badge tone={STATUS_TONE[status]}>{t(`reservation.status.${status}`)}</Badge>
}

// "18.11, 15:00" from the wished date and time
export function pickupText(r) {
  return [r.pickup_date && formatDayMonth(r.pickup_date), r.pickup_time].filter(Boolean).join(', ')
}

export function CancelReasonText({ r, side }) {
  const { t } = useTranslation()
  if (r.status !== 'cancelled') return null
  const who = r.cancelled_by === 'store' ? t('reservation.cancelledBy.store')
    : side === 'store' ? t('reservation.cancelledBy.buyerStore') : t('reservation.cancelledBy.buyer')
  const reason = r.cancel_reason ? [t(`reservation.reason.${r.cancel_reason}`), r.cancel_text].filter(Boolean).join(' — ') : ''
  return <p className="text-sm text-danger">{who}{reason ? `: ${reason}` : ''}</p>
}

function itemPath(r) {
  if (r.build_id) return `/builds/${r.build_id}`
  return r.current?.product_id ? `/products/${r.current.product_id}` : null
}

function ReservationCard({ r, usdRate, highlight, onCancel }) {
  const { t } = useTranslation()
  const path = itemPath(r)
  const place = [t(`cities.${r.store.city}`), r.store.district, r.store.address].filter(Boolean).join(', ')
  const Title = path ? Link : 'span'
  return (
    <Card as="li" className={`min-w-0 ${highlight ? 'ring-2 ring-primary' : ''}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <StatusBadge status={r.status} />
            {!r.seen && <Badge tone="danger">{t('reservation.statusChanged')}</Badge>}
            <span className="text-xs text-muted">{t('reservation.created', { date: formatDate(r.created_at) })}</span>
          </p>
          <Title {...(path ? { to: path } : {})} className="mt-1.5 block text-h3 break-words hover:text-primary">{r.title}</Title>
          <p className="text-sm text-muted">{t(`condition.${r.condition}`)} · {t('reservation.qty', { count: r.quantity })}</p>
          <p className="mt-1 text-sm font-medium">{r.store.name}</p>
          {place && <p className="flex gap-1 text-sm text-muted"><MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />{place}</p>}
          {r.expires_at && ['confirmed', 'ready'].includes(r.status) && (
            <p className="mt-1 text-sm font-medium text-primary">{t('reservation.until', { date: formatDayMonth(r.expires_at) })}</p>
          )}
          {pickupText(r) && <p className="text-sm text-muted">{t('reservation.pickup', { value: pickupText(r) })}</p>}
          <CancelReasonText r={r} side="buyer" />
        </div>
        <div className="shrink-0 sm:text-right">
          <Price price={r.price} currency={r.currency} usdRate={usdRate} size="text-lg" />
          <p className="text-xs text-muted">{t('reservation.priceAt')}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">{t('reservation.payNote')}</p>
      <div className="mt-3 grid gap-2 sm:flex sm:justify-end">
        {r.conversation_id && (
          <Button to={`/messages/${r.conversation_id}`} variant="secondary" className="w-full sm:w-auto">
            <MessageSquare className="size-4" aria-hidden />{t('reservation.chat')}
          </Button>
        )}
        {r.can_cancel && (
          <Button variant="text" className="w-full !text-danger hover:!bg-danger-soft sm:w-auto" onClick={() => onCancel(r)}>
            <X className="size-4" aria-hidden />{t('reservation.cancel')}
          </Button>
        )}
      </div>
    </Card>
  )
}

export default function ReservationsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const { state } = useLocation()
  const [tab, setTab] = useState('active')
  const [items, setItems] = useState(null)
  const [rate, setRate] = useState(null)
  const [cancelling, setCancelling] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.get('/reservations', { params: { done: tab === 'done' } })
    .then((res) => { setItems(res.data); notifyChanged() }).catch(() => setItems([]))
  useEffect(() => { setItems(null); load() }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.get('/rates/usd').then((res) => setRate(res.data?.rate ?? null)).catch(() => {}) }, [])

  const cancel = async () => {
    setError('')
    try {
      await api.post(`/reservations/${cancelling.id}/cancel`, {})
      toast(t('reservation.cancelled'))
      setCancelling(null)
      load()
    } catch (err) {
      setError(t(reservationErrorKey(err)))
    }
  }

  return (
    <section className="mx-auto grid max-w-3xl gap-4">
      <h1 className="text-h1">{t('reservation.title')}</h1>
      <Tabs label={t('reservation.title')} value={tab} onChange={setTab}
        tabs={['active', 'done'].map((v) => ({ value: v, label: t(`reservation.tabs.${v}`) }))} />
      {items === null ? (
        <div className="grid gap-3">{[0, 1].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={CalendarCheck} title={t('reservation.empty')} hint={t('reservation.emptyBuyer')} />
      ) : (
        <ul className="grid gap-3">
          {items.map((r) => <ReservationCard key={r.id} r={r} usdRate={rate} highlight={state?.highlight === r.id} onCancel={setCancelling} />)}
        </ul>
      )}
      <Modal open={!!cancelling} onClose={() => setCancelling(null)} title={t('reservation.cancelConfirm')}
        footer={<>
          <Button variant="secondary" onClick={() => setCancelling(null)}>{t('reservation.keep')}</Button>
          <Button variant="danger" onClick={cancel}>{t('reservation.cancel')}</Button>
        </>}>
        <p className="text-sm text-muted">{t('reservation.cancelConfirmHint')}</p>
        <ErrorText>{error}</ErrorText>
      </Modal>
    </section>
  )
}
