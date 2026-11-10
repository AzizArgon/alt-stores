import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { Download, FileBarChart, X } from 'lucide-react'
import { branchLabel } from '../components/BranchStock'
import { GoodsInput, OperationForm, download } from '../components/Warehouse'
import { useToast } from '../components/overlays'
import { Badge, Button, Card, EmptyState, Input, Pagination, Select, Skeleton, Tabs } from '../components/ui'
import api, { errorKey } from '../services/api'
import { formatPrice } from '../services/format'

const TABS = ['receipt', 'sale', 'adjust', 'journal']
const KINDS = ['initial', 'receipt', 'sale', 'adjust', 'reserve', 'unreserve', 'res_sale', 'import', 'undo', 'manual']

const when = (iso) => new Intl.DateTimeFormat('ru', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

export default function WarehousePage() {
  const { t } = useTranslation()
  const { store } = useOutletContext()
  const [params, setParams] = useSearchParams()
  const tab = TABS.includes(params.get('tab')) ? params.get('tab') : (store.stock_mode === 'stock' ? 'receipt' : 'journal')
  const branches = store.branches || []
  const [start, setStart] = useState(null)
  const [version, setVersion] = useState(0)

  // "Приход" from the overview's "заканчивается": the item is the first line
  const offerId = params.get('offer')
  useEffect(() => {
    if (!offerId) return
    api.get('/seller/stock/search', { params: { q: offerId } }).then((r) => {
      const o = r.data.find((x) => String(x.id) === offerId)
      if (o) setStart(o)
    }).catch(() => {})
  }, [offerId])

  const ops = tab !== 'journal'
  return (
    <div className="grid gap-5">
      <div>
        <h1 className="text-h1">{t('warehouse.title')}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{t('warehouse.hint')}</p>
      </div>
      <Tabs tabs={TABS.map((v) => ({ value: v, label: t(`warehouse.tabs.${v}`) }))} value={tab} label={t('warehouse.title')}
        onChange={(v) => setParams({ tab: v })} />
      {ops && store.stock_mode !== 'stock' && (
        <Card className="grid gap-3">
          <p className="text-sm">{t('warehouse.modeOff')}</p>
          <div><Button to="/seller/profile#stock-mode" variant="secondary">{t('warehouse.toProfile')}</Button></div>
        </Card>
      )}
      {ops && store.stock_mode === 'stock' && !branches.length && <Card><p className="text-sm">{t('warehouse.noBranches')}</p></Card>}
      {ops && store.stock_mode === 'stock' && branches.length > 0 && (
        <Card>
          <OperationForm key={`${tab}-${version}`} kind={tab} branches={branches} initialOffer={tab === 'receipt' ? start : null}
            onPosted={() => setVersion((v) => v + 1)} />
        </Card>
      )}
      {tab === 'journal' && <Journal branches={branches} />}
    </div>
  )
}

export function Journal({ branches }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [f, setF] = useState({ offer: null, branch_id: '', kind: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const params = useCallback(() => ({
    offer_id: f.offer?.id, branch_id: f.branch_id || undefined, kind: f.kind || undefined,
    date_from: f.date_from || undefined, date_to: f.date_to || undefined,
  }), [f])
  useEffect(() => {
    setData(null)
    api.get('/seller/stock/journal', { params: { ...params(), page } }).then((r) => setData(r.data)).catch(() => setData({ items: [], total: 0, pages: 1 }))
  }, [params, page])
  const change = (patch) => { setF((x) => ({ ...x, ...patch })); setPage(1) }
  const dl = () => download('/seller/stock/journal.xlsx', params(), 'journal.xlsx').catch((err) => toast(t(errorKey(err)), 'danger'))
  const filtered = f.offer || f.branch_id || f.kind || f.date_from || f.date_to

  return (
    <div className="grid gap-4">
      <Card className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_auto_auto]">
          {f.offer ? (
            <div className="flex min-h-11 items-center gap-2 self-end rounded-md border border-line px-3 text-sm">
              <span className="min-w-0 flex-1 truncate">{f.offer.name}</span>
              <button type="button" onClick={() => change({ offer: null })} aria-label={t('warehouse.journal.reset')}><X className="size-4" /></button>
            </div>
          ) : (
            <div className="self-end"><GoodsInput autoFocus={false} onPick={(o) => change({ offer: o })} placeholder={t('warehouse.journal.anyGoods')} /></div>
          )}
          <Select label={t('warehouse.branch')} value={f.branch_id} onChange={(e) => change({ branch_id: e.target.value })}>
            <option value="">{t('warehouse.journal.anyBranch')}</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{branchLabel(b)}</option>)}
          </Select>
          <Select label={t('warehouse.journal.kind')} value={f.kind} onChange={(e) => change({ kind: e.target.value })}>
            <option value="">{t('warehouse.journal.anyKind')}</option>
            {KINDS.map((k) => <option key={k} value={k}>{t(`warehouse.kinds.${k}`)}</option>)}
          </Select>
          <Input label={t('warehouse.journal.from')} type="date" value={f.date_from} onChange={(e) => change({ date_from: e.target.value })} />
          <Input label={t('warehouse.journal.to')} type="date" value={f.date_to} onChange={(e) => change({ date_to: e.target.value })} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={dl}><Download className="size-4" aria-hidden />{t('warehouse.journal.download')}</Button>
          {filtered && <Button variant="text" size="sm" onClick={() => change({ offer: null, branch_id: '', kind: '', date_from: '', date_to: '' })}>{t('warehouse.journal.reset')}</Button>}
        </div>
      </Card>
      {data === null ? <Skeleton className="h-48 w-full rounded-xl" /> : data.items.length === 0 ? (
        <EmptyState icon={FileBarChart} title={t('warehouse.journal.empty')} />
      ) : (
        <>
          <ul className="grid gap-2">
            {data.items.map((m) => <MovementRow key={m.id} m={m} />)}
          </ul>
          <Pagination page={data.page} pages={data.pages} onChange={setPage} />
        </>
      )}
    </div>
  )
}

