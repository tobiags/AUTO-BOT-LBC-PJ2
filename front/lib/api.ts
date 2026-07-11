const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export type ListingStatus = 'NOUVELLE' | 'SMS_ENVOYÉ' | 'RÉPONSE' | 'TRAITÉ' | 'ARCHIVÉ'
export type AccountStatus =
  | 'EN_CRÉATION'
  | 'EN_CHAUFFE'
  | 'ACTIF'
  | 'RALENTI'
  | 'BLOQUÉ'
  | 'QUARANTAINE'
export type CampaignStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
export type DatadomeTrustLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export type Listing = {
  id: string
  source: string
  url: string
  title: string | null
  price: number | null
  km: number | null
  location: string | null
  make: string | null
  model: string | null
  year: number | null
  fuel: string | null
  transmission: string | null
  price_score: number | null
  market_avg_price: number | null
  market_sample_size: number | null
  status: ListingStatus
  created_at: string
}

export type PlatformAccount = {
  id: string
  status: AccountStatus
  score_sante: number
  quota_actuel: number
  erreurs_24h: number
  datadome_trust_level: DatadomeTrustLevel
  date_creation: string
  derniere_action: string | null
  browser_use_profile_id: string | null
  browser_use_session_id: string | null
}

export type Campaign = {
  id: string
  type: string
  status: CampaignStatus
  sent: number
  failed: number
  scheduled_at: string | null
  last_error: string | null
  search_criteria: {
    brand_model: string | null
    vehicle_type: string | null
    region: string | null
    budget_min: number | null
    budget_max: number | null
  }
  created_at: string
}

export type AnalyzerStats = {
  total_listings: number
  analyzed: number
  pending: number
  high_confidence: number
  medium_confidence: number
  underpriced: number
  overpriced: number
  avg_price_score: number | null
  top_opportunities: AnalyzerResult[]
}

export type AnalyzerResult = {
  id: string
  url: string
  title: string | null
  make: string | null
  model: string | null
  year: number | null
  km: number | null
  price: number | null
  price_score: number | null
  market_avg_price: number | null
  market_sample_size: number | null
  confidence: string | null
  reliability_score: number | null
  ai_summary: string | null
  known_issues: string[]
  inspection_tips: string[]
  negotiation_tip: string | null
}

export type ServiceBalance = {
  service: string
  label: string
  balance: number | null
  currency: string
  is_low: boolean
  low_threshold: number
  last_updated: string | null
  expires_at: string | null
}

export type ConnectorState =
  | 'disabled'
  | 'unverified'
  | 'ok'
  | 'degraded'
  | 'down'
  | 'misconfigured'

export type DashboardConnector = {
  name: string
  status: ConnectorState
  configured: boolean
  latency_ms: number | null
  last_success_at: string | null
  last_checked_at: string | null
  error_code: string | null
  error_summary: string | null
  details: Record<string, unknown> | null
}

export type DashboardActionItem = {
  code: string
  severity: 'critical' | 'warning' | 'info'
  title: string
  detail: string
  target: string
}

export type DashboardWorkflow = {
  id: string
  workflow_type: string
  status: 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  progress_current: number
  progress_total: number | null
  batch_number: number
  batch_size: number | null
  last_error: string | null
  updated_at: string
}

export type DashboardStats = {
  listings_total: number
  listings_today: number
  sms_sent_total: number
  sms_sent_today: number
  calls_total: number
  calls_today: number
  sms_received_total: number
  sms_received_today: number
  accounts_active: number
  accounts_total: number
  accounts_warming: number
  accounts_slowed: number
  accounts_blocked: number
  accounts_quarantined: number
  campaigns_running: number
  balances: ServiceBalance[]
  lbc_messages_sent_total: number
  lbc_messages_sent_today: number
  lbc_messages_received_total: number
  lbc_messages_received_today: number
  phones_extracted_total: number
  phones_extracted_today: number
  phone_extraction_rate: number
  sms_response_rate: number
  lbc_response_rate: number
  connectors: DashboardConnector[]
  actions_required: DashboardActionItem[]
  workflows: DashboardWorkflow[]
  generated_at: string
}

export const api = {
  listings: {
    list: (params?: { status?: string; limit?: number }) => {
      const qs = new URLSearchParams(params as Record<string, string>)
      return apiFetch<Listing[]>(`/listings?${qs}`)
    },
  },
  campaigns: {
    list: () => apiFetch<Campaign[]>('/campaigns'),
    start: (id: string) => apiFetch<void>(`/campaigns/${id}/start`, { method: 'POST' }),
  },
  accounts: {
    list: () => apiFetch<PlatformAccount[]>('/accounts'),
  },
  dashboard: {
    stats: () => apiFetch<DashboardStats>('/api/v1/dashboard'),
    updateBalance: (service: string, balance: number, currency = 'EUR') =>
      apiFetch<{ ok: boolean }>(`/api/v1/dashboard/balance/${service}`, {
        method: 'PUT',
        body: JSON.stringify({ balance, currency }),
      }),
  },
  analyzer: {
    stats: () => apiFetch<AnalyzerStats>('/analyzer/stats'),
    results: (params?: { limit?: number }) => {
      const qs = new URLSearchParams(params as Record<string, string>)
      return apiFetch<AnalyzerResult[]>(`/analyzer/results?${qs}`)
    },
    run: (listingId: string) =>
      apiFetch<void>(`/analyzer/run/${listingId}`, { method: 'POST' }),
    runBatch: (ids: string[]) =>
      apiFetch<void>('/analyzer/run/batch', {
        method: 'POST',
        body: JSON.stringify({ ids }),
      }),
  },
}
