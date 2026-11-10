import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Trash2 } from 'lucide-react'
import api, { errorKey } from '../services/api'
import { formatPrice } from '../services/format'
import { ProductLine } from './AddFromCatalog'
import { branchLabel, stockOf } from './BranchStock'
import { Modal, useToast } from './overlays'
import { Badge, Button, Input, Select, inputClass } from './ui'
import { checkBarcode, feedback, looksLikeBarcode, useScanner } from '../services/barcode'
import { BindBarcode, CameraButton, resolveCode } from './Barcode'

// Downloads a file of the API (the token goes in a header, so a plain link can't do it)
export async function download(url, params, fallbackName) {
  const res = await api.get(url, { params, responseType: 'blob' })
  const name = /filename="([^"]+)"/.exec(res.headers['content-disposition'] || '')?.[1] || fallbackName
  const href = URL.createObjectURL(res.data)
  const a = Object.assign(document.createElement('a'), { href, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

// The error of an operation: "Строка 2: доступно только 1 шт."
export function stockError(t, err) {
  const d = err.response?.data?.detail
  if (err.response?.status !== 422 || !d?.code) return t(errorKey(err))
  const text = t(`warehouse.error.${d.code}`, d)
  return d.line ? t('warehouse.lineError', { line: d.line, text }) : text
}

// The goods input of every operation: one field with search; Enter takes the first match. A barcode scanner types
// into this same field (a scanner is a keyboard that ends with Enter): the search finds the store's own codes; a
// code it doesn't know goes to `onCode` ("Привязать штрихкод"), a misread EAN/UPC is said at once (phase 12.3).
export function GoodsInput({ onPick, onCode, autoFocus = true, allowCatalog = false, placeholder, hint = true, big = false, inline = false }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [items, setItems] = useState(null)
  const [catalog, setCatalog] = useState(false)
  const ref = useRef(null)
  const seq = useRef(0)

  useEffect(() => { if (autoFocus) ref.current?.focus() }, [autoFocus])
  useEffect(() => {
    const text = q.trim()
    if (!text) { setItems(null); return undefined }
    const n = ++seq.current
    const timer = setTimeout(() => {
      api.get('/seller/stock/search', { params: { q: text } })
        .then((res) => { if (n === seq.current) setItems(res.data) })
        .catch(() => setItems([]))
    }, 200)
    return () => clearTimeout(timer)
  }, [q])

  const pick = (offer) => {
    onPick(offer)
    setQ('')
    setItems(null)
    ref.current?.focus()
  }
  const onKey = async (e) => {
    if (e.key === 'Escape') { setQ(''); setItems(null) }
    if (e.key !== 'Enter') return
    e.preventDefault()
    const text = q.trim()
    if (!text) return
    if (onCode && /^\d+$/.test(text) && checkBarcode(text).error === 'checksum') {
      setQ('')
      setItems(null)
      onCode(text) // the caller says "код считан с ошибкой"
      return
    }
    // Enter right after typing (a scanner is faster than the search delay): ask now
    const found = items ?? (await api.get('/seller/stock/search', { params: { q: text } }).then((r) => r.data).catch(() => []))
    if (found.length) {
      if (onCode && looksLikeBarcode(text)) feedback(true)
      pick(found[0])
    } else if (onCode && looksLikeBarcode(text)) {
      setQ('')
      setItems(null)
      onCode(text)
    } else setItems([])
  }

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-3.5 left-3 size-4 text-faint" aria-hidden />
      <input ref={ref} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} aria-label={t('warehouse.search')}
        placeholder={placeholder || t('warehouse.search')} className={`${inputClass} w-full pl-9 ${big ? 'min-h-14 text-base' : ''}`} autoComplete="off" />
      {items && (
        <div className={`${inline ? "" : "absolute inset-x-0 top-full z-20 shadow-pop"} mt-1 max-h-80 overflow-y-auto rounded-lg border border-line bg-surface`}>
          {items.length === 0 && <p className="px-3 py-2.5 text-sm text-muted">{t('warehouse.notFoundMine')}</p>}
          {items.map((o) => (
            <button key={o.id} type="button" onClick={() => pick(o)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none">
              <span className="min-w-0 truncate">{o.name}</span>
              <span className="shrink-0 text-xs text-muted">{formatPrice(o.price, o.currency)}</span>
            </button>
          ))}
          {allowCatalog && (
            <button type="button" onClick={() => setCatalog(true)}
              className="w-full border-t border-line px-3 py-2.5 text-left text-sm font-medium text-primary hover:bg-surface-2">
              {t('warehouse.fromCatalog')}
            </button>
          )}
        </div>
      )}
      {hint && <p className="mt-1 text-xs text-muted">{t('warehouse.searchHint')}</p>}
      {catalog && <CatalogPick query={looksLikeBarcode(q) ? '' : q} onClose={() => setCatalog(false)} onPicked={(o) => { setCatalog(false); pick(o) }} />}
    </div>
  )
}

// "Нет у вас? Найти в каталоге": a card of the catalog becomes the store's offer (its price), then a receipt line.
// `product`: the card is already chosen (a barcode of the common base, a new card) — only the price is asked
export function CatalogPick({ query = '', product = null, onClose, onPicked }) {
  const { t } = useTranslation()
  const [q, setQ] = useState(query)
  const [items, setItems] = useState([])
  const [chosen, setChosen] = useState(product)
  const [price, setPrice] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [error, setError] = useState('')
  useEffect(() => {
    if (q.trim().length < 2) { setItems([]); return undefined }
    const timer = setTimeout(() => api.get('/seller/catalog-search', { params: { q } }).then((r) => setItems(r.data)).catch(() => setItems([])), 250)
    return () => clearTimeout(timer)
  }, [q])
  const add = async () => {
    setError('')
    try {
      const res = await api.post('/seller/offers', { product_id: chosen.id, price: Number(price), currency, condition: 'new', is_in_stock: false })
      const o = res.data.offer
      onPicked({ id: o.id, name: chosen.name, price: o.price, currency: o.currency, stocks: {} })
    } catch (err) {
      const mine = err.response?.data?.detail?.product?.my_offer
      if (err.response?.status === 409 && mine) onPicked({ id: mine.id, name: chosen.name, price: mine.price, currency: mine.currency, stocks: {} })
      else setError(t(errorKey(err)))
    }
  }
  return (
    <Modal open onClose={onClose} title={t('warehouse.catalogTitle')} fullOnPhone
      footer={chosen && <Button onClick={add} disabled={!(Number(price) > 0)}>{t('warehouse.catalogAdd')}</Button>}>
      {!chosen ? (
        <div className="grid gap-2">
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} className={`${inputClass} w-full`} aria-label={t('warehouse.search')} />
          {items.map((p) => (
            <button key={p.id} type="button" onClick={() => setChosen(p)} className="rounded-md border border-line p-2.5 text-left hover:bg-surface-2">
              <ProductLine product={p} />
            </button>
          ))}
        </div>
      ) : (
        <div className="grid gap-3">
          <ProductLine product={chosen} />
          <div className="flex gap-2">
            <Input label={t('warehouse.catalogPrice')} type="number" min="0" step="any" value={price} onChange={(e) => setPrice(e.target.value)} className="flex-1" autoFocus />
            <Select label="&nbsp;" value={currency} onChange={(e) => setCurrency(e.target.value)} aria-label={t('warehouse.price')}>
              <option value="USD">USD</option><option value="UZS">UZS</option>
            </Select>
          </div>
          <p className="text-xs text-muted">{t('warehouse.catalogHint')}</p>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
      )}
    </Modal>
  )
}

