import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Download, FileSpreadsheet, Search, Trash2, Volume2, VolumeX } from 'lucide-react'
import api, { errorKey } from '../services/api'
import { formatPrice } from '../services/format'
import { ProductLine } from './AddFromCatalog'
import { branchLabel, stockOf } from './BranchStock'
import { Modal, useToast } from './overlays'
import { Badge, Button, Checkbox, Input, Select, inputClass } from './ui'
import { checkBarcode, feedback, looksLikeBarcode, scannerReady, setSound, soundOn, useScanner } from '../services/barcode'
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
export function GoodsInput({ onPick, onCode, autoFocus = true, allowCatalog = false, placeholder, hint = true, big = false, inline = false, adornment = null, scanner = false }) {
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
        placeholder={placeholder || t('warehouse.search')} className={`${inputClass} w-full pl-9 ${big ? 'min-h-14 text-base' : ''} ${adornment ? 'sm:pr-12' : ''}`} autoComplete="off" />
      {adornment && <div className={`absolute right-1.5 hidden sm:block ${big ? 'top-2.5' : 'top-1'}`}>{adornment}</div>}
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
      {scanner && <ScannerStatus field={ref} />}
      {hint && <p className="mt-1 text-xs text-muted">{t('warehouse.searchHint')}</p>}
      {catalog && <CatalogPick query={looksLikeBarcode(q) ? '' : q} onClose={() => setCatalog(false)} onPicked={(o) => { setCatalog(false); pick(o) }} />}
    </div>
  )
}

