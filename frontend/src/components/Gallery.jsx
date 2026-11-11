// Phase 14: photos on the storefront — the card gallery («Фото модели»), small previews of an offer («Фото продавца»)
// and the full-screen viewer with arrows, keys and a finger swipe on a phone.
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

export function Lightbox({ photos, index, label, onClose }) {
  const { t } = useTranslation()
  const [i, setI] = useState(index)
  const start = useRef(null)
  const n = photos.length
  const go = (d) => setI((x) => (x + d + n) % n)

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'ArrowLeft') go(-1)
    }
    document.addEventListener('keydown', onKey)
    const before = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = before }
  }) // eslint-disable-line react-hooks/exhaustive-deps

  const p = photos[i]
  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={label} className="fixed inset-0 z-50 flex flex-col bg-[rgb(12_14_20/0.94)] text-white"
      onPointerDown={(e) => { start.current = e.clientX }}
      onPointerUp={(e) => {
        if (start.current == null) return
        const dx = e.clientX - start.current
        start.current = null
        if (Math.abs(dx) > 40 && n > 1) go(dx < 0 ? 1 : -1)
      }}>
      <div className="flex items-center justify-between gap-3 p-3">
        <span className="text-sm">{label} · {t('photo.of', { n: i + 1, total: n })}</span>
        <button type="button" aria-label={t('common.close')} onClick={onClose}
          className="flex size-11 items-center justify-center rounded-md hover:bg-white/10"><X className="size-6" /></button>
      </div>
      <div className="relative flex min-h-0 flex-1 touch-pan-y items-center justify-center px-2 pb-4">
        <img src={p.url} alt="" className="max-h-full max-w-full rounded-md bg-white object-contain" draggable={false} />
        {n > 1 && <>
          <button type="button" aria-label={t('photo.prev')} onClick={() => go(-1)}
            className="absolute left-2 hidden size-12 items-center justify-center rounded-full bg-black/40 hover:bg-black/60 sm:flex"><ChevronLeft className="size-7" /></button>
          <button type="button" aria-label={t('photo.next')} onClick={() => go(1)}
            className="absolute right-2 hidden size-12 items-center justify-center rounded-full bg-black/40 hover:bg-black/60 sm:flex"><ChevronRight className="size-7" /></button>
        </>}
      </div>
      {n > 1 && (
        <div className="flex justify-center gap-1.5 pb-4" aria-hidden>
          {photos.map((x, k) => <span key={x.id} className={`size-2 rounded-full ${k === i ? 'bg-white' : 'bg-white/40'}`} />)}
        </div>
      )}
    </div>,
    document.body,
  )
}

// A picture with a grey placeholder until it has loaded (no jumping grid: the box has its size before)
export function LazyImg({ src, alt = '', className = '', imgClassName = 'object-contain' }) {
  const [loaded, setLoaded] = useState(false)
  return (
    <span className={`relative block overflow-hidden bg-surface-2 ${className}`}>
      {!loaded && <span className="absolute inset-0 animate-pulse bg-line/60" aria-hidden />}
      <img src={src} alt={alt} loading="lazy" decoding="async" onLoad={() => setLoaded(true)}
        className={`size-full bg-white ${imgClassName} transition-opacity ${loaded ? 'opacity-100' : 'opacity-0'}`} />
    </span>
  )
}

// Small previews in a row; a click opens the viewer
export function PhotoThumbs({ photos, label, big = false, className = '' }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(null)
  if (!photos?.length) return null
  return (
    <div className={className}>
      <p className="text-xs text-muted">{label}</p>
      <ul className="mt-1 flex flex-wrap gap-1.5">
        {photos.map((p, i) => (
          <li key={p.id}>
            <button type="button" onClick={() => setOpen(i)} aria-label={t('photo.open', { n: i + 1 })}
              className="block overflow-hidden rounded-md border border-line outline-none focus-visible:ring-2 focus-visible:ring-primary">
              <LazyImg src={p.thumb} className={big ? 'size-20 md:size-24' : 'size-12 md:size-14'} imgClassName="object-cover" />
            </button>
          </li>
        ))}
      </ul>
      {open != null && <Lightbox photos={photos} index={open} label={label} onClose={() => setOpen(null)} />}
    </div>
  )
}

// The card gallery: the main photo large, the others below; any of them opens the viewer
export function ProductGallery({ photos, label, className = '' }) {
  const { t } = useTranslation()
  const [current, setCurrent] = useState(0)
  const [open, setOpen] = useState(null)
  const p = photos[Math.min(current, photos.length - 1)]
  return (
    <div className={`min-w-0 ${className}`}>
      <button type="button" onClick={() => setOpen(current)} aria-label={t('photo.open', { n: current + 1 })}
        className="block w-full overflow-hidden rounded-lg border border-line outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <LazyImg src={p.url} alt="" className="aspect-square w-full" />
      </button>
      {photos.length > 1 && (
        <ul className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
          {photos.map((x, i) => (
            <li key={x.id} className="shrink-0">
              <button type="button" onClick={() => setCurrent(i)} aria-label={t('photo.open', { n: i + 1 })} aria-current={i === current || undefined}
                className={`block overflow-hidden rounded-md border-2 outline-none ${i === current ? 'border-primary' : 'border-transparent'}`}>
                <LazyImg src={x.thumb} className="size-12" imgClassName="object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1 text-xs text-muted">{label}</p>
      {open != null && <Lightbox photos={photos} index={open} label={label} onClose={() => setOpen(null)} />}
    </div>
  )
}
