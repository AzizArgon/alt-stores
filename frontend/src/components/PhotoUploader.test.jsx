import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { PHOTO } from '../config/photo'
import { PhotoButton } from '../pages/GoodsPage'
import { PhotoFileError, mainOf, moveId, ownOrder, photoError, pickFiles, placement, prepareFile } from '../services/photos'
import PhotoUploader from './PhotoUploader'

const file = (name, type = 'image/jpeg', size = 1000) => ({ name, type, size })
const photo = (id, extra = {}) => ({ id, thumb: `/media/${id}_t.webp`, url: `/media/${id}.webp`, own: true, status: 'published', main: false, ...extra })

describe('phase 14: the photo uploader', () => {
  it('takes several files at once, only pictures, and refuses what does not fit', () => {
    const files = [file('a.jpg'), file('b.png', 'image/png'), file('notes.pdf', 'application/pdf'), file('c.webp', 'image/webp')]
    const { accepted, refused } = pickFiles(files, 2)
    expect(accepted.map((f) => f.name)).toEqual(['a.jpg', 'b.png'])
    expect(refused.map((f) => f.name)).toEqual(['c.webp'])
  })

  it('changes the order by dragging and by the arrows', () => {
    expect(moveId([1, 2, 3, 4], 4, { before: 2 })).toEqual([1, 4, 2, 3]) // dropped on photo 2
    expect(moveId([1, 2, 3], 1, 1)).toEqual([2, 1, 3]) // the arrow to the right
    expect(moveId([1, 2, 3], 1, -1)).toEqual([1, 2, 3]) // already first
    expect(moveId([1, 2, 3], 3, 5)).toEqual([1, 2, 3])
  })

  it('starts from the own photos in order and the main one', () => {
    const view = { items: [photo(5, { own: false, main: true }), photo(7), photo(9)], max: 5, sole: true }
    expect(ownOrder(view)).toEqual([7, 9])
    expect(mainOf(view)).toBe(5)
  })

  it('shows the main one with the star, statuses, the small-photo warning and the rights tick for a card', () => {
    const view = {
      max: 5, sole: false, items: [
        photo(1, { main: true }), photo(2, { status: 'draft', small: true }), photo(3, { status: 'pending' }),
        photo(4, { status: 'rejected', reason: 'Чужой водяной знак' })],
    }
    const html = renderToStaticMarkup(<PhotoUploader ownerType="product" ownerId={1} initial={view} />)
    expect(html).toContain('Главное')
    expect(html).toContain('Не сохранено')
    expect(html).toContain('На проверке')
    expect(html).toContain('Отклонено: Чужой водяной знак')
    expect(html).toContain('Фото маленькое')
    expect(html).toContain('У меня есть право использовать это фото')
    expect(html).toContain('несколько магазинов') // goes to the admin
    expect(html).toContain('multiple') // several files at once
    expect(html).toContain('capture="environment"') // the camera on a phone
    expect(html.indexOf('/media/1_t.webp')).toBeLessThan(html.indexOf('/media/2_t.webp'))
  })

  it('an offer photo needs no rights tick and shows the used-goods hint', () => {
    const html = renderToStaticMarkup(<PhotoUploader ownerType="offer" ownerId={1} initial={{ max: 6, items: [photo(1, { status: 'draft' })] }}
      hint="Сфотографируйте сам товар — покупатели б/у доверяют реальным фото" />)
    expect(html).not.toContain('У меня есть право')
    expect(html).toContain('покупатели б/у доверяют реальным фото')
    expect(html).toContain('1 из 6')
  })

  it('checks files in the browser before sending', async () => {
    await expect(prepareFile(file('x.gif', 'image/gif'))).rejects.toMatchObject({ code: 'format' })
    await expect(prepareFile(file('x.jpg', 'image/jpeg', 9 * 1024 * 1024))).rejects.toMatchObject({ code: 'too_heavy' })
    const small = { width: 300, height: 800 }
    await expect(prepareFile(file('x.jpg'), { decode: async () => small })).rejects.toMatchObject({ code: 'too_small' })
    const ok = await prepareFile(file('x.jpg'), { decode: async () => ({ width: 1200, height: 900 }) })
    expect(ok).toMatchObject({ w: 1200, h: 900 })
  })

  it('server and browser errors become understandable texts', () => {
    expect(photoError(new PhotoFileError('too_small', { px: 400 }))).toEqual({ key: 'photo.err.too_small', params: { px: 400 } })
    expect(photoError({ response: { status: 429, data: { detail: { code: 'photo_limit', limit: 50 } } } }).key).toBe('photo.err.limit')
    expect(photoError({}).key).toBe('photo.err.unknown')
  })

  it('the cropper uses the server formula: whole photo, safe zone, at most 2×', () => {
    const p = placement(1200, 900)
    expect(p.nw).toBe(PHOTO.CANVAS * PHOTO.SAFE_ZONE)
    expect(p.x + p.nw / 2).toBe(PHOTO.CANVAS / 2)
    expect(placement(200, 200).scale).toBe(PHOTO.MAX_UPSCALE)
    const moved = placement(1000, 1000, 4, 0.5, 0.5)
    expect(moved.x + moved.nw).toBeLessThanOrEqual(PHOTO.CANVAS)
  })
})

describe('phase 14: «Мои товары» — photos from the row', () => {
  it('"Добавить фото" without photos, the count with them', () => {
    const none = renderToStaticMarkup(<MemoryRouter><PhotoButton o={{ photos: { own: 0, card: 0 } }} onClick={() => {}} /></MemoryRouter>)
    expect(none).toContain('Добавить фото')
    const some = renderToStaticMarkup(<PhotoButton o={{ photos: { own: 2, card: 1 } }} onClick={() => {}} />)
    expect(some).toContain('Фото 3')
  })
})

describe('phase 14: «Мои товары» — the filter «Без фото»', () => {
  it('is among the filters and keeps its state in the address', async () => {
    const { Filters } = await import('../pages/GoodsPage')
    const html = renderToStaticMarkup(<Filters params={new URLSearchParams('no_photo=1')} setParam={() => {}} categories={[]} branches={[]} />)
    expect(html).toMatch(/checked=""[^>]*\/><span class="min-w-0">Без фото/)
    const off = renderToStaticMarkup(<Filters params={new URLSearchParams('')} setParam={() => {}} categories={[]} branches={[]} />)
    expect(off).toContain('Без фото')
    expect(off).not.toMatch(/checked=""[^>]*\/><span class="min-w-0">Без фото/)
  })
})
