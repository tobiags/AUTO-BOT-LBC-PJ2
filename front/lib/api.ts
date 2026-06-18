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
  title: string
  price: number | null
  km: number | null
  make: string | null
  model: string | null
  year: number | null
  price_score: number | null
  market_avg_price: number | null
  ai_summary: string | null
  status: ListingStatus
  created_at: string
}

export type PlatformAccount = {
  id: string
  email: string
  status: AccountStatus
  score_sante: number
  quota_actuel: number
  erreurs_24h: number
  datadome_trust_level: DatadomeTrustLevel
  date_creation: string
}

export type Campaign = {
  id: string
  name: string
  make: string
  model: string
  year_min: number | null
  year_max: number | null
  price_max: number | null
  status: CampaignStatus
  created_at: string
}

export type AnalyzerStats = {
  total_analyzed: number
  pending: number
  avg_score: number | null
  high_value_count: number
}

export type AnalyzerResult = {
  listing_id: string
  price_score: number
  market_avg_price: number
  market_sample_size: number
  ai_summary: string
  analyzed_at: string
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
    pause: (id: string) => apiFetch<void>(`/campaigns/${id}/pause`, { method: 'POST' }),
    resume: (id: string) => apiFetch<void>(`/campaigns/${id}/resume`, { method: 'POST' }),
  },
  accounts: {
    list: () => apiFetch<PlatformAccount[]>('/accounts'),
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
