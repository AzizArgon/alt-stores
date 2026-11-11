import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { ToastProvider } from '../components/overlays'
import { NAME_COL, StockTotal, stockColumns, stockTotal } from './GoodsPage'

const B = [{ id: 1, name: 'Чиланзар' }, { id: 2, name: 'Юнусабад' }, { id: 3, name: 'Сергели' }]
const offer = { id: 7, stocks: { 1: { quantity: 4 }, 2: { quantity: 0 }, 3: { quantity: 2 } } }

describe('"Мои товары": the table (fix of 11.11.2026)', () => {
  it('the name column is never narrower than 240 px', () => {
    expect(NAME_COL).toContain('min-w-60') // 15rem = 240 px
  })

  it('1–2 places — a column each; 3 and more — one "Остатки"', () => {
    expect(stockColumns(B.slice(0, 2))).toEqual({ places: B.slice(0, 2), columns: B.slice(0, 2), folded: false })
    expect(stockColumns(B)).toEqual({ places: B, columns: [], folded: true })
    expect(stockColumns([...B, { id: 4 }]).places).toHaveLength(4) // every place, not the first three
    expect(stockColumns(B, B[1])).toEqual({ places: [B[1]], columns: [B[1]], folded: false }) // the branch filter
  })

  it('"Остатки" shows the total and the places in the hint', () => {
    expect(stockTotal(offer, B)).toBe(6)
    expect(stockTotal({ stocks: {} }, B)).toBe(null)
    const html = renderToStaticMarkup(<ToastProvider><StockTotal offer={offer} places={B} onSaved={() => {}} readOnly /></ToastProvider>)
    expect(html).toContain('>6<')
    expect(html).toContain('Чиланзар: 4')
    expect(html).toContain('3 места')
  })
})
