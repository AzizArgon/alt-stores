import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorText, SocialButtons, SubmitButton, emailErrorKey, fieldOfError } from '../components/AuthForm'
import { Input, PasswordInput, SiteLink } from '../components/ui'
import { goTo, sellerUrl, storeUrl } from '../config/sites'
import api, { errorKey } from '../services/api'
import { useAuth } from '../services/auth.jsx'
import { homeFor } from '../services/roles'

// The storefront registers buyers, the cabinet (/seller/register) registers stores
export default function RegisterPage({ seller = false }) {
  const { t } = useTranslation()
  const { register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const role = seller ? 'seller' : 'buyer'
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [invite, setInvite] = useState('')
  // On the public demo sellers register only with an invite code
  const [inviteRequired, setInviteRequired] = useState(false)

  useEffect(() => {
    api.get('/auth/options').then((res) => setInviteRequired(res.data.seller_invite_required)).catch(() => {})
  }, [])

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = {}
    const emailError = emailErrorKey(email)
    if (emailError) found.email = t(emailError)
    // Same limits as the backend (bcrypt allows max 72 bytes)
    if (password.length < 8 || password.length > 72) found.password = t('errors.passwordLength')
    if (password !== confirm) found.confirm = t('errors.passwordMismatch')
    if (role === 'seller' && inviteRequired && !invite.trim()) found.invite = t('errors.required')
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const user = await register(email, password, role, invite)
      const from = location.state?.from
      goTo(navigate, user.role !== 'seller' && from?.startsWith('/messages') ? from : homeFor(user))
    } catch (err) {
      const key = errorKey(err)
      setErrors({ [fieldOfError(key)]: t(key) })
    } finally {
      setBusy(false)
    }
  }

  // The old address of seller registration ("/register?role=seller") leads to the cabinet's own page
  if (!seller && new URLSearchParams(location.search).get('role') === 'seller') {
    const url = sellerUrl('/register')
    if (url.startsWith('/')) return <Navigate to={url} replace />
    window.location.replace(url)
    return null
  }

  return (
    <AuthCard title={t(seller ? 'seller.registerTitle' : 'auth.registerTitle')} hint={t(seller ? 'seller.registerHint' : 'auth.registerHint')}>
      <SocialButtons />
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
        <Input label={t('auth.email')} type="email" autoComplete="email" error={errors.email}
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput label={t('auth.password')} autoComplete="new-password" error={errors.password} hint={t('errors.passwordLength')}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <PasswordInput label={t('auth.passwordConfirm')} autoComplete="new-password" error={errors.confirm}
          value={confirm} onChange={(e) => setConfirm(e.target.value)} />

        {role === 'seller' && inviteRequired && (
          <Input label={t('auth.inviteCode')} autoComplete="off" error={errors.invite} hint={t('auth.inviteHint')}
            value={invite} onChange={(e) => setInvite(e.target.value)} />
        )}

        <div className="mt-1">
          <ErrorText>{errors.form}</ErrorText>
          <SubmitButton busy={busy} busyText={t('auth.loading')}>{t('auth.submitRegister')}</SubmitButton>
        </div>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        {t('auth.haveAccount')}{' '}
        <Link to={seller ? '/seller/login' : '/login'} state={location.state} className="font-semibold text-primary hover:underline">{t('nav.login')}</Link>
      </p>
      <p className="mt-2 text-center text-sm text-muted">
        {t(seller ? 'seller.areYouBuyer' : 'seller.areYouSeller')}{' '}
        <SiteLink url={seller ? storeUrl('/register') : sellerUrl('/register')} className="font-semibold text-primary hover:underline">
          {t(seller ? 'seller.buyerRegister' : 'seller.sellerRegister')}
        </SiteLink>
      </p>
    </AuthCard>
  )
}
