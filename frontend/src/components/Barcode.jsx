import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Camera, Plus, X } from 'lucide-react'
import api, { errorKey } from '../services/api'
import { checkBarcode, feedback } from '../services/barcode'
import NewProductForm from './NewProductForm'
import { Modal } from './overlays'
import { Button, inputClass } from './ui'
import { CatalogPick, GoodsInput } from './Warehouse'

// Phase 12.3: barcodes in the cabinet — the camera, "Привязать штрихкод" for an unknown code and the editor field.

const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'itf', 'codabar', 'qr_code']

// The error text of a code: "код считан с ошибкой", "уже у товара «…»"
export function barcodeError(t, err) {
  const d = err?.response?.data?.detail
  if (d?.code) return t(`barcode.error.${d.code}`, d)
  return t(errorKey(err))
}

// A scan anywhere in the cabinet: the local check, then the store's own binding or the common base.
// Returns {offer} | {unknown: {code, suggestion}} | {error: text}; beeps either way (an unknown code is not an error)
export async function resolveCode(t, raw) {
  const local = checkBarcode(raw)
  if (local.error) {
    feedback(false)
    return { error: t(`barcode.error.${local.error}`) }
  }
  try {
    const res = await api.get('/seller/barcodes/lookup', { params: { code: local.code } })
    feedback(true)
    return res.data.status === 'found' ? { offer: res.data.offer } : { unknown: res.data }
  } catch (err) {
    feedback(false)
    return { error: barcodeError(t, err) }
  }
}

// "Сканировать камерой": the browser's own BarcodeDetector where it exists, otherwise ZXing — loaded only now, on
// the button, not with the page. The camera works only over HTTPS (and on localhost). One code read — it closes.
export function CameraScan({ onCode, onClose }) {
  const { t } = useTranslation()
  const video = useRef(null)
  const [error, setError] = useState('')
  const done = useRef(false)

  useEffect(() => {
    let stream
    let timer
    let controls
    let stopped = false
    const finish = (text) => {
      if (done.current || !text) return
      done.current = true
      onCode(String(text).trim())
    }
    const start = async () => {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) { setError(t('barcode.camera.insecure')); return }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
      } catch (err) {
        setError(t(err?.name === 'NotAllowedError' ? 'barcode.camera.denied' : 'barcode.camera.none'))
        return
      }
      if (stopped) { stream.getTracks().forEach((tr) => tr.stop()); return }
      video.current.srcObject = stream
      await video.current.play().catch(() => {})
      if ('BarcodeDetector' in window) {
        const supported = await window.BarcodeDetector.getSupportedFormats().catch(() => [])
        const detector = new window.BarcodeDetector({ formats: FORMATS.filter((f) => supported.includes(f)) })
        const tick = async () => {
          if (stopped) return
          const found = await detector.detect(video.current).catch(() => [])
          if (found[0]?.rawValue) finish(found[0].rawValue)
          else timer = setTimeout(tick, 150)
        }
        tick()
      } else {
        try {
          const { BrowserMultiFormatReader } = await import('@zxing/browser')
          if (stopped) return
          controls = await new BrowserMultiFormatReader().decodeFromStream(stream, video.current, (result) => {
            if (result) finish(result.getText())
          })
        } catch {
          setError(t('barcode.camera.failed'))
        }
      }
    }
    start()
    return () => {
      stopped = true
      clearTimeout(timer)
      controls?.stop()
      stream?.getTracks().forEach((tr) => tr.stop())
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal open onClose={onClose} title={t('barcode.camera.title')} fullOnPhone>
      {error ? <p role="alert" className="py-6 text-sm text-danger">{error}</p> : (
        <div className="grid gap-2">
          <div className="relative overflow-hidden rounded-lg bg-ink">
            <video ref={video} muted playsInline className="aspect-[4/3] w-full object-cover" />
            <div aria-hidden className="pointer-events-none absolute inset-x-8 top-1/2 h-0.5 -translate-y-1/2 bg-danger/80" />
          </div>
          <p className="text-xs text-muted">{t('barcode.camera.hint')}</p>
        </div>
      )}
    </Modal>
  )
}

export function CameraButton({ onCode, className = '', size = 'md' }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="secondary" size={size} className={className} onClick={() => setOpen(true)}>
        <Camera className="size-4" aria-hidden />{t('barcode.camera.button')}
      </Button>
      {open && <CameraScan onClose={() => setOpen(false)} onCode={(code) => { setOpen(false); onCode(code) }} />}
    </>
  )
}

