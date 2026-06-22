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
export type CampaignStatus = 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED'
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
}

export type Campaign = {
  id: string
  type: string
  status: CampaignStatus
  sent: number
  failed: number
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
  ai_summary: string | null
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
  campaigns_running: number
  balances: ServiceBalance[]
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
