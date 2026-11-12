// Phase 15: the interface language — ru (default), uz (Latin), en.
// The choice is kept in the browser and, for a logged-in user, in the profile (the same language on another device).
// First visit: the browser's language if it is uz or en, otherwise ru. Page addresses never change.
export const LANGS = ['ru', 'uz', 'en']
export const LANG_KEY = 'pc_market_lang'

const valid = (lng) => (LANGS.includes(lng) ? lng : null)

function stored() {
  try { return valid(localStorage.getItem(LANG_KEY)) } catch { return null }
}

// "uz-Latn-UZ" -> "uz"; the first of the browser's languages that we have (ru among them stops the search)
export function browserLang(languages = typeof navigator === 'undefined' ? [] : navigator.languages || [navigator.language]) {
  for (const l of languages || []) {
    const base = valid(String(l || '').toLowerCase().split('-')[0])
    if (base) return base
  }
  return 'ru'
}

// Tests run in Node, whose navigator says en-US: they keep the default ru
export const initialLang = () => stored() || (import.meta.env?.MODE === 'test' ? 'ru' : browserLang())

export function rememberLang(lng) {
  try { localStorage.setItem(LANG_KEY, lng) } catch { /* private mode: the language lives until the page closes */ }
}

// <html lang="…">: screen readers, hyphenation and the browser's translator read it
export function applyHtmlLang(lng) {
  if (typeof document !== 'undefined') document.documentElement.lang = lng
}

// Locale for Intl: "uz" is Uzbek Latin in every browser
export const intlLocale = (lng) => valid(lng) || 'ru'

// After login (or /auth/me): the profile's language wins (another device); a profile without one gets the current one
export function profileLang(userLang, current) {
  if (valid(userLang)) return userLang === current ? {} : { change: userLang }
  return { save: current }
}
