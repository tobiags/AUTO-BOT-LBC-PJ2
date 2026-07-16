export type ApifySummary = {
  accounts_total: number
  accounts_active: number
  bindings_total: number
  bindings_enabled: number
  runs_running: number
  runs_failed: number
  items_imported: number
  exceptions_open: number
}

export type ApifyAccount = {
  id: string
  workspace_id: string
  label: string
  apify_user_id: string
  username: string
  token_masked: string
  status: 'active' | 'invalid' | 'suspended'
  last_checked_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export type ApifyCatalogResource = {
  resource_type: 'actor' | 'task'
  resource_id: string
  name: string
  description: string | null
  modified_at: string | null
}

export type ApifyBinding = {
  id: string
  workspace_id: string
  account_id: string
  sector_id: string | null
  campaign_id: string | null
  resource_type: 'actor' | 'task'
  resource_id: string
  name: string
  enabled: boolean
  schedule_authority: 'internal' | 'apify'
  schedule_minutes: number | null
  next_run_at: string | null
  webhook_id: string | null
  schema_fingerprint: string | null
  active_profile_id: string | null
  suspended_reason: string | null
  created_at: string
  updated_at: string
}

export type ApifyRun = {
  id: string
  workspace_id: string
  account_id: string
  binding_id: string
  apify_run_id: string
  status: 'READY' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'ABORTED' | 'TIMED-OUT'
  started_at: string | null
  finished_at: string | null
  default_dataset_id: string | null
  cost_usd: number | null
  items_read: number
  items_imported: number
  items_ignored: number
  items_exception: number
  last_error: string | null
  imported_at: string | null
  created_at: string
  updated_at: string
}

export type ApifyItem = {
  id: string
  workspace_id: string
  account_id: string
  run_id: string
  dataset_index: number
  content_hash: string
  raw_payload: Record<string, unknown>
  normalized_payload: Record<string, unknown> | null
  confidence: number | null
  status: 'pending' | 'imported' | 'ignored' | 'duplicate' | 'exception'
  contact_id: string | null
  listing_id: string | null
  sms_sequence_id: string | null
  error: string | null
  processed_at: string | null
  created_at: string
}

export type ApifyProfile = {
  id: string
  workspace_id: string
  binding_id: string
  version: number
  schema_fingerprint: string
  mappings: Record<string, unknown>
  aliases: Record<string, unknown>
  priorities: Record<string, unknown>
  thresholds: Record<string, unknown>
  metrics: Record<string, unknown>
  status: 'candidate' | 'active' | 'retired'
  created_at: string
  promoted_at: string | null
  retired_at: string | null
}

export type ApifyExperiment = {
  id: string
  workspace_id: string
  binding_id: string
  baseline_profile_id: string | null
  candidate_profile_id: string
  corpus_size: number
  baseline_metrics: Record<string, unknown>
  candidate_metrics: Record<string, unknown>
  decision: 'keep' | 'discard' | 'crash' | null
  reason: string | null
  created_at: string
  evaluated_at: string | null
}

export type ApifyException = {
  id: string
  workspace_id: string
  binding_id: string
  run_id: string | null
  item_id: string | null
  category: string
  evidence: Record<string, unknown>
  status: 'open' | 'resolved' | 'dismissed'
  resolution: string | null
  resolved_by: string | null
  created_at: string
  resolved_at: string | null
}

export type ApifyPage<T> = { items: T[]; total: number; limit: number; offset: number }
export type ApifyLearning = {
  profiles: ApifyProfile[]
  experiments: ApifyExperiment[]
  exceptions: ApifyException[]
}

export type ApifyDashboard = {
  summary: ApifySummary
  accounts: ApifyAccount[]
  bindings: ApifyBinding[]
  runs: ApifyPage<ApifyRun>
  items: ApifyPage<ApifyItem>
  learning: ApifyLearning
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function read<T>(path: string): Promise<T> {
  const token = process.env.CONTROL_TOWER_TOKEN
  if (!token) throw new Error('CONTROL_TOWER_TOKEN is required')
  const response = await fetch(`${API_URL}/api/v1/apify/${path}`, {
    headers: {
      'X-Control-Tower-Token': token,
      'X-Operator-Role': 'viewer',
    },
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`Apify API ${path} failed (${response.status})`)
  return response.json() as Promise<T>
}

export async function fetchApifyDashboard(): Promise<ApifyDashboard> {
  const [summary, accounts, bindings, runs, items, learning] = await Promise.all([
    read<ApifySummary>('summary'),
    read<ApifyAccount[]>('accounts'),
    read<ApifyBinding[]>('bindings'),
    read<ApifyPage<ApifyRun>>('runs'),
    read<ApifyPage<ApifyItem>>('items'),
    read<ApifyLearning>('learning'),
  ])
  return { summary, accounts, bindings, runs, items, learning }
}

export const emptyApifyDashboard: ApifyDashboard = {
  summary: {
    accounts_total: 0,
    accounts_active: 0,
    bindings_total: 0,
    bindings_enabled: 0,
    runs_running: 0,
    runs_failed: 0,
    items_imported: 0,
    exceptions_open: 0,
  },
  accounts: [],
  bindings: [],
  runs: { items: [], total: 0, limit: 50, offset: 0 },
  items: { items: [], total: 0, limit: 50, offset: 0 },
  learning: { profiles: [], experiments: [], exceptions: [] },
}
