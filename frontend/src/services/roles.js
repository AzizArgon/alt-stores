// Where each role belongs. One place for every redirect, so phase 12 adds the admin here as a third interface.
import { sellerUrl, storeUrl } from '../config/sites'

// The page a user lands on after logging in (or when opening a login page while logged in)
export function homeFor(user) {
  if (user?.role === 'seller') return sellerUrl()
  return storeUrl('/')
}

// Who may open /seller/...: a guest is sent to the seller login, a buyer sees "this is for sellers"
export function sellerGate(user) {
  if (!user) return 'login'
  return user.role === 'seller' ? 'allow' : 'notSeller'
}

// After a login or a registration: a guest sent from a cabinet page (seller) or from "Write to the seller" (buyer,
// /messages/...) returns there; anyone else goes to his own interface
export function returnTo(user, from) {
  const back = user?.role === 'seller' ? from?.startsWith('/seller') : from?.startsWith('/messages')
  return back ? from : homeFor(user)
}
