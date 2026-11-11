import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ExternalLink, Send } from 'lucide-react'
import api, { errorKey } from '../services/api'
import { formatDate, formatPrice } from '../services/format'
import { specsText, useSpecDictionary } from '../services/specs'
import { ProductLine } from './AddFromCatalog'
import { StockEditor } from './BranchStock'
import { BarcodeField } from './Barcode'
import { ErrorText } from './AuthForm'
import { CategoryIcon } from './CategoryIcon'
import { SellerFlags } from './AdminDecisions'
import { MarketLabel } from './Market'
import NewProductForm from './NewProductForm'
import { Modal, Sheet, useToast } from './overlays'
import { Button, Skeleton, Switch, inputClass as input } from './ui'
import { OfferPhotos } from './OfferPhotos'

const CONDITIONS = ['new', 'new_openbox', 'used', 'refurbished', 'unknown']
const OWN_FIELDS = ['price', 'currency', 'is_in_stock', 'condition', 'raw_name', 'note']

function Section({ title, children, className = '' }) {
  return (
    <section className={`border-t border-line pt-4 ${className}`}>
      <h3 className="text-h3">{title}</h3>
      {children}
    </section>
  )
}

// "My offer": everything the seller may change at once
function OwnForm({ offer, onSaved }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() => Object.fromEntries(OWN_FIELDS.map((f) => [f, offer[f] ?? ''])))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (field, value) => setForm({ ...form, [field]: value })

  const changes = Object.fromEntries(OWN_FIELDS
    .map((f) => [f, f === 'price' ? (form.price === '' ? null : Number(form.price)) : form[f]])
    .filter(([f, v]) => v !== (offer[f] ?? (f === 'price' ? null : ''))))
  const dirty = Object.keys(changes).length > 0

  const onSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api.patch(`/seller/offers/${offer.id}`, changes)
      onSaved(res.data)
    } catch (err) {
      setError(t(errorKey(err, { 422: `cabinet.error.${err.response?.data?.detail?.code || 'save'}` })))
    }
    setBusy(false)
  }

  return (
    <form onSubmit={onSubmit} className="mt-3 grid gap-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="mb-1 block text-sm text-muted">{t('manual.price')}</span>
          <input type="number" min="0" step="any" inputMode="decimal" value={form.price} className={input} onChange={(e) => set('price', e.target.value)} />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-muted">{t('manual.currency')}</span>
          <select value={form.currency} className={input} onChange={(e) => set('currency', e.target.value)}>
            {['USD', 'UZS'].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-muted">{t('import.col.condition')}</span>
          <select value={form.condition} className={input} onChange={(e) => set('condition', e.target.value)}>
            {CONDITIONS.map((c) => <option key={c} value={c}>{t(`condition.${c}`)}</option>)}
          </select>
        </label>
        <div className="flex items-end pb-2">
          <Switch checked={form.is_in_stock} onChange={(v) => set('is_in_stock', v)} label={t(form.is_in_stock ? 'import.inStock' : 'import.outOfStock')} />
        </div>
      </div>
      {form.currency !== offer.currency && <p className="text-xs text-warning">{t('cabinet.editor.currencyHint')}</p>}
      <label className="block">
        <span className="mb-1 block text-sm text-muted">{t('cabinet.editor.rawName')}</span>
        <input value={form.raw_name} required className={input} onChange={(e) => set('raw_name', e.target.value)} />
        <span className="mt-1 block text-xs text-faint">{t('cabinet.editor.rawNameHint')}</span>
      </label>
      <label className="block">
        <span className="mb-1 block text-sm text-muted">{t('cabinet.editor.note')}</span>
        <textarea value={form.note} rows={2} maxLength={500} className={input} placeholder={t('cabinet.editor.notePlaceholder')}
          onChange={(e) => set('note', e.target.value)} />
      </label>
      <ErrorText>{error}</ErrorText>
      <div><Button type="submit" disabled={!dirty || busy}>{busy ? t('auth.loading') : t('cabinet.editor.save')}</Button></div>
    </form>
  )
}

