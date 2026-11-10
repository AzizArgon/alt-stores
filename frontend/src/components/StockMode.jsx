import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import api, { errorKey } from '../services/api'
import { Modal, useToast } from './overlays'
import { Badge, Button, Card, Input } from './ui'

// Profile: the store's mode ("Только прайс" / "Учёт остатков", with a confirmation) and the "заканчивается" threshold
export default function StockModeBlock({ store, onChanged }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [ask, setAsk] = useState(null) // the preview before switching
  const [busy, setBusy] = useState(false)
  const [low, setLow] = useState(String(store.low_stock ?? 1))
  const on = store.stock_mode === 'stock'

  const open = async () => {
    try {
      setAsk((await api.get('/seller/stock/mode')).data)
    } catch (err) {
      toast(t(errorKey(err)), 'danger')
    }
  }
  const apply = async () => {
    setBusy(true)
    try {
      const res = (await api.post('/seller/stock/mode', { mode: on ? 'price' : 'stock' })).data
      if (res.mode === 'stock') {
        toast(t('warehouse.mode.on', res))
        if (res.unreserved.length) toast(t('warehouse.mode.onShort', { count: res.unreserved.length }), 'info')
      } else toast(t('warehouse.mode.off'))
      onChanged((await api.get('/stores/me')).data)
      setAsk(null)
    } catch (err) {
      toast(t(errorKey(err)), 'danger')
    } finally {
      setBusy(false)
    }
  }
  const saveLow = async () => {
    if (String(store.low_stock) === low) return
    try {
      await api.put('/seller/stock/settings', { low_stock: Math.max(0, Math.round(Number(low) || 0)) })
      onChanged((await api.get('/stores/me')).data)
      toast(t('cabinet.saved'))
    } catch (err) {
      toast(t(errorKey(err)), 'danger')
    }
  }

  return (
    <Card id="stock-mode" className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-h2">{t('warehouse.mode.title')}</h2>
        <Badge tone={on ? 'success' : 'neutral'}>{t(`warehouse.mode.${on ? 'stock' : 'price'}`)}</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {['price', 'stock'].map((m) => (
          <div key={m} className={`rounded-lg border p-3 ${store.stock_mode === m ? 'border-primary bg-primary-soft/40' : 'border-line'}`}>
            <p className="text-sm font-semibold">{t(`warehouse.mode.${m}`)}</p>
            <p className="mt-1 text-xs text-muted">{t(`warehouse.mode.${m}Hint`)}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-start gap-3">
        <Button variant={on ? 'secondary' : 'primary'} onClick={open}>{t(on ? 'warehouse.mode.turnOff' : 'warehouse.mode.turnOn')}</Button>
        {on && (
          <Input label={t('warehouse.mode.lowStock')} hint={t('warehouse.mode.lowStockHint')} type="number" min="0" max="1000" inputMode="numeric"
            value={low} onChange={(e) => setLow(e.target.value)} onBlur={saveLow} onKeyDown={(e) => e.key === 'Enter' && saveLow()} className="w-full sm:w-64" />
        )}
      </div>
      {ask && (
        <Modal open onClose={() => setAsk(null)} title={t(on ? 'warehouse.mode.offTitle' : 'warehouse.mode.confirmTitle')}
          footer={<><Button variant="secondary" onClick={() => setAsk(null)}>{t('branches.cancel')}</Button>
            <Button onClick={apply} disabled={busy}>{t(on ? 'warehouse.mode.turnOff' : 'warehouse.mode.turnOn')}</Button></>}>
          {on ? <p className="text-sm">{t('warehouse.mode.offText')}</p> : (
            <div className="grid gap-2 text-sm">
              <p>{t('warehouse.mode.confirmText', { rows: ask.rows })}</p>
              {ask.unknown > 0 && <p className="text-muted">{t('warehouse.mode.confirmUnknown', { count: ask.unknown })}</p>}
              {ask.reservations > 0 && <p className="text-muted">{t('warehouse.mode.confirmRes', { count: ask.reservations })}</p>}
            </div>
          )}
        </Modal>
      )}
    </Card>
  )
}
