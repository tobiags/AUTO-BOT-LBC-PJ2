import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type {
  AnalyzerResult,
  AnalyzerStats,
  Campaign,
  Listing,
  PlatformAccount,
} from '@/lib/api'
import type { ApifyDashboard } from '@/lib/apify-api'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const mockListing: Listing = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  source: 'leboncoin',
  url: 'https://www.leboncoin.fr/voitures/123',
  title: 'Renault Clio 1.2 TCe 90',
  price: 7500,
  km: 85000,
  location: 'Paris 75001',
  make: 'Renault',
  model: 'Clio',
  year: 2018,
  fuel: 'Essence',
  transmission: 'Manuelle',
  price_score: 7.5,
  market_avg_price: 8200,
  market_sample_size: 31,
  status: 'NOUVELLE',
  created_at: '2026-06-19T10:00:00Z',
}

export const mockAccount: PlatformAccount = {
  id: 'acc-00000001',
  email: 'contact.test@mail.ecovente.com',
  phone_otp: '+33612345678',
  status: 'ACTIF',
  score_sante: 95,
  quota_actuel: 10,
  erreurs_24h: 0,
  datadome_trust_level: 'HIGH',
  date_creation: '2026-06-01T00:00:00Z',
  derniere_action: '2026-06-19T09:00:00Z',
  browser_use_profile_id: 'profile-test',
  browser_use_session_id: null,
}

export const mockCampaign: Campaign = {
  id: 'camp-001',
  type: 'sms_direct',
  status: 'RUNNING',
  sent: 42,
  failed: 1,
  scheduled_at: null,
  last_error: null,
  search_criteria: {
    brand_model: null,
    vehicle_type: null,
    region: null,
    budget_min: null,
    budget_max: null,
  },
  created_at: '2026-06-15T00:00:00Z',
}

export const mockApifyDashboard = {
  summary: {
    accounts_total: 1,
    accounts_active: 1,
    bindings_total: 1,
    bindings_enabled: 0,
    runs_running: 0,
    runs_failed: 0,
    items_imported: 0,
    exceptions_open: 0,
  },
  accounts: [
    {
      id: '10000000-0000-0000-0000-000000000001',
      workspace_id: '20000000-0000-0000-0000-000000000001',
      label: 'Principal',
      apify_user_id: 'user-1',
      username: 'owner',
      token_masked: 'apif...cret',
      status: 'active',
      last_checked_at: '2026-07-16T10:00:00Z',
      last_error: null,
      created_at: '2026-07-16T09:00:00Z',
      updated_at: '2026-07-16T10:00:00Z',
    },
  ],
  bindings: [
    {
      id: '30000000-0000-0000-0000-000000000001',
      workspace_id: '20000000-0000-0000-0000-000000000001',
      account_id: '10000000-0000-0000-0000-000000000001',
      sector_id: null,
      campaign_id: null,
      resource_type: 'actor',
      resource_id: 'owner/example',
      name: 'Example Actor',
      enabled: false,
      schedule_authority: 'internal',
      schedule_minutes: 60,
      next_run_at: null,
      webhook_id: null,
      schema_fingerprint: null,
      active_profile_id: null,
      suspended_reason: null,
      created_at: '2026-07-16T09:00:00Z',
      updated_at: '2026-07-16T10:00:00Z',
    },
  ],
  runs: { items: [], total: 0, limit: 50, offset: 0 },
  items: { items: [], total: 0, limit: 50, offset: 0 },
  learning: { profiles: [], experiments: [], exceptions: [] },
} satisfies ApifyDashboard

export const mockAnalyzerStats: AnalyzerStats = {
  total_listings: 150,
  analyzed: 42,
  pending: 108,
  high_confidence: 12,
  medium_confidence: 18,
  underpriced: 24,
  overpriced: 10,
  avg_price_score: 6.8,
  top_opportunities: [],
}

export const mockAnalyzerResult: AnalyzerResult = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  url: 'https://www.leboncoin.fr/voitures/123',
  title: 'Renault Clio 1.2 TCe 90',
  make: 'Renault',
  model: 'Clio',
  year: 2018,
  km: 85000,
  price: 7500,
  price_score: 7.5,
  market_avg_price: 8200,
  market_sample_size: 31,
  confidence: 'high',
  reliability_score: 84,
  ai_summary: 'Vehicule sous-cote de 8,5% par rapport au marche.',
  known_issues: ['Courroie a surveiller'],
  inspection_tips: ['Verifier l embrayage'],
  negotiation_tip: 'Mettre en avant l entretien a venir.',
}

export const handlers = [
  http.get(`${BASE}/listings`, () => HttpResponse.json([mockListing])),
  http.get(`${BASE}/accounts`, () => HttpResponse.json([mockAccount])),
  http.get(`${BASE}/campaigns`, () => HttpResponse.json([mockCampaign])),
  http.post(`${BASE}/campaigns/:id/start`, () => HttpResponse.json({ queued: true })),
  http.get(`${BASE}/analyzer/stats`, () => HttpResponse.json(mockAnalyzerStats)),
  http.get(`${BASE}/analyzer/results`, () => HttpResponse.json([mockAnalyzerResult])),
  http.post(`${BASE}/analyzer/run/:id`, () => HttpResponse.json({ ok: true })),
  http.post('/api/operations/analyzer/listings/:id', () => HttpResponse.json({ status: 'PENDING' })),
  http.post(`${BASE}/analyzer/run/batch`, () => HttpResponse.json({ ok: true })),
  http.get(`${BASE}/api/v1/apify/summary`, () => HttpResponse.json(mockApifyDashboard.summary)),
  http.get(`${BASE}/api/v1/apify/accounts`, () => HttpResponse.json(mockApifyDashboard.accounts)),
  http.get(`${BASE}/api/v1/apify/bindings`, () => HttpResponse.json(mockApifyDashboard.bindings)),
  http.get(`${BASE}/api/v1/apify/runs`, () => HttpResponse.json(mockApifyDashboard.runs)),
  http.get(`${BASE}/api/v1/apify/items`, () => HttpResponse.json(mockApifyDashboard.items)),
  http.get(`${BASE}/api/v1/apify/learning`, () => HttpResponse.json(mockApifyDashboard.learning)),
  http.post('/api/apify/accounts', () => HttpResponse.json({
    ...mockApifyDashboard.accounts[0],
    id: '10000000-0000-0000-0000-000000000002',
    label: 'Secondaire',
    token_masked: 'apif..._new',
  }, { status: 201 })),
  http.patch('/api/apify/bindings/:id', () => HttpResponse.json(mockApifyDashboard.bindings[0])),
]

export const server = setupServer(...handlers)
