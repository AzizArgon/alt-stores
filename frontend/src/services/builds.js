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
