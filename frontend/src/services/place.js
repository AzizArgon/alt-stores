import { branchLabel } from '../components/BranchStock'

// Phase 12.4: the places of the seller's stock — the warehouse (when the store has one) and the branches. The
// warehouse is the seller's only: the storefront never shows it.

export const PLACE_KEY = 'alt_place'
// Phase 12.5: "Место: Юнусабад" on a page opens the one choice of the place in the top bar
export const PLACE_OPEN = 'place:open'

export function placesOf(store) {
  const branches = store?.branches || []
  return store?.warehouse ? [{ ...store.warehouse, is_warehouse: true }, ...branches] : branches
}

export const placeLabel = (t, p) => (p?.is_warehouse || p === '@warehouse' ? t('place.warehouse') : typeof p === 'string' ? p : branchLabel(p))

export function readPlace() {
  try { return Number(localStorage.getItem(PLACE_KEY)) || null } catch { return null }
}

export function savePlace(id) {
  try { localStorage.setItem(PLACE_KEY, String(id)) } catch { /* private mode */ }
}

// The place of a mode: the chosen one when the mode allows it, else the first allowed
export function placeFor(places, id) {
  return places.find((p) => p.id === id) || places[0] || null
}
