import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { BRAND } from '../config/brand'
import { BrandName } from './Logo'

// Phase 16.2: three columns of links; the description is short, the thesis line sits with the copyright
export const FOOTER_COLUMNS = [
  { title: 'footer.buyers', links: [
    { to: '/catalog', label: 'nav.catalog' },
    { to: '/used', label: 'nav.used' },
    { to: '/builds', label: 'nav.builds' },
    { to: '/stores', label: 'nav.stores' },
    { to: '/reservations', label: 'nav.reservations' },
    { to: '/messages', label: 'chat.title' },
  ] },
  { title: 'footer.sellers', links: [
    { to: '/for-sellers', label: 'footer.forSellers' },
    { to: '/login', label: 'footer.cabinetLogin' },
  ] },
  { title: 'footer.project', links: [
    { to: '/market', label: 'nav.market' },
    { href: BRAND.githubUrl, label: 'footer.github' },
  ] },
]

export default function Footer() {
  const { t } = useTranslation()
  const link = 'text-muted hover:text-ink'
  return (
    <footer className="mt-8 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto grid max-w-7xl gap-4 px-4 pt-5 pb-3 text-sm md:grid-cols-[minmax(0,1.2fr)_minmax(0,1.6fr)_repeat(2,minmax(0,1fr))] md:gap-8 md:px-6">
        <div className="max-md:col-span-full">
          <BrandName className="text-base" />
          <p className="mt-1 max-w-xs text-xs text-muted">{t('footer.about')}</p>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-[minmax(0,2fr)_repeat(2,minmax(0,1fr))] md:contents">
          {FOOTER_COLUMNS.map((col) => (
            <nav key={col.title} aria-label={t(col.title)} className={col.links.length > 3 ? 'max-sm:col-span-2' : ''}>
              <p className="mb-1.5 text-xs font-semibold tracking-wide text-faint uppercase">{t(col.title)}</p>
              <ul className={`grid gap-x-6 gap-y-1 ${col.links.length > 3 ? 'grid-cols-2' : ''}`}>
                {col.links.map((l) => (
                  <li key={l.label}>
                    {l.href
                      ? <a href={l.href} target="_blank" rel="noreferrer" className={link}>{t(l.label)}</a>
                      : <Link to={l.to} className={link}>{t(l.label)}</Link>}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
      </div>
      <p className="mx-auto max-w-7xl border-t border-line px-4 py-2.5 text-xs text-faint md:px-6">
        © {new Date().getFullYear()} {BRAND.name} · {t('footer.thesis')}
      </p>
    </footer>
  )
}
