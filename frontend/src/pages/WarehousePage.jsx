import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { Download, FileBarChart, MapPin, X } from 'lucide-react'
import { PLACE_OPEN } from '../services/place'
import Stocktake from '../components/Stocktake'
import { ModeSwitch } from '../components/StockMode'
import { GoodsInput, OperationForm, download } from '../components/Warehouse'
import { useToast } from '../components/overlays'
import { Badge, Button, Card, EmptyState, Input, Pagination, Select, Skeleton } from '../components/ui'
import api, { errorKey } from '../services/api'
import { formatPrice } from '../services/format'
import { placeFor, placeLabel } from '../services/place'

const KINDS = ['initial', 'receipt', 'move_out', 'move_in', 'sale', 'return', 'inventory', 'adjust', 'reserve', 'unreserve', 'res_sale', 'import', 'undo', 'manual']
const TAB_KEY = 'alt_stock_tab'
const BRANCHES_ONLY = ['move', 'sale', 'return']

const when = (iso) => new Intl.DateTimeFormat('ru', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

// The modes of "Склад" (phase 12.4): Приёмка · Выкладка (only with a warehouse) · Продажа · Возврат · Ревизия ·
// Журнал. A scan (the USB scanner even with no field focused, the camera) works in every mode. The chosen mode is
// kept (the address and the browser); the place is the one of the top bar (some modes allow only branches).
// Phase 12.5: the modes are the section tabs at the top of the page (no second row of buttons here).
export function stockTabs(store) {
  return ['receipt', ...(store?.warehouse ? ['move'] : []), 'sale', 'return', 'stocktake', 'journal']
}

export default function WarehousePage() {
  const { t } = useTranslation()
  const { store, setStore, place, places } = useOutletContext()
  const [params, setParams] = useSearchParams()
  const tabs = stockTabs(store)
  const priceOnly = store.stock_mode !== 'stock'
  const asked = params.get('tab')
  const tab = [...tabs, 'adjust'].includes(asked) ? asked : null
  const [start, setStart] = useState(null)
  const [version, setVersion] = useState(0)
  useEffect(() => setStart(null), [tab])

  // No mode in the address: the last one (or "Приёмка")
  useEffect(() => {
    if (priceOnly) return
    if (tab) {
      if (tab !== 'adjust') { try { localStorage.setItem(TAB_KEY, tab) } catch { /* private mode */ } }
      return
    }
    let saved = null
    try { saved = localStorage.getItem(TAB_KEY) } catch { /* private mode */ }
    setParams((p) => { p.set('tab', tabs.includes(saved) ? saved : 'receipt'); return p }, { replace: true })
  }, [tab, priceOnly]) // eslint-disable-line react-hooks/exhaustive-deps

  // "Приёмка" / "Продажа" from the overview or the scanner's panel: the item is the first line
  const offerId = params.get('offer')
  useEffect(() => {
    if (!offerId) return
    api.get('/seller/stock/search', { params: { q: offerId } }).then((r) => {
      const o = r.data.find((x) => String(x.id) === offerId)
      if (o) setStart(o)
    }).catch(() => {})
  }, [offerId])

  const branches = store.branches || []
  const allowed = BRANCHES_ONLY.includes(tab) ? branches : places
  const here = placeFor(allowed, place?.id)

  if (priceOnly) {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
        <h1 className="text-h1">{t('warehouse.title')}</h1>
        <Card className="grid max-w-2xl gap-3">
          <h2 className="text-h2">{t('warehouse.priceOnly.title')}</h2>
          <p className="text-sm text-muted">{t('warehouse.priceOnly.text')}</p>
          <div><ModeSwitch store={store} onChanged={setStore} size="lg" /></div>
        </Card>
        <h2 className="text-h3">{t('warehouse.priceOnly.journal')}</h2>
        <Journal branches={places} />
      </div>
    )
  }
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div>
        <h1 className="text-h1">{t('warehouse.title')}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{t('warehouse.hint')}</p>
      </div>
      {!branches.length ? <Card><p className="text-sm">{t('warehouse.noBranches')}</p></Card> : tab === 'journal' ? (
        <Journal branches={places} doc={params.get('doc')} />
      ) : !tab ? null : (
        <>
          {places.length > 1 && <PlaceLine place={here} other={here?.id !== place?.id} />}
          {tab === 'stocktake' ? <Stocktake key={here?.id} place={here} places={places} /> : (
            <Card>
              {tab === 'adjust' && <h2 className="mb-1 text-h3">{t('warehouse.tabs.adjust')}</h2>}
              <p className="mb-3 text-sm text-muted">{t(`warehouse.modeHints.${tab}`)}</p>
              <OperationForm key={`${tab}-${here?.id}-${version}`} kind={tab} branches={allowed} branchId={here?.id} big
                warehouseId={tab === 'move' ? store.warehouse?.id : undefined} draftKey={`${tab}_${here?.id}`}
                initialOffer={['receipt', 'sale'].includes(tab) ? start : null}
                onPosted={() => { setStart(null); setVersion((v) => v + 1) }} />
            </Card>
          )}
        </>
      )}
    </div>
  )
}

