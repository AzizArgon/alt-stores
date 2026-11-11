import { useEffect, useRef } from 'react'

// Phase 12.3: barcodes in the browser — the same check of a code as the server (app/services/barcodes.py), the USB
// scanner told apart from a person typing, and a beep with a vibration.

export function checkDigit(digits) {
  let total = 0
  ;[...digits].reverse().forEach((d, i) => { total += Number(d) * (i % 2 === 0 ? 3 : 1) })
  return (10 - (total % 10)) % 10
}

// {code} normalized (UPC-A as EAN-13 with a 0) or {error: 'checksum' | 'format'}
export function checkBarcode(raw) {
  const code = String(raw ?? '').trim()
  if (/^\d+$/.test(code) && [8, 12, 13].includes(code.length)) {
    if (checkDigit(code.slice(0, -1)) !== Number(code.at(-1))) return { error: 'checksum' }
    return { code: code.length === 12 ? `0${code}` : code }
  }
  return /^[\x21-\x7e]{4,32}$/.test(code) ? { code } : { error: 'format' }
}

// Looks like a code from a box rather than words: one token with a digit, 4–32 characters (a name has spaces).
// Short numbers (up to 7 digits) are the "Код ALT" of an offer, not a barcode.
export function looksLikeBarcode(text) {
  const s = String(text ?? '').trim()
  return /^[\x21-\x7e]{4,32}$/.test(s) && /\d/.test(s) && !/^\d{1,7}$/.test(s)
}

// A USB scanner is a keyboard that types a whole code in a few milliseconds and presses Enter. A person types
// 100–300 ms between keys. A key comes "fast" when it is less than `gap` ms after the previous one; a run of fast
// keys (at least `min` characters) ended by Enter is a scan. Pure: `feed(key, time)` returns the code or null.
export function createScanDetector({ gap = 50, min = 4 } = {}) {
  let buf = ''
  let last = -Infinity
  return {
    feed(key, time) {
      const fast = time - last < gap
      last = time
      if (key === 'Enter') {
        const code = fast && buf.length >= min ? buf : null
        buf = ''
        return code
      }
      if (key.length !== 1) { buf = ''; return null }
      buf = fast ? buf + key : key
      return null
    },
    get pending() { return buf },
  }
}

const editable = (el) => el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))

// The page listens to the scanner even when no field is focused ("Склад", "Сканирование"). A focused field gets
// its keys as usual (the goods input itself takes a code with Enter). Enter of a scan never presses a focused button.
// Phase 12.5: "Сканер готов" — the scanner's keys reach the goods field (it has the focus) or nobody's field (the
// page catches a scan without a focus); another field has the focus — the scan would type into it
export function scannerReady(active, field) {
  return !active || active === field || !editable(active)
}

export function useScanner(onScan, enabled = true) {
  const cb = useRef(onScan)
  cb.current = onScan
  useEffect(() => {
    if (!enabled) return undefined
    const detector = createScanDetector()
    const onKey = (e) => {
      if (editable(e.target) || e.ctrlKey || e.metaKey || e.altKey) return
      const code = detector.feed(e.key, e.timeStamp || performance.now())
      if (code) {
        e.preventDefault()
        e.stopPropagation()
        cb.current(code)
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [enabled])
}

let audio
// Phase 12.5: the beep can be switched off next to "Сканер готов" (the choice is kept in the browser)
export const SOUND_KEY = 'alt_scan_sound'
export function soundOn() {
  try { return localStorage.getItem(SOUND_KEY) !== 'off' } catch { return true }
}
export function setSound(on) {
  try { localStorage.setItem(SOUND_KEY, on ? 'on' : 'off') } catch { /* private mode */ }
}

// A short high beep for a success, two low ones for an error; a vibration on a phone
export function feedback(ok) {
  try {
    navigator.vibrate?.(ok ? 60 : [120, 80, 120])
  } catch { /* not allowed */ }
  if (!soundOn()) return
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)()
    const beep = (freq, at, len) => {
      const o = audio.createOscillator()
      const g = audio.createGain()
      o.frequency.value = freq
      o.type = 'square'
      g.gain.value = 0.06
      o.connect(g).connect(audio.destination)
      o.start(audio.currentTime + at)
      o.stop(audio.currentTime + at + len)
    }
    if (ok) beep(1800, 0, 0.09)
    else { beep(300, 0, 0.15); beep(300, 0.22, 0.15) }
  } catch { /* no sound in this browser */ }
}
