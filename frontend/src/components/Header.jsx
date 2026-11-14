import { CalendarCheck, ChartLine, LayoutDashboard, LogOut, Menu, MessageSquare, Search, UserCog, UserRound, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { linkProps, sellerUrl } from '../config/sites'
import { useAuth } from '../services/auth.jsx'
import { useUnread } from '../services/chat'
import { useUnseenReservations } from '../services/reservations'
import { loginState } from '../services/roles'
import Logo, { BrandName } from './Logo'
import { Dropdown, DropdownItem, Sheet } from './overlays'
import LangSwitch from './LangSwitch'
import { NotificationBell } from './Notifications'
import SearchBar, { SEARCH_ROW_PATHS } from './SearchBar'
import { Button } from './ui'

// Phase 16.2: the header is light — sections only; the search and the city live in the search row under it
export const NAV_LINKS = [
  { to: '/catalog', label: 'nav.catalog' },
  { to: '/used', label: 'nav.used' },
  { to: '/builds', label: 'nav.builds' },
]
// "Цены на рынке" is a small chart icon in the header row, a labelled item in the phone menu
export const MARKET_LINK = { to: '/market', label: 'nav.market' }
const AVATAR_COLORS = ['#2546e8', '#0f7a55', '#a64b00', '#7c3aed', '#be185d', '#0b6a94']
const ICON_BUTTON = 'flex size-10 shrink-0 items-center justify-center rounded-md outline-none hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-primary'

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

function UserLinks({ logout, Item, unread, unseen }) {
  const { t } = useTranslation()
  return (
    <>
      <Item as={Link} to="/messages" icon={MessageSquare}>
        <span className="flex flex-1 items-center justify-between gap-2">{t('chat.title')}<UnreadBadge count={unread} /></span>
      </Item>
      <Item as={Link} to="/reservations" icon={CalendarCheck}>
        <span className="flex flex-1 items-center justify-between gap-2">{t('nav.reservations')}<UnreadBadge count={unseen} /></span>
      </Item>
      <Item as={Link} to="/profile" icon={UserCog}>{t('nav.profile')}</Item>
      <Item icon={LogOut} onClick={logout}>{t('nav.logout')}</Item>
    </>
  )
}

function UserMenu({ user, logout, unread, unseen }) {
  const { t } = useTranslation()
  return (
    <Dropdown trigger={({ open, toggle }) => (
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={t('nav.account')} title={user.email}
        className="relative rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
        <Avatar email={user.email} />
        <UnreadBadge count={unread + unseen} className="absolute -top-1 -right-1.5 ring-2 ring-surface" />
      </button>
    )}>
      <div className="flex items-center gap-2.5 border-b border-line p-2.5 pb-3 mb-1.5">
        <Avatar email={user.email} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold" title={user.email}>{user.email}</p>
          <p className="text-xs text-muted">{t(`roles.${user.role}`)}</p>
        </div>
      </div>
      <UserLinks logout={logout} Item={DropdownItem} unread={unread} unseen={unseen} />
    </Dropdown>
  )
}

// Phone and tablet menu: everything the desktop header shows in its row
function MobileMenu({ open, onClose, user, logout, unread, unseen }) {
  const { t } = useTranslation()
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
        <Link to={MARKET_LINK.to} className={`${row} gap-2`}><ChartLine className="size-4 text-muted" aria-hidden />{t(MARKET_LINK.label)}</Link>
        {user && <div className="my-2 border-t border-line" />}
        {user?.role === 'seller'
          ? <Button {...linkProps(sellerUrl())} className="mt-1 w-full"><LayoutDashboard className="size-4" aria-hidden />{t('nav.myCabinet')}</Button>
          : user && <UserLinks logout={logout} Item={DropdownItem} unread={unread} unseen={unseen} />}
      </nav>
      <p className="mt-4 mb-1.5 text-sm font-medium">{t('lang.label')}</p>
      <LangSwitch wide />
      {!user && (
        <div className="mt-5 grid" onClick={(e) => e.target.closest('a') && onClose()}>
          <SignInButton />
        </div>
      )}
    </Sheet>
  )
}

