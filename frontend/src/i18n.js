import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { BRAND } from './config/brand'
import en from './locales/en.json'
import ru from './locales/ru.json'
import uz from './locales/uz.json'
import { applyHtmlLang, initialLang, LANGS, rememberLang } from './services/lang'

// Phase 15: three languages; plural forms come from Intl.PluralRules (ru: one/few/many, uz and en: one/other)
i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, uz: { translation: uz }, en: { translation: en } },
  supportedLngs: LANGS,
  lng: initialLang(),
  fallbackLng: 'ru',
  interpolation: { escapeValue: false, defaultVariables: { brand: BRAND.name } },
})

applyHtmlLang(i18n.language)
i18n.on('languageChanged', (lng) => { applyHtmlLang(lng); rememberLang(lng) })

export default i18n
