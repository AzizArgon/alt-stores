// Phase 14: photos — checks and shrinking in the browser before sending, the uploader's API calls
import { PHOTO } from '../config/photo'
import api from './api'

export class PhotoFileError extends Error {
  constructor(code, params = {}) {
    super(code)
    this.code = code
    this.params = params
  }
}

// The i18n key and params of a failed upload (a browser check or the server's {detail: {code: 'photo_xxx'}})
export function photoError(err) {
  if (err instanceof PhotoFileError) return { key: `photo.err.${err.code}`, params: err.params }
  const detail = err?.response?.data?.detail
  const code = typeof detail?.code === 'string' ? detail.code.replace(/^photo_/, '') : null
  if (code) return { key: `photo.err.${code}`, params: detail }
  if (err?.response?.status === 413) return { key: 'photo.err.too_heavy', params: { mb: PHOTO.MAX_MB } }
  return { key: 'photo.err.unknown', params: {} }
}

const canvasBlob = (canvas, type, quality) => new Promise((resolve) => canvas.toBlob(resolve, type, quality))

// Checks a file like the server does, and shrinks a big one to 2000 px by the longest side (upright by EXIF).
// Returns the file to send and its own resolution, which the server keeps as "исходное разрешение"
export async function prepareFile(file, { decode = globalThis.createImageBitmap } = {}) {
  if (!PHOTO.TYPES.includes(file.type)) throw new PhotoFileError('format')
  if (file.size > PHOTO.MAX_MB * 1024 * 1024) throw new PhotoFileError('too_heavy', { mb: PHOTO.MAX_MB })
  if (!decode) return { blob: file, w: null, h: null }
  let bmp
  try {
    bmp = await decode(file, { imageOrientation: 'from-image' })
  } catch {
    throw new PhotoFileError('not_image')
  }
  const { width: w, height: h } = bmp
  if (Math.max(w, h) > PHOTO.MAX_SIDE) throw new PhotoFileError('too_big', { px: PHOTO.MAX_SIDE })
  if (Math.min(w, h) < PHOTO.MIN_SIDE) throw new PhotoFileError('too_small', { px: PHOTO.MIN_SIDE })
  const long = Math.max(w, h)
  if (long <= PHOTO.SOURCE_MAX) return { blob: file, w, h }
  const k = PHOTO.SOURCE_MAX / long
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * k)
  canvas.height = Math.round(h * k)
  canvas.getContext('2d').drawImage(bmp, 0, 0, canvas.width, canvas.height)
  // WebP keeps transparency; a browser that cannot make WebP sends PNG (transparent) or JPEG
  let blob = await canvasBlob(canvas, 'image/webp', 0.92)
  if (!blob || blob.type !== 'image/webp') blob = await canvasBlob(canvas, file.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.92)
  return { blob: blob || file, w, h }
}

export const loadPhotos = (ownerType, ownerId) =>
  api.get('/seller/photos', { params: { owner_type: ownerType, owner_id: ownerId } }).then((r) => r.data)

export async function uploadPhoto(ownerType, ownerId, file, onProgress) {
  const { blob, w, h } = await prepareFile(file)
  const form = new FormData()
  form.append('owner_type', ownerType)
  form.append('owner_id', ownerId)
  // The server never uses the file name: a fixed one
  form.append('file', blob, blob.type === 'image/png' ? 'photo.png' : blob.type === 'image/jpeg' ? 'photo.jpg' : 'photo.webp')
  if (w && h) {
    form.append('orig_w', w)
    form.append('orig_h', h)
  }
  const r = await api.post('/seller/photos', form, {
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded / e.total) * 100) : 50),
  })
  return r.data
}

export const adjustPhoto = (id, changes) => api.patch(`/seller/photos/${id}`, changes).then((r) => r.data)

export const savePhotos = (ownerType, ownerId, ids, mainId, rights) =>
  api.put('/seller/photos', { owner_type: ownerType, owner_id: ownerId, ids, main_id: mainId, rights }).then((r) => r.data)

// Image files of a paste (Ctrl+V) or a drop
export const imageFiles = (list) => Array.from(list || []).filter((f) => f && f.type?.startsWith('image/'))

// Several files at once: the ones that fit into the free places and the rest (refused with "не больше N фото")
export function pickFiles(files, room) {
  const list = imageFiles(files)
  return { accepted: list.slice(0, Math.max(room, 0)), refused: list.slice(Math.max(room, 0)) }
}

// The uploader's starting state from the server's view: own photos in order, the main one
export const ownOrder = (view) => (view?.items || []).filter((p) => p.own).map((p) => p.id)
export const mainOf = (view) => (view?.items || []).find((p) => p.main)?.id ?? null

// Moves an id before another one ({ before: id }, drag to reorder) or by a step (-1 / 1, the arrow buttons)
export function moveId(ids, id, target) {
  const from = ids.indexOf(id)
  if (from < 0) return ids
  const rest = ids.filter((x) => x !== id)
  const to = typeof target === 'number' ? Math.min(Math.max(from + target, 0), rest.length) : rest.indexOf(target.before)
  rest.splice(to < 0 ? rest.length : to, 0, id)
  return rest
}

// The placement of the cropper — the same formula as backend imaging.placement()
export function placement(w, h, zoom = 1, ox = 0, oy = 0) {
  const { CANVAS: C, SAFE_ZONE, MAX_UPSCALE } = PHOTO
  const fit = Math.min((C * SAFE_ZONE) / w, (C * SAFE_ZONE) / h, MAX_UPSCALE)
  const cap = Math.min(MAX_UPSCALE, C / w, C / h)
  const scale = Math.min(fit * Math.max(zoom, 0.3), cap)
  const nw = Math.max(1, Math.round(w * scale))
  const nh = Math.max(1, Math.round(h * scale))
  const cx = Math.min(Math.max(C / 2 + ox * C, nw / 2), C - nw / 2)
  const cy = Math.min(Math.max(C / 2 + oy * C, nh / 2), C - nh / 2)
  return { scale, nw, nh, x: Math.round(cx - nw / 2), y: Math.round(cy - nh / 2), maxZoom: cap / fit }
}
