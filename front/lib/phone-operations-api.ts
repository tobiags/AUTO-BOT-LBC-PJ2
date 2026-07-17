export type PhoneOperationsSummary = {
  active_numbers: number
  received_numbers: number
  expiring_soon: number
  sms_sent: number
  sms_received: number
  sms_failed: number
}

export type PhoneActivation = {
  id: string
  provider: string
  provider_order_id: string
  phone_e164: string
  country: string
  service: string
  cost: number
  status: 'reserved' | 'waiting' | 'received' | 'used' | 'cancelled' | 'expired' | 'refunded' | 'failed'
  origin: 'automatic' | 'manual'
  platform_account_id: string | null
  workflow_id: string | null
  expires_at: string
  received_at: string | null
  used_at: string | null
  received_sms: string | null
  received_code: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export type SmsMessage = {
  id: string
  direction: 'inbound' | 'outbound'
  phone_e164: string
  sim_id: string
  body: string
  status: string
  project: string
  cost_eur: number | null
  campaign_id: string | null
  contact_id: string | null
  listing_id: string | null
  sequence_step: number | null
  variant_key: string | null
  classification: string | null
  occurred_at: string
}

export type Page<T> = { items: T[]; total: number }
export type PhoneOperationsDashboard = {
  summary: PhoneOperationsSummary
  activations: Page<PhoneActivation>
  messages: Page<SmsMessage>
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function read<T>(path: string): Promise<T> {
  const token = process.env.CONTROL_TOWER_TOKEN
  if (!token) throw new Error('CONTROL_TOWER_TOKEN is required')
  const response = await fetch(`${API_URL}/api/v1/phone-operations/${path}`, {
    headers: { 'X-Control-Tower-Token': token, 'X-Operator-Role': 'viewer' },
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`Phone operations API failed (${response.status})`)
  return response.json() as Promise<T>
}

export const emptyPhoneOperationsDashboard: PhoneOperationsDashboard = {
  summary: {
    active_numbers: 0,
    received_numbers: 0,
    expiring_soon: 0,
    sms_sent: 0,
    sms_received: 0,
    sms_failed: 0,
  },
  activations: { items: [], total: 0 },
  messages: { items: [], total: 0 },
}

export async function fetchPhoneOperationsDashboard(): Promise<PhoneOperationsDashboard> {
  const [summary, activations, messages] = await Promise.all([
    read<PhoneOperationsSummary>('summary'),
    read<Page<PhoneActivation>>('activations?limit=100'),
    read<Page<SmsMessage>>('messages?limit=100'),
  ])
  return { summary, activations, messages }
}
