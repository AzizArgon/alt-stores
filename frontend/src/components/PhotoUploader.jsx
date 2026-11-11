// Phase 14: one uploader for card photos, offer photos and build photos.
// Drag files in, paste with Ctrl+V, choose several, take a picture on a phone. Each file is checked and shrunk in the
// browser, uploaded with its own progress bar and comes back as a draft in the 1500×1500 standard. Order by dragging
// (or the arrows), main with the star, turn, crop. "Сохранить фото" publishes (a card sold by several stores — after the
// admin's check).
import { ArrowLeft, ArrowRight, Camera, Crop, ImagePlus, RotateCw, Star, TriangleAlert, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PHOTO } from '../config/photo'
import {
  adjustPhoto, imageFiles, loadPhotos, mainOf, moveId, ownOrder, photoError, pickFiles, savePhotos, uploadPhoto,
} from '../services/photos'
import PhotoCropper from './PhotoCropper'
import { Badge, Button, Checkbox } from './ui'

const STATUS_TONE = { draft: 'warning', pending: 'info', rejected: 'danger' }
let tmpSeq = 0

function IconButton({ label, onClick, children, active = false, disabled = false }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled} aria-pressed={active || undefined}
      className={`flex size-8 items-center justify-center rounded-md bg-surface/90 shadow-card outline-none hover:bg-surface focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-40 ${active ? 'text-warning' : 'text-ink'}`}>
      {children}
    </button>
  )
}

