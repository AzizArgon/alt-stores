// Phase 11: "Reserve" next to "Write to the seller" and the reservation form (a window; the whole screen on a phone).
// No money and no delivery: paid and picked up in the store.
import { CalendarCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { notifyChanged } from '../services/chat'
import {
  CONTACTS, FIELD_ERRORS, MAX_COMMENT, canReserve, checkForm, formatPhone, reservationErrorKey, reservePath, todayIso,
} from '../services/reservations'
import { ErrorText } from './AuthForm'
import { Modal, useToast } from './overlays'
import Price from './Price'
import { Button, FieldBox, Input, inputClass } from './ui'

const PUBLIC_DEMO = import.meta.env.VITE_PUBLIC_DEMO === '1'
const EMPTY = { name: '', phone: '', contact: 'call', telegram: '', quantity: 1, pickup_date: '', pickup_time: '', comment: '' }

// `item`: { kind: 'offer' | 'build', id, title, condition, price, currency, inStock }; not for Telegram ads,
// sellers or what is not on sale. A guest logs in and comes back to the same page with the form open.
export function ReserveButton({ item, store, usdRate, className = '', size = 'lg' }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const { pathname, search } = useLocation()
  const [params, setParams] = useSearchParams()
  const [open, setOpen] = useState(false)
  const key = `${item.kind}:${item.id}`

  // Back from the login page: the form of this item opens again
  useEffect(() => {
    if (params.get('reserve') !== key || !user || user.role === 'seller') return
    setOpen(true)
    params.delete('reserve')
    setParams(params, { replace: true })
  }, [user, key]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!canReserve(store, user, item)) return null
  const onClick = () => (user ? setOpen(true)
    : navigate('/login', { state: { from: reservePath(pathname, search, item.kind, item.id) } }))
  return (
    <>
      <Button size={size} variant="secondary" className={className} onClick={onClick}>
        <CalendarCheck className="size-4" aria-hidden />{t('reservation.reserve')}
      </Button>
      {open && <ReserveForm item={item} store={store} usdRate={usdRate} onClose={() => setOpen(false)} />}
    </>
  )
}

function Radio({ name, checked, onChange, children }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary-soft">
      <input type="radio" name={name} checked={checked} onChange={onChange} className="size-4 accent-primary" />
      {children}
    </label>
  )
}

export function ReserveForm({ item, store, usdRate, onClose }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (field) => (e) => {
    setForm((f) => ({ ...f, [field]: e.target.value }))
    setErrors((errs) => (errs[field] ? { ...errs, [field]: undefined } : errs)) // fixed: the error goes away
  }

  // Name, phone and Telegram of the last reservation (the buyer may change them)
  useEffect(() => {
    api.get('/reservations/contacts').then((res) => setForm((f) => ({
      ...f, name: f.name || res.data.name, phone: f.phone || formatPhone(res.data.phone), telegram: f.telegram || res.data.telegram,
    }))).catch(() => {})
  }, [])

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const own = checkForm(form)
    setErrors(own)
    if (Object.keys(own).length) return
    setBusy(true)
    try {
      const res = await api.post('/reservations', {
        kind: item.kind, item_id: item.id, ...form, quantity: Number(form.quantity),
        telegram: form.contact === 'telegram' || form.telegram.trim() ? form.telegram.trim() : null,
        pickup_date: form.pickup_date || null, pickup_time: form.pickup_time || null,
      })
      toast(t('reservation.sent'))
      notifyChanged()
      onClose()
      navigate('/reservations', { state: { highlight: res.data.id } })
    } catch (err) {
      const code = err.response?.data?.detail?.code
      if (FIELD_ERRORS.includes(code)) setErrors({ [code]: code })
      else setError(t(reservationErrorKey(err)))
    } finally {
      setBusy(false)
    }
  }

  const err = (f) => (errors[f] ? t(`reservation.error.${errors[f]}`) : undefined)
  const place = [t(`cities.${store.city}`), store.district, store.address].filter(Boolean).join(', ')
  return (
    <Modal open fullOnPhone onClose={onClose} title={t('reservation.formTitle')}>
      <form id="reserve-form" onSubmit={onSubmit} noValidate className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label={t('reservation.name')} value={form.name} onChange={set('name')} error={err('name')}
            autoComplete="name" maxLength={100} required />
          <Input label={t('reservation.phone')} type="tel" inputMode="tel" value={form.phone} onChange={set('phone')}
            error={err('phone')} placeholder={t('reservation.phonePlaceholder')} autoComplete="tel" required />
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">{t('reservation.contact')}</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {CONTACTS.map((c) => (
              <Radio key={c} name="contact" checked={form.contact === c} onChange={() => setForm((f) => ({ ...f, contact: c }))}>
                {t(`reservation.contactKind.${c}`)}
              </Radio>
            ))}
          </div>
        </fieldset>
        {form.contact === 'telegram' && (
          <Input label={t('reservation.telegram')} value={form.telegram} onChange={set('telegram')} error={err('telegram')}
            placeholder={t('reservation.telegramPlaceholder')} maxLength={33} />
        )}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Input label={t('reservation.quantity')} type="number" min={1} max={99} value={form.quantity}
            onChange={set('quantity')} error={err('quantity')} />
          <Input label={`${t('reservation.pickupDate')}`} hint={t('reservation.optional')} type="date" min={todayIso()}
            value={form.pickup_date} onChange={set('pickup_date')} error={err('pickup_date')} />
          <Input label={t('reservation.pickupTime')} type="time" value={form.pickup_time} onChange={set('pickup_time')}
            error={err('pickup_time')} />
        </div>
        <FieldBox label={t('reservation.comment')} id="reserve-comment" error={err('comment')}
          hint={`${t('reservation.commentHint')} · ${form.comment.length}/${MAX_COMMENT}`}>
          <textarea id="reserve-comment" rows={2} maxLength={MAX_COMMENT} value={form.comment} onChange={set('comment')}
            className={`${inputClass} resize-y`} />
        </FieldBox>

        <div className="rounded-lg bg-surface-2 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold break-words">{item.title}</p>
              <p className="text-xs text-muted">{t(`condition.${item.condition}`)} · {store.name}</p>
              {place && <p className="text-xs text-muted">{place}</p>}
            </div>
            <div className="shrink-0 text-right"><Price price={item.price} currency={item.currency} usdRate={usdRate} size="text-lg" /></div>
          </div>
          <p className="mt-2 text-sm font-medium">{t('reservation.payNote')}</p>
          {PUBLIC_DEMO && <p className="mt-1 text-xs font-medium text-warning">{t('reservation.demoNote')}</p>}
          <p className="mt-1 text-xs text-muted">{t('reservation.remembered')}</p>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" size="lg" disabled={busy} className="w-full">{t('reservation.send')}</Button>
      </form>
    </Modal>
  )
}