// Phase 12.5: the place is chosen once, in the top bar; here — a short line, a click opens that choice
function PlaceLine({ place, other }) {
  const { t } = useTranslation()
  return (
    <button type="button" onClick={() => window.dispatchEvent(new Event(PLACE_OPEN))} data-testid="place-line"
      className="-mt-1 inline-flex max-w-full items-center gap-1.5 justify-self-start rounded-md px-1 text-sm text-muted outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-primary">
      <MapPin className="size-4 shrink-0 text-primary" aria-hidden />
      <span className="truncate"><span className="font-semibold text-ink">{t('place.label', { place: placeLabel(t, place) })}</span>
        {other && ` · ${t('place.onlyBranches')}`}</span>
    </button>
  )
}

export function Journal({ branches, doc = null }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [f, setF] = useState({ offer: null, branch_id: '', kind: '', date_from: '', date_to: '', doc })
  useEffect(() => setF((x) => ({ ...x, doc })), [doc])
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const params = useCallback(() => ({
    offer_id: f.offer?.id, branch_id: f.branch_id || undefined, kind: f.kind || undefined,
    date_from: f.date_from || undefined, date_to: f.date_to || undefined, doc: f.doc || undefined,
  }), [f])
  useEffect(() => {
    setData(null)
    api.get('/seller/stock/journal', { params: { ...params(), page } }).then((r) => setData(r.data)).catch(() => setData({ items: [], total: 0, pages: 1 }))
  }, [params, page])
  const change = (patch) => { setF((x) => ({ ...x, ...patch })); setPage(1) }
  const dl = () => download('/seller/stock/journal.xlsx', params(), 'journal.xlsx').catch((err) => toast(t(errorKey(err)), 'danger'))
  const filtered = f.offer || f.branch_id || f.kind || f.date_from || f.date_to || f.doc

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <Card className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_auto_auto]">
          {f.offer ? (
            <div className="flex min-h-11 items-center gap-2 self-end rounded-md border border-line px-3 text-sm">
              <span className="min-w-0 flex-1 truncate">{f.offer.name}</span>
              <button type="button" onClick={() => change({ offer: null })} aria-label={t('warehouse.journal.reset')}><X className="size-4" /></button>
            </div>
          ) : (
            <div className="self-end"><GoodsInput autoFocus={false} hint={false} onPick={(o) => change({ offer: o })} placeholder={t('warehouse.journal.anyGoods')} /></div>
          )}
          <Select label={t('warehouse.branch')} value={f.branch_id} onChange={(e) => change({ branch_id: e.target.value })}>
            <option value="">{t('warehouse.journal.anyBranch')}</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{placeLabel(t, b)}</option>)}
          </Select>
          <Select label={t('warehouse.journal.kind')} value={f.kind} onChange={(e) => change({ kind: e.target.value })}>
            <option value="">{t('warehouse.journal.anyKind')}</option>
            {KINDS.map((k) => <option key={k} value={k}>{t(`warehouse.kinds.${k}`)}</option>)}
          </Select>
          <Input label={t('warehouse.journal.from')} type="date" value={f.date_from} onChange={(e) => change({ date_from: e.target.value })} />
          <Input label={t('warehouse.journal.to')} type="date" value={f.date_to} onChange={(e) => change({ date_to: e.target.value })} />
        </div>
        <div className="flex flex-wrap gap-2">
          {f.doc && <Badge tone="info" className="self-center">{t('warehouse.journal.docFilter', { doc: f.doc })}</Badge>}
          <Button variant="secondary" size="sm" onClick={dl}><Download className="size-4" aria-hidden />{t('warehouse.journal.download')}</Button>
          {filtered && <Button variant="text" size="sm" onClick={() => change({ offer: null, branch_id: '', kind: '', date_from: '', date_to: '', doc: null })}>{t('warehouse.journal.reset')}</Button>}
        </div>
      </Card>
      {data === null ? <Skeleton className="h-48 w-full rounded-xl" /> : data.items.length === 0 ? (
        <EmptyState icon={FileBarChart} title={t('warehouse.journal.empty')} />
      ) : (
        <>
          <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
            {data.items.map((m) => <MovementRow key={m.id} m={m} />)}
          </ul>
          <Pagination page={data.page} pages={data.pages} onChange={setPage} />
        </>
      )}
    </div>
  )
}

