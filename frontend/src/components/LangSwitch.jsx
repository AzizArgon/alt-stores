import { useTranslation } from 'react-i18next'
import { useAuth } from '../services/auth.jsx'
import { LANGS } from '../services/lang'

// Phase 15: "RU · UZ · EN" — a short choice in the headers of the storefront, the cabinet and the admin.
// `wide`: full-width buttons for a phone menu (the mobile sheet, the account menu)
export default function LangSwitch({ wide = false, className = '' }) {
  const { t, i18n } = useTranslation()
  const { setLang } = useAuth()
  return (
    <div role="group" aria-label={t('lang.label')}
      className={`flex shrink-0 items-center rounded-md border border-line bg-surface p-0.5 ${wide ? 'w-full' : ''} ${className}`}>
      {LANGS.map((lng) => {
        const active = i18n.language === lng
        return (
          <button key={lng} type="button" lang={lng} aria-pressed={active} title={t(`lang.names.${lng}`)}
            onClick={() => setLang(lng)}
            className={`min-h-8 rounded px-2 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-primary ${wide ? 'min-h-10 flex-1 text-sm' : ''} ${active ? 'bg-primary text-white' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
            {lng.toUpperCase()}
          </button>
        )
      })}
    </div>
  )
}
