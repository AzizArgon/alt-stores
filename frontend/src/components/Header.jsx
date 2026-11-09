import { ChevronDown, LayoutDashboard, LogOut, MapPin, Menu, MessageSquare, Search, UserCog } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { CITIES } from '../config/cities'
import { linkProps, sellerUrl } from '../config/sites'
import { useAuth } from '../services/auth.jsx'
import { useUnread } from '../services/chat'
import { useCity } from '../services/city.jsx'
import Logo, { BrandName } from './Logo'
import { Dropdown, DropdownItem, Sheet } from './overlays'
import { Button, Select, inputClass } from './ui'

const SEARCH_DELAY_MS = 300
const NAV_LINKS = [
  { to: '/catalog', label: 'nav.catalog' },
  { to: '/used', label: 'nav.used' },
  { to: '/builds', label: 'nav.builds' },
  { to: '/market', label: 'nav.market' },
]
const AVATAR_COLORS = ['#2546e8', '#0f7a55', '#a64b00', '#7c3aed', '#be185d', '#0b6a94']

// In the catalog the search works as you type (through the address); on other pages Enter opens the catalog
function HeaderSearch({ className = '' }) {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const onCatalog = location.pathname === '/catalog'
  const urlQuery = onCatalog ? new URLSearchParams(location.search).get('q') || '' : null
  const [value, setValue] = useState(urlQuery || '')

  const openResults = (text, replace) => {
    const next = new URLSearchParams(onCatalog ? location.search : '')
    if (text) next.set('q', text)
    else next.delete('q')
    next.delete('page')
    navigate({ pathname: '/catalog', search: next.toString() }, { replace })
  }

  // The address changed from outside (logo, "back"): the field follows it
  useEffect(() => {
    if (urlQuery !== null && urlQuery !== value.trim()) setValue(urlQuery)
  }, [urlQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!onCatalog || value.trim() === urlQuery) return
    const timer = setTimeout(() => openResults(value.trim(), true), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [value]) // eslint-disable-line react-hooks/exhaustive-deps

  const onSubmit = (e) => {
    e.preventDefault()
    openResults(value.trim(), onCatalog)
  }

  return (
    <form role="search" onSubmit={onSubmit} className={`relative min-w-0 ${className}`}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input type="search" enterKeyHint="search" value={value} onChange={(e) => setValue(e.target.value)}
        placeholder={t('catalog.searchPlaceholder')} aria-label={t('catalog.searchPlaceholder')}
        className={`${inputClass} bg-surface-2 pl-9 hover:border-line-strong focus:bg-surface`} />
    </form>
  )
}

export function CityMenu({ className = 'max-w-48 px-2 hover:bg-surface-2' }) {
  const { t } = useTranslation()
  const { city, setCity } = useCity()
  return (
    <Dropdown align="left" panelClassName="max-h-96 w-56 overflow-y-auto" trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={t('nav.city')} title={t('nav.city')}
        className={`flex min-h-11 items-center gap-1.5 rounded-md text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-primary ${className}`}>
        <MapPin className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="truncate">{t(`cities.${city}`)}</span>
        <ChevronDown className="size-4 shrink-0 text-muted" aria-hidden />
      </button>
    )}>
      {CITIES.map((c) => (
        <DropdownItem key={c} selected={c === city} onClick={() => setCity(c)}>{t(`cities.${c}`)}</DropdownItem>
      ))}
    </Dropdown>
  )
}

