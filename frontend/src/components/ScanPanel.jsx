import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ScanBarcode, X } from 'lucide-react'
import { checkBarcode, useScanner } from '../services/barcode'
import { placeLabel } from '../services/place'
import { BindBarcode, CameraButton, resolveCode } from './Barcode'
import { useToast } from './overlays'
import { Button, Card, inputClass } from './ui'

// Phase 12.4: scanning is a way of input everywhere, not a page. On a cabinet page without its own scanning the
// USB scanner opens a small panel at the bottom: a known code — the item, its stock in the current place and
// [Открыть товар] [Приёмка] [Продажа]; an unknown one — [Добавить товар с этим кодом].
export function ScanPanel({ enabled, place, stockMode }) {
  const { t } = useTranslation()
  const [hit, setHit] = useState(null) // {offer} | {unknown} | {error}
  const [binding, setBinding] = useState(null)
  const onCode = async (code) => setHit(await resolveCode(t, code))
  useScanner(onCode, enabled && !binding)
  if (!hit && !binding) return null
  const s = hit?.offer && place ? hit.offer.stocks?.[String(place.id)] : null
  const qty = s ? (s.quantity != null ? s.quantity : (s.in_stock ? t('barcode.panel.yes') : t('barcode.panel.no'))) : null
  return (
    <>
      {hit && (
        <div role="status" aria-label={t('barcode.panel.label')}
          className="fixed inset-x-2 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-40 md:inset-x-auto md:right-6 md:bottom-6 md:w-[26rem]">
          <Card className="grid gap-2 shadow-pop ring-2 ring-primary">
            <div className="flex items-start gap-2">
              <ScanBarcode className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
              <div className="min-w-0 flex-1 text-sm">
                {hit.error ? <p className="text-danger">{hit.error}</p> : hit.offer ? (
                  <>
                    <p className="font-semibold break-words">{hit.offer.name}</p>
                    {place && <p className="text-xs text-muted">{qty != null ? t('barcode.panel.here', { place: placeLabel(t, place), qty }) : t('barcode.panel.hereUnknown', { place: placeLabel(t, place) })}</p>}
                  </>
                ) : <p>{t('barcode.bind.unknown')} <span className="font-mono font-semibold">{hit.unknown.code}</span></p>}
              </div>
              <button type="button" onClick={() => setHit(null)} aria-label={t('barcode.panel.close')}
                className="grid size-9 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2"><X className="size-4" aria-hidden /></button>
            </div>
            {hit.offer && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" to={`/seller/goods?edit=${hit.offer.id}`} onClick={() => setHit(null)}>{t('barcode.panel.open')}</Button>
                {stockMode && <Button size="sm" to={`/seller/stock?tab=receipt&offer=${hit.offer.id}`} onClick={() => setHit(null)}>{t('barcode.panel.receipt')}</Button>}
                {stockMode && <Button size="sm" to={`/seller/stock?tab=sale&offer=${hit.offer.id}`} onClick={() => setHit(null)}>{t('barcode.panel.sale')}</Button>}
              </div>
            )}
            {hit.unknown && <div><Button size="sm" onClick={() => { setBinding(hit.unknown); setHit(null) }}>{t('barcode.panel.add')}</Button></div>}
          </Card>
        </div>
      )}
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(offer) => { setBinding(null); setHit({ offer }) }} />}
    </>
  )
}

// "Добавить товары" -> "Отсканировать коробку": the same as a receipt of an unknown code, without a quantity (works
// in "Только прайс" too): the common base or the catalog gives the card, the seller gives the price.
export function ScanBox({ onAdded }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [known, setKnown] = useState(null)
  const [binding, setBinding] = useState(null)
  const [added, setAdded] = useState([])
  const onCode = async (raw) => {
    setError('')
    setKnown(null)
    const local = checkBarcode(raw)
    const res = await resolveCode(t, local.code || raw)
    if (res.error) setError(res.error)
    else if (res.offer) setKnown(res.offer)
    else setBinding(res.unknown)
  }
  useScanner(onCode, !binding)
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <p className="text-sm text-muted">{t('barcode.box.hint')}</p>
      <div className="flex flex-wrap gap-2">
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder={t('barcode.box.input')} aria-label={t('barcode.box.input')}
          className={`${inputClass} min-h-14 min-w-0 flex-1 basis-56 font-mono text-base`} autoComplete="off" inputMode="numeric"
          onKeyDown={(e) => { if (e.key === 'Enter' && value.trim()) { e.preventDefault(); onCode(value.trim()); setValue('') } }} />
        <CameraButton onCode={onCode} size="lg" className="min-h-14 w-full sm:w-auto" />
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {known && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface-2 p-3 text-sm">
          <span className="min-w-0 flex-1"><span className="text-muted">{t('barcode.box.known')}: </span><span className="font-medium">{known.name}</span></span>
          <Link to={`/seller/goods?edit=${known.id}`} className="font-medium text-primary hover:underline">{t('barcode.box.open')}</Link>
        </div>
      )}
      {binding && <BindBarcode code={binding.code} suggestion={binding.suggestion} onClose={() => setBinding(null)}
        onBound={(offer) => { setBinding(null); toast(t('barcode.box.addedToast')); setAdded((a) => [offer, ...a]); onAdded?.() }} />}
      <div>
        <p className="text-sm font-medium">{t('barcode.box.added')}</p>
        {added.length === 0 ? <p className="mt-1 text-sm text-muted">{t('barcode.box.empty')}</p> : (
          <ul className="mt-1 grid gap-1">
            {added.map((o) => <li key={o.id} className="truncate text-sm"><Link to={`/seller/goods?edit=${o.id}`} className="hover:underline">{o.name}</Link> <span className="font-mono text-xs text-muted">{o.barcodes?.join(', ')}</span></li>)}
          </ul>
        )}
      </div>
    </div>
  )
}