// Phase 12.5: "Сканер готов" (a green dot) or a grey one with "нажмите здесь, чтобы пикать" (the focus went to
// another field), and the beep on / off next to it
export function ScannerStatus({ field }) {
  const { t } = useTranslation()
  const [ready, setReady] = useState(true)
  const [sound, setSoundState] = useState(soundOn)
  useEffect(() => {
    const check = () => setReady(scannerReady(document.activeElement === document.body ? null : document.activeElement, field.current))
    const later = () => setTimeout(check, 0) // the focus left: wait where it goes
    check()
    document.addEventListener('focusin', check)
    document.addEventListener('focusout', later)
    return () => { document.removeEventListener('focusin', check); document.removeEventListener('focusout', later) }
  }, [field])
  const toggle = () => { setSound(!sound); setSoundState(!sound) }
  const Icon = sound ? Volume2 : VolumeX
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs" data-testid="scanner-status">
      {ready ? (
        <span className="inline-flex items-center gap-1.5 font-medium text-success" role="status">
          <span className="size-2 rounded-full bg-success" aria-hidden />{t('scanner.ready')}
        </span>
      ) : (
        <button type="button" onClick={() => field.current?.focus()} className="inline-flex items-center gap-1.5 text-muted hover:text-ink" role="status">
          <span className="size-2 rounded-full bg-faint" aria-hidden />{t('scanner.notReady')} — <span className="underline">{t('scanner.focusHere')}</span>
        </button>
      )}
      <button type="button" onClick={toggle} aria-pressed={sound} title={t(sound ? 'scanner.soundOn' : 'scanner.soundOff')}
        aria-label={t(sound ? 'scanner.soundOn' : 'scanner.soundOff')} className="grid size-7 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-ink">
        <Icon className="size-4" aria-hidden />
      </button>
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
      primary={chosen && { label: t('warehouse.catalogAdd'), onClick: add, disabled: !(Number(price) > 0) }}>
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
// Phase 12.4: `move` ("Выкладка": `branchId` is the branch, `warehouseId` the source), `return` (reason; a defect may
// stay out of the stock), a sale is never blocked: more than the books — a warning; a reserved item — "продать всё
// равно?" and the document goes again with `confirm`.
export function OperationForm({ kind, branches, onPosted, initialOffer, branchId, warehouseId, scan = false, priceOnly = false, big = false, draftKey }) {
  const { t } = useTranslation()
  const toast = useToast()
  const dk = draftKey || kind
  const [lines, setLines] = useState(() => readDraft(dk))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [fresh, setFresh] = useState(null) // the key of the line the last scan touched
  const [binding, setBinding] = useState(null)
  const [askReserved, setAskReserved] = useState(false)
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
      reason: kind === 'return' ? 'changed_mind' : 'inventory', restock: true, comment: '',
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
  const post = async (confirm = false) => {
    setBusy(true)
    setError('')
    setAskReserved(false)
    try {
      const body = lines.map((l) => ({
        offer_id: l.offer.id, branch_id: Number(l.branch_id), qty: Number(l.qty) || 0,
        cost: kind === 'receipt' && l.cost !== '' && !priceOnly ? Number(l.cost) : null,
        price: kind === 'sale' && l.price !== '' ? Number(l.price) : null,
        reason: kind === 'adjust' || kind === 'return' ? l.reason : null, comment: l.comment || null,
        restock: kind === 'return' ? l.reason !== 'defect' || Boolean(l.restock) : true,
      }))
      const res = await api.post('/seller/stock/operations', { kind, lines: body, scan, confirm })
      toast(t('warehouse.posted', { count: res.data.count }))
      try { localStorage.removeItem(DRAFT(dk)) } catch { /* private mode */ }
      setLines([])
      onPosted?.()
    } catch (err) {
      if (err.response?.data?.detail?.code === 'reserved') setAskReserved(true)
      else setError(stockError(t, err))
    } finally {
      setBusy(false)
    }
  }
  const total = lines.reduce((s, l) => s + (Number(l.qty) || 0), 0)

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap gap-2 [&>:first-child]:min-w-0 [&>:first-child]:flex-1 [&>:first-child]:basis-64">
        <GoodsInput onPick={add} onCode={onCode} allowCatalog={kind === 'receipt'} big={big} hint={!big} scanner
          adornment={<CameraButton icon onCode={onCode} />} />
        {/* A phone: the camera is the main way — a large button; a computer: the icon inside the field */}
        <CameraButton onCode={onCode} size={big ? 'lg' : 'md'} className={`w-full sm:hidden ${big ? 'min-h-14' : ''}`} />
      </div>
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(offer) => { setBinding(null); add(offer) }} />}
      {lines.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{t('warehouse.empty')}</p>
      ) : (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
          {lines.map((l, i) => <Line key={l.key} n={i + 1} kind={kind} line={l} branches={branches} onChange={(p) => set(l.key, p)}
            fresh={l.key === fresh} big={big} priceOnly={priceOnly} fixedBranch={Boolean(branchId)} warehouseId={warehouseId}
            onRemove={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} />)}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {lines.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">{kind !== 'adjust' && <span className="mr-3 font-medium text-ink">{t('warehouse.total', { qty: total })}</span>}{t('warehouse.draftKept')}</p>
          <div className="flex gap-2">
            <Button variant="secondary" size={big ? 'lg' : 'md'} onClick={() => setLines([])}>{t('warehouse.clear')}</Button>
            <Button size={big ? 'lg' : 'md'} onClick={() => post(false)} disabled={busy}>{t('warehouse.post')}</Button>
          </div>
        </div>
      )}
      {askReserved && (
        <Modal open onClose={() => setAskReserved(false)} title={t('warehouse.reservedTitle')}
          footer={<><Button variant="secondary" onClick={() => setAskReserved(false)}>{t('branches.cancel')}</Button>
            <Button onClick={() => post(true)} disabled={busy}>{t('warehouse.sellAnyway')}</Button></>}>
          <p className="text-sm">{t('warehouse.reservedText')}</p>
        </Modal>
      )}
    </div>
  )
}

