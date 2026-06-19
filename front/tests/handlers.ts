import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type {
  AnalyzerResult,
  AnalyzerStats,
  Campaign,
  Listing,
  PlatformAccount,
} from '@/lib/api'

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
  status: 'ACTIF',
  score_sante: 95,
  quota_actuel: 10,
  erreurs_24h: 0,
  datadome_trust_level: 'HIGH',
  date_creation: '2026-06-01T00:00:00Z',
  derniere_action: '2026-06-19T09:00:00Z',
}

export const mockCampaign: Campaign = {
  id: 'camp-001',
  type: 'sms_direct',
  status: 'RUNNING',
  sent: 42,
  failed: 1,
  created_at: '2026-06-15T00:00:00Z',
}

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
  ai_summary: 'Véhicule sous-coté de 8,5% par rapport au marché.',
}

export const handlers = [
  http.get(`${BASE}/listings`, () => HttpResponse.json([mockListing])),
  http.get(`${BASE}/accounts`, () => HttpResponse.json([mockAccount])),
  http.get(`${BASE}/campaigns`, () => HttpResponse.json([mockCampaign])),
  http.get(`${BASE}/analyzer/stats`, () => HttpResponse.json(mockAnalyzerStats)),
  http.get(`${BASE}/analyzer/results`, () => HttpResponse.json([mockAnalyzerResult])),
  http.post(`${BASE}/analyzer/run/:id`, () => HttpResponse.json({ ok: true })),
  http.post(`${BASE}/analyzer/run/batch`, () => HttpResponse.json({ ok: true })),
]

export const server = setupServer(...handlers)
