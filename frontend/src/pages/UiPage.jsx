// Development-only page with every basic component: for checks and screenshots for the thesis.
// Its texts are samples and it never reaches the public build, so they live here, not in ru.json
import { ChevronDown, LogOut, Settings } from 'lucide-react'
import { useState } from 'react'
import Flags from '../components/Flags'
import { BrandName, LogoMark } from '../components/Logo'
import { MarketLabel } from '../components/Market'
import { Dropdown, DropdownItem, Modal, Sheet, useToast } from '../components/overlays'
import Price from '../components/Price'
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, Pagination, PasswordInput, Select, Skeleton, SkeletonCards, Switch, Tabs,
} from '../components/ui'

const COLORS = ['primary', 'primary-soft', 'accent', 'accent-soft', 'bg', 'surface', 'surface-2', 'ink', 'muted', 'faint', 'line', 'line-strong',
  'success', 'info', 'info-soft', 'warning', 'warning-soft', 'danger', 'danger-soft', 'below', 'below-soft', 'at', 'at-soft', 'above', 'above-soft']
const SAMPLE_FLAGS = [
  { type: 'server_hardware', level: 'info', reason_key: 'server_xeon', source: 'ai', params: {} },
  { type: 'spec_mismatch', level: 'warning', reason_key: 'ddr_mismatch', source: 'rule', params: { gens: 'DDR4 и DDR5' } },
  { type: 'spec_mismatch', level: 'danger', reason_key: 'gpu_nonexistent', source: 'rule', params: { model: 'GTX 3060', suggestion: 'RTX 3060' } },
]

function Block({ title, children }) {
  return (
    <Card>
      <h2 className="mb-4 text-h2">{title}</h2>
      {children}
    </Card>
  )
}

export default function UiPage() {
  const toast = useToast()
  const [modal, setModal] = useState(false)
  const [sheet, setSheet] = useState(false)
  const [tab, setTab] = useState('one')
  const [on, setOn] = useState(true)
  const [page, setPage] = useState(5)

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <h1 className="text-h1">Компоненты</h1>
      <Block title="Логотип и типографика">
        <div className="flex items-center gap-3"><LogoMark className="size-10" /><BrandName className="text-2xl" /></div>
        <p className="mt-4 text-h1">Заголовок 1</p>
        <p className="text-h2">Заголовок 2</p>
        <p className="text-h3">Заголовок 3</p>
        <p className="mt-2">Основной текст, узбекская латиница: Oʻzbekiston, gʻoya, oʻrta.</p>
        <p className="text-sm text-muted">Приглушённый текст, мелкий</p>
      </Block>
      <Block title="Цвета">
        <div className="grid grid-cols-3 gap-3 md:grid-cols-6 lg:grid-cols-9">
          {COLORS.map((c) => (
            <div key={c}>
              <div className="h-12 rounded-md border border-line" style={{ background: `var(--color-${c})` }} />
              <p className="mt-1 text-xs break-words text-muted">{c}</p>
            </div>
          ))}
        </div>
      </Block>
      <Block title="Кнопки">
        <div className="flex flex-wrap gap-3">
          <Button>Основная</Button>
          <Button variant="secondary">Второстепенная</Button>
          <Button variant="text">Текстовая</Button>
          <Button variant="danger">Опасная</Button>
          <Button disabled>Неактивная</Button>
          <Button size="sm">Маленькая</Button>
          <Button size="lg">Большая</Button>
        </div>
      </Block>
      <Block title="Поля">
        <div className="grid gap-4 md:grid-cols-2">
          <Input label="Поле ввода" placeholder="Подсказка внутри" hint="Пояснение под полем" />
          <Input label="С ошибкой" defaultValue="не почта" error="Введите адрес вида name@mail.uz" />
          <PasswordInput label="Пароль" defaultValue="sekret-123" />
          <Select label="Выпадающий список"><option>Первый</option><option>Второй</option></Select>
          <Checkbox label="Чекбокс" defaultChecked />
          <Switch label="Переключатель" checked={on} onChange={setOn} />
        </div>
      </Block>
      <Block title="Плашки">
        <div className="flex flex-wrap gap-2">
          {['neutral', 'primary', 'accent', 'success', 'info', 'warning', 'danger'].map((b) => <Badge key={b} tone={b}>{b}</Badge>)}
          <MarketLabel info={{ label: 'below', diff_pct: 8 }} />
          <MarketLabel info={{ label: 'at', diff_pct: 0 }} />
          <MarketLabel info={{ label: 'above', diff_pct: 12 }} />
        </div>
        <Flags flags={SAMPLE_FLAGS} className="mt-4 grid gap-1" />
      </Block>
      <Block title="Цена">
        <div className="flex flex-wrap gap-8">
          <Price price={120} currency="USD" usdRate={12700} rateDate="2026-11-01" />
          <Price price={1524000} currency="UZS" usdRate={12700} rateDate="2026-11-01" prefix="от " size="text-lg" />
          <Price price={120} currency="USD" />
        </div>
      </Block>
      <Block title="Вкладки и пагинация">
        <Tabs value={tab} onChange={setTab} tabs={[{ value: 'one', label: 'Первая' }, { value: 'two', label: 'Вторая' }, { value: 'three', label: 'Третья' }]} />
        <Pagination className="mt-4" page={page} pages={20} onChange={setPage} />
      </Block>
      <Block title="Окна и уведомления">
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => setModal(true)}>Модальное окно</Button>
          <Button variant="secondary" onClick={() => setSheet(true)}>Панель снизу</Button>
          <Button variant="secondary" onClick={() => toast('Изменения сохранены')}>Уведомление</Button>
          <Button variant="secondary" onClick={() => toast('Что-то пошло не так', 'danger')}>Ошибка</Button>
          <Dropdown align="left" trigger={({ toggle }) => <Button variant="secondary" onClick={toggle}>Меню <ChevronDown className="size-4" /></Button>}>
            <DropdownItem icon={Settings} selected>Настройки</DropdownItem>
            <DropdownItem icon={LogOut}>Выйти</DropdownItem>
          </Dropdown>
        </div>
        <Modal open={modal} onClose={() => setModal(false)} title="Модальное окно"
          footer={<><Button variant="secondary" onClick={() => setModal(false)}>Отмена</Button><Button onClick={() => setModal(false)}>Готово</Button></>}>
          <p className="text-sm text-muted">Закрывается кнопкой, кликом снаружи и клавишей Esc.</p>
        </Modal>
        <Sheet open={sheet} onClose={() => setSheet(false)} title="Панель снизу" footer={<Button className="w-full" onClick={() => setSheet(false)}>Готово</Button>}>
          <p className="text-sm text-muted">Так на телефоне открываются фильтры каталога.</p>
        </Sheet>
      </Block>
      <Block title="Скелетон и пустое состояние">
        <Skeleton className="mb-4 h-4 w-48" />
        <SkeletonCards count={3} />
        <EmptyState title="Ничего не найдено" hint="Попробуйте изменить запрос или фильтры."><Button variant="secondary">Сбросить</Button></EmptyState>
      </Block>
    </div>
  )
}