const TONE = { receipt: 'success', initial: 'neutral', sale: 'primary', res_sale: 'primary', adjust: 'warning', reserve: 'info', unreserve: 'info', import: 'neutral', undo: 'danger', manual: 'neutral', move_out: 'info', move_in: 'success', return: 'success', inventory: 'warning' }

export function MovementRow({ m, compact = false }) {
  const { t } = useTranslation()
  const reserve = m.kind === 'reserve' || m.kind === 'unreserve'
  const change = reserve ? m.reserved_delta : m.delta
  const qty = (v) => (v == null ? t('warehouse.journal.unknown') : v)
  return (
    <li className="rounded-lg border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Badge tone={TONE[m.kind]}>{t(`warehouse.kinds.${m.kind}`)}</Badge>
        <span className="min-w-0 flex-1 truncate font-medium" title={m.name}>{m.name}</span>
        <span className={`font-semibold tabular-nums ${change > 0 ? 'text-success' : change < 0 ? 'text-danger' : 'text-muted'}`}>
          {change > 0 ? `+${change}` : change}{reserve && ` ${t('warehouse.journal.reserve', { count: Math.abs(change) }).split(' ')[0]}`}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
        <span>{when(m.at)}</span>
        {m.branch && <span>{placeLabel(t, m.branch)}</span>}
        {m.units != null && <span>{t('warehouse.journal.units', { count: m.units })}</span>}
        <span>{t('warehouse.journal.wasNow')}: {qty(m.before)} → {qty(m.after)}{m.reserved_after > 0 && ` (${t('warehouse.journal.reserve', { count: m.reserved_after })})`}</span>
        {!compact && <span>{t('warehouse.journal.who')}: {t(`warehouse.journal.whoName.${m.who}`)}</span>}
        {m.cost != null && <span>{t('warehouse.cost.column')}: {formatPrice(m.cost, m.currency)}</span>}
        {m.price != null && <span>{t('warehouse.price')}: {formatPrice(m.price, m.currency)}</span>}
        {m.reason && <span>{t(`warehouse.reasons.${m.reason}`)}</span>}
        {m.comment && <span className="italic">«{m.comment}»</span>}
        {!compact && m.doc && <Link className="hover:underline" to={`/seller/stock?tab=journal&doc=${m.doc}`}>{t('warehouse.journal.doc', { doc: m.doc })}</Link>}
        {m.reservation_id && <Link className="text-primary hover:underline" to={`/seller/reservations?id=${m.reservation_id}`}>{t('warehouse.journal.res', { id: m.reservation_id })}</Link>}
        {m.import_id && <Link className="text-primary hover:underline" to={`/seller/imports/${m.import_id}`}>{t('warehouse.journal.upload', { id: m.import_id })}</Link>}
      </div>
    </li>
  )
}

export function ReportsPage() {
  const { t } = useTranslation()
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <h1 className="text-h1">{t('warehouse.reports.title')}</h1>
      <Card className="mx-auto w-full max-w-xl text-center md:!p-8">
        <FileBarChart className="mx-auto size-10 text-primary" aria-hidden />
        <h2 className="mt-4 text-h2">{t('warehouse.reports.soon')}</h2>
        <p className="mt-2 text-sm text-muted">{t('warehouse.reports.text')}</p>
        <div className="mt-5"><Button variant="secondary" to="/seller/stock?tab=journal">{t('warehouse.overview.openJournal')}</Button></div>
      </Card>
    </div>
  )
}