export function Avatar({ email, className = 'size-10 text-base' }) {
  const code = [...email].reduce((sum, ch) => sum + ch.codePointAt(0), 0)
  return (
    <span aria-hidden style={{ background: AVATAR_COLORS[code % AVATAR_COLORS.length] }}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold text-white uppercase ${className}`}>
      {email[0]}
    </span>
  )
}

// A red counter of unread messages (on the avatar, in the menu, in the cabinet sections)
export function UnreadBadge({ count, className = '' }) {
  const { t } = useTranslation()
  if (!count) return null
  return (
    <span aria-label={t('chat.unread', { count })} title={t('chat.unread', { count })}
      className={`flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1.5 text-[11px] font-semibold text-white ${className}`}>
      {count > 99 ? '99+' : count}
    </span>
  )
}

function UserLinks({ logout, Item, unread }) {
  const { t } = useTranslation()
  return (
    <>
      <Item as={Link} to="/messages" icon={MessageSquare}>
        <span className="flex flex-1 items-center justify-between gap-2">{t('chat.title')}<UnreadBadge count={unread} /></span>
      </Item>
      <Item as={Link} to="/profile" icon={UserCog}>{t('nav.profile')}</Item>
      <Item icon={LogOut} onClick={logout}>{t('nav.logout')}</Item>
    </>
  )
}

function UserMenu({ user, logout, unread }) {
  const { t } = useTranslation()
  return (
    <Dropdown trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={t('nav.account')} title={user.email}
        className="relative rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
        <Avatar email={user.email} />
        <UnreadBadge count={unread} className="absolute -top-1 -right-1.5 ring-2 ring-surface" />
      </button>
    )}>
      <div className="flex items-center gap-2.5 border-b border-line p-2.5 pb-3 mb-1.5">
        <Avatar email={user.email} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold" title={user.email}>{user.email}</p>
          <p className="text-xs text-muted">{t(`roles.${user.role}`)}</p>
        </div>
      </div>
      <UserLinks logout={logout} Item={DropdownItem} unread={unread} />
    </Dropdown>
  )
}

// Phone and tablet menu: everything the desktop header shows in its row
function MobileMenu({ open, onClose, user, logout, unread }) {
  const { t } = useTranslation()
  const { city, setCity } = useCity()
  const row = 'flex min-h-11 items-center rounded-md px-2.5 text-sm font-medium hover:bg-surface-2'
  return (
    <Sheet open={open} onClose={onClose} side="left" title={<BrandName />}>
      {user && (
        <div className="mb-3 flex items-center gap-2.5 border-b border-line pb-4">
          <Avatar email={user.email} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{user.email}</p>
            <p className="text-xs text-muted">{t(`roles.${user.role}`)}</p>
          </div>
        </div>
      )}
      <nav onClick={(e) => e.target.closest('a,button') && onClose()} className="grid gap-0.5">
        {NAV_LINKS.map((link) => <Link key={link.to} to={link.to} className={row}>{t(link.label)}</Link>)}
        {user && <div className="my-2 border-t border-line" />}
        {user?.role === 'seller'
          ? <Button {...linkProps(sellerUrl())} className="mt-1 w-full"><LayoutDashboard className="size-4" aria-hidden />{t('nav.myCabinet')}</Button>
          : user && <UserLinks logout={logout} Item={DropdownItem} unread={unread} />}
      </nav>
      <Select label={t('nav.city')} className="mt-4" value={city} onChange={(e) => setCity(e.target.value)}>
        {CITIES.map((c) => <option key={c} value={c}>{t(`cities.${c}`)}</option>)}
      </Select>
      {!user && (
        <div className="mt-5 grid gap-2" onClick={(e) => e.target.closest('a') && onClose()}>
          <Button to="/login" variant="secondary">{t('nav.login')}</Button>
          <Button to="/register">{t('nav.register')}</Button>
        </div>
      )}
    </Sheet>
  )
}

export default function Header() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const unread = useUnread(!!user && user.role !== 'seller')

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface">
      <div className="mx-auto max-w-7xl px-4 md:px-6">
        <div className="flex h-16 items-center gap-2 md:gap-3">
          <button type="button" onClick={() => setMenuOpen(true)} aria-label={t('nav.menu')}
            className="-ml-2 flex size-10 shrink-0 items-center justify-center rounded-md outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary xl:hidden">
            <Menu className="size-6" aria-hidden />
          </button>
          <Logo />
          <div className="hidden md:block"><CityMenu /></div>
          <HeaderSearch className="hidden flex-1 md:block" />
          <div className="flex-1 md:hidden" />
          <nav className="hidden shrink-0 items-center gap-1 xl:flex">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} end className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap hover:bg-surface-2 ${isActive ? 'text-primary' : 'text-ink'}`}>
                {t(link.label)}
              </NavLink>
            ))}
          </nav>
          {/* A seller works in the cabinet: on the storefront he has only the way back there */}
          {user?.role === 'seller' ? (
            <Button {...linkProps(sellerUrl())} size="sm" className="shrink-0">
              <LayoutDashboard className="size-4" aria-hidden />{t('nav.myCabinet')}
            </Button>
          ) : user ? <UserMenu user={user} logout={logout} unread={unread} /> : (
            <div className="flex shrink-0 items-center gap-2">
              <Button to="/login" variant="secondary" size="sm">{t('nav.login')}</Button>
              <span className="hidden sm:block"><Button to="/register" size="sm">{t('nav.register')}</Button></span>
            </div>
          )}
        </div>
        {/* The home page has its own big search: the phone row would repeat it */}
        {pathname !== '/' && <div className="pb-3 md:hidden"><HeaderSearch /></div>}
      </div>
      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={user} logout={logout} unread={unread} />
    </header>
  )
}
