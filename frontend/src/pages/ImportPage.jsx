import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { Monitor } from 'lucide-react'
import { ErrorText } from '../components/AuthForm'
import { Button, Card, Checkbox, Pagination, Skeleton, inputClass } from '../components/ui'
import Flags from '../components/Flags'
import ImportSummary, { ModeChoice } from '../components/ImportSummary'
import { Modal } from '../components/overlays'
import api, { errorKey } from '../services/api'
import { formatDayMonth, importTitle, formatPrice, roundSum, roundUsd } from '../services/format'
import { specsText, useSpecDictionary } from '../services/specs'

const PAGE_SIZE = 50
const POLL_MS = 2000
const CHECK_DELAY_MS = 600
const SUMMARY_DELAY_MS = 800
const CONDITIONS = ['new', 'new_openbox', 'used', 'refurbished', 'unknown']

// Rows the seller should look at: no price, unknown category, no brand or an Anti-Fraud warning
const isFlagged = (r) => (r.flags || []).some((f) => f.level !== 'info')
const needsAttention = (r) => r.source === 'failed' || r.currency_check || r.condition === 'unknown' || Boolean(r.specs?._suspect) || r.price == null || r.category === 'other' || !r.brand || isFlagged(r)
const SOURCE_STYLE = { rule: 'text-info', cache: 'text-muted', ai: 'text-primary', failed: 'text-danger' }

const cellInput = 'w-full rounded border border-transparent bg-transparent px-1.5 py-1 hover:border-line-strong focus:border-primary focus:bg-surface outline-none'

function Progress({ imp }) {
  const { t } = useTranslation()
  const pct = imp.chunks_total ? Math.round((imp.chunks_done / imp.chunks_total) * 100) : 0
  return (
    <Card>
      <p>{imp.chunks_total
        ? t('import.processing', { done: imp.chunks_done, total: imp.chunks_total })
        : t('import.preparing')}</p>
      <div className="mt-3 h-2 rounded bg-surface-2">
        <div className="h-2 rounded bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
    </Card>
  )
}

const rawSpecsText = (specs) => Object.entries(specs || {}).map(([k, v]) => `${k}: ${v}`).join(' · ')

// Confirmed specs are written in the row and already normalized by the dictionary; AI guesses are shown apart
// as the AI wrote them and are never saved
function Specs({ category, specs, guess }) {
  const { t } = useTranslation()
  const dictionary = useSpecDictionary()
  const confirmed = specsText(category, specs, dictionary)
  const guessed = rawSpecsText(guess)
  // A number outside its plausible range ("DDR5 600 МГц"): not used in filters, the seller should fix the row
  const suspect = specsText(category, specs?._suspect, dictionary)
  if (!confirmed && !guessed && !suspect) return null
  return (
    <>
      {suspect && <p className="px-1.5 text-xs font-medium text-danger">{t('import.possibleTypo')}: {suspect}</p>}
      <p className="truncate px-1.5 text-xs text-muted" title={[confirmed, guessed].filter(Boolean).join('\n')}>
        {confirmed}
        {guessed && (
          <span className="italic text-warning">{confirmed && ' · '}{t('import.aiGuess')}: {guessed}</span>
        )}
      </p>
    </>
  )
}

// Under the editable price: the other currency by the CBU rate. Sum is what buyers see first
function ConvertedPrice({ price, currency, rate }) {
  const { t } = useTranslation()
  if (price == null || !rate) return null
  const hint = t('price.rateHint', { date: formatDayMonth(rate.rate_date) })
  return currency === 'USD'
    ? <p className="px-1.5 text-xs font-medium text-ink" title={hint}>≈ {formatPrice(roundSum(price * rate.rate), 'UZS')}</p>
    : <p className="px-1.5 text-xs text-muted" title={hint}>≈ {formatPrice(roundUsd(price / rate.rate), 'USD')}</p>
}

