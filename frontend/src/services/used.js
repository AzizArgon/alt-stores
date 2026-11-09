// New and used goods apart (phase 9): counts per group and the tab a product card opens on
export function groupCounts(offers) {
  const counts = { new: 0, used: 0 }
  offers.forEach((o) => { counts[o.group] += 1 })
  return counts
}

// "New" by default; "Used" when the product has no new offers at all
export function defaultGroup(counts) {
  return counts.new === 0 && counts.used > 0 ? 'used' : 'new'
}
