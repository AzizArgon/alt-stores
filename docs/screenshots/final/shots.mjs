// Screenshots for the diploma (phase 19): a copy of the local DB with Age hidden, frontend-verify :5175 -> backend :8001
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const OUT = 'F:/claudy/diplom/docs/screenshots/final'
const WEB = 'http://localhost:5175'
const API = 'http://127.0.0.1:8001/api'
fs.mkdirSync(OUT, { recursive: true })
const only = process.argv.slice(2)

async function token(email) {
  const r = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'demo12345' }) })
  return (await r.json()).access_token
}
async function setLang(tok, lang) {
  if (tok) await fetch(`${API}/auth/me/lang`, { method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` }, body: JSON.stringify({ lang }) })
}

const browser = await puppeteer.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })

async function shot(name, path, { who = null, lang = 'ru', w = 1920, h = 1080, full = false, maxH = 2400, before = null, mobile = false } = {}) {
  if (only.length && !only.includes(name)) return
  const tok = who ? await token(who) : null
  await setLang(tok, lang)
  const ctx = await browser.createBrowserContext()
  const page = await ctx.newPage()
  await page.setViewport({ width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile })
  await page.evaluateOnNewDocument((tok, lang) => {
    localStorage.setItem('pc_market_lang', lang)
    if (tok) localStorage.setItem('pc_market_token', tok)
  }, tok, lang)
  await page.goto(WEB + path, { waitUntil: 'networkidle0', timeout: 60000 })
  await new Promise(r => setTimeout(r, 1200))
  if (before) { await before(page); await new Promise(r => setTimeout(r, 1000)) }
  let opts = { path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 85 }
  if (full) {
    const height = await page.evaluate(() => document.documentElement.scrollHeight)
    opts = { ...opts, clip: { x: 0, y: 0, width: w, height: Math.min(height, maxH) }, captureBeyondViewport: true }
  }
  await page.screenshot(opts)
  console.log('ok', name)
  await setLang(tok, 'ru')
  await ctx.close()
}

const clickText = (sel, text) => async page => {
  const els = await page.$$(sel)
  for (const el of els) {
    const t = await page.evaluate(e => e.textContent || '', el)
    if (t.includes(text)) { await el.click(); return }
  }
}
const clickBell = async page => { const b = await page.$('button[title="Уведомления"], button[title="Bildirishnomalar"]'); if (b) await b.click() }

const scan = async page => {
  const inp = await page.$('main input') ; if (inp) await inp.focus()
  for (let i = 0; i < 2; i++) { await page.keyboard.type('2900000000018', { delay: 5 }); await page.keyboard.press('Enter'); await new Promise(r => setTimeout(r, 1500)) }
}
const BUILD = process.env.BUILD_ID || '1'
const IMPORT = process.env.IMPORT_ID || '16'

await shot('01_home', '/')
await shot('02_search_12400f', '/catalog?q=12400f')
await shot('03_product_offers', '/products/8', { full: true, maxH: 2600 })
await shot('04_used', '/used')
await shot('05_build', `/builds/${BUILD}`, { full: true, maxH: 2200 })
await shot('06_seller_goods', '/seller/goods', { who: 'demo1@example.com' })
await shot('07_import_preview', `/seller/imports/${IMPORT}`, { who: 'live@example.com', full: true, maxH: 2000 })
await shot('08_stock', '/seller/stock', { who: 'demo1@example.com', before: scan })
await shot('08b_stock_journal', '/seller/stock', { who: 'demo1@example.com', before: clickText('button, a', 'Журнал') })
await shot('09_reservations', '/seller/reservations', { who: 'demo1@example.com' })
await shot('10_notifications', '/seller', { who: 'demo1@example.com', before: clickBell })
await shot('11_admin', '/admin', { who: 'admin@example.com' })
await shot('11b_admin_reports', '/admin/reports', { who: 'admin@example.com' })
await shot('14_market', '/market', { full: true, maxH: 2000 })
await shot('15_buyer_reservations', '/reservations', { who: 'buyer1@example.com' })
await shot('phone_home', '/', { w: 375, h: 812, mobile: true })
await shot('phone_product', '/products/8', { w: 375, h: 812, mobile: true, full: true, maxH: 2400 })
await shot('phone_seller_stock', '/seller/stock', { who: 'demo1@example.com', w: 375, h: 812, mobile: true })
await shot('01_home_uz', '/', { lang: 'uz' })
await shot('03_product_offers_uz', '/products/8', { lang: 'uz', full: true, maxH: 2600 })
await shot('08_stock_uz', '/seller/stock', { who: 'demo1@example.com', lang: 'uz', before: scan })
await browser.close()
