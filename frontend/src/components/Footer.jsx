import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { BRAND } from '../config/brand'
import { useAuth } from '../services/auth.jsx'
import { BrandName } from './Logo'

export default function Footer() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const link = 'text-muted hover:text-ink'
  return (
    <footer className="mt-10 border-t border-line bg-surface">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 text-sm md:grid-cols-[1fr_auto] md:gap-12 md:px-6">
        <div>
          <BrandName className="text-lg" />
          <p className="mt-2 max-w-md text-muted">{t('footer.about')}</p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 md:grid md:content-start md:gap-2">
          <Link to="/catalog" className={link}>{t('nav.catalog')}</Link>
          <Link to="/market" className={link}>{t('nav.market')}</Link>
          <Link to={user?.role === 'seller' ? '/seller' : '/register?role=seller'} className={link}>{t('footer.forSellers')}</Link>
          <a href={BRAND.githubUrl} target="_blank" rel="noreferrer" className={link}>{t('footer.github')}</a>
        </nav>
        <p className="text-xs text-faint md:col-span-2">{t('footer.thesis')}</p>
      </div>
    </footer>
  )
}