function Line({ n, kind, line, branches, onChange, onRemove, fresh, big, priceOnly, fixedBranch, warehouseId }) {
  const { t } = useTranslation()
  const ref = useRef(null)
  const s = line.offer.stocks?.[line.branch_id]
  const wh = warehouseId ? line.offer.stocks?.[warehouseId] : null
  const whFree = wh && wh.quantity != null ? wh.quantity - (wh.reserved || 0) : 0
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
            {kind === 'move' && ` · ${t('warehouse.inWarehouse', { qty: whFree })}`}
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
        {kind === 'return' && (
          <Select label={t('warehouse.returnReason')} value={line.reason} onChange={(e) => onChange({ reason: e.target.value, restock: e.target.value !== 'defect' })}>
            {['changed_mind', 'defect', 'other'].map((r) => <option key={r} value={r}>{t(`warehouse.returnReasons.${r}`)}</option>)}
          </Select>
        )}
        {kind === 'adjust' && (
          <Select label={t('warehouse.reason')} value={line.reason} onChange={(e) => onChange({ reason: e.target.value })}>
            {['inventory', 'defect', 'loss', 'other'].map((r) => <option key={r} value={r}>{t(`warehouse.reasons.${r}`)}</option>)}
          </Select>
        )}
        <Input label={t('warehouse.comment')} value={line.comment} maxLength={300} onChange={(e) => onChange({ comment: e.target.value })}
          placeholder={(kind === 'adjust' || kind === 'return') && line.reason === 'other' ? t('warehouse.commentRequired') : ''} />
      </div>
      {kind === 'return' && line.reason === 'defect' && (
        <div className="mt-2">
          <Checkbox label={t('warehouse.restock')} checked={Boolean(line.restock)} onChange={(e) => onChange({ restock: e.target.checked })} />
          {!line.restock && <p className="mt-1 text-xs text-muted">{t('warehouse.restockHint')}</p>}
        </div>
      )}
      {kind === 'sale' && !priceOnly && qty > (s?.quantity ?? 0) && <Badge tone="warning" className="mt-2 whitespace-normal">{t('warehouse.oversoldWarn', { qty: s?.quantity ?? 0 })}</Badge>}
      {kind === 'sale' && !priceOnly && s?.reserved > 0 && qty > (free ?? 0) && qty <= (s?.quantity ?? 0) && <Badge tone="info" className="mt-2 whitespace-normal">{t('warehouse.reservedWarn', { count: s.reserved })}</Badge>}
      {kind === 'move' && qty > whFree && <Badge tone="warning" className="mt-2">{t('warehouse.error.not_enough_wh', { available: whFree })}</Badge>}
    </li>
  )
}

export const EXCEL_POINTS = ['point1', 'point2', 'point3']

// A dashed zone: drop a file on it or click it to choose (keyboard: it is a label of a file input)
export function DropZone({ label, overLabel, file, onFile, accept = '.xlsx' }) {
  const [over, setOver] = useState(false)
  return (
    <label data-dropzone onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]) }}
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-7 text-center transition-colors focus-within:ring-2 focus-within:ring-primary ${
        over ? 'border-primary bg-primary-soft/50' : 'border-line-strong hover:border-primary hover:bg-surface-2'}`}>
      <FileSpreadsheet className={`size-8 ${over ? 'text-primary' : 'text-muted'}`} aria-hidden />
      <span className="font-medium">{over ? overLabel : label}</span>
      {file && <span className="max-w-full truncate text-xs text-muted">{file.name}</span>}
      <input type="file" accept={accept} className="sr-only" onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }} />
    </label>
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
  const pick = (f) => {
    if (!f) return
    if (!/\.xlsx$/i.test(f.name)) { setError(t('warehouse.excel.onlyXlsx')); return }
    setFile(f)
    setPlan(null)
    send(f, false)
  }
  const template = () => download('/seller/stock/offers.xlsx', {}, 'goods.xlsx').catch((err) => setError(t(errorKey(err))))
  // Phase 17.1: three short points, a drop zone, "Скачать шаблон"; at the bottom "Отмена" + "Загрузить"
  return (
    <Modal open onClose={onClose} title={t('warehouse.excel.importTitle')} fullOnPhone
      primary={{ label: t('warehouse.excel.upload'), onClick: () => send(file, true), disabled: busy || !(plan?.total > 0) }}>
      <div className="grid gap-4 text-sm">
        <ul className="grid gap-1.5">
          {EXCEL_POINTS.map((k) => (
            <li key={k} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />{t(`warehouse.excel.${k}`)}</li>
          ))}
        </ul>
        <DropZone label={t('warehouse.excel.drop')} overLabel={t('warehouse.excel.dropHere')} file={file} onFile={pick} />
        <button type="button" onClick={template} className="inline-flex w-fit items-center gap-1.5 font-medium text-primary hover:underline">
          <Download className="size-4" aria-hidden />{t('warehouse.excel.template')}
        </button>
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
