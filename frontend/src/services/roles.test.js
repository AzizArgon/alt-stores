import { describe, expect, it, vi } from 'vitest'
import { adminGate, homeFor, loginAtAdminDoor, returnTo, sellerGate } from './roles'

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

describe('one login for everyone (fix of 11.11.2026)', () => {
  const admin = { email: 'admin@example.com', role: 'admin' }
  const notAdmin = Object.assign(new Error('403'), { response: { status: 403, data: { detail: { code: 'not_admin' } } } })
  const wrong = Object.assign(new Error('401'), { response: { status: 401, data: { detail: 'Invalid email or password' } } })

  it('the usual login sends each role to its own section', () => {
    expect(returnTo(seller, undefined)).toBe('/seller')
    expect(returnTo(buyer, undefined)).toBe('/')
    expect(returnTo(admin, undefined)).toBe('/admin')
  })

  it('an already logged-in user on a login page goes to his section (GuestOnly uses the same rule)', () => {
    expect(returnTo(seller, '/admin')).toBe('/seller')
    expect(returnTo(admin, '/seller')).toBe('/admin')
  })

  it('/admin/login: an admin logs in there', async () => {
    const login = vi.fn()
    expect(await loginAtAdminDoor(async () => admin, login, 'a', 'p')).toBe(admin)
    expect(login).not.toHaveBeenCalled()
  })

  it('/admin/login: a seller is logged in the usual way and goes to the cabinet', async () => {
    const login = vi.fn(async () => seller)
    const user = await loginAtAdminDoor(async () => { throw notAdmin }, login, 'demo1@example.com', 'p')
    expect(login).toHaveBeenCalledWith('demo1@example.com', 'p')
    expect(returnTo(user, '/admin')).toBe('/seller')
  })

  it('/admin/login: a wrong password stays an error', async () => {
    const login = vi.fn()
    await expect(loginAtAdminDoor(async () => { throw wrong }, login, 'a', 'p')).rejects.toBe(wrong)
    expect(login).not.toHaveBeenCalled()
  })
})
