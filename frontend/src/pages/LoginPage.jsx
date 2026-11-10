import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, SocialButtons, SubmitButton, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput, SiteLink } from '../components/ui'
import { goTo, sellerUrl, storeUrl } from '../config/sites'
import { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { returnTo } from '../services/roles'

// `seller`: the cabinet's own login (/seller/login); after any login each role goes to its own interface
export default function LoginPage({ seller = false }) {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = {}
    const emailError = emailErrorKey(email)
    if (emailError) found.email = t(emailError)
    if (!password) found.password = t('errors.required')
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const user = await login(email, password)
      goTo(navigate, returnTo(user, location.state?.from))
    } catch (err) {
      const key = errorKey(err)
      const detail = err.response?.data?.detail  // a blocked user: {code: 'user_blocked', reason}
      setErrors({ [fieldOfError(key)]: t(key, typeof detail === 'object' ? detail : {}) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t(seller ? 'seller.loginTitle' : 'auth.loginTitle')} hint={t(seller ? 'seller.loginHint' : 'auth.loginHint')}>
      <SocialButtons />
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <Input label={t('auth.email')} type="email" autoComplete="email" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label={t('auth.password')} autoComplete="current-password" error={errors.password}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="mt-1">
          <ErrorText>{errors.form}</ErrorText>
          <SubmitButton busy={busy} busyText={t('auth.loading')}>{t('auth.submitLogin')}</SubmitButton>
        </div>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {t('auth.noAccount')}{' '}
        <Link to={seller ? '/seller/register' : '/register'} state={location.state} className="font-semibold text-primary hover:underline">{t('nav.register')}</Link>
      </p>
      <p className="mt-2 text-center text-sm text-muted">
        {t(seller ? 'seller.areYouBuyer' : 'seller.areYouSeller')}{' '}
        <SiteLink url={seller ? storeUrl('/login') : sellerUrl('/login')} className="font-semibold text-primary hover:underline">
          {t(seller ? 'seller.buyerLogin' : 'seller.sellerLogin')}
        </SiteLink>
      </p>
    </AuthCard>
  )
}
