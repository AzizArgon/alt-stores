import { afterEach, describe, expect, it, vi } from 'vitest'
import { MAX_TEXT, THREAD_POLL_MS, UNREAD_POLL_MS, canWrite, chatErrorKey, pollWhileVisible, writePath } from './chat'
import { returnTo } from './roles'

// A fake page: hidden or visible, with the visibilitychange listener
function fakeDoc(hidden = false) {
  const listeners = new Set()
  return {
    hidden,
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
    setHidden(value) { this.hidden = value; listeners.forEach((fn) => fn()) },
    listeners,
  }
}

describe('Write to the seller', () => {
  it('Telegram ads have no Write (only Open the post), stores do', () => {
    expect(canWrite({ kind: 'telegram' })).toBe(false)
    expect(canWrite({ kind: 'shop' })).toBe(true)
    expect(canWrite(null)).toBe(false)
  })
  it('leads to a page that opens or finds the conversation of the topic', () => {
    expect(writePath('offer', 5)).toBe('/messages/new?kind=offer&id=5')
    expect(writePath('build', 2)).toBe('/messages/new?kind=build&id=2')
    expect(writePath('store', 3)).toBe('/messages/new?kind=store&store=3')
  })
  it('a guest returns to the conversation after login; a seller does not land in buyer messages', () => {
    const from = writePath('offer', 5)
    expect(returnTo({ role: 'buyer' }, from)).toBe(from)
    expect(returnTo({ role: 'seller' }, from)).toBe('/seller')
    expect(returnTo({ role: 'buyer' }, '/seller/goods')).toBe('/')
    expect(returnTo({ role: 'buyer' }, undefined)).toBe('/')
  })
})

describe('errors of the chat API have their own texts', () => {
  const err = (status, code) => ({ response: { status, data: { detail: code ? { code } : 'x' } } })
  it('rate limits, block, too long', () => {
    expect(chatErrorKey(err(429, 'rate_minute'))).toBe('chat.error.rate_minute')
    expect(chatErrorKey(err(403, 'blocked'))).toBe('chat.error.blocked')
    expect(chatErrorKey(err(400, 'too_long'))).toBe('chat.error.too_long')
    expect(chatErrorKey({})).toBe('errors.network')
    expect(MAX_TEXT).toBe(2000)
  })
})

describe('polling without WebSocket', () => {
  afterEach(() => vi.useRealTimers())
  it('asks every 5 s (thread) / 30 s (counter) and stops while the tab is hidden', () => {
    expect([THREAD_POLL_MS, UNREAD_POLL_MS]).toEqual([5000, 30000])
    vi.useFakeTimers()
    const doc = fakeDoc()
    const fn = vi.fn()
    const stop = pollWhileVisible(fn, THREAD_POLL_MS, doc)
    vi.advanceTimersByTime(15000)
    expect(fn).toHaveBeenCalledTimes(3)
    doc.setHidden(true)
    vi.advanceTimersByTime(60000)
    expect(fn).toHaveBeenCalledTimes(3) // hidden: nothing is asked
    doc.setHidden(false) // shown again: catches up at once, then every 5 s
    expect(fn).toHaveBeenCalledTimes(4)
    vi.advanceTimersByTime(5000)
    expect(fn).toHaveBeenCalledTimes(5)
    stop()
    vi.advanceTimersByTime(60000)
    expect(fn).toHaveBeenCalledTimes(5)
    expect(doc.listeners.size).toBe(0)
  })
  it('a page opened in a hidden tab waits until it is shown', () => {
    vi.useFakeTimers()
    const doc = fakeDoc(true)
    const fn = vi.fn()
    pollWhileVisible(fn, 1000, doc)
    vi.advanceTimersByTime(10000)
    expect(fn).not.toHaveBeenCalled()
  })
})