// Phase 16.3: one button for guests — the one login (registration is a tab there); the page is kept to come back to
function SignInButton({ size = 'md', className = '' }) {
  const { t } = useTranslation()
  const location = useLocation()
  return (
    <Button to="/login" state={loginState(location)} variant="secondary" size={size} className={className}>
      <UserRound className="size-4" aria-hidden />{t('nav.signIn')}
    </Button>
  )
}

// A small chart icon with a tooltip on hover/focus (the label is in the phone menu)
function MarketIcon() {
  const { t } = useTranslation()
  return (
    <NavLink to={MARKET_LINK.to} aria-label={t(MARKET_LINK.label)} title={t(MARKET_LINK.label)}
      className={({ isActive }) => `group relative ${ICON_BUTTON} ${isActive ? 'text-primary' : 'text-ink'}`}>
      <ChartLine className="size-5" aria-hidden />
      <span role="tooltip" className="pointer-events-none absolute top-full left-1/2 z-40 mt-1.5 hidden -translate-x-1/2 rounded-md bg-ink px-2 py-1 text-xs font-medium whitespace-nowrap text-white shadow-pop group-hover:block group-focus-visible:block">
        {t(MARKET_LINK.label)}
      </span>
    </NavLink>
  )
}

export default function Header() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  // The magnifier's row belongs to the page it was opened on: another page starts with it closed
  const [searchOn, setSearchOn] = useState(null)
  const searchOpen = searchOn === pathname
  const setSearchOpen = (open) => setSearchOn(open ? pathname : null)
  const unread = useUnread(!!user && user.role !== 'seller')
  const unseen = useUnseenReservations(!!user && user.role !== 'seller')
  // Home and catalog have the search row under the header; on the other pages a magnifier opens the same row
  const searchRow = SEARCH_ROW_PATHS.includes(pathname)

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
      <div className="mx-auto max-w-7xl px-4 md:px-6">
        <div className="flex h-16 items-center gap-1.5 md:gap-3">
          <button type="button" onClick={() => setMenuOpen(true)} aria-label={t('nav.menu')} className={`-ml-2 ${ICON_BUTTON} lg:hidden`}>
            <Menu className="size-6" aria-hidden />
          </button>
          <Logo />
          <nav className="ml-4 hidden min-w-0 items-center gap-1 lg:flex">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} end className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap hover:bg-surface-2 ${isActive ? 'text-primary' : 'text-ink'}`}>
                {t(link.label)}
              </NavLink>
            ))}
          </nav>
          <div className="flex-1" />
          {!searchRow && (
            <button type="button" onClick={() => setSearchOpen(!searchOpen)} aria-expanded={searchOpen}
              aria-label={searchOpen ? t('search.close') : t('search.open')} title={searchOpen ? t('search.close') : t('search.open')} className={ICON_BUTTON}>
              {searchOpen ? <X className="size-5" aria-hidden /> : <Search className="size-5" aria-hidden />}
            </button>
          )}
          <div className="hidden lg:block"><MarketIcon /></div>
          <LangSwitch className="hidden md:flex" />
          {/* A seller works in the cabinet: on the storefront he has only the way back there */}
          {user?.role === 'seller' ? (
            <Button {...linkProps(sellerUrl())} size="sm" className="shrink-0">
              <LayoutDashboard className="size-4" aria-hidden /><span className="max-sm:sr-only">{t('nav.myCabinet')}</span>
            </Button>
          ) : user ? (
            <div className="flex shrink-0 items-center gap-1">
              {user.role === 'buyer' && <NotificationBell allPath="/notifications" />}
              <UserMenu user={user} logout={logout} unread={unread} unseen={unseen} />
            </div>
          ) : (
            <SignInButton size="sm" className="shrink-0" />
          )}
        </div>
        {!searchRow && searchOpen && <div className="pb-3"><SearchBar autoFocus /></div>}
      </div>
      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={user} logout={logout} unread={unread} unseen={unseen} />
    </header>
  )
}
