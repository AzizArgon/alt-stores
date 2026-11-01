import { UserCog } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, EmptyState } from '../components/ui'

// Placeholder: filled in phase B3
export default function ProfilePage() {
  const { t } = useTranslation()
  return (
    <div className="mx-auto grid max-w-2xl gap-6">
      <h1 className="text-h1">{t('nav.profile')}</h1>
      <Card><EmptyState icon={UserCog} title={t('profile.soonTitle')} hint={t('profile.soonHint')} /></Card>
    </div>
  )
}
