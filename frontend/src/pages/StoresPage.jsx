import { useEffect, useState } from 'react'
import { BadgeCheck, Package, Store } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import StoreWhere from '../components/StoreWhere'
import { Badge, Breadcrumbs, Card, EmptyState, Select, SkeletonCards } from '../components/ui'
import { CITIES, cityParam } from '../config/cities'
import api from '../services/api'
import { useCity } from '../services/city.jsx'

// "Stores" (phase 12): partner shops of the city chosen in the header; Telegram channels are not stores
export default function StoresPage() {
  const { t } = useTranslation()
  const { city, setCity } = useCity()
  const [items, setItems] = useState(null)

  useEffect(() => {
    setItems(null)
    api.get('/catalog/stores', { params: { city: cityParam(city) } })
      .then((res) => setItems(res.data.items)).catch(() => setItems([]))
  }, [city])

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <Breadcrumbs items={[{ to: '/', label: t('catalog.home') }, { label: t('stores.title') }]} />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-h2 md:text-h1">{t('stores.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('stores.hint')}</p>
        </div>
        <Select label={t('nav.city')} value={city} onChange={(e) => setCity(e.target.value)} className="w-full sm:w-56">
          {CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
        </Select>
      </div>
      {!items ? <SkeletonCards className="grid gap-3 md:grid-cols-2 md:gap-4" count={4} /> : items.length === 0
        ? <EmptyState icon={Store} title={t('stores.empty')} hint={t('stores.emptyHint')} />
        : (
          <div className="grid gap-3 md:grid-cols-2 md:gap-4">
            {items.map((s) => (
              <Card key={s.id} className="flex min-w-0 flex-col">
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/store/${s.id}`} className="text-h3 break-words hover:text-primary hover:underline">{s.name}</Link>
                  {s.is_verified && <Badge tone="success"><BadgeCheck className="mr-1 inline size-3.5" aria-hidden />{t('store.verifiedShort')}</Badge>}
                </div>
                <StoreWhere store={s} className="mt-2" />
                {!s.address && <p className="mt-2 text-sm text-muted">{t(`cities.${s.city}`)} · {t('stores.noAddress')}</p>}
                <Link to={`/store/${s.id}`} className="mt-3 flex items-center gap-1.5 text-sm text-muted hover:text-primary">
                  <Package className="size-4" aria-hidden />{t('stores.inStock', { count: s.in_stock })}
                </Link>
              </Card>
            ))}
          </div>
        )}
    </div>
  )
}