const DRAFT = (kind) => `alt_stock_draft_${kind}`
const readDraft = (kind) => {
  try { return JSON.parse(localStorage.getItem(DRAFT(kind))) || [] } catch { return [] }
}

// A document of one kind: receipt (many lines, purchase price), sale (price), adjustment (new quantity, reason).
// The draft is kept in the browser: a reload does not lose it. Phase 12.3: a scan (the USB scanner even with no
// field focused, the camera, a code typed into the goods input) adds a line; the same goods again — its quantity +1;
// an unknown code opens "Привязать штрихкод". "Сканирование" passes its branch, `scan` and `priceOnly` (a store in
// "Только прайс": the stock changes as a hand edit), `big` — large controls for a finger.
export function OperationForm({ kind, branches, onPosted, initialOffer, branchId, scan = false, priceOnly = false, big = false, draftKey }) {
  const { t } = useTranslation()
  const toast = useToast()
  const dk = draftKey || kind
  const [lines, setLines] = useState(() => readDraft(dk))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [fresh, setFresh] = useState(null) // the key of the line the last scan touched
  const [binding, setBinding] = useState(null)
  const lastBranch = useRef(lines.at(-1)?.branch_id || branches[0]?.id)

  useEffect(() => {
    try { localStorage.setItem(DRAFT(dk), JSON.stringify(lines)) } catch { /* private mode */ }
  }, [dk, lines])

  const add = (offer) => {
    setError('')
    const stocks = offer.stocks || {}
    // The chosen branch of "Сканирование"; else the branch of the last line; for a sale — the first branch where
    // it is available
    const branch = branchId || (kind === 'sale'
      ? branches.find((b) => (stocks[b.id]?.quantity ?? 0) - (stocks[b.id]?.reserved ?? 0) > 0)?.id || lastBranch.current
      : lastBranch.current)
    const now = stocks[branch]?.quantity
    const same = kind !== 'adjust' && lines.find((l) => l.offer.id === offer.id && Number(l.branch_id) === Number(branch))
    if (same) {
      setFresh(same.key)
      setLines((ls) => ls.map((l) => (l.key === same.key ? { ...l, qty: (Number(l.qty) || 0) + 1 } : l)))
      return
    }
    const key = `${Date.now()}-${Math.random()}`
    setFresh(key)
    setLines((ls) => [...ls, {
      key, offer: { id: offer.id, name: offer.name, price: offer.price, currency: offer.currency, stocks },
      branch_id: branch, qty: kind === 'adjust' ? (now ?? '') : 1, cost: offer.cost_last ?? '', price: offer.price ?? '',
      reason: 'inventory', comment: '',
    }])
  }
  const onCode = async (code) => {
    const res = await resolveCode(t, code)
    if (res.error) setError(res.error)
    else if (res.offer) add(res.offer)
    else setBinding(res.unknown)
  }
  useScanner(onCode, !binding)
  useEffect(() => { if (initialOffer) add(initialOffer) }, [initialOffer?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key, patch) => {
    if (patch.branch_id) lastBranch.current = patch.branch_id
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }
  const post = async () => {
    setBusy(true)
    setError('')
    try {
      const body = lines.map((l) => ({
        offer_id: l.offer.id, branch_id: Number(l.branch_id), qty: Number(l.qty) || 0,
        cost: kind === 'receipt' && l.cost !== '' && !priceOnly ? Number(l.cost) : null,
        price: kind === 'sale' && l.price !== '' ? Number(l.price) : null,
        reason: kind === 'adjust' ? l.reason : null, comment: l.comment || null,
      }))
      const res = await api.post('/seller/stock/operations', { kind, lines: body, scan })
      toast(t('warehouse.posted', { count: res.data.count }))
      try { localStorage.removeItem(DRAFT(dk)) } catch { /* private mode */ }
      setLines([])
      onPosted?.()
    } catch (err) {
      setError(stockError(t, err))
    } finally {
      setBusy(false)
    }
  }
  const total = lines.reduce((s, l) => s + (Number(l.qty) || 0), 0)

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap gap-2 [&>:first-child]:min-w-0 [&>:first-child]:flex-1 [&>:first-child]:basis-64">
        <GoodsInput onPick={add} onCode={onCode} allowCatalog={kind === 'receipt'} big={big} hint={!big} />
        <CameraButton onCode={onCode} size={big ? 'lg' : 'md'} className={big ? 'min-h-14 w-full sm:w-auto' : ''} />
      </div>
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(offer) => { setBinding(null); add(offer) }} />}
      {lines.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{t('warehouse.empty')}</p>
      ) : (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
          {lines.map((l, i) => <Line key={l.key} n={i + 1} kind={kind} line={l} branches={branches} onChange={(p) => set(l.key, p)}
            fresh={l.key === fresh} big={big} priceOnly={priceOnly} fixedBranch={Boolean(branchId)}
            onRemove={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} />)}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {lines.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">{kind !== 'adjust' && <span className="mr-3 font-medium text-ink">{t('warehouse.total', { qty: total })}</span>}{t('warehouse.draftKept')}</p>
          <div className="flex gap-2">
            <Button variant="secondary" size={big ? 'lg' : 'md'} onClick={() => setLines([])}>{t('warehouse.clear')}</Button>
            <Button size={big ? 'lg' : 'md'} onClick={post} disabled={busy}>{t('warehouse.post')}</Button>
          </div>
        </div>
      )}
    </div>
  )
}

