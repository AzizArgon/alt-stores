// Phase 14: the cropper with the template's rulers — the 1500×1500 frame, the dashed safe zone (80%) and the centre
// lines. The photo moves with the mouse or a finger, scales with the wheel, two fingers or the slider; the result is
// drawn at once by the same formula as the server (services/photos.js placement). "Белый фон / размытый фон" switches
// the background when the automatic choice was wrong. "Применить" asks the server to make the square again.
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PHOTO } from '../config/photo'
import { placement } from '../services/photos'
import { Modal } from './overlays'
import { Button, Tabs } from './ui'

const C = PHOTO.CANVAS
const clamp = (v, a, b) => Math.min(Math.max(v, a), b)

export default function PhotoCropper({ photo, onClose, onApply }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState(photo.mode)
  const [zoom, setZoom] = useState(photo.zoom || 1)
  const [pos, setPos] = useState({ ox: photo.ox || 0, oy: photo.oy || 0 })
  const [img, setImg] = useState(null)
  const [busy, setBusy] = useState(false)
  const canvas = useRef(null)
  const pointers = useRef(new Map())
  const pinch = useRef(null)
  const size = 320

  // Card photos on a white background are trimmed to the product (the box the server found)
  const box = photo.trim && mode === 'white' && photo.box ? photo.box : [0, 0, photo.src_w, photo.src_h]
  const rw = box[2] - box[0]
  const rh = box[3] - box[1]
  const place = placement(rw, rh, zoom, pos.ox, pos.oy)
  const maxZoom = Math.max(1, place.maxZoom)

  useEffect(() => {
    const image = new Image()
    image.onload = () => setImg(image)
    image.src = photo.src
  }, [photo.src])

  useEffect(() => {
    const ctx = canvas.current?.getContext('2d')
    if (!ctx || !img) return
    const k = size / C
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.filter = 'none'
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, size, size)
    if (mode === 'blur') {
      // The background: the whole photo covering the square, strongly blurred and a bit darker
      const s = Math.max(size / img.width, size / img.height)
      ctx.filter = 'blur(14px) brightness(0.82)'
      ctx.drawImage(img, (size - img.width * s) / 2, (size - img.height * s) / 2, img.width * s, img.height * s)
      ctx.filter = 'none'
    }
    ctx.drawImage(img, box[0], box[1], rw, rh, place.x * k, place.y * k, place.nw * k, place.nh * k)
  }, [img, mode, zoom, pos, box[0], box[1], rw, rh]) // eslint-disable-line react-hooks/exhaustive-deps

  const onDown = (e) => {
    e.currentTarget.setPointerCapture?.(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      pinch.current = { d: Math.hypot(a.x - b.x, a.y - b.y), zoom }
    }
  }
  const onMove = (e) => {
    const prev = pointers.current.get(e.pointerId)
    if (!prev) return
    const now = { x: e.clientX, y: e.clientY }
    pointers.current.set(e.pointerId, now)
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()]
      setZoom(clamp(pinch.current.zoom * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.current.d), 0.3, maxZoom))
      return
    }
    setPos((p) => ({ ox: clamp(p.ox + (now.x - prev.x) / size, -0.5, 0.5), oy: clamp(p.oy + (now.y - prev.y) / size, -0.5, 0.5) }))
  }
  const onUp = (e) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinch.current = null
  }
  const onWheel = (e) => {
    e.preventDefault()
    setZoom((z) => clamp(z * (e.deltaY < 0 ? 1.08 : 1 / 1.08), 0.3, maxZoom))
  }
  // The wheel must not scroll the page under the window (a passive React listener cannot stop it)
  const frame = useRef(null)
  useEffect(() => {
    const el = frame.current
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  const apply = async () => {
    setBusy(true)
    // The final position is the clamped one (the photo stays whole inside the square)
    const ox = (place.x + place.nw / 2) / C - 0.5
    const oy = (place.y + place.nh / 2) / C - 0.5
    await onApply({ mode, zoom: Number(zoom.toFixed(3)), ox: Number(ox.toFixed(4)), oy: Number(oy.toFixed(4)) })
    setBusy(false)
  }

  const margin = ((1 - PHOTO.SAFE_ZONE) / 2) * 100
  return (
    <Modal open onClose={onClose} title={t('photo.cropper.title')} fullOnPhone footer={<>
      <Button variant="secondary" onClick={() => { setZoom(1); setPos({ ox: 0, oy: 0 }); setMode(photo.auto_mode) }}>{t('photo.cropper.reset')}</Button>
      <Button onClick={apply} disabled={busy}>{t('photo.cropper.apply')}</Button>
    </>}>
      <div className="grid justify-items-center gap-3">
        <p className="text-sm text-muted">{t('photo.cropper.hint')}</p>
        <Tabs label={t('photo.cropper.title')} value={mode} onChange={setMode}
          tabs={[{ value: 'white', label: t('photo.cropper.white') }, { value: 'blur', label: t('photo.cropper.blur') }]} />
        <div ref={frame} className="relative touch-none select-none" style={{ width: size, height: size, maxWidth: '100%' }}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
          aria-label={t('photo.cropper.frame')} role="img">
          <canvas ref={canvas} width={size} height={size} className="block size-full cursor-move rounded-sm border border-line-strong" />
          {/* The template: the frame, the dashed safe zone, the centre lines */}
          <svg className="pointer-events-none absolute inset-0 size-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            <rect x="0.3" y="0.3" width="99.4" height="99.4" fill="none" stroke="var(--color-primary)" strokeWidth="0.6" />
            {/* White under the dashes: the zone is seen on a dark or a busy photo too */}
            <rect x={margin} y={margin} width={100 - 2 * margin} height={100 - 2 * margin} fill="none" stroke="#fff" strokeWidth="1" strokeOpacity="0.8" />
            <rect x={margin} y={margin} width={100 - 2 * margin} height={100 - 2 * margin} fill="none"
              stroke="var(--color-primary)" strokeWidth="0.6" strokeDasharray="2 1.5" />
            <path d="M50 0V100M0 50H100" stroke="var(--color-primary)" strokeWidth="0.25" strokeOpacity="0.5" />
          </svg>
        </div>
        <label className="flex w-full max-w-80 items-center gap-3 text-sm">
          <span className="shrink-0 text-muted">{t('photo.cropper.zoom')}</span>
          <input type="range" min={0.3} max={maxZoom} step={0.01} value={Math.min(zoom, maxZoom)}
            onChange={(e) => setZoom(Number(e.target.value))} className="min-w-0 flex-1 accent-primary" />
        </label>
        {photo.small && <p className="text-sm text-warning">{t('photo.small')}</p>}
      </div>
    </Modal>
  )
}
