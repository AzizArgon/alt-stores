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

// After a login or a registration: a guest sent from a cabinet page (seller), from "Write to the seller" (buyer,
// /messages/...), from "Reserve" (a page with ?reserve=..., the form opens again) or from "My reservations"
// returns there; anyone else goes to his own interface
export function returnTo(user, from) {
  const buyerBack = (p) => p?.startsWith('/messages') || p?.startsWith('/reservations') || /[?&]reserve=/.test(p || '')
  const back = user?.role === 'seller' ? from?.startsWith('/seller')
    : user?.role === 'admin' ? from?.startsWith('/admin') : buyerBack(from)
  return back ? from : homeFor(user)
}

// The admin entrance (/admin/login) for anyone: an admin logs in there; a seller or a buyer (the server answers
// "not_admin" — the password was right) is logged in the usual way and goes to his own section. The server still
// gives the /admin data only to an admin.
export async function loginAtAdminDoor(adminLogin, login, email, password) {
  try {
    return await adminLogin(email, password)
  } catch (err) {
    if (err.response?.data?.detail?.code !== 'not_admin') throw err
    return login(email, password)
  }
}
