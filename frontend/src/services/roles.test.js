import { describe, expect, it } from 'vitest'
import { homeFor, sellerGate } from './roles'

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
