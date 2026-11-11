import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import '../i18n'
import { MessageBubble } from './Chat'

const message = (text, extra = {}) => ({ id: 1, author: 'buyer', text, is_read: false, created_at: '2026-11-09T10:00:00Z', ...extra })

describe('a message is shown as text only', () => {
  it('HTML in the text is not executed: it is escaped', () => {
    const html = renderToStaticMarkup(<MessageBubble message={message('<img src=x onerror="alert(1)"><script>x()</script>')} own />)
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<script')
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
  })
  it('links and phone numbers are not made clickable', () => {
    const html = renderToStaticMarkup(<MessageBubble message={message('https://t.me/scam +998 90 123 45 67')} own={false} />)
    expect(html).not.toContain('<a')
    expect(html).toContain('https://t.me/scam +998 90 123 45 67')
  })
  it('own read message says "read"', () => {
    expect(renderToStaticMarkup(<MessageBubble message={message('Привет', { is_read: true })} own />)).toContain('прочитано')
  })
})
