// Phase 17.3: the cabinet polish, round 3 — the menu, the widths of «Мои товары», the empty state, the tabs
import { describe, expect, it } from 'vitest'
import './i18n'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { Home, Package } from 'lucide-react'
import Workspace from './layouts/Workspace'
import { COL, NAME_COL, NAME_MIN, PRICE_INPUT } from './pages/GoodsPage'
import GoodsCode from './pages/GoodsPage.jsx?raw'
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')

globalThis.localStorage ??= { getItem: () => null, setItem: () => {}, removeItem: () => {} }

describe('the cabinet menu (phase 17.3)', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={['/seller/goods']}>
      <Workspace home="/seller" subtitle="s" navKey="cabinet.nav" tabKey="cabinet.tab"
        sections={[{ to: '/seller', key: 'overview', icon: Home, end: true, tab: true }, { to: '/seller/goods', key: 'goods', icon: Package, tab: true }]}>
        <p>page</p>
      </Workspace>
    </MemoryRouter>,
  )
  const aside = html.slice(html.indexOf('<aside'), html.indexOf('</aside>'))

  it('the menu is as high as the screen minus the top block, never the whole screen', () => {
    expect(aside).toContain('ws-side')
    expect(aside).not.toContain('100dvh')
    const rule = css.slice(css.indexOf('.ws-side {'), css.indexOf('}', css.indexOf('.ws-side {')))
    expect(rule).toContain('top: var(--ws-head')
    expect(rule).toContain('calc(100vh - var(--ws-head')
    expect(rule).toContain('calc(100dvh - var(--ws-head')
  })

  it('the items scroll in their own box and the fold button is the last thing of the menu (always seen)', () => {
    expect(aside).toMatch(/<nav[^>]*class="[^"]*flex-1[^"]*overflow-y-auto/)
    expect(aside).toMatch(/flex-col/)
    expect(aside.lastIndexOf('<button')).toBeGreaterThan(aside.lastIndexOf('</nav>'))
    expect(aside.slice(aside.lastIndexOf('<button'))).toContain('shrink-0')
  })

  it('the top bar and the demo line are one sticky block (the menu is placed under both)', () => {
    expect(html).toMatch(/<div class="sticky top-0 z-30"><header/)
  })
})

describe('«Мои товары»: the spare width goes to "Товар" only (phase 17.3)', () => {
  it('not table-fixed: "Товар" is w-full, every other column is as narrow as its content and on one line', () => {
    expect(GoodsCode).toContain('<table className="w-full text-sm">')
    expect(NAME_COL).toBe('w-full')
    expect(NAME_MIN).toBe('min-w-60')
    for (const w of Object.values(COL)) expect(w).toBe('w-px whitespace-nowrap')
  })
  it('the price field is compact (112 px), the currency beside it, to the right', () => {
    expect(PRICE_INPUT).toBe('w-28')
    expect(GoodsCode).toContain('inputWidth={PRICE_INPUT} className="justify-end"')
  })
  it('the long one-line texts of a name do not widen its column', () => {
    expect(GoodsCode).toContain('[contain:inline-size]')
  })
})
