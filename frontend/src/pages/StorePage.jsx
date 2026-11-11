import { useEffect, useState } from 'react'
import { BadgeCheck, Phone, Send, Store } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { BranchesByCity } from '../components/BranchList'
import BuildTile from '../components/BuildTile'
import { WriteButton } from '../components/Chat'
import ProductTile from '../components/ProductTile'
import StoreWhere from '../components/StoreWhere'
import { Badge, Breadcrumbs, Button, Card, EmptyState, Pagination, Skeleton, SkeletonCards, Tabs } from '../components/ui'
import api from '../services/api'
import { useCity } from '../services/city.jsx'
import { useSpecDictionary } from '../services/specs'

const GROUPS = ['new', 'used']
const tgLink = (nick) => `https://t.me/${nick.replace(/^https?:\/\/t\.me\//, '').replace(/^@/, '')}`

// /store/<id> (phase 12): who the store is, where to go, its goods in stock (new / used) and its ready PCs
export default function StorePage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const dictionary = useSpecDictionary()
  const { city } = useCity()
  const [store, setStore] = useState(null)
  const [missing, setMissing] = useState(false)
  const [group, setGroup] = useState('new')
  const [page, setPage] = useState(1)
  const [goods, setGoods] = useState(null)

  useEffect(() => {
    setStore(null)
    setMissing(false)
    setPage(1)
    api.get(`/catalog/stores/${id}`).then((res) => {
      setStore(res.data)
      // A store with only used goods opens on them
      setGroup(res.data.counts.new === 0 && res.data.counts.used > 0 ? 'used' : 'new')
    }).catch(() => setMissing(true))
  }, [id])

  useEffect(() => {
    if (!store) return
    setGoods(null)
    api.get(`/catalog/stores/${id}/offers`, { params: { group, page } })
      .then((res) => setGoods(res.data)).catch(() => setGoods({ items: [], total: 0, page_size: 24 }))
  }, [id, store, group, page])

  if (missing) return <EmptyState icon={Store} title={t('stores.notFound')}><Button to="/stores">{t('stores.all')}</Button></EmptyState>
  if (!store) return <Skeleton className="h-64 w-full rounded-xl" />
  const pages = goods ? Math.max(1, Math.ceil(goods.total / goods.page_size)) : 1

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <Breadcrumbs items={[{ to: '/', label: t('catalog.home') }, { to: '/stores', label: t('stores.title') }, { label: store.name }]} />
      <Card className="grid gap-4 md:grid-cols-[minmax(0,1fr)_15rem]">
        <div className="min-w-0">
          <h1 className="text-h2 break-words md:text-h1">{store.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {store.is_verified && <Badge tone="success"><BadgeCheck className="mr-1 inline size-3.5" aria-hidden />{t('store.verifiedShort')}</Badge>}
            {(store.cities?.length ? store.cities : [store.city]).map((c) => <Badge key={c}>{t(`cities.${c}`)}</Badge>)}
            {store.is_demo && <Badge>{t('stores.demo')}</Badge>}
          </div>
          {store.branches?.length > 1 ? (
            // Phase 12.1: every branch by city, the chosen city first
            <div className="mt-4"><BranchesByCity branches={store.branches} city={city} /></div>
          ) : <StoreWhere store={store.branches?.[0] ? { ...store, ...store.branches[0], id: store.id } : store} route className="mt-4" />}
          {!store.address && !store.branches?.length && <p className="mt-4 text-sm text-muted">{t('stores.noAddress')}</p>}
        </div>
        <div className="flex flex-col gap-2">
          {store.phone && <Button href={`tel:${store.phone.replace(/[^\d+]/g, '')}`} variant="secondary"><Phone className="size-4" aria-hidden />{store.phone}</Button>}
          {store.telegram && <Button href={tgLink(store.telegram)} target="_blank" rel="noopener noreferrer" variant="secondary"><Send className="size-4" aria-hidden />Telegram</Button>}
          <WriteButton kind="store" id={store.id} store={store} size="md" className="w-full" />
        </div>
      </Card>

      <section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-h2">{t('stores.goods')}</h2>
          <Tabs label={t('stores.goods')} value={group} onChange={(g) => { setGroup(g); setPage(1) }}
            tabs={GROUPS.map((g) => ({ value: g, label: `${t(`stores.group.${g}`)} · ${store.counts[g]}` }))} />
        </div>
        {!goods ? <SkeletonCards className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4" /> : goods.items.length === 0
          ? <p className="mt-4 text-sm text-muted">{t('stores.noGoods')}</p>
          : (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
                {goods.items.map((item) => <ProductTile key={item.offer_id} item={item} usdRate={store.usd_rate} rateDate={store.usd_rate_date}
                  to={group === 'used' ? `/products/${item.id}?tab=used` : undefined} />)}
              </div>
              {pages > 1 && <Pagination page={page} pages={pages} onChange={setPage} className="mt-4" />}
            </>
          )}
      </section>

      {store.builds.length > 0 && (
        <section>
          <h2 className="text-h2">{t('stores.builds', { count: store.builds.length })}</h2>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 md:gap-4">
            {store.builds.map((item) => <BuildTile key={item.id} item={item} dictionary={dictionary} usdRate={store.usd_rate} rateDate={store.usd_rate_date} />)}
          </div>
        </section>
      )}
    </div>
  )
}
