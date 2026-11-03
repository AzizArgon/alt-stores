import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe('one setting for the seller site address', () => {
  it('by default the cabinet is on the same site under /seller', async () => {
    const { sellerUrl, storeUrl, linkProps } = await import('./sites')
    expect(sellerUrl()).toBe('/seller')
    expect(sellerUrl('/login')).toBe('/seller/login')
    expect(storeUrl('/')).toBe('/')
    expect(linkProps(sellerUrl())).toEqual({ to: '/seller' })
  })

  it('a future subdomain: links become full addresses, paths stay under /seller', async () => {
    vi.stubEnv('VITE_SELLER_URL', 'https://seller.example.uz/')
    vi.stubEnv('VITE_STORE_URL', 'https://example.uz')
    const { sellerUrl, storeUrl, linkProps } = await import('./sites')
    const { homeFor } = await import('../services/roles')
    expect(sellerUrl('/login')).toBe('https://seller.example.uz/seller/login')
    expect(storeUrl('/')).toBe('https://example.uz/')
    expect(linkProps(sellerUrl())).toEqual({ href: 'https://seller.example.uz/seller' })
    expect(homeFor({ role: 'seller' })).toBe('https://seller.example.uz/seller')
    expect(homeFor({ role: 'buyer' })).toBe('https://example.uz/')
  })
})
