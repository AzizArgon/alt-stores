import { Clock, MapPin, Navigation } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { mapsLink, routeLink } from '../config/maps'
import { Button } from './ui'

const external = { target: '_blank', rel: 'noopener noreferrer' }

// The store name as a link to its page /store/<id> (phase 12); a Telegram channel is not a store: plain text
export function StoreName({ store, className = '' }) {
  if (!store) return null
  if (store.kind === 'telegram' || !store.id) return <span className={className}>{store.name}</span>
  return <Link to={`/store/${store.id}`} className={`hover:text-primary hover:underline ${className}`}>{store.name}</Link>
}

// "Open in Yandex Maps" (the store's link or a search of its address) and, when asked, "Route"
export function MapButtons({ store, route = false, size = 'sm', className = '' }) {
  const { t } = useTranslation()
  const city = store?.city ? t(`cities.${store.city}`) : ''
  const open = mapsLink(store, city)
  if (!open) return null
  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      <Button href={open} {...external} size={size} variant="secondary"><MapPin className="size-4" aria-hidden />{t('store.openMap')}</Button>
      {route && <Button href={routeLink(store, city)} {...external} size={size} variant="secondary"><Navigation className="size-4" aria-hidden />{t('store.route')}</Button>}
    </div>
  )
}

// Address, opening hours and the map button: where to go for the item
export default function StoreWhere({ store, route = false, buttons = true, className = '' }) {
  const { t } = useTranslation()
  if (!store || store.kind === 'telegram' || (!store.address && !store.hours)) return null
  return (
    <div className={`text-sm ${className}`}>
      {store.address && (
        <p className="flex gap-1.5 break-words"><MapPin className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />
          <span>{[store.city && t(`cities.${store.city}`), store.district, store.address].filter(Boolean).join(', ')}</span></p>
      )}
      {store.hours && (
        <p className="mt-1 flex gap-1.5 text-muted"><Clock className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />{store.hours}</p>
      )}
      {buttons && <MapButtons store={store} route={route} className="mt-2" />}
    </div>
  )
}
