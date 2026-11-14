import { createContext, useContext, useEffect, useState } from 'react'
import i18n from '../i18n'
import api, { TOKEN_KEY } from './api'
import { LANGS, profileLang } from './lang'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => !!localStorage.getItem(TOKEN_KEY))

  // Restore session from a saved token
  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return
    api.get('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  // Phase 15: the profile keeps the language — it wins on login (another device); a profile without one gets this one
  useEffect(() => {
    if (!user) return
    const step = profileLang(user.lang, i18n.language)
    if (step.change) i18n.changeLanguage(step.change)
    if (step.save) api.put('/auth/me/lang', { lang: step.save }).catch(() => {})
  }, [user])

  const saveSession = (data) => {
    localStorage.setItem(TOKEN_KEY, data.access_token)
    setUser(data.user)
    return data.user
  }

  // The language switch: the browser remembers it (i18n.js), the profile too when logged in
  const setLang = (lng) => {
    if (!LANGS.includes(lng)) return
    i18n.changeLanguage(lng)
    if (user) {
      setUser((u) => ({ ...u, lang: lng }))
      api.put('/auth/me/lang', { lang: lng }).catch(() => {})
    }
  }

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password })
    return saveSession(res.data)
  }

  const register = async (email, password, role, inviteCode = '') => {
    const res = await api.post('/auth/register', { email, password, role, invite_code: inviteCode })
    return saveSession(res.data)
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setLang }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
