import i18n from '../i18n'
import { formatSpec } from './specs'

// Ready PCs (phase B4). A part has a precision level the buyer always sees:
//   exact      — a reference card (a link to it);
//   specs      — values by the category dictionary, no card ("RTX 3060 · 12 ГБ", the maker not said);
//   integrated — integrated graphics instead of a GPU;
//   none       — only the seller's words, or nothing.
export const SLOTS = ['cpu', 'motherboard', 'ram', 'gpu', 'storage', 'psu', 'case', 'cooling', 'other']
export const PRECISE = ['exact', 'integrated']
// The category whose dictionary the "only specs" values of a slot use (a storage slot may be ssd or hdd)
export const SLOT_CATEGORIES = {
  cpu: ['cpu'], motherboard: ['motherboard'], ram: ['ram'], gpu: ['gpu'], storage: ['ssd', 'hdd'],
  psu: ['psu'], case: ['case'], cooling: ['cooling'],
}

// "Only specs" as one line: a CPU model first, then values in dictionary order; the brand is shown apart
export function specsValues(category, specs, dictionary) {
  const known = dictionary?.[category] || []
  const values = known
    .filter((s) => s.key !== 'brand' && specs?.[s.key] !== undefined && specs[s.key] !== '')
    .map((s) => formatSpec({ ...s, value: specs[s.key] }))
  return [specs?.model, ...values].filter(Boolean).join(' · ')
}

// What a part is, in words: the card name, the values, "integrated graphics" or the seller's text
export function partText(part, dictionary) {
  if (part.level === 'exact') return part.product.name
  if (part.level === 'integrated') return i18n.t('builds.integrated')
  if (part.level === 'specs') {
    const brand = part.specs?.brand
    return [brand, specsValues(part.category, part.specs, dictionary)].filter(Boolean).join(' ')
  }
  return part.raw_text || i18n.t('builds.notSpecified')
}

export const allPrecise = (precision) => precision.total > 0 && precision.exact === precision.total

// The same minimum as the server: a CPU at least by its model ("Ryzen 5 5600", "i5-12400F"),
// a GPU at least by its chip ("RTX 3060") or integrated graphics. Parts as the editor keeps them.
export const CPU_MODEL = /\b(?:core\s*)?(?:i[3579]|ryzen\s*(?:ai\s*)?[3579]|ultra\s*[579]|pentium|celeron|athlon|xeon|threadripper)\b[\s-]*[\w-]*?\d{3,5}/i

export function missingRequired(parts) {
  const has = (slot, test) => parts.some((p) => p.slot === slot && test(p))
  const card = (p, category) => p.mode === 'exact' && p.product?.category === category
  const specs = (p) => (p.mode === 'specs' ? p.specs || {} : {})
  const missing = []
  if (!has('cpu', (p) => card(p, 'cpu') || CPU_MODEL.test(String(specs(p).model || '')))) missing.push('cpu')
  if (!has('gpu', (p) => card(p, 'gpu') || specs(p).chip || specs(p).integrated)) missing.push('gpu')
  return missing
}

// A part of the server (with its level) -> the editor's part; and back to what the server takes
export function toEditorPart(c, key) {
  const mode = c.level === 'exact' ? 'exact' : c.level === 'none' ? 'none' : 'specs'
  return { key, slot: c.slot, mode, product: c.product, category: c.category || SLOT_CATEGORIES[c.slot]?.[0] || null,
    specs: c.specs || {}, raw_text: c.raw_text || '', quantity: c.quantity || 1 }
}

export function toPayloadPart(p) {
  const base = { slot: p.slot, quantity: Number(p.quantity) || 1, raw_text: p.raw_text || '' }
  if (p.mode === 'exact' && p.product) return { ...base, product_id: p.product.id }
  if (p.mode === 'specs') return { ...base, category: p.category, specs: p.specs }
  return base
}
