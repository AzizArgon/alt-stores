import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import '../i18n'
import { Modal, ToastProvider, escCloses } from './overlays'
import { DropZone, EXCEL_POINTS, StockImport } from './Warehouse'
import OverlaysCode from './overlays.jsx?raw'

const html = (el) => renderToStaticMarkup(<MemoryRouter><ToastProvider>{el}</ToastProvider></MemoryRouter>)

describe('one modal window (phase 17.1)', () => {
  const draw = (props = {}) => html(
    <Modal open onClose={() => {}} title="Заголовок" primary={{ label: 'Сохранить', onClick: () => {} }} {...props}>Тело</Modal>,
  )
  it('title + cross over a line, the body, "Отмена" then the main button at the bottom right', () => {
    const out = draw()
    expect(out).toContain('role="dialog"')
    expect(out).toContain('Заголовок')
    expect(out).toContain('aria-label="Закрыть"')
    expect(out.indexOf('Заголовок')).toBeLessThan(out.indexOf('Тело'))
    expect(out.indexOf('Тело')).toBeLessThan(out.indexOf('Отмена'))
    expect(out.indexOf('Отмена')).toBeLessThan(out.indexOf('Сохранить'))
    expect(out).toContain('justify-end')
  })
  it('width by the content 560–640 px, 24 px inside, the whole width on a phone, a darker page behind', () => {
    const out = draw()
    expect(out).toContain('sm:min-w-[560px]')
    expect(out).toContain('sm:max-w-[640px]')
    expect(out).toContain('px-6')
    expect(out).toMatch(/class="relative flex w-full /)
    expect(out).toContain('bg-ink/65')
  })
  it('closes on Esc and on a click on the dimmed page; other keys do nothing', () => {
    const onClose = vi.fn()
    escCloses({ key: 'Enter' }, onClose)
    expect(onClose).not.toHaveBeenCalled()
    escCloses({ key: 'Escape' }, onClose)
    expect(onClose).toHaveBeenCalledOnce()
    expect(draw()).toContain('data-backdrop')
    expect(OverlaysCode).toContain('data-backdrop className="absolute inset-0 animate-[fade-in_150ms] bg-ink/65 backdrop-blur-[2px]" onClick={onClose}')
  })
  it('a closed window draws nothing; without buttons there is no bottom line', () => {
    expect(html(<Modal open={false} onClose={() => {}} title="x">y</Modal>)).not.toContain('role="dialog"')
    expect(html(<Modal open onClose={() => {}} title="x">y</Modal>)).not.toContain('Отмена')
  })
})

describe('"Остатки из Excel" (phase 17.1)', () => {
  it('three short points, the drop zone, "Скачать шаблон", "Отмена" + "Загрузить"', () => {
    const out = html(<StockImport onClose={() => {}} onDone={() => {}} />)
    expect(EXCEL_POINTS).toHaveLength(3)
    expect(out).toContain('Меняется только количество, цены — нет')
    expect(out).toContain('столбцы с названиями филиалов')
    expect(out).toContain('Пустая ячейка или «+» — без изменений')
    expect(out).toContain('Перетащите .xlsx или выберите файл')
    expect(out).toContain('border-dashed')
    expect(out).toContain('Скачать шаблон')
    expect(out.indexOf('Отмена')).toBeLessThan(out.indexOf('Загрузить'))
    // nothing to upload before a file is checked
    expect(out).toMatch(/<button[^>]*disabled=""[^>]*>Загрузить/)
  })
  it('the drop zone takes only .xlsx and shows the chosen file', () => {
    const out = html(<DropZone label="Перетащите" overLabel="Отпустите" file={{ name: 'goods.xlsx' }} onFile={() => {}} />)
    expect(out).toContain('accept=".xlsx"')
    expect(out).toContain('goods.xlsx')
  })
})