// An unknown code: bind it to one of "Мои товары"; the store doesn't sell it — a card of the catalog (a new
// offer) or a new card. A code confirmed in the common base offers its card at once.
export function BindBarcode({ code, suggestion, onBound, onClose }) {
  const { t } = useTranslation()
  const [error, setError] = useState('')
  const [pick, setPick] = useState(null) // a card for a new offer (price first)
  const [creating, setCreating] = useState(false)
  const bind = async (offerId) => {
    setError('')
    try {
      const res = await api.post('/seller/barcodes', { code, offer_id: offerId, source: 'scan' })
      feedback(true)
      onBound(res.data.offer)
    } catch (err) {
      feedback(false)
      setError(barcodeError(t, err))
    }
  }
  return (
    <Modal open onClose={onClose} title={t('barcode.bind.title')} fullOnPhone>
      <div className="grid gap-4 text-sm">
        <p>{t('barcode.bind.unknown')} <span className="font-mono font-semibold">{code}</span></p>
        {suggestion && (
          <div className="rounded-lg border border-success-line bg-success-soft p-3">
            <p className="text-xs text-success">{t('barcode.bind.common')}</p>
            <p className="mt-1 font-medium">{suggestion.name}</p>
            <Button size="sm" className="mt-2" onClick={() => (suggestion.my_offer_id ? bind(suggestion.my_offer_id)
              : setPick({ id: suggestion.product_id, name: suggestion.name, category: suggestion.category, specs: [] }))}>
              {t(suggestion.my_offer_id ? 'barcode.bind.useMine' : 'barcode.bind.addCard')}
            </Button>
          </div>
        )}
        {!creating && (
          <div className="grid gap-1">
            <p className="font-medium">{t('barcode.bind.mine')}</p>
            <GoodsInput onPick={(o) => bind(o.id)} allowCatalog inline hint={false} placeholder={t('barcode.bind.search')} />
          </div>
        )}
        {error && <p role="alert" className="text-danger">{error}</p>}
        {creating ? (
          <NewProductForm onCancel={() => setCreating(false)} onCreated={(p) => { setCreating(false); setPick(p) }} />
        ) : (
          <div>
            <p className="text-xs text-muted">{t('barcode.bind.noCard')}</p>
            <Button size="sm" variant="secondary" className="mt-1" onClick={() => setCreating(true)}>{t('barcode.bind.create')}</Button>
          </div>
        )}
      </div>
      {pick && <CatalogPick product={pick} onClose={() => setPick(null)} onPicked={(o) => { setPick(null); bind(o.id) }} />}
    </Modal>
  )
}

// The editor of an offer: its codes (one offer may have several), add by hand, by the scanner or the camera
export function BarcodeField({ offer, onChanged }) {
  const { t } = useTranslation()
  const [items, setItems] = useState(offer.barcodes || [])
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  useEffect(() => setItems(offer.barcodes || []), [offer.id, offer.barcodes])
  const add = async (raw) => {
    setError('')
    const local = checkBarcode(raw)
    if (local.error) { feedback(false); setError(t(`barcode.error.${local.error}`)); return }
    try {
      const res = await api.post('/seller/barcodes', { code: local.code, offer_id: offer.id })
      feedback(true)
      setItems(res.data.barcodes)
      setValue('')
      onChanged?.(res.data.barcodes)
    } catch (err) {
      feedback(false)
      setError(barcodeError(t, err))
    }
  }
  const remove = async (b) => {
    await api.delete(`/seller/barcodes/${b.id}`)
    const next = items.filter((x) => x.id !== b.id)
    setItems(next)
    onChanged?.(next)
  }
  return (
    <div className="grid gap-2">
      {items.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((b) => (
            <li key={b.id} className="inline-flex items-center gap-1 rounded-md border border-line bg-surface-2 py-0.5 pr-0.5 pl-2 font-mono text-sm">
              {b.code}
              <button type="button" onClick={() => remove(b)} aria-label={t('barcode.field.remove', { code: b.code })}
                className="grid size-8 place-items-center rounded text-muted hover:bg-surface hover:text-danger"><X className="size-4" aria-hidden /></button>
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-muted">{t('barcode.field.none')}</p>}
      <div className="flex flex-wrap gap-2">
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder={t('barcode.field.placeholder')}
          aria-label={t('barcode.field.placeholder')} className={`${inputClass} min-w-0 flex-1 basis-48 font-mono`} autoComplete="off"
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (value.trim()) add(value) } }} />
        <Button variant="secondary" onClick={() => value.trim() && add(value)}><Plus className="size-4" aria-hidden />{t('barcode.field.add')}</Button>
        <CameraButton onCode={add} />
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <p className="text-xs text-muted">{t('barcode.field.hint')}</p>
    </div>
  )
}