function Line({ n, kind, line, branches, onChange, onRemove, fresh, big, priceOnly, fixedBranch }) {
  const { t } = useTranslation()
  const ref = useRef(null)
  const s = line.offer.stocks?.[line.branch_id]
  const free = s && s.quantity != null ? s.quantity - (s.reserved || 0) : null
  useEffect(() => { if (fresh) ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }) }, [fresh, line.qty])
  const qty = Number(line.qty) || 0
  return (
    <li ref={ref} className={`rounded-lg border p-3 transition-colors ${fresh ? 'border-primary bg-primary-soft ring-2 ring-primary' : 'border-line bg-surface'}`}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-xs text-faint">{n}.</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={line.offer.name}>{line.offer.name}</p>
          <p className="text-xs text-muted">
            {s?.quantity != null ? t('warehouse.now', { qty: s.quantity }) : t('warehouse.nowUnknown')}
            {free != null && s.reserved > 0 && ` · ${t('warehouse.free', { count: free })}`}
          </p>
        </div>
        <button type="button" onClick={onRemove} aria-label={t('warehouse.remove')} className="grid size-9 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-danger">
          <Trash2 className="size-4" aria-hidden />
        </button>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 [&>*]:min-w-0">
        {!fixedBranch && (
          <Select label={t('warehouse.branch')} value={line.branch_id} onChange={(e) => onChange({ branch_id: Number(e.target.value) })}>
            {branches.map((b) => {
              const bs = stockOf(line.offer, b)
              return <option key={b.id} value={b.id}>{branchLabel(b)}{bs?.quantity != null ? ` (${bs.quantity})` : ''}</option>
            })}
          </Select>
        )}
        {big && kind !== 'adjust' ? (
          <div className="col-span-2 sm:col-span-1">
            <span className="mb-1.5 block text-sm font-medium">{t('warehouse.qty')}</span>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => onChange({ qty: Math.max(1, qty - 1) })} aria-label={t('barcode.scan.minus')}
                className="grid size-12 shrink-0 place-items-center rounded-md border border-line-strong text-xl font-semibold hover:bg-surface-2">−</button>
              <input type="number" min="1" step="1" inputMode="numeric" value={line.qty} aria-label={t('warehouse.qty')}
                onChange={(e) => onChange({ qty: e.target.value })} className={`${inputClass} min-h-12 min-w-0 flex-1 text-center text-base font-semibold`} />
              <button type="button" onClick={() => onChange({ qty: qty + 1 })} aria-label={t('barcode.scan.plus')}
                className="grid size-12 shrink-0 place-items-center rounded-md border border-line-strong text-xl font-semibold hover:bg-surface-2">+</button>
            </div>
          </div>
        ) : (
          <Input label={kind === 'adjust' ? t('warehouse.newQty') : t('warehouse.qty')} type="number" min={kind === 'adjust' ? 0 : 1} step="1" inputMode="numeric"
            value={line.qty} onChange={(e) => onChange({ qty: e.target.value })} />
        )}
        {kind === 'receipt' && !priceOnly && (
          <Input label={`${t('warehouse.cost.column')}, ${line.offer.currency}`} hint={undefined} type="number" min="0" step="any" value={line.cost}
            onChange={(e) => onChange({ cost: e.target.value })} placeholder={t('warehouse.costOptional')} title={t('warehouse.costHint')} />
        )}
        {kind === 'sale' && !priceOnly && (
          <Input label={`${t('warehouse.price')}, ${line.offer.currency}`} type="number" min="0" step="any" value={line.price}
            onChange={(e) => onChange({ price: e.target.value })} />
        )}
        {kind === 'adjust' && (
          <Select label={t('warehouse.reason')} value={line.reason} onChange={(e) => onChange({ reason: e.target.value })}>
            {['inventory', 'defect', 'loss', 'other'].map((r) => <option key={r} value={r}>{t(`warehouse.reasons.${r}`)}</option>)}
          </Select>
        )}
        <Input label={t('warehouse.comment')} value={line.comment} maxLength={300} onChange={(e) => onChange({ comment: e.target.value })}
          placeholder={kind === 'adjust' && line.reason === 'other' ? t('warehouse.commentRequired') : ''} />
      </div>
      {kind === 'sale' && free != null && Number(line.qty) > free && <Badge tone="warning" className="mt-2">{t('warehouse.error.not_enough', { available: free })}</Badge>}
    </li>
  )
}

