// Phase 15: uz.json and en.json have every key of ru.json (plural forms by the language), no empty values,
// the same {{params}}; components have no Russian text outside i18n. The same check: scripts/check_locales.py
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from './en.json'
import ru from './ru.json'
import uz from './uz.json'

const PLURAL = /_(zero|one|two|few|many|other)$/
const params = (s) => new Set([...String(s).matchAll(/\{\{\s*(\w+)/g)].map((m) => m[1]).filter((p) => p !== 'count'))

function flat(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    if (v && typeof v === 'object') flat(v, `${prefix}${k}.`, out)
    else out[prefix + k] = v
  }
  return out
}

// "found_many" is a plural form when "found_one" exists ("too_many" alone is a plain key)
const pluralBase = (k, keys) => {
  const base = k.replace(PLURAL, '')
  return base !== k && `${base}_one` in keys ? base : null
}

function problems(lang, dict) {
  const fr = flat(ru)
  const fo = flat(dict)
  const want = {}
  for (const [k, v] of Object.entries(fr)) {
    const base = pluralBase(k, fr)
    if (!base) { want[k] = { must: params(v), may: params(v) }; continue }
    const forms = Object.keys(fr).filter((kk) => pluralBase(kk, fr) === base).map((kk) => fr[kk])
    const may = new Set(forms.flatMap((t) => [...params(t)]))
    want[`${base}_one`] = { must: new Set(), may }
    want[`${base}_other`] = { must: params(fr[`${base}_other`] ?? fr[`${base}_many`] ?? v), may }
  }
  const out = []
  for (const [k, { must, may }] of Object.entries(want)) {
    if (!(k in fo)) { out.push(`${lang}: missing ${k}`); continue }
    if (!String(fo[k]).trim()) { out.push(`${lang}: empty ${k}`); continue }
    const got = params(fo[k])
    if (![...must].every((p) => got.has(p)) || ![...got].every((p) => may.has(p))) out.push(`${lang}: params ${k}`)
  }
  for (const k of Object.keys(fo)) if (!(k in want)) out.push(`${lang}: extra ${k}`)
  return out
}

describe('translations', () => {
  it.each([['uz', uz], ['en', en]])('%s has every key of ru with the same params', (lang, dict) => {
    expect(problems(lang, dict)).toEqual([])
  })

  it('Uzbek uses the proper letters oʻ, gʻ and the sign ʼ, not a plain apostrophe', () => {
    const bad = Object.entries(flat(uz)).filter(([, v]) => /[A-Za-z]['`‘’][A-Za-z]/.test(v)).map(([k]) => k)
    expect(bad).toEqual([])
  })
})

// Russian text in code — outside comments — would not be translated
function sources(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) sources(p, out)
    else if (/\.jsx?$/.test(name) && !name.includes('.test.') && name !== 'UiPage.jsx') out.push(p)
  }
  return out
}

describe('no Russian strings in components', () => {
  it('every interface text goes through i18n', () => {
    const found = []
    for (const file of sources(join(__dirname, '..'))) {
      const code = readFileSync(file, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
        .replace(/\/(?:\\.|[^/\n])+\/[gimsuy]*/g, '') // regex literals ("г." of a date)
      code.split('\n').forEach((line, i) => { if (/[А-Яа-яЁё]/.test(line)) found.push(`${file}:${i + 1}`) })
    }
    expect(found).toEqual([])
  })
})
