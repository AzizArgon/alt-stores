import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOutletContext, useSearchParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, Camera, ChevronDown, Download, Info, OctagonAlert, PackageSearch, TriangleAlert, Upload } from 'lucide-react'
import { QtyInput, branchLabel, stockOf } from '../components/BranchStock'
import { StockImport, download } from '../components/Warehouse'
import { CategoryIcon } from '../components/CategoryIcon'
import { MarketLabel } from '../components/Market'
import OfferEditor from '../components/OfferEditor'
import OfferPhotosModal from '../components/OfferPhotos'
import { Dropdown, DropdownItem, Modal, useToast } from '../components/overlays'
import { Badge, Button, Card, Checkbox, EmptyState, Pagination, Skeleton, Switch, inputClass } from '../components/ui'
import api, { errorKey } from '../services/api'
import { formatDate, formatPrice, roundSum, roundUsd } from '../services/format'

const CONDITIONS = ['new', 'new_openbox', 'used', 'refurbished', 'unknown']
const SORTS = ['updated', 'name', 'price', 'condition', 'stock', 'market', 'flags']
const FLAG_ICON = { info: Info, warning: TriangleAlert, danger: OctagonAlert }
const selectClass = `${inputClass} min-w-0`

// "≈ 1 234 000 сум" under a dollar price, "≈ $98" under a sum price (CBU rate)
export function Converted({ price, currency, rate, className = 'text-xs text-muted' }) {
  if (price == null || !rate) return null
  return (
    <p className={className}>
      ≈ {currency === 'USD' ? formatPrice(roundSum(price * rate.rate), 'UZS') : formatPrice(roundUsd(price / rate.rate), 'USD')}
    </p>
  )
}

// Compact Anti-Fraud badges for the list; the full soft text is in the editor
export function FlagBadges({ flags }) {
  const { t } = useTranslation()
  if (!flags?.length) return null
  return (
    <span className="flex flex-wrap gap-1">
      {flags.map((f) => {
        const Icon = FLAG_ICON[f.level]
        return (
          <Badge key={`${f.type}-${f.reason_key}`} tone={f.level} title={t(`flags.reason.${f.reason_key}`, f.params)}>
            <Icon className="size-3" aria-hidden />{t(`flags.type.${f.type}`)}
          </Badge>
        )
      })}
    </span>
  )
}

// The price right in the row: Enter or leaving the field saves, Esc brings the old value back
function PriceInput({ offer, onSave, className = '' }) {
  const { t } = useTranslation()
  const [value, setValue] = useState(offer.price ?? '')
  const cancelled = useRef(false)
  useEffect(() => setValue(offer.price ?? ''), [offer.price])

  const save = () => {
    if (cancelled.current) {
      cancelled.current = false
      return
    }
    const next = value === '' ? null : Number(value)
    if (next === offer.price) return
    if (!next || next <= 0) {
      setValue(offer.price ?? '')
      return
    }
    onSave(offer.id, { price: next })
  }
  return (
    <span className={`flex items-center gap-1 ${className}`}>
      <input type="number" inputMode="decimal" min="0" step="any" value={value} aria-label={t('cabinet.col.price')}
        onChange={(e) => setValue(e.target.value)} onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur()
          if (e.key === 'Escape') {
            cancelled.current = true
            setValue(offer.price ?? '')
            e.currentTarget.blur()
          }
        }}
        className="h-9 w-full min-w-0 rounded-md border border-line-strong bg-surface px-2 text-sm tabular-nums outline-none hover:border-faint focus:border-primary focus:ring-2 focus:ring-primary-soft" />
      <span className="shrink-0 text-xs text-muted">{offer.currency === 'USD' ? '$' : t('currency.UZS')}</span>
    </span>
  )
}

function SortHeader({ k, sort, desc, onSort, className = '', children }) {
  const active = sort === k
  const Arrow = desc ? ArrowDown : ArrowUp
  return (
    <th className={`px-2 py-2 font-medium ${className}`} aria-sort={active ? (desc ? 'descending' : 'ascending') : undefined}>
      <button type="button" onClick={() => onSort(k)} className={`inline-flex items-center gap-1 rounded hover:text-ink ${active ? 'text-ink' : ''}`}>
        {children}{active && <Arrow className="size-3.5" aria-hidden />}
      </button>
    </th>
  )
}

