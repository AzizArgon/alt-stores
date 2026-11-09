import { describe, expect, it } from 'vitest'
import { defaultGroup, groupCounts } from './used'

describe('new and used tabs', () => {
  it('counts offers per group', () => {
    expect(groupCounts([{ group: 'new' }, { group: 'used' }, { group: 'used' }])).toEqual({ new: 1, used: 2 })
  })
  it('opens on new, or on used when there are no new offers', () => {
    expect(defaultGroup({ new: 2, used: 5 })).toBe('new')
    expect(defaultGroup({ new: 0, used: 1 })).toBe('used')
    expect(defaultGroup({ new: 0, used: 0 })).toBe('new')
  })
})
