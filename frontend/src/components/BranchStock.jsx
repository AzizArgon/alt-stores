import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import api, { errorKey } from '../services/api'
import { formatDate } from '../services/format'
import { useToast } from './overlays'
import { Button } from './ui'

// A short branch name for a column: its own name, else the first words of the address
export const branchLabel = (b) => b?.name || (b?.address || '').split(',')[0]

// The seller's stock of one branch: a number (quantity), empty with "есть" (quantity unknown) or "не указано"
export const stockOf = (offer, branch) => offer?.stocks?.[String(branch.id)] || null

export async function saveStocks(offerId, items) {
  const res = await api.put(`/seller/offers/${offerId}/stocks`, items)
  return res.data
}

// The quantity right in the row of "My goods": Enter or leaving the field saves, Esc brings it back;
// an empty field = "не указано" (the branch is not tracked for this item)
export function QtyInput({ offer, branch, onSaved, className = '', readOnly = false }) {
  const { t } = useTranslation()
  const toast = useToast()
  const stock = stockOf(offer, branch)
  const initial = stock?.quantity ?? ''
  const [value, setValue] = useState(initial)
  const cancelled = useRef(false)
  useEffect(() => setValue(initial), [initial])

  const save = async () => {
    if (cancelled.current) {
      cancelled.current = false
      return
    }
    if (String(value) === String(initial)) return
    const item = value === '' ? { branch_id: branch.id, clear: true } : { branch_id: branch.id, quantity: Math.max(0, Math.round(Number(value))) }
    try {
      onSaved(await saveStocks(offer.id, [item]))
      toast(t('cabinet.saved'))
    } catch (err) {
      setValue(initial)
      toast(t(errorKey(err, { 422: `cabinet.error.${err.response?.data?.detail?.code || 'save'}` })), 'danger')
    }
  }
  const present = stock && stock.quantity == null && stock.in_stock
  // "Учёт остатков" (phase 12.2): the number is shown, it changes only by operations of "Склад"
  if (readOnly) {
    return (
      <span title={t('cabinet.error.stock_mode')} className={`flex h-9 items-center px-2 text-sm tabular-nums ${stock?.quantity === 0 ? 'text-faint' : ''} ${className}`}>
        {stock ? (stock.quantity ?? (stock.in_stock ? t('stock.present') : '—')) : '—'}
        {stock?.reserved > 0 && <span className="ml-1 text-xs text-info">({stock.reserved})</span>}
      </span>
    )
  }
  return (
    <input type="number" inputMode="numeric" min="0" step="1" value={value} onChange={(e) => setValue(e.target.value)} onBlur={save}
      aria-label={t('stock.qtyIn', { branch: branchLabel(branch) })} title={stock?.stale ? t('stock.staleSeller') : undefined}
      placeholder={present ? t('stock.present') : '—'}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur()
        if (e.key === 'Escape') {
          cancelled.current = true
          setValue(initial)
          e.currentTarget.blur()
        }
      }}
      className={`h-9 w-full min-w-0 rounded-md border bg-surface px-2 text-sm tabular-nums outline-none hover:border-faint focus:border-primary focus:ring-2 focus:ring-primary-soft ${
        present ? 'placeholder:text-success' : ''} ${stock?.stale ? 'border-warning' : 'border-line-strong'} ${className}`} />
  )
}

// The editor: stock per branch — a quantity, or only "есть / нет", or "не указано"
export function StockEditor({ offer, branches, onSaved }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  if (!branches?.length) return null
  const put = async (item) => {
    setBusy(true)
    try {
      onSaved(await saveStocks(offer.id, [item]))
      toast(t('cabinet.saved'))
    } catch (err) {
      toast(t(errorKey(err, { 422: `cabinet.error.${err.response?.data?.detail?.code || 'save'}` })), 'danger')
    }
    setBusy(false)
  }
  return (
    <div className="mt-3 grid gap-2">
      <p className="text-xs text-muted">{t('stock.editorHint')}</p>
      <ul className="grid gap-2">
        {branches.map((b) => {
          const s = stockOf(offer, b)
          return (
            <li key={b.id} className="grid gap-2 rounded-lg border border-line p-2 sm:grid-cols-[minmax(0,1fr)_7rem]">
              <div className="min-w-0">
                <p className="break-words text-sm font-medium">{branchLabel(b)}{b.is_main && <span className="ml-1 text-xs text-muted">· {t('branches.main')}</span>}</p>
                <p className="text-xs text-muted">
                  {!s ? t('stock.notTracked') : s.quantity == null ? t(s.in_stock ? 'stock.presentNoQty' : 'stock.absent')
                    : t('stock.qty', { count: s.quantity })}
                  {s?.reserved > 0 && ` · ${t('stock.reserved', { count: s.reserved })}`}
                  {s?.stale && <span className="text-warning"> · {t('stock.staleSeller')}</span>}
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => put({ branch_id: b.id, present: true })}>{t('stock.markPresent')}</Button>
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => put({ branch_id: b.id, present: false })}>{t('stock.markAbsent')}</Button>
                  {s && <Button size="sm" variant="text" disabled={busy} onClick={() => put({ branch_id: b.id, clear: true })}>{t('stock.clear')}</Button>}
                </div>
              </div>
              <QtyInput offer={offer} branch={b} onSaved={onSaved} />
            </li>
          )
        })}
      </ul>
      {Object.values(offer.stocks || {}).length > 0 && (
        <p className="text-xs text-muted">{t('stock.general')}</p>
      )}
    </div>
  )
}

export const stockDate = (s) => (s?.updated_at ? formatDate(s.updated_at) : '')