// "Загрузить остатки из Excel": only quantities; the summary by branch first, then "Применить"
export function StockImport({ onClose, onDone }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const send = async (f, apply) => {
    setBusy(true)
    setError('')
    const body = new FormData()
    body.append('file', f)
    body.append('apply', apply ? 'true' : 'false')
    try {
      const res = await api.post('/seller/stock/import', body)
      if (apply) {
        toast(t('warehouse.excel.applied'))
        onDone()
      } else setPlan(res.data)
    } catch (err) {
      setError(stockError(t, err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal open onClose={onClose} title={t('warehouse.excel.importTitle')} fullOnPhone
      footer={plan?.total > 0 && <Button onClick={() => send(file, true)} disabled={busy}>{t('warehouse.excel.apply')}</Button>}>
      <div className="grid gap-3 text-sm">
        <p className="text-muted">{t('warehouse.excel.importHint')}</p>
        <label className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-md border border-line-strong px-4 py-2 font-semibold hover:bg-surface-2">
          {t('warehouse.excel.choose')}
          <input type="file" accept=".xlsx" className="sr-only" onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) { setFile(f); setPlan(null); send(f, false) }
          }} />
        </label>
        {file && <p className="truncate text-xs text-muted">{file.name}</p>}
        {error && <p role="alert" className="text-danger">{error}</p>}
        {plan && (
          <div className="grid gap-2 rounded-lg bg-surface-2 p-3">
            <p className="font-semibold">{t('warehouse.excel.summary')}</p>
            <p className="text-xs text-muted">{t('warehouse.excel.rows', { count: plan.rows })}</p>
            {plan.total === 0 ? <p className="text-success">{t('warehouse.excel.nothing')}</p> : (
              <>
                <ul className="grid gap-0.5">
                  {plan.branches.map((b) => <li key={b.branch_id}>{t('warehouse.excel.branchLine', { branch: b.name, changed: b.changed, plus: b.plus, minus: b.minus })}</li>)}
                </ul>
                <ul className="max-h-48 overflow-y-auto text-xs text-muted">
                  {plan.changes.map((c) => <li key={`${c.offer_id}-${c.branch_id}`} className="truncate">{c.name} · {c.branch}: {c.before ?? '—'} → {c.after}</li>)}
                </ul>
              </>
            )}
            {plan.unknown > 0 && <p className="text-xs text-warning">{t('warehouse.excel.unknown', { count: plan.unknown })}</p>}
          </div>
        )}
      </div>
    </Modal>
  )
}
