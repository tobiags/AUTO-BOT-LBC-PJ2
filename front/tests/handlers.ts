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
  make: 'Renault',
  model: 'Clio',
  year: 2018,
  price_score: 7.5,
  market_avg_price: 8200,
  ai_summary: 'Bon rapport qualité/prix — kilométrage raisonnable pour l\'année.',
  status: 'NOUVELLE',
  created_at: '2026-06-19T10:00:00Z',
}

export const mockAccount: PlatformAccount = {
  id: 'acc-001',
  email: 'test@autotransfert-tmp.fr',
  status: 'ACTIF',
  score_sante: 95,
  quota_actuel: 10,
  erreurs_24h: 0,
  datadome_trust_level: 'HIGH',
  date_creation: '2026-06-01T00:00:00Z',
}

export const mockCampaign: Campaign = {
  id: 'camp-001',
  name: 'Recherche Clio 2018',
  make: 'Renault',
  model: 'Clio',
  year_min: 2016,
  year_max: 2020,
  price_max: 10000,
  status: 'RUNNING',
  created_at: '2026-06-15T00:00:00Z',
}

export const mockAnalyzerStats: AnalyzerStats = {
  total_analyzed: 42,
  pending: 3,
  avg_score: 6.8,
  high_value_count: 12,
}

export const mockAnalyzerResult: AnalyzerResult = {
  listing_id: '123e4567-e89b-12d3-a456-426614174000',
  price_score: 7.5,
  market_avg_price: 8200,
  market_sample_size: 31,
  ai_summary: 'Véhicule sous-coté de 8,5% par rapport au marché.',
  analyzed_at: '2026-06-19T11:00:00Z',
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
