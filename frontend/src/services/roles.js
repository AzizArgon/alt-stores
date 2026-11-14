// Where each role belongs. One place for every redirect, so phase 12 adds the admin here as a third interface.
import { sellerUrl, storeUrl } from '../config/sites'

// The page a user lands on after logging in (or when opening a login page while logged in)
export function homeFor(user) {
  if (user?.role === 'admin') return '/admin'  // phase 13: the third interface
  if (user?.role === 'seller') return sellerUrl()
  return storeUrl('/')
}

// Who may open /seller/...: a guest is sent to the seller login, a buyer sees "this is for sellers"
export function sellerGate(user) {
  if (!user) return 'login'
  return user.role === 'seller' ? 'allow' : 'notSeller'
}

// Who may open /admin/... (phase 13): a guest goes to the admin login, anyone else sees "no access"
export function adminGate(user) {
  if (!user) return 'login'
  return user.role === 'admin' ? 'allow' : 'noAccess'
}

// Phase 16.3: one login for everyone. After a login, a registration or when a logged-in user opens /login, each
// role goes to its own section; a guest who was sent to the login from somewhere returns there if it is his part
// of the site: a seller — a cabinet page, an admin — an admin page, a buyer — any storefront page (a product,
// "Write to the seller", "Reserve" with ?reserve=..., "My reservations")
const inArea = (path, area) => new RegExp(`^/${area}(/|\\?|$)`).test(path)
const AUTH_PAGES = /^\/(login|register)(\/|\?|$)/

export function returnTo(user, from) {
  if (typeof from !== 'string' || !from.startsWith('/') || from.startsWith('//')) return homeFor(user)
  const area = inArea(from, 'seller') ? 'seller' : inArea(from, 'admin') ? 'admin' : 'store'
  if (user?.role === 'seller' || user?.role === 'admin') return area === user.role ? from : homeFor(user)
  return area === 'store' && !AUTH_PAGES.test(from) ? from : homeFor(user)
}

// The old login and register addresses (before phase 16.3) lead to the one login: where to and where to return after
export const OLD_AUTH = {
  '/seller/login': { to: '/login', from: '/seller' },
  '/seller/register': { to: '/register?role=seller', from: '/seller' },
  '/admin/login': { to: '/login', from: '/admin' },
}
export function oldAuthTarget(pathname, state) {
  const old = OLD_AUTH[pathname] || { to: '/login' }
  return { to: old.to, state: { from: state?.from || old.from } }
}

// /register?role=seller (the "For sellers" button) opens the registration with "I am a store" chosen
export const registerRole = (search) => {
  const role = new URLSearchParams(search).get('role')
  return role === 'seller' || role === 'buyer' ? role : ''
}

// The login link of a guest: remembers the page to come back to
export const loginState = (location) => ({ from: location.pathname + location.search })
