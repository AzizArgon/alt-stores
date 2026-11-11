// Phase 13: helpers of the admin panel (texts in ru.json admin.*)
import { useCallback, useEffect, useState } from 'react'
import api, { errorKey } from './api'

// The admin API answers {detail: {code}}: its own texts admin.error.<code>, anything else — the common errors
export function adminErrorKey(err) {
  const code = err?.response?.data?.detail?.code
  return code && err.response.status !== 429 ? `admin.error.${code}` : errorKey(err)
}

// The journal filter: an action "store_block" belongs to the group "store"
export const LOG_GROUPS = ['store', 'report', 'flag', 'fix', 'barcode', 'channel', 'user', 'photo']
export const actionGroup = (action) => action.split('_')[0]

// "10.11.2026, 14:05"
export function dateTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// Query params without empty values: {verified: ''} is "all"
export function cleanParams(params) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined))
}

// GET with a reload function: [data, reload]; data is undefined while loading, null after an error
export function useAdminData(url, params) {
  const [data, setData] = useState(undefined)
  const key = JSON.stringify(params || {})
  const load = useCallback(() => api.get(url, { params: cleanParams(JSON.parse(key)) })
    .then((res) => setData(res.data)).catch(() => setData(null)), [url, key])
  useEffect(() => { load() }, [load])
  return [data, load]
}
