// Phase 14: photos of one item of the store — its own photos (the real item, used goods above all) and the photos of
// the model's card (one set for all stores). Used in the offer editor, after «Найти в каталоге» and from a row of
// «Мои товары». One uploader at a time, so Ctrl+V goes to the visible one.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Modal } from './overlays'
import PhotoUploader from './PhotoUploader'
import { Tabs } from './ui'

const USED = ['used', 'unknown', 'refurbished', 'for_parts']

export function OfferPhotos({ offer, onSaved }) {
  const { t } = useTranslation()
  const used = USED.includes(offer.condition)
  const [tab, setTab] = useState(used || offer.photos?.card ? 'offer' : 'card')
  return (
    <div className="grid gap-3">
      <Tabs label={t('photo.manage')} value={tab} onChange={setTab} tabs={[
        { value: 'offer', label: t('photo.offerTitle') }, { value: 'card', label: t('photo.cardTitle') }]} />
      {tab === 'offer'
        ? <PhotoUploader key="offer" ownerType="offer" ownerId={offer.id} onSaved={onSaved}
            hint={used ? t('photo.usedHint') : t('photo.offerHint')} />
        : <PhotoUploader key="card" ownerType="product" ownerId={offer.product_id} onSaved={onSaved} hint={t('photo.cardHint')} />}
    </div>
  )
}

export default function OfferPhotosModal({ offer, onClose, onSaved }) {
  const { t } = useTranslation()
  if (!offer) return null
  return (
    <Modal open onClose={onClose} title={`${t('photo.manage')}: ${offer.name}`} fullOnPhone>
      <OfferPhotos offer={offer} onSaved={onSaved} />
    </Modal>
  )
}
