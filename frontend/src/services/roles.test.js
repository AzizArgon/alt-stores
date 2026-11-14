import { describe, expect, it } from 'vitest'
import { OLD_AUTH, adminGate, homeFor, loginState, oldAuthTarget, registerRole, returnTo, sellerGate } from './roles'

const seller = { email: 'demo1@example.com', role: 'seller' }
const buyer = { email: 'buyer@example.com', role: 'buyer' }

describe('after login each role goes to its own interface', () => {
  it('seller → cabinet overview', () => expect(homeFor(seller)).toBe('/seller'))
  it('buyer → storefront', () => expect(homeFor(buyer)).toBe('/'))
  it('a seller on the usual /login is sent to the cabinet too (same rule)', () => expect(homeFor(seller)).toMatch(/^\/seller/))
})

describe('who may open /seller/...', () => {
  it('seller → the cabinet', () => expect(sellerGate(seller)).toBe('allow'))
  it('buyer → "this section is for sellers"', () => expect(sellerGate(buyer)).toBe('notSeller'))
  it('guest → seller login', () => expect(sellerGate(null)).toBe('login'))
})

describe('who may open /admin/... (phase 13)', () => {
  const admin = { email: 'admin@example.com', role: 'admin' }
  it('admin → the admin panel', () => expect(adminGate(admin)).toBe('allow'))
  it('seller and buyer → "no access"', () => {
    expect(adminGate(seller)).toBe('noAccess')
    expect(adminGate(buyer)).toBe('noAccess')
  })
  it('guest → admin login', () => expect(adminGate(null)).toBe('login'))
  it('admin lands on /admin and returns there after a login', () => {
    expect(homeFor(admin)).toBe('/admin')
    expect(returnTo(admin, '/admin/flags')).toBe('/admin/flags')
    expect(returnTo(seller, '/admin/flags')).toBe('/seller')
  })
})

describe('one login for everyone (phase 16.3)', () => {
  const admin = { email: 'admin@example.com', role: 'admin' }

  it('the role is not chosen: after /login each role goes to its own section', () => {
    expect(returnTo(seller, undefined)).toBe('/seller')
    expect(returnTo(buyer, undefined)).toBe('/')
    expect(returnTo(admin, undefined)).toBe('/admin')
  })

  it('a buyer returns to the storefront page he came from (any page, not only messages and reservations)', () => {
    expect(returnTo(buyer, '/products/42')).toBe('/products/42')
    expect(returnTo(buyer, '/catalog?category=cpu')).toBe('/catalog?category=cpu')
    expect(returnTo(buyer, '/messages/new?offer=5')).toBe('/messages/new?offer=5')
    expect(returnTo(buyer, '/products/7?reserve=offer-3')).toBe('/products/7?reserve=offer-3')
  })

  it('nobody returns to a part of the site that is not his, or to a login page, or to another site', () => {
    expect(returnTo(buyer, '/seller/goods')).toBe('/')
    expect(returnTo(buyer, '/admin')).toBe('/')
    expect(returnTo(buyer, '/login')).toBe('/')
    expect(returnTo(buyer, '/register?role=seller')).toBe('/')
    expect(returnTo(buyer, '//evil.example.com')).toBe('/')
    expect(returnTo(buyer, 'https://evil.example.com')).toBe('/')
    expect(returnTo(seller, '/products/42')).toBe('/seller')
    expect(returnTo(seller, '/admin/flags')).toBe('/seller')
    expect(returnTo(admin, '/seller/goods')).toBe('/admin')
    expect(returnTo(admin, '/products/42')).toBe('/admin')
  })

  it('a seller and an admin return to the page of their section', () => {
    expect(returnTo(seller, '/seller/stock?tab=sale')).toBe('/seller/stock?tab=sale')
    expect(returnTo(admin, '/admin/stores/3')).toBe('/admin/stores/3')
    expect(returnTo(buyer, '/sellers-guide')).toBe('/sellers-guide')  // a storefront page that only starts with "seller"
  })

  it('a logged-in user who opens /login or /register goes to his section (GuestOnly uses the same rule)', () => {
    expect(returnTo(seller, '/admin')).toBe('/seller')
    expect(returnTo(admin, '/seller')).toBe('/admin')
    expect(returnTo(buyer, undefined)).toBe('/')
  })

  it('the old addresses lead to the one login and registration and remember where to return', () => {
    expect(oldAuthTarget('/seller/login', null)).toEqual({ to: '/login', state: { from: '/seller' } })
    expect(oldAuthTarget('/admin/login', null)).toEqual({ to: '/login', state: { from: '/admin' } })
    expect(oldAuthTarget('/seller/register', null)).toEqual({ to: '/register?role=seller', state: { from: '/seller' } })
    // A cabinet page sent the guest to the old login: he comes back to that page
    expect(oldAuthTarget('/seller/login', { from: '/seller/goods' }).state.from).toBe('/seller/goods')
    expect(Object.keys(OLD_AUTH).sort()).toEqual(['/admin/login', '/seller/login', '/seller/register'])
    // After the old admin login an admin lands in the admin panel, a seller — in the cabinet, a buyer — on the storefront
    const from = oldAuthTarget('/admin/login', null).state.from
    expect([returnTo(admin, from), returnTo(seller, from), returnTo(buyer, from)]).toEqual(['/admin', '/seller', '/'])
  })

  it('the login link of a guest remembers the page', () => {
    expect(loginState({ pathname: '/products/42', search: '?tab=used' })).toEqual({ from: '/products/42?tab=used' })
  })
})

describe('one registration with the role (phase 16.3)', () => {
  it('?role=seller chooses "I am a store"; without it nothing is chosen yet', () => {
    expect(registerRole('?role=seller')).toBe('seller')
    expect(registerRole('?role=buyer')).toBe('buyer')
    expect(registerRole('')).toBe('')
    expect(registerRole('?role=admin')).toBe('')  // an admin is never registered on the site
  })
})
