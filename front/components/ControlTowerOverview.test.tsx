import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { describe, expect, it } from 'vitest'

import { ControlTowerOverview } from '@/components/ControlTowerOverview'
import type { DashboardStats } from '@/lib/api'

const stats = {
  listings_total: 1284,
  listings_today: 42,
  sms_sent_total: 207,
  sms_sent_today: 31,
  calls_total: 8,
  calls_today: 2,
  sms_received_total: 23,
  sms_received_today: 3,
  accounts_active: 2,
  accounts_total: 3,
  accounts_warming: 1,
  accounts_slowed: 0,
  accounts_blocked: 0,
  accounts_quarantined: 0,
  campaigns_running: 1,
  balances: [],
  lbc_messages_sent_total: 318,
  lbc_messages_sent_today: 18,
  lbc_messages_received_total: 105,
  lbc_messages_received_today: 7,
  phones_extracted_total: 94,
  phones_extracted_today: 5,
  phone_extraction_rate: 89.5,
  sms_response_rate: 11.1,
  lbc_response_rate: 33,
  connectors: [{
    name: 'iproxy',
    status: 'misconfigured',
    configured: true,
    latency_ms: 120,
    last_success_at: null,
    last_checked_at: '2026-07-10T12:00:00Z',
    error_code: 'HTTP_401',
    error_summary: 'Authentification refusee',
    details: null,
  }],
  actions_required: [{
    code: 'connector.iproxy.HTTP_401',
    severity: 'critical',
    title: 'Connecteur iproxy indisponible',
    detail: 'Authentification refusee',
    target: 'iproxy',
  }],
  workflows: [],
  generated_at: '2026-07-10T12:00:00Z',
} satisfies DashboardStats

describe('ControlTowerOverview', () => {
  it('shows messaging metrics and required actions', () => {
    render(<Theme><ControlTowerOverview stats={stats} /></Theme>)

    expect(screen.getByText('Messages LBC envoyes')).toBeTruthy()
    expect(screen.getByText('Numeros extraits')).toBeTruthy()
    expect(screen.getByText('89.5%')).toBeTruthy()
    expect(screen.getByText('Connecteur iproxy indisponible')).toBeTruthy()
    expect(screen.getAllByText('HTTP_401')).toHaveLength(2)
  })
})
