import { describe, expect, it } from 'vitest'

import { parseBackofficeEvent } from '@/lib/websocket'

describe('parseBackofficeEvent', () => {
  it('parses incoming_call events', () => {
    const event = parseBackofficeEvent(JSON.stringify({
      event: 'incoming_call',
      caller: '+33601020304',
      listing: { title: 'Peugeot 208' },
    }))

    expect(event).toEqual({
      event: 'incoming_call',
      caller: '+33601020304',
      listing: { title: 'Peugeot 208' },
    })
  })

  it('parses balance_update events', () => {
    const event = parseBackofficeEvent(JSON.stringify({
      event: 'balance_update',
      service: 'smstools',
      label: 'SMSTools SMS',
      balance: 8.5,
      currency: 'EUR',
      is_low: true,
      low_threshold: 10,
      last_updated: '2026-06-30T16:00:00Z',
    }))

    expect(event).toEqual({
      event: 'balance_update',
      service: 'smstools',
      label: 'SMSTools SMS',
      balance: 8.5,
      currency: 'EUR',
      is_low: true,
      low_threshold: 10,
      last_updated: '2026-06-30T16:00:00Z',
    })
  })

  it('rejects malformed payloads', () => {
    expect(parseBackofficeEvent('not-json')).toBeNull()
    expect(parseBackofficeEvent(JSON.stringify({ event: 'incoming_call', caller: 'x' }))).toBeNull()
    expect(parseBackofficeEvent(JSON.stringify({ event: 'other' }))).toBeNull()
  })
})