export function Filters({ params, setParam, categories, branches }) {
  const { t } = useTranslation()
  const [q, setQ] = useState(params.get('q') || '')
  // The search waits until the seller stops typing
  useEffect(() => {
    const timer = setTimeout(() => { if (q !== (params.get('q') || '')) setParam('q', q) }, 350)
    return () => clearTimeout(timer)
  }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  const select = (key, options, labelKey) => (
    <select value={params.get(key) || ''} onChange={(e) => setParam(key, e.target.value)} aria-label={t(`cabinet.filter.${key}`)}
      className={`${selectClass} ${params.get(key) ? 'border-primary' : ''}`}>
      <option value="">{t(`cabinet.filter.${key}`)}: {t('cabinet.filter.all')}</option>
      {options.map((o) => <option key={o} value={o}>{t(`${labelKey}.${o}`)}</option>)}
    </select>
  )
  return (
    <div className="grid gap-2 border-b border-line p-3 md:p-4">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('cabinet.searchPlaceholder')} className={inputClass} type="search" />
      <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
        {select('category', categories, 'categories')}
        {select('stock', ['in', 'out'], 'cabinet.stock')}
        {select('condition', CONDITIONS, 'condition')}
        {select('market', ['below', 'at', 'above'], 'cabinet.marketFilter')}
        {branches.length > 0 && (
          // Phase 12.1: the stock filter and the columns of one branch
          <select value={params.get('branch') || ''} onChange={(e) => setParam('branch', e.target.value)} aria-label={t('stock.branchFilter')}
            className={`${selectClass} ${params.get('branch') ? 'border-primary' : ''}`}>
            <option value="">{t('stock.branchFilter')}: {t('stock.allBranches')}</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{branchLabel(b)}</option>)}
          </select>
        )}
      </div>
      <div className="flex flex-wrap gap-x-5">
        <Checkbox label={t('cabinet.filter.flagged')} checked={params.get('flagged') === '1'} onChange={(e) => setParam('flagged', e.target.checked ? '1' : '')} />
        <Checkbox label={t('cabinet.filter.stale')} checked={params.get('stale') === '1'} onChange={(e) => setParam('stale', e.target.checked ? '1' : '')} />
        <Checkbox label={t('photo.noPhoto')} checked={params.get('no_photo') === '1'} onChange={(e) => setParam('no_photo', e.target.checked ? '1' : '')} />
      </div>
    </div>
  )
}

// Bulk actions over chosen rows (or all by the filter): preview "N goods will change" first
function BulkBar({ count, total, allByFilter, onAll, onClear, onAction, branches }) {
  const { t } = useTranslation()
  const [percent, setPercent] = useState('5')
  const [branch, setBranch] = useState(() => String(branches[0]?.id || ''))
  return (
    <div className="sticky top-16 z-10 flex flex-wrap items-center gap-2 border-b border-primary bg-primary-soft px-3 py-2 text-sm md:px-4">
      <span className="font-medium">{t('cabinet.bulk.selected', { count: allByFilter ? total : count })}</span>
      {!allByFilter && total > count && (
        <button type="button" onClick={onAll} className="text-primary underline">{t('cabinet.bulk.selectAll', { count: total })}</button>
      )}
      <button type="button" onClick={onClear} className="text-muted underline">{t('cabinet.bulk.clear')}</button>
      <span className="flex w-full flex-wrap items-center gap-2 lg:ml-auto lg:w-auto">
        <Button size="sm" variant="secondary" onClick={() => onAction('off')}>{t('cabinet.bulk.off')}</Button>
        <Button size="sm" variant="secondary" onClick={() => onAction('on')}>{t('cabinet.bulk.on')}</Button>
        <span className="flex items-center gap-1">
          <input type="number" step="any" value={percent} onChange={(e) => setPercent(e.target.value)} aria-label={t('cabinet.bulk.percent')}
            className="h-9 w-16 rounded-md border border-line-strong bg-surface px-2 text-sm tabular-nums" />
          <span className="text-muted">%</span>
          <Button size="sm" disabled={!Number(percent)} onClick={() => onAction('price', Number(percent))}>{t('cabinet.bulk.price')}</Button>
        </span>
        {branches.length > 0 && (
          <span className="flex min-w-0 flex-wrap items-center gap-1">
            <select value={branch} onChange={(e) => setBranch(e.target.value)} aria-label={t('stock.bulkBranch')}
              className="h-9 max-w-44 min-w-0 rounded-md border border-line-strong bg-surface px-2 text-sm">
              {branches.map((b) => <option key={b.id} value={b.id}>{t('stock.inBranch', { branch: branchLabel(b) })}</option>)}
            </select>
            <Button size="sm" variant="secondary" onClick={() => onAction('branch_on', null, Number(branch))}>{t('stock.markPresent')}</Button>
            <Button size="sm" variant="secondary" onClick={() => onAction('branch_off', null, Number(branch))}>{t('stock.markAbsent')}</Button>
          </span>
        )}
      </span>
    </div>
  )
}

