import { describe, expect, it } from 'vitest'
import { allPrecise, missingRequired, partText, toEditorPart, toPayloadPart } from './builds'

const dictionary = {
  gpu: [{ key: 'chip', kind: 'choice' }, { key: 'memory', kind: 'number', unit: 'GB' }, { key: 'brand', kind: 'choice' }],
}
const part = (slot, mode, extra = {}) => ({ slot, mode, product: null, specs: {}, raw_text: '', quantity: 1, ...extra })

describe('required minimum of a build', () => {
  it('asks for a CPU model and a GPU chip', () => {
    expect(missingRequired([])).toEqual(['cpu', 'gpu'])
    expect(missingRequired([part('cpu', 'specs', { specs: { socket: 'AM4' } }), part('gpu', 'none', { raw_text: 'RTX 3060' })]))
      .toEqual(['cpu', 'gpu'])
  })
  it('takes an exact card, a CPU model or a chip, and integrated graphics', () => {
    expect(missingRequired([part('cpu', 'exact', { product: { id: 1, category: 'cpu' } }), part('gpu', 'specs', { specs: { chip: 'RTX 3060' } })])).toEqual([])
    expect(missingRequired([part('cpu', 'specs', { specs: { model: 'i5-12400F' } }), part('gpu', 'specs', { specs: { integrated: true } })])).toEqual([])
    expect(missingRequired([part('cpu', 'specs', { specs: { model: 'Ryzen 5 5600' } }), part('gpu', 'exact', { product: { id: 2, category: 'gpu' } })])).toEqual([])
    expect(missingRequired([part('cpu', 'specs', { specs: { model: 'Ryzen 5' } }), part('gpu', 'specs', { specs: { integrated: true } })])).toEqual(['cpu'])
  })
})

describe('parts of a build', () => {
  it('says what each level knows', () => {
    expect(partText({ level: 'exact', product: { name: 'MSI RTX 3050' } }, dictionary)).toBe('MSI RTX 3050')
    expect(partText({ level: 'specs', category: 'gpu', specs: { chip: 'RTX 3060', memory: 12 } }, dictionary)).toBe('RTX 3060 · 12 ГБ')
    expect(partText({ level: 'integrated' }, dictionary)).toBe('Встроенная графика')
    expect(partText({ level: 'none', raw_text: '' }, dictionary)).toBe('не указано')
  })
  it('sends only what the chosen level needs', () => {
    const exact = toEditorPart({ slot: 'cpu', level: 'exact', product: { id: 7 }, specs: {}, raw_text: 'Ryzen 5 5600', quantity: 1 }, 'a')
    expect(toPayloadPart(exact)).toEqual({ slot: 'cpu', quantity: 1, raw_text: 'Ryzen 5 5600', product_id: 7 })
    const specs = toEditorPart({ slot: 'storage', level: 'specs', category: 'ssd', specs: { capacity: 1000 }, quantity: 2 }, 'b')
    expect(toPayloadPart(specs)).toEqual({ slot: 'storage', quantity: 2, raw_text: '', category: 'ssd', specs: { capacity: 1000 } })
    expect(toPayloadPart({ ...specs, mode: 'none', raw_text: 'SSD' })).toEqual({ slot: 'storage', quantity: 2, raw_text: 'SSD' })
  })
  it('calls a build fully exact only when every part is', () => {
    expect(allPrecise({ exact: 6, total: 6 })).toBe(true)
    expect(allPrecise({ exact: 5, total: 6 })).toBe(false)
    expect(allPrecise({ exact: 0, total: 0 })).toBe(false)
  })
})
