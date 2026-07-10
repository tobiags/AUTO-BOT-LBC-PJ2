import { describe, expect, it } from 'vitest'

import type { DashboardStats } from '@/lib/api'
import {
  incrementCallCounters,
  prependIncomingCall,
  upsertBalance,
} from '@/lib/dashboard-state'

const baseStats: DashboardStats = {
  listings_total: 10,
  listings_today: 2,
  sms_sent_total: 5,
  sms_sent_today: 1,
  calls_total: 3,
  calls_today: 1,
  sms_received_total: 2,
  sms_received_today: 1,
  accounts_active: 4,
  accounts_total: 5,
  campaigns_running: 1,
  lbc_messages_sent_total: 0,
  lbc_messages_sent_today: 0,
  lbc_messages_received_total: 0,
  lbc_messages_received_today: 0,
  phones_extracted_total: 0,
  phones_extracted_today: 0,
  connectors: [],
  actions_required: [],
  workflows: [],
  generated_at: '2026-07-10T12:00:00Z',
  balances: [{
    service: 'smstools',
    label: 'SMSTools SMS',
    balance: 15,
    currency: 'EUR',
    is_low: false,
    low_threshold: 10,
    last_updated: '2026-06-30T16:00:00Z',
    expires_at: null,
  }],
}

describe('dashboard-state', () => {
  it('increments call counters', () => {
    const next = incrementCallCounters(baseStats)

    expect(next.calls_total).toBe(4)
    expect(next.calls_today).toBe(2)
  })

  it('updates an existing balance in place', () => {
    const balances = upsertBalance(baseStats.balances, {
      event: 'balance_update',
      service: 'smstools',
      label: 'SMSTools SMS',
      balance: 8.5,
      currency: 'EUR',
      is_low: true,
      low_threshold: 10,
      last_updated: '2026-06-30T17:00:00Z',
    })

    expect(balances).toHaveLength(1)
    expect(balances[0].balance).toBe(8.5)
    expect(balances[0].is_low).toBe(true)
  })

  it('prepends latest incoming calls and caps to five', () => {
    let calls = Array.from({ length: 5 }, (_, index) => ({
      event: 'incoming_call' as const,
      caller: `+3360000000${index}`,
      listing: { title: `Annonce ${index}` },
    }))

    calls = prependIncomingCall(calls, {
      event: 'incoming_call',
      caller: '+33699999999',
      listing: { title: 'Derniere annonce' },
    })

    expect(calls).toHaveLength(5)
    expect(calls[0].caller).toBe('+33699999999')
  })
})
