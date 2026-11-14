// Phase 16.2: the sections of the home page in groups with headings (names: home.groups.* in the locales).
// A category that is not listed (a new one) goes to "Аксессуары и прочее".
// Phase 17.1: "Прочее" is not shown on the home page (in the catalog it stays the last one)
export const HOME_GROUPS = [
  { key: 'components', slugs: ['cpu', 'gpu', 'motherboard', 'ram', 'ssd', 'hdd', 'psu', 'case', 'cooling'] },
  { key: 'peripherals', slugs: ['monitor', 'mouse', 'keyboard', 'headphones', 'speakers', 'webcams', 'microphones', 'chair'] },
  { key: 'devices', slugs: ['laptop', 'aio', 'desktop'] },
  { key: 'office', slugs: ['printer', 'consumables', 'projector', 'ups', 'scanners', 'screens', 'panels'] },
  { key: 'other', slugs: ['accessories', 'flash', 'bags'] },
]

export const HIDDEN_ON_HOME = 'other'

// The categories that have goods → groups in the fixed order; empty groups are dropped
export function groupSections(items) {
  const bySlug = new Map(items.map((item) => [item.slug, item]))
  const known = new Set([...HOME_GROUPS.flatMap((g) => g.slugs), HIDDEN_ON_HOME])
  const groups = HOME_GROUPS.map((g) => {
    const list = g.slugs.map((s) => bySlug.get(s)).filter(Boolean)
    if (g.key === 'other') list.push(...items.filter((i) => !known.has(i.slug)))
    return { key: g.key, items: list }
  })
  return groups.filter((g) => g.items.length > 0)
}

// Columns of the tile grid: phone 2, tablet 4, laptop 5, wide 6. The "Готовые ПК" tile takes the last column
// on laptops and wider (several rows high), on a phone and a tablet it is a strip under the group
export const GRID_COLS = { base: 2, md: 4, lg: 5, xl: 6 }

// How many rows the tall tile spans: as many as the tiles beside it take (at least 2 when there are enough)
export const sideRows = (count, cols) => Math.max(1, Math.ceil(count / (cols - 1)))

// Small groups share a row (e.g. "Готовые устройства" 3 + "Офис" 3 on a wide screen). For one breakpoint:
// every group gets its width in columns; a group that does not fit the rest of the row starts a new one.
// Phase 17.1: tiles are never stretched — every tile is one column, an empty place at the end of a row is fine.
// The first group carries the tall tile (`side`) and takes whole rows
export function packGroups(counts, cols, side = false) {
  const out = []
  let used = 0 // columns taken in the current row by small groups
  const closeRow = () => {
    // the group before the gap takes the rest of the row, so the next group starts on a new line; its tiles stay one column
    if (used > 0 && used < cols) out[out.length - 1].span += cols - used
    used = 0
  }
  counts.forEach((n, i) => {
    const withSide = side && i === 0
    if (withSide || n >= cols) {
      closeRow()
      out.push({ span: cols })
      return
    }
    if (used + n > cols) closeRow()
    out.push({ span: n })
    used += n
    if (used === cols) used = 0
  })
  closeRow()
  return out
}

// Tailwind needs whole class names in the code: lookups instead of building them
const SPAN = {
  base: { 1: 'col-span-1', 2: 'col-span-2' },
  md: { 1: 'md:col-span-1', 2: 'md:col-span-2', 3: 'md:col-span-3', 4: 'md:col-span-4' },
  lg: { 1: 'lg:col-span-1', 2: 'lg:col-span-2', 3: 'lg:col-span-3', 4: 'lg:col-span-4', 5: 'lg:col-span-5' },
  xl: { 1: 'xl:col-span-1', 2: 'xl:col-span-2', 3: 'xl:col-span-3', 4: 'xl:col-span-4', 5: 'xl:col-span-5', 6: 'xl:col-span-6' },
}
// The tall tile is placed by grid-area (row start / column start / rows / 1 column) in one property — separate
// row-start + row-span classes override each other between breakpoints. Row 1 of a group is its heading
const AREA = {
  lg: { 1: 'lg:[grid-area:2/5/span_1/span_1]', 2: 'lg:[grid-area:2/5/span_2/span_1]', 3: 'lg:[grid-area:2/5/span_3/span_1]', 4: 'lg:[grid-area:2/5/span_4/span_1]', 5: 'lg:[grid-area:2/5/span_5/span_1]' },
  xl: { 1: 'xl:[grid-area:2/6/span_1/span_1]', 2: 'xl:[grid-area:2/6/span_2/span_1]', 3: 'xl:[grid-area:2/6/span_3/span_1]', 4: 'xl:[grid-area:2/6/span_4/span_1]', 5: 'xl:[grid-area:2/6/span_5/span_1]' },
}
const BPS = ['base', 'md', 'lg', 'xl']
const SIDE_BPS = ['lg', 'xl'] // the tall tile is beside the tiles only on laptops and wider

// Classes for each group: `wrap` — its width in the page grid
export function groupLayout(counts) {
  const packs = Object.fromEntries(BPS.map((bp) => [bp, packGroups(counts, GRID_COLS[bp], SIDE_BPS.includes(bp))]))
  return counts.map((_, i) => ({
    wrap: BPS.map((bp) => SPAN[bp][packs[bp][i].span]).join(' '),
  }))
}

// Classes of the tall "Готовые ПК" tile: a full strip under the group on phone/tablet, the last column above
export function sideTileClass(count) {
  const lg = Math.min(5, sideRows(count, GRID_COLS.lg))
  const xl = Math.min(5, sideRows(count, GRID_COLS.xl))
  return `col-span-full ${AREA.lg[lg]} ${AREA.xl[xl]}`
}
