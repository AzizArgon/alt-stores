import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ClipboardCheck } from 'lucide-react'
import api from '../services/api'
import { useScanner } from '../services/barcode'
import { placeLabel } from '../services/place'
import { BindBarcode, CameraButton, resolveCode } from './Barcode'
import { Modal, useToast } from './overlays'
import { Badge, Button, Card, Checkbox, EmptyState, Skeleton, inputClass } from './ui'
import { GoodsInput, stockError } from './Warehouse'
import i18n from '../i18n'

// Phase 12.4 "Ревизия": the seller scans every item on the shelf of one place. Each scan is saved on the server at
// once, so a reload or a closed page loses nothing. "Завершить подсчёт" -> the differences (совпадает / недостача /
// излишек / не найдено), the seller may leave a line out, "Применить" -> "Ревизия" lines of the journal.

const TONE = { match: 'success', short: 'danger', over: 'warning', missing: 'danger' }
const when = (iso) => new Intl.DateTimeFormat(i18n.language, { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

export default function Stocktake({ place, places }) {
  const { t } = useTranslation()
  const [lists, setLists] = useState(null)
  const [current, setCurrent] = useState(null)
  const reload = () => api.get('/seller/stock/stocktakes').then((r) => setLists(r.data)).catch(() => setLists({ open: [], history: [] }))
  useEffect(() => { reload() }, [])
  const open = lists?.open.find((s) => s.branch_id === place?.id)
  useEffect(() => {
    if (!open) { setCurrent(null); return }
    api.get(`/seller/stock/stocktakes/${open.id}`).then((r) => setCurrent(r.data)).catch(() => setCurrent(null))
  }, [open?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!lists) return <Skeleton className="h-48 w-full rounded-xl" />
  const placeName = (s) => (s.is_warehouse ? t('place.warehouse') : s.branch)
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      {!open ? <StartForm place={place} onStarted={(st) => { setCurrent(st); reload() }} />
        : !current ? <Skeleton className="h-48 w-full rounded-xl" />
          : current.status === 'counting'
            ? <Counting st={current} onChange={setCurrent} onDone={reload} />
            : <Review st={current} onChange={setCurrent} onDone={reload} />}
      {lists.open.filter((s) => s.branch_id !== place?.id).map((s) => (
        <p key={s.id} className="text-sm text-muted">{t('warehouse.overview.openStocktake')}: {placeName(s)} · {when(s.created_at)}</p>
      ))}
      <Card>
        <h2 className="text-h3">{t('warehouse.stocktake.history')}</h2>
        {lists.history.length === 0 ? <p className="mt-2 text-sm text-muted">{t('warehouse.stocktake.historyEmpty')}</p> : (
          <ul className="mt-2 grid gap-2">
            {lists.history.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-sm first:border-0 first:pt-0">
                <span className="font-medium">{when(s.finished_at)} · {placeName(s)}</span>
                <span className="text-muted">{t('warehouse.stocktake.historyLine', s)}</span>
                <Link to={`/seller/stock?tab=journal&doc=${s.doc}`} className="text-primary hover:underline">{t('warehouse.stocktake.openJournal')}</Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <p className="text-xs text-muted">{t('warehouse.stocktake.adjustLink')} <Link to="/seller/stock?tab=adjust" className="text-primary hover:underline">{t('warehouse.tabs.adjust')}</Link></p>
      {places.length === 0 && <p className="text-sm">{t('warehouse.noBranches')}</p>}
    </div>
  )
}

function StartForm({ place, onStarted }) {
  const { t } = useTranslation()
  const [cats, setCats] = useState([])
  const [chosen, setChosen] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.get('/categories').then((r) => setCats(r.data)).catch(() => {}) }, [])
  const start = async () => {
    setError('')
    try {
      onStarted((await api.post('/seller/stock/stocktakes', { branch_id: place.id, categories: chosen })).data)
    } catch (err) {
      setError(stockError(t, err))
    }
  }
  return (
    <Card className="grid gap-4">
      <div>
        <h2 className="text-h2">{t('warehouse.stocktake.title')} · {placeLabel(t, place)}</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">{t('warehouse.stocktake.hint')}</p>
      </div>
      <details className="rounded-lg border border-line p-3">
        <summary className="cursor-pointer text-sm font-medium">{t('warehouse.stocktake.categories')}: {chosen.length ? chosen.length : t('warehouse.stocktake.allCategories')}</summary>
        <div className="mt-3 grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
          {cats.map((c) => (
            <Checkbox key={c.slug} label={c.name} checked={chosen.includes(c.slug)}
              onChange={(e) => setChosen((x) => (e.target.checked ? [...x, c.slug] : x.filter((v) => v !== c.slug)))} />
          ))}
        </div>
      </details>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <div><Button size="lg" onClick={start}><ClipboardCheck className="size-5" aria-hidden />{t('warehouse.stocktake.start')}</Button></div>
    </Card>
  )
}

function Counting({ st, onChange, onDone }) {
  const { t } = useTranslation()
  const [error, setError] = useState('')
  const [binding, setBinding] = useState(null)
  const [fresh, setFresh] = useState(null)
  const [asking, setAsking] = useState(false)
  const send = async (offerId, body) => {
    setError('')
    try {
      onChange((await api.post(`/seller/stock/stocktakes/${st.id}/count`, { offer_id: offerId, ...body })).data)
      setFresh(offerId)
    } catch (err) {
      setError(stockError(t, err))
    }
  }
  const onCode = async (code) => {
    const res = await resolveCode(t, code)
    if (res.error) setError(res.error)
    else if (res.offer) send(res.offer.id, { delta: 1 })
    else setBinding(res.unknown)
  }
  useScanner(onCode, !binding && !asking)
  const act = async (action) => {
    setError('')
    try {
      onChange((await api.post(`/seller/stock/stocktakes/${st.id}/${action}`)).data)
    } catch (err) {
      setError(stockError(t, err))
    }
  }
  const cancel = async () => {
    await api.delete(`/seller/stock/stocktakes/${st.id}`).catch(() => {})
    setAsking(false)
    onDone()
  }
  return (
    <Card className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-h2">{t('warehouse.stocktake.title')} · {st.is_warehouse ? t('place.warehouse') : st.branch}</h2>
        <span className="text-xs text-muted">{st.doc}</span>
      </div>
      <div className="rounded-lg bg-surface-2 p-3">
        <p className="text-base font-semibold">{t('warehouse.stocktake.progress', { found: st.found_positions, expected: st.expected_positions })}</p>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-line" aria-hidden>
          <div className="h-full bg-primary transition-all" style={{ width: `${st.expected_positions ? Math.min(100, (st.found_positions / st.expected_positions) * 100) : 0}%` }} />
        </div>
        <p className="mt-1 text-xs text-muted">{t('warehouse.stocktake.units', { count: st.counted_units })}</p>
      </div>
      <div className="flex flex-wrap gap-2 [&>:first-child]:min-w-0 [&>:first-child]:flex-1 [&>:first-child]:basis-64">
        <GoodsInput onPick={(o) => send(o.id, { delta: 1 })} onCode={onCode} big hint={false} />
        <CameraButton onCode={onCode} size="lg" className="min-h-14 w-full sm:w-auto" />
      </div>
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(o) => { setBinding(null); send(o.id, { delta: 1 }) }} />}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {st.counts.length === 0 ? <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{t('warehouse.stocktake.empty')}</p> : (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
          {st.counts.map((c) => (
            <li key={c.offer_id} className={`flex flex-wrap items-center gap-2 rounded-lg border p-2.5 ${fresh === c.offer_id ? 'border-primary bg-primary-soft ring-2 ring-primary' : 'border-line'}`}>
              <div className="min-w-0 flex-1 basis-48">
                <p className="truncate text-sm font-medium" title={c.name}>{c.name}</p>
                <p className="text-xs text-muted">{c.expected == null ? t('warehouse.stocktake.notInBooks') : `${t('warehouse.stocktake.expected')}: ${c.expected}`}</p>
              </div>
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => send(c.offer_id, { delta: -1 })} aria-label={t('barcode.scan.minus')}
                  className="grid size-11 place-items-center rounded-md border border-line-strong text-xl font-semibold hover:bg-surface-2">−</button>
                <input type="number" min="0" inputMode="numeric" defaultValue={c.counted} key={c.counted} aria-label={t('warehouse.stocktake.counted')}
                  onBlur={(e) => Number(e.target.value) !== c.counted && send(c.offer_id, { set: Math.max(0, Number(e.target.value) || 0) })}
                  onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                  className={`${inputClass} min-h-11 w-20 text-center text-base font-semibold`} />
                <button type="button" onClick={() => send(c.offer_id, { delta: 1 })} aria-label={t('barcode.scan.plus')}
                  className="grid size-11 place-items-center rounded-md border border-line-strong text-xl font-semibold hover:bg-surface-2">+</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="text" onClick={() => setAsking(true)}>{t('warehouse.stocktake.cancel')}</Button>
        <Button size="lg" onClick={() => act('finish')}>{t('warehouse.stocktake.finish')}</Button>
      </div>
      {asking && (
        <Modal open onClose={() => setAsking(false)} title={t('warehouse.stocktake.cancel')}
          footer={<><Button variant="secondary" onClick={() => setAsking(false)}>{t('branches.cancel')}</Button><Button variant="danger" onClick={cancel}>{t('warehouse.stocktake.cancel')}</Button></>}>
          <p className="text-sm">{t('warehouse.stocktake.cancelAsk')}</p>
        </Modal>
      )}
    </Card>
  )
}

function Review({ st, onChange, onDone }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [onlyDiff, setOnlyDiff] = useState(true)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const excluded = new Set(st.excluded)
  const counts = st.lines.reduce((a, l) => ({ ...a, [l.status]: (a[l.status] || 0) + 1 }), {})
  const toApply = st.lines.filter((l) => l.diff !== 0 && !excluded.has(l.offer_id)).length
  const act = async (fn) => {
    setError('')
    try { onChange((await fn()).data) } catch (err) { setError(stockError(t, err)) }
  }
  const apply = async () => {
    setAsking(false)
    try {
      const res = (await api.post(`/seller/stock/stocktakes/${st.id}/apply`)).data
      toast(t('warehouse.stocktake.applied', { count: toApply }))
      setResult(res)
    } catch (err) {
      setError(stockError(t, err))
    }
  }
  if (result) {
    return (
      <Card className="grid gap-3 text-center md:!p-8">
        <ClipboardCheck className="mx-auto size-10 text-success" aria-hidden />
        <h2 className="text-h2">{t('warehouse.stocktake.applied', { count: toApply })}</h2>
        <p className="text-sm text-muted">{t('warehouse.stocktake.historyLine', result)}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="secondary" to={`/seller/stock?tab=journal&doc=${result.doc}`}>{t('warehouse.stocktake.openJournal')}</Button>
          <Button onClick={onDone}>{t('warehouse.stocktake.start')}</Button>
        </div>
      </Card>
    )
  }
  const rows = st.lines.filter((l) => !onlyDiff || l.status !== 'match')
  return (
    <Card className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-h2">{t('warehouse.stocktake.title')} · {st.is_warehouse ? t('place.warehouse') : st.branch}</h2>
        <span className="text-xs text-muted">{st.doc}</span>
      </div>
      <p className="text-sm">{t('warehouse.stocktake.summary', { match: counts.match || 0, short: counts.short || 0, over: counts.over || 0, missing: counts.missing || 0 })}</p>
      <Checkbox label={t('warehouse.stocktake.onlyDiff')} checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} />
      {rows.length === 0 ? <EmptyState icon={ClipboardCheck} title={t('warehouse.stocktake.status.match')} /> : (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
          {rows.map((l) => {
            const off = excluded.has(l.offer_id)
            return (
              <li key={l.offer_id} className={`grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${off ? 'opacity-60' : ''}`}>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={TONE[l.status]}>{t(`warehouse.stocktake.status.${l.status}`)}</Badge>
                    <span className="min-w-0 truncate text-sm font-medium" title={l.name}>{l.name}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {t('warehouse.stocktake.expected')}: {l.expected} · {t('warehouse.stocktake.counted')}: {l.counted}
                    {l.diff !== 0 && <> · {t('warehouse.stocktake.diff')}: <span className={l.diff < 0 ? 'text-danger' : 'text-warning'}>{l.diff > 0 ? `+${l.diff}` : l.diff}</span></>}
                  </p>
                </div>
                {l.diff !== 0 && (
                  <Checkbox label={off ? t('warehouse.stocktake.excluded') : t('warehouse.stocktake.include')} checked={!off}
                    onChange={(e) => act(() => api.put(`/seller/stock/stocktakes/${st.id}/exclude`, { offer_id: l.offer_id, excluded: !e.target.checked }))} />
                )}
              </li>
            )
          })}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="secondary" onClick={() => act(() => api.post(`/seller/stock/stocktakes/${st.id}/resume`))}>{t('warehouse.stocktake.resume')}</Button>
        <Button size="lg" onClick={() => setAsking(true)}>{t('warehouse.stocktake.apply')}</Button>
      </div>
      {asking && (
        <Modal open onClose={() => setAsking(false)} title={t('warehouse.stocktake.apply')}
          footer={<><Button variant="secondary" onClick={() => setAsking(false)}>{t('branches.cancel')}</Button><Button onClick={apply}>{t('warehouse.stocktake.apply')}</Button></>}>
          <p className="text-sm">{t('warehouse.stocktake.applyAsk', { count: toApply })}</p>
        </Modal>
      )}
    </Card>
  )
}
