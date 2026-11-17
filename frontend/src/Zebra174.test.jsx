// Phase 17.4: one "zebra" for every table and list of the cabinet and the admin
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import './i18n'
import { ZEBRA_CELL, ZEBRA_HEAD, zebra } from './components/ui'
import { MovementRow } from './pages/WarehousePage'
import { LogLine } from './pages/AdminPage'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')
const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')

describe('zebra rows (phase 17.4)', () => {
  it('odd and even rows get different classes, a ticked row its own one', () => {
    expect(zebra(0)).toContain('zebra-odd')
    expect(zebra(1)).toContain('zebra-even')
    expect(zebra(2)).toBe(zebra(0))
    expect(zebra(0)).not.toContain('zebra-selected')
    expect(zebra(1, true)).toContain('zebra-selected')
    for (const i of [0, 1]) expect(zebra(i)).toContain('zebra-row')
  })

  it('the colours: white / light grey / hover / light blue, fixed cells take the row colour, the header apart', () => {
    expect(css).toMatch(/\.zebra-row\s*\{[^}]*--row-bg: var\(--color-surface\)/)
    expect(css).toMatch(/\.zebra-even\s*\{\s*--row-bg/)
    expect(css).toMatch(/\.zebra-row:hover\s*\{\s*--row-bg/)
    expect(css).toMatch(/\.zebra-selected, \.zebra-selected:hover\s*\{\s*--row-bg/)
    expect(css).toMatch(/\.zebra-row > \.zebra-cell\s*\{\s*background-color: var\(--row-bg\)/)
    expect(css).toMatch(/\.zebra-head\s*\{/)
    expect(ZEBRA_CELL).toBe('zebra-cell')
    expect(ZEBRA_HEAD).toBe('zebra-head')
  })

  it('the shared rows take their place in the zebra', () => {
    const m = { id: 1, kind: 'income', delta: 2, name: 'X', at: '2026-11-17T10:00:00', before: 0, after: 2, who: 'seller' }
    const a = { id: 1, action: 'store_block', created_at: '2026-11-17T10:00:00', params: {} }
    const html = (el) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>)
    expect(html(<MovementRow m={m} i={1} />)).toContain('zebra-even')
    expect(html(<LogLine a={a} i={0} />)).toContain('zebra-odd')
  })

  it('no table or list of the cabinet and the admin is left without the zebra', () => {
    const files = ['pages/GoodsPage.jsx', 'pages/WarehousePage.jsx', 'components/Warehouse.jsx', 'components/Stocktake.jsx',
      'pages/SellerPage.jsx', 'pages/SellerReservationsPage.jsx', 'pages/AdminPage.jsx', 'pages/AdminModeration.jsx',
      'pages/ImportPage.jsx', 'pages/SellerAnalyticsPage.jsx']
    for (const f of files) expect(read(`./${f}`), f).toContain('zebra(')
    const goods = read('./pages/GoodsPage.jsx')
    expect(goods).toContain('zebra(i, selected.has(o.id) || allByFilter)')
    expect(goods.match(/ZEBRA_CELL}/g).length).toBeGreaterThanOrEqual(4)
    expect(goods).not.toContain('bg-primary-soft/40')
  })
})
