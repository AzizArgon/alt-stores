// The storefront and the seller cabinet are two views of one site. Links between them go only through these
// helpers, so the cabinet can later move to its own subdomain (seller.…) by setting VITE_SELLER_URL and
// VITE_STORE_URL at build time (docs/deploy.md). Empty = the same site, the usual in-app links.
const trim = (url) => (url || '').replace(/\/+$/, '')

export const SELLER_BASE = trim(import.meta.env.VITE_SELLER_URL)
export const STORE_BASE = trim(import.meta.env.VITE_STORE_URL)

// All cabinet addresses live under /seller (also on a subdomain): sellerUrl('/login') → "/seller/login"
export const sellerUrl = (path = '') => `${SELLER_BASE}/seller${path}`
export const storeUrl = (path = '/') => `${STORE_BASE}${path}`

// A link to the other site: through the router when it is the same site, a plain link to another address
export const isExternal = (url) => /^https?:\/\//.test(url)
export const linkProps = (url) => (isExternal(url) ? { href: url } : { to: url })
export const goTo = (navigate, url) => (isExternal(url) ? window.location.assign(url) : navigate(url))
