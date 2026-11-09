// Phase 10: chat of a buyer with a store. No WebSocket: the open conversation asks the server every 5 seconds,
// the unread counter every 30 seconds; while the browser tab is hidden nothing is asked.
import { useEffect, useRef, useState } from 'react'
import api, { errorKey } from './api'

export const THREAD_POLL_MS = 5000
export const UNREAD_POLL_MS = 30000
export const MAX_TEXT = 2000
export const CHANGED = 'chat:changed' // a window event: something was read or sent, counters ask again

// Calls `fn` every `ms` while the tab is visible; when the tab is shown again it catches up at once.
// Returns the function that stops it. `doc` is the page's document (a fake one in tests)
export function pollWhileVisible(fn, ms, doc = document) {
  let timer = null
  const stop = () => { clearInterval(timer); timer = null }
  const start = () => { stop(); timer = setInterval(fn, ms) }
  const onVisibility = () => {
    if (doc.hidden) stop()
    else { fn(); start() }
  }
  if (!doc.hidden) start()
  doc.addEventListener('visibilitychange', onVisibility)
  return () => { stop(); doc.removeEventListener('visibilitychange', onVisibility) }
}

export function usePolling(fn, ms, enabled = true) {
  const saved = useRef(fn)
  saved.current = fn
  useEffect(() => (enabled ? pollWhileVisible(() => saved.current(), ms) : undefined), [ms, enabled])
}

export const notifyChanged = () => window.dispatchEvent(new Event(CHANGED))

// Unread messages of the logged-in user (a buyer's own or the seller's store)
export function useUnread(enabled) {
  const [count, setCount] = useState(0)
  const load = () => api.get('/chat/unread').then((res) => setCount(res.data.count)).catch(() => {})
  useEffect(() => {
    if (!enabled) { setCount(0); return undefined }
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [enabled])
  usePolling(load, UNREAD_POLL_MS, enabled)
  return count
}

// "Write to the seller" leads here; a guest logs in first and comes back to the same address
export function writePath(kind, id) {
  return kind === 'store' ? `/messages/new?kind=store&store=${id}` : `/messages/new?kind=${kind}&id=${id}`
}

// A Telegram channel is not a store: its ads have only "Open the post"
export const canWrite = (store) => !!store && store.kind !== 'telegram'

// Codes of the chat API (rate limits, block, too long) have their own texts
export function chatErrorKey(err) {
  const code = err.response?.data?.detail?.code
  return code ? `chat.error.${code}` : errorKey(err)
}

export function formatChatTime(iso, now = new Date()) {
  const at = new Date(iso)
  const sameDay = at.toDateString() === now.toDateString()
  return new Intl.DateTimeFormat('ru', sameDay ? { hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(at)
}