function BulkConfirm({ preview, onCancel, onApply, busy }) {
  const { t } = useTranslation()
  if (!preview) return null
  const { action, percent, result, branch } = preview
  return (
    <Modal open onClose={onCancel} title={t(`cabinet.bulk.title.${action}`, { percent: percent > 0 ? `+${percent}` : percent, branch: branchLabel(branch) })}
      footer={<>
        <Button variant="secondary" onClick={onCancel}>{t('manual.cancel')}</Button>
        <Button disabled={busy || result.count === 0} onClick={onApply}>{t('cabinet.bulk.apply', { count: result.count })}</Button>
      </>}>
      <p className="text-sm">{result.count ? t('cabinet.bulk.willChange', { count: result.count }) : t('cabinet.bulk.nothing')}</p>
      {action === 'price' && result.count > 0 && (
        <>
          <p className="mt-1 text-xs text-muted">{t('cabinet.bulk.rounding')}</p>
          <ul className="mt-3 max-h-72 divide-y divide-line overflow-y-auto text-sm">
            {result.items.map((i) => (
              <li key={i.id} className="flex justify-between gap-3 py-1.5">
                <span className="min-w-0 truncate">{i.name}</span>
                <span className="shrink-0 tabular-nums text-muted">{formatPrice(i.old_price, i.currency)} → <span className="font-medium text-ink">{formatPrice(i.price, i.currency)}</span></span>
              </li>
            ))}
          </ul>
          {result.count > result.items.length && <p className="mt-1 text-xs text-muted">{t('importSummary.more', { count: result.count - result.items.length })}</p>}
        </>
      )}
    </Modal>
  )
}