const TONE = { receipt: 'success', initial: 'neutral', sale: 'primary', res_sale: 'primary', adjust: 'warning', reserve: 'info', unreserve: 'info', import: 'neutral', undo: 'danger', manual: 'neutral' }

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
        {m.branch && <span>{m.branch}</span>}
        <span>{t('warehouse.journal.wasNow')}: {qty(m.before)} → {qty(m.after)}{m.reserved_after > 0 && ` (${t('warehouse.journal.reserve', { count: m.reserved_after })})`}</span>
        {!compact && <span>{t('warehouse.journal.who')}: {t(`warehouse.journal.whoName.${m.who}`)}</span>}
        {m.cost != null && <span>{t('warehouse.cost')}: {formatPrice(m.cost, m.currency)}</span>}
        {m.price != null && <span>{t('warehouse.price')}: {formatPrice(m.price, m.currency)}</span>}
        {m.reason && <span>{t(`warehouse.reasons.${m.reason}`)}</span>}
        {m.comment && <span className="italic">«{m.comment}»</span>}
        {!compact && m.doc && <span>{t('warehouse.journal.doc', { doc: m.doc })}</span>}
        {m.reservation_id && <Link className="text-primary hover:underline" to={`/seller/reservations?id=${m.reservation_id}`}>{t('warehouse.journal.res', { id: m.reservation_id })}</Link>}
        {m.import_id && <Link className="text-primary hover:underline" to={`/seller/imports/${m.import_id}`}>{t('warehouse.journal.upload', { id: m.import_id })}</Link>}
      </div>
    </li>
  )
}

export function ReportsPage() {
  const { t } = useTranslation()
  return (
    <div className="grid gap-5">
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
