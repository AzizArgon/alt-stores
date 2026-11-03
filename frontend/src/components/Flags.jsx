import { Info, OctagonAlert, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const FLAG_STYLE = {
  info: 'border-info-line bg-info-soft text-info',
  warning: 'border-warning-line bg-warning-soft text-warning',
  danger: 'border-danger-line bg-danger-soft text-danger',
}
const FLAG_ICON = { info: Info, warning: TriangleAlert, danger: OctagonAlert }

// Anti-Fraud badges: the server sends a reason key + params, the soft text is in the translations
export default function Flags({ flags, className = 'mt-1 grid gap-1 px-1.5' }) {
  const { t } = useTranslation()
  if (!flags?.length) return null
  return (
    <div className={className}>
      {flags.map((f) => {
        const Icon = FLAG_ICON[f.level]
        return (
          <p key={`${f.type}-${f.reason_key}-${f.params?.component || ''}`} className={`flex gap-1.5 rounded-md border px-2 py-1 text-xs ${FLAG_STYLE[f.level]}`}>
            <Icon className="mt-px size-3.5 shrink-0" aria-hidden />
            <span>
              {f.params?.component && <span className="break-words">{f.params.component}: </span>}
              <span className="font-semibold">{t(`flags.type.${f.type}`)}</span>
              {f.source === 'ai' && <span className="opacity-70"> ({t('flags.ai')})</span>}
              {' — '}{t(`flags.reason.${f.reason_key}`, f.params)}
            </span>
          </p>
        )
      })}
    </div>
  )
}
