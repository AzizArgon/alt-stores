import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { UndoSummary } from './ImportSummary'

const EMPTY = { prices: [], back_in_stock: [], out_of_stock: [], removed_new: [], kept_new: [], conflicts: [] }
const item = (name, price, oldPrice) => ({ name, raw_name: name, price, currency: 'USD', old_price: oldPrice, old_currency: 'USD' })

describe('undo summary (phase 12)', () => {
  it('shows what comes back and the conflicts left as they are', () => {
    const html = renderToStaticMarkup(<UndoSummary summary={{
      ...EMPTY, prices: [item('Lexar', 58, 65), item('Kingston', 120, 110)], removed_new: [item('Goodram', null, 25)],
      conflicts: [item('Patriot', 40, 45)],
    }} />)
    expect(html).toContain('цены вернутся')
    expect(html).toContain('новый товар будет убран')
    expect(html).toContain('товар изменён после загрузки — оставлен как есть')
    expect(html).toContain('ваши правки не трогаем')
    expect(html).not.toContain('Возвращать нечего')
  })
  it('an upload that changed nothing', () => {
    expect(renderToStaticMarkup(<UndoSummary summary={EMPTY} />)).toContain('Возвращать нечего')
  })
})