// `initial`: the server's view known in advance (tests, a page that has it already)
export default function PhotoUploader({ ownerType, ownerId, hint, onSaved, initial = null, api: deps = {} }) {
  const { t } = useTranslation()
  const call = { loadPhotos, uploadPhoto, adjustPhoto, savePhotos, ...deps }
  const [view, setView] = useState(initial) // the server's view: items, max, sole (cards)
  const [order, setOrder] = useState(() => ownOrder(initial)) // ids of the store's own photos, as shown
  const [mainId, setMainId] = useState(() => mainOf(initial))
  const [uploads, setUploads] = useState([]) // { tmp, name, progress, error }
  const [rights, setRights] = useState(false)
  const [message, setMessage] = useState(null)
  const [saving, setSaving] = useState(false)
  const [cropping, setCropping] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const dragged = useRef(null)
  const fileInput = useRef(null)
  const cameraInput = useRef(null)
  const card = ownerType === 'product'

  const apply = useCallback((v) => {
    setView(v)
    setOrder(ownOrder(v))
    setMainId(mainOf(v))
  }, [])

  useEffect(() => {
    if (initial) return undefined
    let alive = true
    call.loadPhotos(ownerType, ownerId).then((v) => alive && apply(v)).catch(() => alive && setMessage({ key: 'photo.err.unknown' }))
    return () => { alive = false }
  }, [ownerType, ownerId]) // eslint-disable-line react-hooks/exhaustive-deps

  const byId = Object.fromEntries((view?.items || []).map((p) => [p.id, p]))
  const others = (view?.items || []).filter((p) => !p.own)
  const max = view?.max ?? PHOTO.LIMITS[ownerType]
  const room = max - order.length - uploads.filter((u) => !u.error).length

  const addFiles = useCallback((files) => {
    const { accepted, refused } = pickFiles(files, room)
    if (!accepted.length && !refused.length) return
    setMessage(null)
    refused.forEach((file) => setUploads((u) => [...u, { tmp: ++tmpSeq, name: file.name, progress: 0, error: { key: 'photo.err.too_many', params: { max } } }]))
    accepted.forEach((file) => {
      const tmp = ++tmpSeq
      setUploads((u) => [...u, { tmp, name: file.name, progress: 0 }])
      call.uploadPhoto(ownerType, ownerId, file, (progress) =>
        setUploads((u) => u.map((x) => (x.tmp === tmp ? { ...x, progress } : x))))
        .then((photo) => {
          setUploads((u) => u.filter((x) => x.tmp !== tmp))
          setView((v) => ({ ...v, items: [...v.items, photo] }))
          setOrder((o) => [...o, photo.id])
        })
        .catch((err) => setUploads((u) => u.map((x) => (x.tmp === tmp ? { ...x, error: photoError(err) } : x))))
    })
  }, [room, max, ownerType, ownerId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl+V anywhere on the page while the uploader is open
  useEffect(() => {
    const onPaste = (e) => {
      const files = imageFiles(e.clipboardData?.files)
      if (files.length) {
        e.preventDefault()
        addFiles(files)
      }
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [addFiles])

  const replace = (photo) => setView((v) => ({ ...v, items: v.items.map((p) => (p.id === photo.id ? photo : p)) }))
  const run = (promise) => promise.then(replace).catch((err) => setMessage(photoError(err)))

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files)
  }

  const save = async () => {
    const drafts = order.some((id) => byId[id]?.status === 'draft')
    if (card && drafts && !rights) {
      setMessage({ key: 'photo.rightsNeeded' })
      return
    }
    setSaving(true)
    setMessage(null)
    try {
      const v = await call.savePhotos(ownerType, ownerId, order, mainId, rights)
      apply(v)
      setUploads((u) => u.filter((x) => !x.error))
      setMessage({ key: 'photo.saved', ok: true })
      onSaved?.(v)
    } catch (err) {
      setMessage(photoError(err))
    } finally {
      setSaving(false)
    }
  }

  if (!view) return <div className="h-40 animate-pulse rounded-lg bg-surface-2" />
  const canStar = (p) => !card || view.sole ? p.status !== 'rejected' : false
  const tiles = [...others.map((p) => ({ ...p, readonly: true })), ...order.map((id) => byId[id]).filter(Boolean)]

  return (
    <div className="grid gap-3" data-testid="photo-uploader">
      {hint && <p className="rounded-md bg-primary-soft px-3 py-2 text-sm text-primary">{hint}</p>}
      {card && <p className="text-sm text-muted">{t(view.sole ? 'photo.sole' : 'photo.moderated')}</p>}

      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3" aria-label={t('photo.photos')}>
        {tiles.map((p) => {
          const own = !p.readonly
          const pos = order.indexOf(p.id)
          return (
            <li key={p.id} draggable={own}
              onDragStart={() => { dragged.current = p.id }}
              onDragOver={(e) => { if (own && dragged.current) e.preventDefault() }}
              onDrop={(e) => {
                if (!dragged.current) return
                e.preventDefault()
                e.stopPropagation()
                setOrder((o) => moveId(o, dragged.current, { before: p.id }))
                dragged.current = null
              }}
              className={`relative overflow-hidden rounded-lg border bg-surface-2 ${mainId === p.id ? 'border-warning ring-2 ring-warning/40' : 'border-line'} ${own ? 'cursor-grab' : ''}`}
              title={own ? t('photo.drag') : t('photo.otherStore')}>
              <img src={p.thumb} alt="" className="aspect-square w-full object-cover" draggable={false} />
              <div className="absolute top-1 left-1 flex flex-wrap gap-1">
                {mainId === p.id && <Badge tone="warning">{t('photo.main')}</Badge>}
                {STATUS_TONE[p.status] && <Badge tone={STATUS_TONE[p.status]}>{t(`photo.status.${p.status}`)}</Badge>}
                {p.readonly && <Badge>{t('photo.model')}</Badge>}
              </div>
              {p.small && own && (
                <span className="absolute right-1 bottom-11 flex size-7 items-center justify-center rounded-full bg-warning-soft text-warning" title={t('photo.small')}>
                  <TriangleAlert className="size-4" aria-label={t('photo.small')} />
                </span>
              )}
              <div className="absolute inset-x-1 bottom-1 flex flex-wrap justify-end gap-1">
                {canStar(p) && (
                  <IconButton label={t('photo.makeMain')} active={mainId === p.id} onClick={() => setMainId(p.id)}>
                    <Star className="size-4" fill={mainId === p.id ? 'currentColor' : 'none'} aria-hidden />
                  </IconButton>
                )}
                {own && <>
                  <IconButton label={t('photo.left')} disabled={pos <= 0} onClick={() => setOrder((o) => moveId(o, p.id, -1))}><ArrowLeft className="size-4" aria-hidden /></IconButton>
                  <IconButton label={t('photo.right')} disabled={pos >= order.length - 1} onClick={() => setOrder((o) => moveId(o, p.id, 1))}><ArrowRight className="size-4" aria-hidden /></IconButton>
                  <IconButton label={t('photo.rotate')} onClick={() => run(call.adjustPhoto(p.id, { rotate: 1 }))}><RotateCw className="size-4" aria-hidden /></IconButton>
                  <IconButton label={t('photo.crop')} onClick={() => setCropping(p)}><Crop className="size-4" aria-hidden /></IconButton>
                  <IconButton label={t('photo.remove')} onClick={() => { setOrder((o) => o.filter((x) => x !== p.id)); if (mainId === p.id) setMainId(null) }}><X className="size-4" aria-hidden /></IconButton>
                </>}
              </div>
              {p.status === 'rejected' && p.reason && (
                <p className="absolute inset-x-0 top-8 bg-danger-soft px-2 py-1 text-xs text-danger">{t('photo.rejected', { reason: p.reason })}</p>
              )}
            </li>
          )
        })}
        {uploads.map((u) => (
          <li key={u.tmp} className="flex aspect-square flex-col justify-end gap-2 rounded-lg border border-line bg-surface-2 p-2 text-xs">
            <span className="line-clamp-2 break-all text-muted">{u.name}</span>
            {u.error ? (
              <span className="flex items-start gap-1 text-danger" role="alert">
                <span className="min-w-0 flex-1">{t(u.error.key, u.error.params)}</span>
                <button type="button" aria-label={t('common.close')} onClick={() => setUploads((x) => x.filter((y) => y.tmp !== u.tmp))}><X className="size-4" /></button>
              </span>
            ) : (
              <span role="progressbar" aria-label={t('photo.uploading', { name: u.name })} aria-valuenow={u.progress} aria-valuemin={0} aria-valuemax={100}
                className="block h-1.5 overflow-hidden rounded-full bg-line">
                <span className="block h-full bg-primary transition-all" style={{ width: `${u.progress}%` }} />
              </span>
            )}
          </li>
        ))}
      </ul>

      {room > 0 && (
        <div onDragOver={(e) => { if (!dragged.current) { e.preventDefault(); setDragOver(true) } }}
          onDragLeave={() => setDragOver(false)} onDrop={onDrop}
          className={`grid justify-items-center gap-2 rounded-lg border-2 border-dashed p-4 text-center text-sm ${dragOver ? 'border-primary bg-primary-soft' : 'border-line-strong'}`}>
          <ImagePlus className="size-7 text-muted" aria-hidden />
          <p>
            <span className="hidden sm:inline">{t('photo.drop')} </span>
            <button type="button" className="font-semibold text-primary underline-offset-2 hover:underline" onClick={() => fileInput.current?.click()}>
              <span className="hidden sm:inline">{t('photo.choose')}</span><span className="sm:hidden">{t('photo.dropPhone')}</span>
            </button>
          </p>
          <Button variant="secondary" size="sm" className="sm:hidden" onClick={() => cameraInput.current?.click()}>
            <Camera className="size-4" aria-hidden />{t('photo.camera')}
          </Button>
          <p className="text-xs text-muted">{t('photo.formats')} {t('photo.count', { n: order.length, max })}</p>
          <input ref={fileInput} type="file" accept={PHOTO.TYPES.join(',')} multiple hidden data-testid="photo-input"
            onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
          <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
        </div>
      )}

      {card && order.some((id) => byId[id]?.status === 'draft') && (
        <Checkbox label={t('photo.rights')} checked={rights} onChange={(e) => setRights(e.target.checked)} />
      )}
      <div className="flex flex-wrap items-center justify-end gap-3">
        {message && <p role={message.ok ? 'status' : 'alert'} className={`mr-auto text-sm ${message.ok ? 'text-success' : 'text-danger'}`}>{t(message.key, message.params)}</p>}
        <Button onClick={save} disabled={saving || uploads.some((u) => !u.error)}>{saving ? t('photo.saving') : t('photo.save')}</Button>
      </div>

      {cropping && (
        <PhotoCropper photo={cropping} onClose={() => setCropping(null)}
          onApply={(changes) => run(call.adjustPhoto(cropping.id, changes)).then(() => setCropping(null))} />
      )}
    </div>
  )
}