// The shared card: changed at once when only this store sells it, otherwise "suggest a fix" for the admin
function CardSection({ detail, onApplied, onMerge }) {
  const { t } = useTranslation()
  const dictionary = useSpecDictionary()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [sent, setSent] = useState(Boolean(detail.pending_fix))
  const { card } = detail
  const shared = detail.other_stores > 0
  const specs = specsText(card.category, card.specs, dictionary)

  const submit = async (payload) => (await api.put(`/seller/offers/${detail.id}/card`, payload)).data
  const onDone = (res, merge) => {
    setEditing(false)
    if (merge) return onMerge(res)
    if (res.status === 'suggested') {
      setSent(true)
      toast(t('cabinet.card.sent'))
    } else {
      toast(t('cabinet.saved'))
      onApplied()
    }
  }

  return (
    <Section title={t('cabinet.card.title')}>
      <p className="mt-1 text-xs text-muted">
        {shared ? t('cabinet.card.shared', { count: detail.other_stores }) : t('cabinet.card.onlyYou')}
      </p>
      {!editing && (
        <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">{t('import.col.name')}</dt><dd className="break-words">{card.name}</dd>
          <dt className="text-muted">{t('import.col.brand')}</dt><dd>{card.brand || '—'}</dd>
          <dt className="text-muted">{t('import.col.model')}</dt><dd className="break-words">{card.model || '—'}</dd>
          <dt className="text-muted">{t('import.col.category')}</dt><dd>{t(`categories.${card.category}`)}</dd>
          {specs && <><dt className="text-muted">{t('manual.specs')}</dt><dd className="break-words">{specs}</dd></>}
        </dl>
      )}
      {sent && !editing && (
        <p className="mt-3 flex items-center gap-2 rounded-md bg-info-soft px-3 py-2 text-sm text-info">
          <Send className="size-4 shrink-0" aria-hidden />{t('cabinet.card.pending')}
        </p>
      )}
      {editing ? (
        <NewProductForm initial={card} submit={submit} onCreated={onDone} onCancel={() => setEditing(false)}
          title={t(shared ? 'cabinet.card.suggestTitle' : 'cabinet.card.editTitle')}
          hint={t(shared ? 'cabinet.card.suggestHint' : 'cabinet.card.editHint')}
          submitLabel={t(shared ? 'cabinet.card.suggestSubmit' : 'cabinet.card.editSubmit')} />
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>{t(shared ? 'cabinet.card.suggest' : 'cabinet.card.edit')}</Button>
          <Button size="sm" variant="text" to={`/products/${detail.product_id}`} target="_blank">
            {t('cabinet.card.open')}<ExternalLink className="size-3.5" aria-hidden />
          </Button>
        </div>
      )}
    </Section>
  )
}