// "My goods": the store's offers, price and stock right in the row, the editor on a click
export default function GoodsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const { store } = useOutletContext() || {}
  const branches = store?.branches || []
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [categories, setCategories] = useState([])
  const [rate, setRate] = useState(null)
  const [selected, setSelected] = useState(() => new Set())
  const [allByFilter, setAllByFilter] = useState(false)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  // ?edit=<offer id>: opened from a reservation ("Take it off sale" - the seller decides, the site changes nothing)
  const [editing, setEditing] = useState(() => Number(params.get('edit')) || null)
  const [photosFor, setPhotosFor] = useState(null)
  // Phase 12.4: "Открыть товар" of the scanner's panel on this same page
  const editParam = Number(params.get('edit')) || null
  useEffect(() => { if (editParam) setEditing(editParam) }, [editParam])
  const [reloadKey, setReloadKey] = useState(0)
  const [showCost, setShowCost] = useState(() => { try { return localStorage.getItem('alt_goods_cost') === '1' } catch { return false } })
  useEffect(() => { try { localStorage.setItem('alt_goods_cost', showCost ? '1' : '0') } catch { /* private mode */ } }, [showCost])

  const sort = params.get('sort') || 'updated'
  const desc = params.get('desc') !== '0'
  const page = Number(params.get('page')) || 1
  const query = params.toString()

  useEffect(() => {
    api.get('/seller/overview').then((res) => setCategories(res.data.categories)).catch(() => {})
    api.get('/rates/usd').then((res) => setRate(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const p = Object.fromEntries(new URLSearchParams(query))
    if (p.flagged) p.flagged = true
    if (p.stale) p.stale = true
    if (p.no_photo) p.no_photo = true
    api.get('/seller/offers', { params: p }).then((res) => setData(res.data)).catch(() => setData({ total: 0, items: [], page_size: 50 }))
  }, [query, reloadKey])

  const filterKey = [...params.entries()].filter(([k]) => !['page', 'sort', 'desc'].includes(k)).join('&')
  useEffect(() => { setSelected(new Set()); setAllByFilter(false) }, [filterKey])

  const setParam = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  const onSort = (k) => {
    const next = new URLSearchParams(params)
    next.set('sort', k)
    // A new column starts from A to Z / cheap first; the same column flips the direction
    next.set('desc', sort === k ? (desc ? '0' : '1') : (['name', 'price', 'condition'].includes(k) ? '0' : '1'))
    next.delete('page')
    setParams(next, { replace: true })
  }

  const replaceRow = (row) => setData((d) => ({ ...d, items: d.items.map((o) => (o.id === row.id ? row : o)) }))
  const patch = async (id, changes) => {
    try {
      const res = await api.patch(`/seller/offers/${id}`, changes)
      replaceRow(res.data)
      toast(t('cabinet.saved'))
    } catch (err) {
      toast(t(errorKey(err, { 422: `cabinet.error.${err.response?.data?.detail?.code || 'save'}` })), 'danger')
      setReloadKey((k) => k + 1)
    }
  }

  const toggle = (id) => setSelected((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setAllByFilter(false)
    return next
  })
  const pageIds = data?.items.map((o) => o.id) || []
  const pageChecked = pageIds.length > 0 && pageIds.every((id) => selected.has(id))
  const togglePage = () => setSelected((prev) => {
    const next = new Set(prev)
    pageIds.forEach((id) => (pageChecked ? next.delete(id) : next.add(id)))
    setAllByFilter(false)
    return next
  })

  const bulkBody = (action, percent, branchId) => {
    const extra = branchId ? { branch_id: branchId } : {}
    if (!allByFilter) return { ids: [...selected], action, percent, ...extra }
    const f = Object.fromEntries(new URLSearchParams(query))
    delete f.page; delete f.sort; delete f.desc
    return { filter: { ...f, flagged: Boolean(f.flagged), stale: Boolean(f.stale), no_photo: Boolean(f.no_photo) }, action, percent, ...extra }
  }
  const askBulk = async (action, percent, branchId) => {
    try {
      const res = await api.post('/seller/offers/bulk', { ...bulkBody(action, percent, branchId), apply: false })
      setPreview({ action, percent, branchId, branch: branches.find((b) => b.id === branchId), result: res.data })
    } catch (err) {
      toast(t(errorKey(err)), 'danger')
    }
  }
  const applyBulk = async () => {
    setBusy(true)
    try {
      const res = await api.post('/seller/offers/bulk', { ...bulkBody(preview.action, preview.percent, preview.branchId), apply: true })
      toast(t('cabinet.bulk.done', { count: res.data.count }))
      setPreview(null)
      setSelected(new Set())
      setAllByFilter(false)
      setReloadKey((k) => k + 1)
    } catch (err) {
      toast(t(errorKey(err)), 'danger')
    } finally {
      setBusy(false)
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const anySelected = selected.size > 0 || allByFilter
  const hasFilters = filterKey.length > 0
  // Columns by branch (phase 12.1): the chosen branch, else all; 3+ places fold into one "Остатки"
  const chosen = branches.find((b) => String(b.id) === params.get('branch'))
  const { places, columns, folded } = stockColumns(branches, chosen)
  const stockCols = columns.length > 0 || folded
  const stockMode = store?.stock_mode === 'stock'
  // The general switch of an item kept by branch: in "Учёт остатков" only operations change it
  const lockStock = (o) => stockMode && Object.keys(o.stocks || {}).length > 0

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="text-h2 md:text-h1">{t('cabinet.nav.goods')}</h1>
        {data && <p className="text-sm text-muted">{t('cabinet.found', { count: data.total })}</p>}
      </div>
      <ExcelBar query={query} stockMode={stockMode} showCost={showCost} setShowCost={setShowCost} onImported={() => setReloadKey((k) => k + 1)} />
      <Card padded={false} className="min-w-0">
        <Filters params={params} setParam={setParam} categories={categories} branches={branches} />
        <div className="flex items-center gap-2 border-b border-line px-3 py-2 text-sm md:px-4 lg:hidden">
          <Checkbox label={t('cabinet.bulk.page')} checked={pageChecked} onChange={togglePage} />
          <select value={sort} onChange={(e) => onSort(e.target.value)} aria-label={t('cabinet.sort')} className="ml-auto h-9 max-w-[55%] min-w-0 rounded-md border border-line-strong bg-surface px-2 text-sm">
            {SORTS.map((s) => <option key={s} value={s}>{t(`cabinet.sortBy.${s}`)}</option>)}
          </select>
          <button type="button" onClick={() => onSort(sort)} aria-label={t('cabinet.sortDirection')}
            className="flex size-9 shrink-0 items-center justify-center rounded-md border border-line-strong">
            {desc ? <ArrowDown className="size-4" aria-hidden /> : <ArrowUp className="size-4" aria-hidden />}
          </button>
        </div>
        {anySelected && (
          <BulkBar count={selected.size} total={data?.total || 0} allByFilter={allByFilter} onAll={() => setAllByFilter(true)}
            onClear={() => { setSelected(new Set()); setAllByFilter(false) }} onAction={askBulk} branches={branches} />
        )}

        {!data && <div className="grid gap-2 p-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16 w-full" />)}</div>}
        {data?.items.length === 0 && (
          <EmptyState icon={PackageSearch} title={t(hasFilters ? 'cabinet.emptyFiltered' : 'cabinet.empty')}
            hint={t(hasFilters ? 'cabinet.emptyFilteredHint' : 'cabinet.emptyHint')}>
            {!hasFilters && <Button to="/seller/add">{t('cabinet.overview.upload')}</Button>}
          </EmptyState>
        )}

        {data?.items.length > 0 && (
          <>
            {/* Computer: a table; the condition and the date fold under the name on a narrower screen */}
            {/* Many columns (the stock, the purchase and the markup): the table scrolls sideways inside its block, the
                tick and the name stay on the left; the name is never narrower than 240 px */}
            <div className="hidden overflow-x-auto overscroll-x-contain lg:block" data-testid="goods-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-left text-muted">
                <tr>
                  <th className={`${STICKY_TICK} w-10 bg-surface-2 px-3`}><input type="checkbox" className="size-4 accent-primary" checked={pageChecked} onChange={togglePage} aria-label={t('cabinet.bulk.page')} /></th>
                  <SortHeader k="name" sort={sort} desc={desc} onSort={onSort} className={`${STICKY_NAME} ${NAME_COL} bg-surface-2`}>{t('cabinet.col.name')}</SortHeader>
                  <SortHeader k="price" sort={sort} desc={desc} onSort={onSort} className={stockCols ? 'w-32 min-w-32' : 'w-40 min-w-40'}>{t('cabinet.col.price')}</SortHeader>
                  <SortHeader k="condition" sort={sort} desc={desc} onSort={onSort} className={`hidden w-32 ${stockCols ? '2xl:table-cell' : 'xl:table-cell'}`}>{t('cabinet.col.condition')}</SortHeader>
                  <SortHeader k="stock" sort={sort} desc={desc} onSort={onSort} className="w-24">{t('cabinet.col.stock')}</SortHeader>
                  {columns.map((b) => (
                    <th key={b.id} className="w-[4.5rem] min-w-[4.5rem] px-1 py-2 font-medium" title={b.address}><span className="block max-w-[5rem] truncate">{branchLabel(b)}</span></th>
                  ))}
                  {folded && <th className="w-24 min-w-24 px-2 py-2 font-medium">{t('cabinet.col.stockTotal')}</th>}
                  {showCost && <th className="w-24 min-w-24 px-2 py-2 font-medium">{t('warehouse.cost.column')}</th>}
                  {showCost && <th className="w-20 min-w-20 px-2 py-2 font-medium">{t('warehouse.cost.markup')}</th>}
                  <SortHeader k="market" sort={sort} desc={desc} onSort={onSort} className={`w-36 ${stockCols ? 'hidden xl:table-cell' : ''}`}>{t('cabinet.col.market')}</SortHeader>
                  <SortHeader k="updated" sort={sort} desc={desc} onSort={onSort} className={`hidden w-28 ${stockCols ? '2xl:table-cell' : 'xl:table-cell'}`}>{t('cabinet.col.updated')}</SortHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((o) => (
                  <tr key={o.id} className={`group ${selected.has(o.id) || allByFilter ? 'bg-primary-soft/40' : 'hover:bg-surface-2'}`}>
                    <td className={`${STICKY_TICK} ${stickyBg(selected.has(o.id) || allByFilter)} px-3 py-2 align-top`}>
                      <input type="checkbox" className="mt-1 size-4 accent-primary" checked={allByFilter || selected.has(o.id)} onChange={() => toggle(o.id)} aria-label={o.name} />
                    </td>
                    <td className={`${STICKY_NAME} ${NAME_COL} ${stickyBg(selected.has(o.id) || allByFilter)} px-2 py-2 align-top`}>
                      {/* 240 px (352 px from 1280): a long name takes two lines instead of pushing the other columns out */}
                      <button type="button" onClick={() => setEditing(o.id)} className="flex w-60 min-w-0 gap-2 text-left xl:w-[22rem]">
                        {o.photo
                          ? <img src={o.photo} alt="" loading="lazy" className="size-9 shrink-0 rounded-sm border border-line bg-white object-contain" />
                          : <CategoryIcon category={o.category} className="mt-0.5 size-5 shrink-0 text-muted" />}
                        <span className="min-w-0">
                          {/* Two lines at most, by words; the whole name in the hint */}
                          <span className="line-clamp-2 font-medium break-words hover:text-primary" title={o.name}>{o.name}</span>
                          <span className="block truncate text-xs text-faint" title={o.raw_name}>{o.raw_name}</span>
                          <Codes o={o} />
                          <span className={`block text-xs text-muted ${stockCols ? '2xl:hidden' : 'xl:hidden'}`}>{t(`condition.${o.condition}`)} · {formatDate(o.updated_at)}</span>
                        </span>
                      </button>
                      <div className="mt-1 flex flex-wrap gap-1 pl-7">
                        {stockCols && <span className="xl:hidden"><MarketLabel info={o.market} /></span>}
                        <FlagBadges flags={o.flags} />
                        {/* Phase 14: photos straight from the row, without the editor */}
                        <PhotoButton o={o} onClick={() => setPhotosFor(o)} />
                      </div>
                    </td>
                    <td className="px-2 py-2 align-top">
                      <PriceInput offer={o} onSave={patch} />
                      <Converted price={o.price} currency={o.currency} rate={rate} className="mt-0.5 px-1 text-xs text-muted" />
                    </td>
                    <td className={`hidden px-2 py-3 align-top ${stockCols ? '2xl:table-cell' : 'xl:table-cell'}`}>{t(`condition.${o.condition}`)}</td>
                    <td className="px-2 py-2.5 align-top">
                      <Switch checked={o.is_in_stock} disabled={lockStock(o)} onChange={(v) => patch(o.id, { is_in_stock: v })} label={<span className="sr-only">{t('cabinet.col.stock')}</span>} />
                    </td>
                    {columns.map((b) => (
                      <td key={b.id} className="px-1 py-2 align-top"><QtyInput offer={o} branch={b} onSaved={replaceRow} readOnly={stockMode} /></td>
                    ))}
                    {folded && <td className="px-2 py-2 align-top"><StockTotal offer={o} places={places} onSaved={replaceRow} readOnly={stockMode} /></td>}
                    {showCost && <td className="px-2 py-3 align-top tabular-nums">{o.cost_avg != null ? formatPrice(o.cost_avg, o.currency) : '—'}</td>}
                    {showCost && <td className="px-2 py-3 align-top tabular-nums">{o.markup != null ? `${o.markup}%` : '—'}</td>}
                    <td className={`px-2 py-2.5 align-top ${stockCols ? 'hidden xl:table-cell' : ''}`}><MarketLabel info={o.market} /></td>
                    <td className={`hidden px-2 py-3 align-top text-muted ${stockCols ? '2xl:table-cell' : 'xl:table-cell'}`}>{formatDate(o.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>

            {/* Phone and tablet: cards, the price and stock are edited the same way */}
            <ul className="divide-y divide-line lg:hidden">
              {data.items.map((o) => (
                <li key={o.id} className={`flex gap-3 p-3 ${selected.has(o.id) || allByFilter ? 'bg-primary-soft/40' : ''}`}>
                  <input type="checkbox" className="mt-1 size-4 shrink-0 accent-primary" checked={allByFilter || selected.has(o.id)} onChange={() => toggle(o.id)} aria-label={o.name} />
                  <div className="min-w-0 flex-1">
                    <button type="button" onClick={() => setEditing(o.id)} className="flex w-full min-w-0 gap-2 text-left">
                      {o.photo
                        ? <img src={o.photo} alt="" loading="lazy" className="size-10 shrink-0 rounded-sm border border-line bg-white object-contain" />
                        : <CategoryIcon category={o.category} className="mt-0.5 size-5 shrink-0 text-muted" />}
                      <span className="min-w-0">
                        <span className="block font-medium break-words">{o.name}</span>
                        <span className="block truncate text-xs text-faint">{o.raw_name}</span>
                        <Codes o={o} />
                      </span>
                    </button>
                    <div className="mt-2 flex flex-wrap items-center gap-1"><MarketLabel info={o.market} /><FlagBadges flags={o.flags} /><PhotoButton o={o} onClick={() => setPhotosFor(o)} /></div>
                    <div className="mt-2 flex items-start justify-between gap-3">
                      <div className="w-40 min-w-0">
                        <PriceInput offer={o} onSave={patch} />
                        <Converted price={o.price} currency={o.currency} rate={rate} className="mt-0.5 px-1 text-xs text-muted" />
                      </div>
                      <Switch checked={o.is_in_stock} disabled={lockStock(o)} onChange={(v) => patch(o.id, { is_in_stock: v })}
                        label={<span className="text-xs">{t(o.is_in_stock ? 'import.inStock' : 'import.outOfStock')}</span>} />
                    </div>
                    {places.length > 0 && (
                      <div className="mt-2 grid grid-cols-3 gap-2">
                        {places.map((b) => (
                          <label key={b.id} className="block min-w-0">
                            <span className="block truncate text-xs text-muted">{branchLabel(b)}</span>
                            <QtyInput offer={o} branch={b} onSaved={replaceRow} readOnly={stockMode} />
                          </label>
                        ))}
                      </div>
                    )}
                    {showCost && <p className="mt-1 text-xs text-muted"><CostLine o={o} /></p>}
                    <p className="mt-1 text-xs text-muted">{t(`condition.${o.condition}`)} · {t('cabinet.updatedOn', { date: formatDate(o.updated_at) })}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
        {pages > 1 && <div className="border-t border-line p-3"><Pagination page={Math.min(page, pages)} pages={pages} onChange={(p) => setParam('page', String(p))} /></div>}
      </Card>

      <BulkConfirm preview={preview} busy={busy} onCancel={() => setPreview(null)} onApply={applyBulk} />
      <OfferPhotosModal offer={photosFor} onClose={() => { setPhotosFor(null); setReloadKey((k) => k + 1) }} />
      <OfferEditor offerId={editing} rate={rate} branches={branches} onClose={() => setEditing(null)}
        onChanged={(row) => (row ? replaceRow(row) : setReloadKey((k) => k + 1))} />
    </div>
  )
}

// "Закупка 80 $ · наценка 25%" (only the seller sees it)
// The tick and the name stay on the left while the table scrolls sideways (opaque: the cells pass under them)
const STICKY_TICK = 'sticky left-0 z-10'
const STICKY_NAME = 'sticky left-10 z-10 border-r border-line'
export const NAME_COL = 'min-w-60'
const stickyBg = (picked) => (picked ? 'bg-primary-soft' : 'bg-surface group-hover:bg-surface-2')

// 1–2 places — a column each; 3 and more — one column "Остатки" with the total (phase 12.5 fix)
export function stockColumns(branches, chosen = null) {
  const places = chosen ? [chosen] : branches
  return places.length >= 3 ? { places, columns: [], folded: true } : { places, columns: places, folded: false }
}

export function stockTotal(offer, places) {
  let total = 0
  let known = false
  for (const b of places) {
    const q = stockOf(offer, b)?.quantity
    if (q != null) { total += q; known = true }
  }
  return known ? total : null
}

// "Остатки": the total; a hover or a click shows it by place (editable as the separate columns were)
export function StockTotal({ offer, places, onSaved, readOnly }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])
  const total = stockTotal(offer, places)
  const byPlace = places.map((b) => `${branchLabel(b)}: ${stockOf(offer, b)?.quantity ?? '—'}`).join('\n')
  return (
    <div ref={box} className="relative" onMouseLeave={() => setOpen(false)}>
      <button type="button" onClick={() => setOpen(!open)} onMouseEnter={() => setOpen(true)} aria-expanded={open}
        title={byPlace} aria-label={t('cabinet.col.stockByPlace', { count: total ?? 0 })}
        className="inline-flex min-h-9 items-center gap-1 rounded-md border border-line px-2.5 font-semibold tabular-nums hover:border-primary">
        {total ?? '—'}<span className="text-xs font-normal text-muted">{t('cabinet.col.places', { count: places.length })}</span>
      </button>
      {open && (
        <div role="dialog" className="absolute top-full right-0 z-20 mt-1 w-56 rounded-lg border border-line bg-surface p-2 shadow-pop">
          <ul className="grid gap-1.5">
            {places.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 truncate text-muted" title={b.address}>{branchLabel(b)}</span>
                <QtyInput offer={offer} branch={b} onSaved={onSaved} readOnly={readOnly} className="w-20 shrink-0" />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function CostLine({ o }) {
  const { t } = useTranslation()
  return <>{t('warehouse.cost.column')}: {o.cost_avg != null ? formatPrice(o.cost_avg, o.currency) : '—'} · {t('warehouse.cost.markup')}: {o.markup != null ? `${o.markup}%` : '—'}</>
}

// Excel both ways (phase 12.2): "Скачать в Excel" with the current filters; "Загрузить остатки из Excel"
// Phase 12.3: the store's barcodes of the offer (the search of "My goods" finds them too)
function Codes({ o }) {
  const { t } = useTranslation()
  return (
    <>
      {o.barcodes?.length > 0 && <span className="block truncate font-mono text-xs text-muted" title={t('barcode.column')}>▮ {o.barcodes.map((b) => b.code).join(', ')}</span>}
      {/* Phase 12.4: sold at the counter more than the books had */}
      {o.oversold && <span className="mt-0.5 block text-xs font-medium text-warning">{t('cabinet.oversold')}</span>}
    </>
  )
}

// Phase 14: "Фото N" / "Добавить фото" in a row of «Мои товары»
export function PhotoButton({ o, onClick }) {
  const { t } = useTranslation()
  const n = (o.photos?.own || 0) + (o.photos?.card || 0)
  return (
    <button type="button" onClick={onClick}
      className={`inline-flex min-h-7 items-center gap-1 rounded-sm px-1.5 text-xs outline-none hover:bg-primary-soft focus-visible:ring-2 focus-visible:ring-primary ${n ? 'text-muted' : 'font-medium text-primary'}`}>
      <Camera className="size-3.5" aria-hidden />{n ? `${t('photo.photos')} ${n}` : t('photo.add')}
    </button>
  )
}

function ExcelBar({ query, stockMode, showCost, setShowCost, onImported }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [importing, setImporting] = useState(false)
  const dl = (withCost) => {
    const p = Object.fromEntries(new URLSearchParams(query))
    delete p.page; delete p.sort; delete p.desc
    if (p.flagged) p.flagged = true
    if (p.stale) p.stale = true
    if (p.no_photo) p.no_photo = true
    download('/seller/stock/offers.xlsx', { ...p, cost: withCost }, 'goods.xlsx').catch((err) => toast(t(errorKey(err)), 'danger'))
  }
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <Dropdown align="left" panelClassName="w-64" trigger={({ open, toggle }) => (
        <Button size="sm" variant="secondary" onClick={toggle} aria-expanded={open} aria-haspopup="menu">
          <Download className="size-4" aria-hidden />{t('warehouse.excel.download')}<ChevronDown className="size-4" aria-hidden />
        </Button>
      )}>
        <DropdownItem onClick={() => dl(false)}>{t('warehouse.excel.plain')}</DropdownItem>
        <DropdownItem onClick={() => dl(true)}>{t('warehouse.excel.withCost')}</DropdownItem>
      </Dropdown>
      {stockMode && <Button size="sm" variant="secondary" onClick={() => setImporting(true)}><Upload className="size-4" aria-hidden />{t('warehouse.excel.importStock')}</Button>}
      <Checkbox label={t('warehouse.cost.show')} checked={showCost} onChange={(e) => setShowCost(e.target.checked)} />
      {importing && <StockImport onClose={() => setImporting(false)} onDone={() => { setImporting(false); onImported() }} />}
    </div>
  )
}
