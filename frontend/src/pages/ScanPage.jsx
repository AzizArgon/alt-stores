import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { BindBarcode, CameraButton, resolveCode } from '../components/Barcode'
import { branchLabel } from '../components/BranchStock'
import { GoodsInput, OperationForm } from '../components/Warehouse'
import { Button, Card, Select } from '../components/ui'
import { useScanner } from '../services/barcode'
import { formatPrice } from '../services/format'

// Phase 12.3: "Сканирование" — the seller picks a box with the USB scanner or the phone's camera. Приход / Продажа:
// every scan is a line of the document (the same goods again — +1), "Провести" goes through the operations and the
// journal of 12.2 (a store in "Только прайс" changes its stock as a hand edit). Найти: the goods for the seller.
const MODES = ['receipt', 'sale', 'find']
const BRANCH_KEY = 'alt_scan_branch'

export default function ScanPage() {
  const { t } = useTranslation()
  const { store } = useOutletContext()
  const branches = store.branches || []
  const [params, setParams] = useSearchParams()
  const mode = MODES.includes(params.get('mode')) ? params.get('mode') : 'receipt'
  const [branch, setBranchState] = useState(() => {
    let saved = null
    try { saved = Number(localStorage.getItem(BRANCH_KEY)) } catch { /* private mode */ }
    return branches.some((b) => b.id === saved) ? saved : branches[0]?.id
  })
  const [start, setStart] = useState(null) // {mode, offer}: "Приход" / "Продажа" from "Найти"
  const [version, setVersion] = useState(0)
  const priceOnly = store.stock_mode !== 'stock'

  const setMode = (m) => { setStart(null); setParams({ mode: m }) }
  const setBranch = (id) => {
    setStart(null)
    setBranchState(id)
    try { localStorage.setItem(BRANCH_KEY, String(id)) } catch { /* private mode */ }
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div>
        <h1 className="text-h1">{t('barcode.scan.title')}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{t(priceOnly ? 'barcode.scan.hintPrice' : 'barcode.scan.hint')}</p>
      </div>
      {!branches.length ? <Card><p className="text-sm">{t('warehouse.noBranches')}</p></Card> : (
        <>
          <div role="tablist" aria-label={t('barcode.scan.title')} className="grid grid-cols-3 gap-1 rounded-lg bg-surface-2 p-1">
            {MODES.map((m) => (
              <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                className={`min-h-12 rounded-md px-2 text-base font-semibold outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  mode === m ? 'bg-surface text-primary shadow-sm' : 'text-muted hover:text-ink'}`}>
                {t(`barcode.scan.modes.${m}`)}
              </button>
            ))}
          </div>
          {branches.length > 1 && (
            <Select label={t('warehouse.branch')} value={branch} selectClassName="min-h-12 text-base" onChange={(e) => setBranch(Number(e.target.value))}>
              {branches.map((b) => <option key={b.id} value={b.id}>{branchLabel(b)}</option>)}
            </Select>
          )}
          {mode === 'find' ? (
            <FindMode branches={branches} priceOnly={priceOnly} onAction={(m, offer) => { setStart({ mode: m, offer }); setParams({ mode: m }) }} />
          ) : (
            <Card>
              <OperationForm key={`${mode}-${branch}-${version}`} kind={mode} branches={branches} branchId={branch} scan big
                priceOnly={priceOnly} draftKey={`scan_${mode}_${branch}`} initialOffer={start?.mode === mode ? start.offer : null}
                onPosted={() => { setStart(null); setVersion((v) => v + 1) }} />
              <p className="mt-3 text-xs text-muted">{t('barcode.scan.journal')} <Link to="/seller/stock?tab=journal" className="text-primary hover:underline">{t('warehouse.tabs.journal')}</Link></p>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

// "Найти": what the seller needs at the counter — stock and reserve by branch, price, purchase price, the codes
function FindMode({ branches, priceOnly, onAction }) {
  const { t } = useTranslation()
  const [offer, setOffer] = useState(null)
  const [error, setError] = useState('')
  const [binding, setBinding] = useState(null)
  const onCode = async (code) => {
    setError('')
    const res = await resolveCode(t, code)
    if (res.error) setError(res.error)
    else if (res.offer) setOffer(res.offer)
    else setBinding(res.unknown)
  }
  useScanner(onCode, !binding)
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap gap-2 [&>:first-child]:min-w-0 [&>:first-child]:flex-1 [&>:first-child]:basis-64">
        <GoodsInput onPick={(o) => { setError(''); setOffer(o) }} onCode={onCode} big hint={false} />
        <CameraButton onCode={onCode} size="lg" className="min-h-14 w-full sm:w-auto" />
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(o) => { setBinding(null); setOffer(o) }} />}
      {!offer ? <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{t('barcode.scan.findEmpty')}</p> : (
        <Card className="grid gap-3 ring-2 ring-primary">
          <div>
            <Link to={`/products/${offer.product_id}`} target="_blank" className="font-semibold break-words hover:underline">{offer.name}</Link>
            {offer.barcodes?.length > 0 && <p className="mt-0.5 font-mono text-xs text-muted">{offer.barcodes.join(', ')}</p>}
          </div>
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <div><dt className="text-xs text-muted">{t('warehouse.price')}</dt><dd className="font-semibold">{offer.price != null ? formatPrice(offer.price, offer.currency) : '—'}</dd></div>
            <div><dt className="text-xs text-muted">{t('barcode.scan.costAvg')}</dt><dd>{offer.cost_avg != null ? formatPrice(offer.cost_avg, offer.currency) : '—'}</dd></div>
            <div><dt className="text-xs text-muted">{t('barcode.scan.costLast')}</dt><dd>{offer.cost_last != null ? formatPrice(offer.cost_last, offer.currency) : '—'}</dd></div>
          </dl>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted">
              <th className="py-1 font-medium">{t('warehouse.branch')}</th>
              <th className="py-1 text-right font-medium">{t('barcode.scan.qty')}</th>
              <th className="py-1 text-right font-medium">{t('barcode.scan.reserved')}</th>
              <th className="py-1 text-right font-medium">{t('barcode.scan.free')}</th>
            </tr></thead>
            <tbody>
              {branches.map((b) => {
                const s = offer.stocks?.[String(b.id)]
                const q = s?.quantity
                return (
                  <tr key={b.id} className="border-t border-line">
                    <td className="py-2 pr-2">{branchLabel(b)}</td>
                    <td className="py-2 text-right">{q != null ? q : s?.in_stock ? t('barcode.scan.yes') : '—'}</td>
                    <td className="py-2 text-right">{s?.reserved || 0}</td>
                    <td className="py-2 text-right font-semibold">{q != null ? Math.max(0, q - (s.reserved || 0)) : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="grid grid-cols-2 gap-2">
            <Button size="lg" onClick={() => onAction('receipt', offer)}>{t('barcode.scan.modes.receipt')}</Button>
            <Button size="lg" variant="secondary" onClick={() => onAction('sale', offer)}>{t('barcode.scan.modes.sale')}</Button>
          </div>
          {priceOnly && <p className="text-xs text-muted">{t('barcode.scan.priceOnlyNote')}</p>}
        </Card>
      )}
    </div>
  )
}
