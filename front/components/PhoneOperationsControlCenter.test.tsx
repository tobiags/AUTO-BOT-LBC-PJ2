import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { PhoneOperationsDashboard } from '@/lib/phone-operations-api'
import { PhoneOperationsControlCenter } from './PhoneOperationsControlCenter'

const activation = {
  id: 'activation-1',
  provider: 'smsapp',
  provider_order_id: 'order-1',
  phone_e164: '+33612345678',
  country: 'france',
  service: 'leboncoin',
  cost: 0.28,
  status: 'waiting',
  origin: 'manual',
  platform_account_id: null,
  workflow_id: null,
  expires_at: new Date(Date.now() + 300_000).toISOString(),
  received_at: null,
  used_at: null,
  received_sms: null,
  received_code: null,
  last_error: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const dashboard: PhoneOperationsDashboard = {
  summary: {
    active_numbers: 1,
    received_numbers: 0,
    expiring_soon: 1,
    sms_sent: 12,
    sms_received: 3,
    sms_failed: 1,
  },
  activations: { items: [activation], total: 1 },
  messages: {
    total: 1,
    items: [{
      id: 'sms-1',
      direction: 'outbound',
      phone_e164: '+33687654321',
      sim_id: 'sim-1',
      body: 'Bonjour, votre vehicule est-il disponible ?',
      status: 'sent',
      project: 'P2',
      cost_eur: 0.04,
      campaign_id: null,
      contact_id: null,
      listing_id: null,
      sequence_step: 0,
      variant_key: 'initial-a',
      classification: null,
      occurred_at: new Date().toISOString(),
    }],
  },
}

afterEach(() => vi.unstubAllGlobals())

describe('PhoneOperationsControlCenter', () => {
  it('keeps temporary numbers and SMS history in one control center', () => {
    render(<PhoneOperationsControlCenter initialData={dashboard} />)

    expect(screen.getByText('+33612345678')).toBeInTheDocument()
    expect(screen.getByText(/expire dans/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Historique SMS' }))
    expect(screen.getByText('Bonjour, votre vehicule est-il disponible ?')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Exporter CSV' })).toHaveAttribute(
      'href',
      '/api/phone-operations/messages.csv',
    )
  })

  it('allows a manual reservation without leaving the page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...activation, id: 'activation-2', phone_e164: '+33711111111' }),
    }))
    render(<PhoneOperationsControlCenter initialData={dashboard} />)

    fireEvent.click(screen.getByRole('button', { name: 'Reserver un numero' }))

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Numero reserve'))
    expect(screen.getByText('+33711111111')).toBeInTheDocument()
  })
})