// "Not this product": move the offer to another card found in the catalog, or to a new card
function RelinkSection({ detail, rate, onMoved }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [found, setFound] = useState({ q: '', items: [] })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (q.trim().length < 2) return undefined
    const timer = setTimeout(() => {
      api.get('/seller/catalog-search', { params: { q } }).then((res) => setFound({ q, items: res.data })).catch(() => {})
    }, 250)
    return () => clearTimeout(timer)
  }, [q])

  const move = async (product) => {
    setError('')
    try {
      await api.post(`/seller/offers/${detail.id}/relink`, { product_id: product.id })
      onMoved()
    } catch (err) {
      setError(t(errorKey(err, { 409: 'cabinet.error.offer_exists' })))
    }
  }
  const items = (found.q === q ? found.items : []).filter((p) => p.id !== detail.product_id)

  return (
    <Section title={t('cabinet.relink.title')}>
      <p className="mt-1 text-xs text-muted">{t('cabinet.relink.hint')}</p>
      {!open ? (
        <Button size="sm" variant="secondary" className="mt-3" onClick={() => setOpen(true)}>{t('cabinet.relink.start')}</Button>
      ) : (
        <div className="mt-3">
          <input value={q} autoFocus placeholder={t('manual.searchPlaceholder')} className={input} onChange={(e) => setQ(e.target.value)} />
          {items.length > 0 && (
            <ul className="mt-1 max-h-72 divide-y divide-line overflow-auto rounded-md border border-line">
              {items.map((p) => (
                <li key={p.id}>
                  <button type="button" disabled={Boolean(p.my_offer)} onClick={() => move(p)}
                    className="w-full px-3 py-2 text-left hover:bg-surface-2 disabled:opacity-70">
                    <ProductLine product={p} rate={rate} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {found.q === q && q.trim().length >= 2 && items.length === 0 && <p className="mt-2 text-sm text-muted">{t('manual.nothingFound')}</p>}
          <ErrorText>{error}</ErrorText>
          {!creating && (
            <button type="button" onClick={() => setCreating(true)} className="mt-3 text-sm font-medium text-primary hover:underline">
              {t('cabinet.relink.create')}
            </button>
          )}
          {creating && <NewProductForm initialName={q || detail.raw_name} onCreated={move} onCancel={() => setCreating(false)} />}
        </div>
      )}
    </Section>
  )
}

function History({ items }) {
  const { t } = useTranslation()
  const text = (h) => {
    if (h.field === 'price') return t('cabinet.history.price', { price: formatPrice(h.price, h.currency) })
    if (h.field === 'stock') return t(h.value === '1' ? 'cabinet.history.on' : 'cabinet.history.off')
    if (h.field === 'condition') return t('cabinet.history.condition', { value: t(`condition.${h.value}`) })
    if (h.field === 'product') return t('cabinet.history.product')
    return t('cabinet.history.removed')
  }
  return (
    <Section title={t('cabinet.history.title')}>
      {items.length === 0 ? <p className="mt-2 text-sm text-muted">{t('cabinet.history.empty')}</p> : (
        <ul className="mt-2 max-h-64 divide-y divide-line overflow-y-auto text-sm">
          {items.map((h, i) => (
            <li key={i} className="flex justify-between gap-3 py-1.5">
              <span>{text(h)}{h.source && <span className="text-faint"> · {t(`cabinet.history.source.${h.source}`)}</span>}</span>
              <span className="shrink-0 text-muted tabular-nums">{formatDate(h.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

// The offer editor: a panel on the right (full screen on a phone), opened by a click on a row of "My goods"
export default function OfferEditor({ offerId, rate, branches = [], onClose, onChanged }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [detail, setDetail] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!offerId) return
    api.get(`/seller/offers/${offerId}`).then((res) => setDetail(res.data)).catch(() => setDetail(null))
  }, [offerId, reloadKey])

  const close = () => {
    setDetail(null)
    onClose()
  }
  const refresh = (row) => {
    setReloadKey((k) => k + 1)
    onChanged(row)
  }
  const saved = (row) => {
    toast(t('cabinet.saved'))
    refresh(row)
  }
  const takeOff = async () => {
    const res = await api.patch(`/seller/offers/${offerId}`, { is_in_stock: false })
    saved(res.data)
  }
  const remove = async () => {
    await api.delete(`/seller/offers/${offerId}`)
    setConfirmDelete(false)
    toast(t('cabinet.editor.deleted'))
    onChanged(null)
    close()
  }
  const moved = () => {
    toast(t('cabinet.relink.done'))
    refresh(null)
  }

  return (
    <Sheet open={Boolean(offerId)} onClose={close} side="wide" title={t('cabinet.editor.title')}>
      {!detail || detail.id !== offerId ? <Skeleton className="h-96 w-full" /> : (
        <div className="grid gap-5">
          <div className="flex gap-3">
            <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted">
              <CategoryIcon category={detail.category} className="size-7" />
            </span>
            <div className="min-w-0">
              <Link to={`/products/${detail.product_id}`} target="_blank" className="font-semibold break-words hover:underline">{detail.name}</Link>
              <p className="text-xs text-muted">{t(`categories.${detail.category}`)} · {t('cabinet.updatedOn', { date: formatDate(detail.updated_at) })}</p>
              <div className="mt-1"><MarketLabel info={detail.market} /></div>
            </div>
          </div>
          <SellerFlags offer={detail} onChanged={() => refresh(null)} />

          <Section title={t('cabinet.editor.own')} className="border-t-0 pt-0">
            <OwnForm key={`${detail.id}-${reloadKey}`} offer={detail} onSaved={saved} />
          </Section>
          {branches.length > 0 && (
            <Section title={t('stock.title')}>
              <StockEditor offer={detail} branches={branches} onSaved={(row) => { setDetail((d) => ({ ...d, ...row })); onChanged(row) }} />
            </Section>
          )}
          <Section title={t('photo.manage')}>
            <div className="mt-2"><OfferPhotos key={`photos-${detail.id}`} offer={detail} onSaved={() => onChanged(null)} /></div>
          </Section>
          <Section title={t('barcode.field.title')}>
            <div className="mt-2"><BarcodeField offer={detail} onChanged={() => onChanged(null)} /></div>
          </Section>
          <CardSection key={`card-${detail.id}-${reloadKey}`} detail={detail} onApplied={() => refresh(null)}
            onMerge={(product) => api.post(`/seller/offers/${detail.id}/relink`, { product_id: product.id }).then(moved)
              .catch((err) => toast(t(errorKey(err, { 409: 'cabinet.error.offer_exists' })), 'danger'))} />
          <RelinkSection key={`relink-${detail.id}-${reloadKey}`} detail={detail} rate={rate} onMoved={moved} />
          <History items={detail.history} />

          <Section title={t('cabinet.editor.danger')}>
            <div className="mt-3 flex flex-wrap gap-2">
              {detail.is_in_stock && <Button size="sm" variant="secondary" onClick={takeOff}>{t('cabinet.editor.takeOff')}</Button>}
              <Button size="sm" variant="danger" onClick={() => setConfirmDelete(true)}>{t('cabinet.editor.delete')}</Button>
            </div>
            <p className="mt-2 text-xs text-muted">{t('cabinet.editor.deleteHint')}</p>
          </Section>
        </div>
      )}
      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title={t('cabinet.editor.deleteTitle')}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>{t('manual.cancel')}</Button>
          <Button variant="danger" onClick={remove}>{t('cabinet.editor.deleteConfirm')}</Button>
        </>}>
        <p className="text-sm">{t('cabinet.editor.deleteText', { name: detail?.name })}</p>
      </Modal>
    </Sheet>
  )
}
