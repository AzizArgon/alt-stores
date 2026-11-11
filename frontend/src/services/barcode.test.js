import { describe, expect, it } from 'vitest'
import { checkBarcode, createScanDetector, looksLikeBarcode } from './barcode'

const type = (detector, text, step, start = 1000) => {
  let out = null
  ;[...text, 'Enter'].forEach((k, i) => { out = detector.feed(k, start + i * step) ?? out })
  return out
}

describe('barcode check', () => {
  it('passes right check digits of EAN-13, EAN-8 and UPC-A (as EAN-13)', () => {
    expect(checkBarcode('4006381333931')).toEqual({ code: '4006381333931' })
    expect(checkBarcode('96385074')).toEqual({ code: '96385074' })
    expect(checkBarcode('036000291452')).toEqual({ code: '0036000291452' })
  })
  it('a wrong check digit is a misread', () => {
    expect(checkBarcode('4006381333932').error).toBe('checksum')
    expect(checkBarcode('96385075').error).toBe('checksum')
  })
  it('other formats: 4–32 characters without spaces', () => {
    expect(checkBarcode('SN-77x')).toEqual({ code: 'SN-77x' })
    expect(checkBarcode('ab1').error).toBe('format')
    expect(checkBarcode('A'.repeat(33)).error).toBe('format')
    expect(checkBarcode('AB 12').error).toBe('format')
  })
  it('a short number is the offer code, a name is words', () => {
    expect(looksLikeBarcode('4006381333931')).toBe(true)
    expect(looksLikeBarcode('125')).toBe(false)
    expect(looksLikeBarcode('Kingston DDR5')).toBe(false)
  })
})

describe('scanner detection', () => {
  it('a fast run ended by Enter is a scan', () => {
    expect(type(createScanDetector(), '2000000000015', 8)).toBe('2000000000015')
  })
  it('a person typing is not a scanner', () => {
    expect(type(createScanDetector(), '2000000000015', 160)).toBe(null)
  })
  it('a slow start then a fast run takes only the fast part; too short is nothing', () => {
    const d = createScanDetector()
    d.feed('x', 0)
    expect(type(d, '2000000000015', 5, 500)).toBe('2000000000015')
    expect(type(createScanDetector(), '12', 5)).toBe(null)
  })
  it('a late Enter after a fast run is not a scan', () => {
    const d = createScanDetector()
    ;[...'20000000'].forEach((k, i) => d.feed(k, i * 5))
    expect(d.feed('Enter', 1000)).toBe(null)
  })
})