function PreviewTable({ importId, rows, setRows, categories, currency, rate, readOnly }) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [onlyIssues, setOnlyIssues] = useState(false)
  const [onlyFlagged, setOnlyFlagged] = useState(false)
  const timers = useRef({})
  const [page, setPage] = useState(1)
  const [reparsing, setReparsing] = useState({}) // row -> true while the AI reads it again
  const [rowErrors, setRowErrors] = useState({})

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) =>
      (!onlyIssues || needsAttention(r)) &&
      (!onlyFlagged || r.flags?.length > 0) &&
      (!q || r.name.toLowerCase().includes(q) || r.raw_name.toLowerCase().includes(q)))
  }, [rows, query, onlyIssues, onlyFlagged])

  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const pageRows = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  // An edited row is checked by the Anti-Fraud rules again (no AI request)
  const recheck = (row) => {
    clearTimeout(timers.current[row.row])
    timers.current[row.row] = setTimeout(() =>
      api.post(`/imports/${importId}/check`, { rows: [row] })
        .then((res) => setRows((prev) => prev.map((r) => (r.row === row.row ? { ...r, flags: res.data.flags[0] } : r))))
        .catch(() => {}), CHECK_DELAY_MS)
  }

  const perRowCurrency = rows.some((r) => r.currency)

  // "Re-parse without the cache": the AI reads the row again, a wrong remembered answer is forgotten
  const reparse = async (rowId) => {
    setReparsing((prev) => ({ ...prev, [rowId]: true }))
    setRowErrors((prev) => ({ ...prev, [rowId]: null }))
    try {
      const res = await api.post(`/imports/${importId}/rows/${rowId}/reparse`)
      setRows((prev) => prev.map((r) => (r.row === rowId ? res.data : r)))
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [rowId]: t(errorKey(err, { 422: 'import.reparseNotProduct' })) }))
    } finally {
      setReparsing((prev) => ({ ...prev, [rowId]: false }))
    }
  }

  const edit = (rowId, field, value) => {
    const next = { ...rows.find((r) => r.row === rowId), [field]: value }
    if (field === 'price') next.is_in_stock = value != null
    if (field === 'currency') next.currency_check = false // the seller looked at it
    setRows(rows.map((r) => (r.row === rowId ? next : r)))
    recheck(next)
  }

  return (
    <Card padded={false} className="min-w-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line p-4 text-sm">
        <input value={query} placeholder={t('import.search')}
          onChange={(e) => { setQuery(e.target.value); setPage(1) }}
          className={`${inputClass} md:w-72`} />
        <Checkbox label={t('import.onlyIssues')} checked={onlyIssues} onChange={(e) => { setOnlyIssues(e.target.checked); setPage(1) }} />
        <Checkbox label={t('import.onlyFlagged')} checked={onlyFlagged} onChange={(e) => { setOnlyFlagged(e.target.checked); setPage(1) }} />
        <span className="ml-auto text-muted">{t('import.rows', { count: visible.length })}</span>
      </div>
      {/* The preview stays a table even on a phone: it scrolls inside its own box, the page does not */}
      <p className="flex gap-2 border-b border-line bg-info-soft px-4 py-2 text-xs text-info md:hidden">
        <Monitor className="size-4 shrink-0" aria-hidden />{t('import.desktopHint')}
      </p>
      <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] table-fixed text-sm">
        <thead className="bg-surface-2 text-left text-muted">
          <tr>
            <th className="w-[32%] px-3 py-2 font-medium">{t('import.col.name')}</th>
            <th className="w-[11%] px-3 py-2 font-medium">{t('import.col.brand')}</th>
            <th className="w-[15%] px-3 py-2 font-medium">{t('import.col.category')}</th>
            {/* Pasted text: every line has its own currency, shown in the cell */}
            <th className="w-[11%] px-3 py-2 font-medium">{t('import.col.price')}{!perRowCurrency && `, ${currency}`}</th>
            <th className="w-[13%] px-3 py-2 font-medium">{t('import.col.condition')}</th>
            <th className="w-[11%] px-3 py-2 font-medium">{t('import.col.stock')}</th>
            <th className="w-[7%]" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {pageRows.map((r) => (
            <tr key={r.row} className={needsAttention(r) ? 'bg-warning-soft/50' : ''}>
              <td className="px-2 py-1.5 align-top">
                <input className={`${cellInput} font-medium`} disabled={readOnly} value={r.name} required
                  onChange={(e) => edit(r.row, 'name', e.target.value)} />
                <p className="truncate px-1.5 text-xs text-faint" title={r.raw_name}>
                  <span className={SOURCE_STYLE[r.source] || ''}>{t(`import.source.${r.source || 'ai'}`)}</span>
                  {' · '}{t('import.original')}: {r.raw_name}
                </p>
                {r.note && <p className="truncate px-1.5 text-xs text-muted" title={r.note}>{t('import.note')}: {r.note}</p>}
                <Specs category={r.category} specs={r.specs} guess={r.specs_guess} />
                <Flags flags={r.flags} />
                {rowErrors[r.row] && <p className="px-1.5 text-xs text-danger">{rowErrors[r.row]}</p>}
              </td>
              <td className="px-2 py-1.5 align-top">
                <input className={cellInput} disabled={readOnly} value={r.brand ?? ''}
                  onChange={(e) => edit(r.row, 'brand', e.target.value || null)} />
              </td>
              <td className="px-2 py-1.5 align-top">
                <select className={cellInput} disabled={readOnly} value={r.category} onChange={(e) => edit(r.row, 'category', e.target.value)}>
                  {categories.map((c) => <option key={c.slug} value={c.slug}>{t(`categories.${c.slug}`)}</option>)}
                </select>
              </td>
              <td className="px-2 py-1.5 align-top">
                <input className={cellInput} disabled={readOnly} type="number" min="0" step="any" value={r.price ?? ''}
                  onChange={(e) => edit(r.row, 'price', e.target.value === '' ? null : Number(e.target.value))} />
                {r.currency && (
                  <select disabled={readOnly} value={r.currency} onChange={(e) => edit(r.row, 'currency', e.target.value)}
                    className={`${cellInput} mt-1 ${r.currency_check ? 'border-warning-line bg-warning-soft' : ''}`}>
                    {['USD', 'UZS'].map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                )}
                {r.currency_check && <p className="px-1.5 text-xs text-warning">{t('import.checkCurrency')}</p>}
                <ConvertedPrice price={r.price} currency={r.currency || currency} rate={rate} />
              </td>
              <td className="px-2 py-1.5 align-top">
                <select className={cellInput} disabled={readOnly} value={r.condition} onChange={(e) => edit(r.row, 'condition', e.target.value)}>
                  {CONDITIONS.map((c) => <option key={c} value={c}>{t(`condition.${c}`)}</option>)}
                </select>
                {r.condition === 'unknown' && <p className="px-1.5 text-xs text-warning">{t('import.checkCondition')}</p>}
              </td>
              <td className={`px-3 py-2.5 align-top ${r.is_in_stock ? 'text-success' : 'text-faint'}`}>
                {t(r.is_in_stock ? 'import.inStock' : 'import.outOfStock')}
              </td>
              <td className="px-2 py-1.5 text-center align-top">
                <button title={t('import.reparse')} hidden={readOnly} disabled={reparsing[r.row]} onClick={() => reparse(r.row)}
                  className="rounded px-2 py-1 text-faint hover:bg-surface-2 hover:text-ink disabled:animate-spin">↻</button>
                <button title={t('import.remove')} hidden={readOnly} onClick={() => setRows(rows.filter((x) => x.row !== r.row))}
                  className="rounded px-2 py-1 text-faint hover:bg-danger-soft hover:text-danger">✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {pages > 1 && <div className="border-t border-line p-3"><Pagination page={current} pages={pages} onChange={setPage} /></div>}
    </Card>
  )
}

export default function ImportPage() {
  const { id } = useParams()
  const { t } = useTranslation()
  const [imp, setImp] = useState(null)
  const [rows, setRows] = useState([])
  const [categories, setCategories] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [stats, setStats] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [rate, setRate] = useState(null)
  const [mode, setMode] = useState(null) // a file may switch "full" / "append" before publishing
  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [confirmDrop, setConfirmDrop] = useState(false)

  useEffect(() => {
    api.get('/categories').then((res) => setCategories(res.data)).catch(() => {})
    api.get('/rates/usd').then((res) => setRate(res.data)).catch(() => {})
  }, [])

  // Poll while the AI is still parsing
  useEffect(() => {
    let timer
    const load = () =>
      api.get(`/imports/${id}`)
        .then((res) => {
          setImp(res.data)
          setRows(res.data.rows)
          setMode(res.data.mode)
          if (res.data.status === 'processing') timer = setTimeout(load, POLL_MS)
        })
        .catch((err) => setError(t(errorKey(err))))
    load()
    return () => clearTimeout(timer)
  }, [id, t, reloadKey])

  // "What will change" is counted again after every edit of the rows or a change of the mode
  const ready = imp?.status === 'ready'
  useEffect(() => {
    if (!ready || rows.length === 0) return undefined
    setSummaryLoading(true)
    const timer = setTimeout(() =>
      api.post(`/imports/${id}/summary`, { rows, mode })
        .then((res) => setSummary(res.data))
        .catch(() => {})
        .finally(() => setSummaryLoading(false)), SUMMARY_DELAY_MS)
    return () => clearTimeout(timer)
  }, [id, ready, rows, mode])

  const publish = async (confirmed = false) => {
    setError('')
    // A full file that takes off sale over 30% of the goods looks incomplete: the seller confirms first
    if (summary?.large_drop && !confirmed) {
      setConfirmDrop(true)
      return
    }
    setConfirmDrop(false)
    setBusy(true)
    try {
      const res = await api.post(`/imports/${id}/publish`, { rows, mode, confirm_drop: confirmed })
      setStats(res.data)
      setImp({ ...imp, status: 'published', mode })
    } catch (err) {
      if (err.response?.data?.detail?.code === 'large_drop') setConfirmDrop(true)
      else setError(t(errorKey(err, { 409: 'errors.importNotReady' })))
    } finally {
      setBusy(false)
    }
  }

  // Re-parse rows that failed (e.g. the next day, when the free AI quota is back)
  const retry = async () => {
    setError('')
    try {
      await api.post(`/imports/${id}/retry`)
      setReloadKey((k) => k + 1)
    } catch (err) {
      setError(t(errorKey(err, { 409: 'errors.importNotReady' })))
    }
  }

  // error is "rows_failed:N" or "ai_quota:N" when some rows could not be parsed
  const [failReason, failedCount] = imp?.status === 'ready' && imp.error ? imp.error.split(':') : []
  const parseStats = imp?.stats?.rows ? imp.stats : null

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link to="/seller/imports" className="text-sm text-muted hover:underline">← {t('import.back')}</Link>
          <h1 className="mt-1 text-h2 break-words md:text-h1">{t('import.title')}{imp && `: ${importTitle(imp)}`}</h1>
        </div>
        {imp?.status === 'ready' && (
          <Button size="lg" className="w-full md:w-auto" onClick={() => publish()} disabled={busy || rows.length === 0}>
            {busy ? t('import.publishing') : t('import.publish')}
          </Button>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
      {!imp && !error && <Skeleton className="h-96 w-full rounded-xl" />}
      {imp?.status === 'processing' && <Progress imp={imp} />}
      {imp?.status === 'failed' && (
        <ErrorText>{t([`import.error.${imp.error?.split(':')[0]}`, 'import.failed'])}</ErrorText>
      )}
      {imp?.status === 'published' && (
        <div className="rounded-xl border border-success-line bg-success-soft p-4 text-success">
          <p className="font-medium">{t('import.published')}</p>
          {stats && <p className="mt-1 text-sm">{t('import.publishedStats', stats)}</p>}
        </div>
      )}
      {imp?.status === 'undone' && (
        <div className="rounded-xl border border-warning-line bg-warning-soft p-4 text-sm text-warning">{t('import.undone')}</div>
      )}
      {imp?.status === 'ready' && (
        <>
          {failedCount && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning">
              <span>{t(failReason === 'ai_quota' ? 'import.partialQuota' : 'import.partial', { count: failedCount })}</span>
              <button onClick={retry} className="rounded-md border border-warning-line px-3 py-1 hover:bg-warning-line">
                {t('import.retry')}
              </button>
            </div>
          )}
          {parseStats && <p className="text-sm text-muted">{t('import.stats', parseStats)}</p>}
          {/* Shop remarks found in the file ("Оплата только в национальной валюте"): they do not set the currency */}
          {imp?.stats?.notices?.length > 0 && (
            <p className="mt-1 text-sm text-warning">{t('import.notices', { text: imp.stats.notices.join(' · ') })}</p>
          )}
          {rows.some((r) => r.flags?.length) && (
            <p className="text-sm text-warning">{t('import.flaggedStats', { count: rows.filter((r) => r.flags?.length).length })}</p>
          )}
          <p className="text-sm text-muted">{t('import.hint')}</p>
          {imp.source === 'file' && (
            <Card><ModeChoice mode={mode} onChange={setMode} name="import-mode" /></Card>
          )}
          <ImportSummary summary={summary} loading={summaryLoading} />
          {summary && (
            <Button size="lg" className="w-full md:w-auto md:justify-self-end" onClick={() => publish()} disabled={busy || rows.length === 0}>
              {busy ? t('import.publishing') : t('import.publish')}
            </Button>
          )}
        </>
      )}
      <Modal open={confirmDrop} onClose={() => setConfirmDrop(false)} title={t('importSummary.confirmTitle')}
        footer={<>
          <Button variant="secondary" onClick={() => { setMode('append'); setConfirmDrop(false) }}>{t('importSummary.switchToAppend')}</Button>
          <Button variant="danger" onClick={() => publish(true)}>{t('importSummary.publishAnyway')}</Button>
        </>}>
        <p className="text-sm">{t('importSummary.confirmText', { count: summary?.out_of_stock.length ?? 0, total: summary?.on_sale ?? 0 })}</p>
      </Modal>
      {['ready', 'published', 'undone'].includes(imp?.status) && rows.length > 0 && (
        <PreviewTable importId={id} rows={rows} setRows={setRows} categories={categories}
          currency={imp.currency} rate={rate} readOnly={imp.status !== 'ready'} />
      )}
    </div>
  )
}
