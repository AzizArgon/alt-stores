import { placeLabel } from '../services/place'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useOutletContext } from 'react-router-dom'
import { ArrowRight, CalendarCheck, CircleCheck, CircleSlash, Clock, MessageSquare, Monitor, ShieldAlert } from 'lucide-react'
import { DemoNote } from '../components/Market'
import UndoUpload from '../components/UndoUpload'
import { DecisionsBlock } from '../components/AdminDecisions'
import { MovementRow } from './WarehousePage'
import { Button, Card, Skeleton } from '../components/ui'
import api from '../services/api'

// Each number opens "My goods" with the matching filter
const STATS = [
  { key: 'in_stock', icon: CircleCheck, tone: 'text-success', query: 'stock=in' },
  { key: 'out_of_stock', icon: CircleSlash, tone: 'text-muted', query: 'stock=out' },
  { key: 'flagged', icon: ShieldAlert, tone: 'text-warning', query: 'flagged=1' },
  { key: 'stale', icon: Clock, tone: 'text-faint', query: 'stale=1' },
]
const MARKET = [
  { key: 'below', tone: 'text-below' },
  { key: 'at', tone: 'text-at' },
  { key: 'above', tone: 'text-above' },
]

// "Overview": what is with the store's goods right now and where to go next
export default function CabinetOverview() {
  const { t } = useTranslation()
  const { store } = useOutletContext()
  const [data, setData] = useState(null)
  const [market, setMarket] = useState(null)

  const loadOverview = () => api.get('/seller/overview').then((res) => setData(res.data)).catch(() => setData({}))
  useEffect(() => {
    loadOverview()
    api.get('/seller/analytics', { params: { period: 'quarter' } }).then((res) => setMarket(res.data)).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-h2 break-words md:text-h1">{store.name}</h1>
          <p className="mt-1 text-sm text-muted">
            {/* A link to the upload history: on a phone it is not in the tab bar */}
            {data?.last_upload
              ? <Link to="/seller/imports" className="hover:text-primary hover:underline">{t('cabinet.overview.lastUpload', { date: new Date(data.last_upload.created_at).toLocaleDateString('ru-RU') })}</Link>
              : data && t('cabinet.overview.noUpload')}
          </p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <Button to="/seller/add?method=file" className="flex-1 sm:flex-none">{t('cabinet.overview.upload')}</Button>
          <Button to="/seller/add?method=catalog" variant="secondary" className="flex-1 sm:flex-none">{t('cabinet.overview.addOne')}</Button>
        </div>
      </div>

      {data?.undo && (
        <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface-2 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-w-0 text-sm break-words">
            <span className="font-medium">{t('undo.overview', { name: data.undo.filename || t('manual.source.text') })}</span>
            <span className="block text-muted">{t('undo.deadline', { date: new Date(data.undo.deadline).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) })}</span>
          </p>
          <UndoUpload importId={data.undo.id} onDone={loadOverview} className="w-full shrink-0 sm:w-auto" />
        </div>
      )}

      {!data ? <Skeleton className="h-28 w-full rounded-xl" /> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {STATS.map(({ key, icon: Icon, tone, query }) => (
            <Link key={key} to={`/seller/goods?${query}`}
              className="rounded-xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-hover">
              <Icon className={`size-5 ${tone}`} aria-hidden />
              <p className="mt-2 text-h1 tabular-nums">{data[key] ?? 0}</p>
              <p className="text-sm text-muted">{t(`cabinet.overview.stat.${key}`)}</p>
            </Link>
          ))}
        </div>
      )}
      {data?.stale > 0 && <p className="-mt-3 text-xs text-muted">{t('cabinet.overview.staleHint')}</p>}
      <DecisionsBlock />
      {data?.chat && (
        <Link to="/seller/messages" className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-hover">
          <span className="flex min-w-0 items-center gap-2.5">
            <MessageSquare className="size-5 shrink-0 text-primary" aria-hidden />
            <span className="text-sm">
              {t('cabinet.overview.chatNew', { count: data.chat.new_messages })}
              {data.chat.waiting_day > 0 && <span className="font-medium text-warning"> · {t('cabinet.overview.chatWaiting', { count: data.chat.waiting_day })}</span>}
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary">{t('cabinet.overview.chatLink')}<ArrowRight className="size-4" aria-hidden /></span>
        </Link>
      )}
      {data?.reservations && (
        <Link to="/seller/reservations" className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-hover">
          <span className="flex min-w-0 items-center gap-2.5">
            <CalendarCheck className="size-5 shrink-0 text-primary" aria-hidden />
            <span className="text-sm">
              {t('cabinet.overview.reservationsNew', { count: data.reservations.new })}
              {data.reservations.ending_today > 0 && <span className="font-medium text-warning"> · {t('cabinet.overview.reservationsEnding', { count: data.reservations.ending_today })}</span>}
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary">{t('cabinet.overview.reservationsLink')}<ArrowRight className="size-4" aria-hidden /></span>
        </Link>
      )}
      {data?.builds && (
        <Link to="/seller/builds" className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-hover">
          <span className="flex min-w-0 items-center gap-2.5">
            <Monitor className="size-5 shrink-0 text-primary" aria-hidden />
            <span className="text-sm">{t('cabinet.overview.builds', { on: data.builds.on_sale, off: data.builds.off_sale })}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary">{t('cabinet.overview.buildsLink')}<ArrowRight className="size-4" aria-hidden /></span>
        </Link>
      )}

      {data?.warehouse && <WarehouseOverview w={data.warehouse} />}
      {data?.stock && <StockOverview stock={data.stock} />}

      <Card as="section">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex flex-wrap items-center gap-2 text-h3">{t('cabinet.overview.marketTitle')} <DemoNote show={market?.includes_demo} /></h2>
          <Link to="/seller/analytics" className="flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            {t('cabinet.overview.marketMore')}<ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
        <p className="mt-1 text-sm text-muted">{t('cabinet.overview.marketHint')}</p>
        {!market ? <Skeleton className="mt-4 h-16 w-full" /> : (
          <div className="mt-4 grid grid-cols-3 gap-3">
            {MARKET.map(({ key, tone }) => (
              <Link key={key} to={`/seller/goods?market=${key}`} className="rounded-lg bg-surface-2 p-3 hover:bg-line">
                <p className={`text-h2 tabular-nums ${tone}`}>{market.position.counts[key]}</p>
                <p className="text-xs text-muted md:text-sm">{t(`cabinet.overview.market.${key}`)}</p>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

const day = (iso) => new Intl.DateTimeFormat('ru', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(iso))

// Phase 12.4: what needs the seller's eyes — sold more than the books had, reservations whose item was sold, an
// unfinished stocktake, the last one, goods only in the warehouse
function WarehouseOverview({ w }) {
  const { t } = useTranslation()
  const last = w.last_stocktake
  const placeName = (s) => (s.is_warehouse ? t('place.warehouse') : s.branch)
  const List = ({ items, link, label }) => (
    <ul className="mt-2 divide-y divide-line">
      {items.map((i) => (
        <li key={i.offer_id ?? i.id} className="flex items-center justify-between gap-3 py-2 text-sm">
          <span className="min-w-0 truncate font-medium" title={i.name || i.title}>{i.name || i.title}{i.quantity != null && <span className="font-normal text-muted"> · {i.quantity}</span>}</span>
          {link && <Button size="sm" variant="secondary" to={link(i)} className="shrink-0">{label}</Button>}
        </li>
      ))}
    </ul>
  )
  return (
    <Card as="section" className="grid grid-cols-[minmax(0,1fr)] gap-5">
      {w.open_stocktakes.map((s) => (
        <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning-line bg-warning-soft p-3">
          <span className="text-sm"><span className="font-semibold">{t('warehouse.overview.openStocktake')}</span> · {placeName(s)} · {t('warehouse.stocktake.units', { count: s.counted_units })}</span>
          <Button size="sm" to="/seller/stock?tab=stocktake">{t('warehouse.overview.continue')}</Button>
        </div>
      ))}
      {w.oversold.length > 0 && (
        <div>
          <h2 className="text-h3 text-warning">{t('warehouse.overview.oversold')}</h2>
          <p className="mt-0.5 text-xs text-muted">{t('warehouse.overview.oversoldHint')}</p>
          <List items={w.oversold} link={() => '/seller/stock?tab=stocktake'} label={t('warehouse.tabs.stocktake')} />
          {w.oversold_total > w.oversold.length && <p className="mt-1 text-xs text-muted">{t('warehouse.overview.more', { count: w.oversold_total - w.oversold.length })}</p>}
        </div>
      )}
      {w.sold_reservations.length > 0 && (
        <div>
          <h2 className="text-h3 text-danger">{t('warehouse.overview.soldRes')}</h2>
          <p className="mt-0.5 text-xs text-muted">{t('warehouse.overview.soldResHint')}</p>
          <List items={w.sold_reservations} link={(r) => `/seller/reservations?id=${r.id}`} label={t('cabinet.nav.reservations')} />
        </div>
      )}
      {w.only_warehouse.length > 0 && (
        <div>
          <h2 className="text-h3">{t('warehouse.overview.onlyWarehouse')}</h2>
          <p className="mt-0.5 text-xs text-muted">{t('warehouse.overview.onlyWarehouseHint')}</p>
          <List items={w.only_warehouse} link={(i) => `/seller/stock?tab=move&offer=${i.offer_id}`} label={t('warehouse.overview.toMove')} />
          {w.only_warehouse_total > w.only_warehouse.length && <p className="mt-1 text-xs text-muted">{t('warehouse.overview.more', { count: w.only_warehouse_total - w.only_warehouse.length })}</p>}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span><span className="font-semibold">{t('warehouse.overview.lastStocktake')}:</span> {last
          ? t('warehouse.overview.lastStocktakeLine', { ...last, date: day(last.finished_at), place: placeName(last) })
          : <span className="text-muted">{t('warehouse.overview.noStocktake')}</span>}</span>
        <Link to="/seller/stock?tab=stocktake" className="flex items-center gap-1 font-medium text-primary hover:underline">{t('warehouse.tabs.stocktake')}<ArrowRight className="size-4" aria-hidden /></Link>
      </div>
    </Card>
  )
}

// Phase 12.2, "Учёт остатков": running low (with a receipt link), reservations without a reserve, last movements
function StockOverview({ stock }) {
  const { t } = useTranslation()
  return (
    <Card as="section" className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <div>
        <h2 className="text-h3">{t('warehouse.overview.low')}</h2>
        <p className="mt-0.5 text-xs text-muted">{t('warehouse.overview.lowHint', { count: stock.threshold })}</p>
        {stock.low.length === 0 ? <p className="mt-2 text-sm text-muted">{t('warehouse.overview.lowNone')}</p> : (
          <ul className="mt-2 divide-y divide-line">
            {stock.low.map((i) => (
              <li key={`${i.offer_id}-${i.branch_id}`} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0">
                  <span className="block truncate font-medium" title={i.name}>{i.name}</span>
                  <span className="text-xs text-muted">{placeLabel(t, i.branch)} ·<span className={i.available === 0 ? 'text-danger' : 'text-warning'}>{t('warehouse.overview.available', { count: i.available })}</span></span>
                </span>
                <Button size="sm" variant="secondary" to={`/seller/stock?tab=receipt&offer=${i.offer_id}`} className="shrink-0">{t('warehouse.overview.toReceipt')}</Button>
              </li>
            ))}
          </ul>
        )}
        {stock.low_total > stock.low.length && <p className="mt-1 text-xs text-muted">{t('warehouse.overview.more', { count: stock.low_total - stock.low.length })}</p>}
      </div>
      {stock.unreserved.length > 0 && (
        <div>
          <h2 className="text-h3 text-warning">{t('warehouse.overview.unreserved')}</h2>
          <p className="mt-0.5 text-xs text-muted">{t('warehouse.overview.unreservedHint')}</p>
          <ul className="mt-2 grid gap-1 text-sm">
            {stock.unreserved.map((r) => (
              <li key={r.id}><Link className="text-primary hover:underline" to={`/seller/reservations?id=${r.id}`}>№{r.id} · {r.title}</Link> <span className="text-muted">× {r.quantity}{r.branch && ` · ${r.branch}`}</span></li>
            ))}
          </ul>
        </div>
      )}
      {stock.last.length > 0 && (
        <div>
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-h3">{t('warehouse.overview.last')}</h2>
            <Link to="/seller/stock?tab=journal" className="flex items-center gap-1 text-sm font-medium text-primary hover:underline">{t('warehouse.overview.openJournal')}<ArrowRight className="size-4" aria-hidden /></Link>
          </div>
          <ul className="mt-2 grid grid-cols-[minmax(0,1fr)] gap-2">{stock.last.map((m) => <MovementRow key={m.id} m={m} compact />)}</ul>
        </div>
      )}
    </Card>
  )
}
