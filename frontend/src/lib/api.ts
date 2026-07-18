// All requests go through /api, which is proxied to the backend (Vite dev + nginx).
const BASE = '/api'

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return (await res.json()) as T
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  config: {
    openai_configured: boolean
    anthropic_configured: boolean
    elasticsearch_url: string
    chroma_persist_dir: string
  }
}

export const getHealth = () => apiGet<HealthResponse>('/health')

// ── Part 1: customers, stores, ingestion ────────────────────────────
export interface CustomerSummary {
  id: string
  name: string
  type: string
  industry?: string | null
  protect_summary: string
  asset_count: number
  ingested: boolean
}

export interface Concern {
  type: string
  note?: string | null
}

export interface Asset {
  id: string
  type: string
  value: string
  aliases: string[]
  concerns: Concern[]
}

export interface CustomerDetail {
  id: string
  name: string
  type: string
  industry?: string | null
  description: string
  protect_summary: string
  assets: Asset[]
  ingested: boolean
}

export interface StoresStatus {
  elasticsearch: { up: boolean; index: string; assets_indexed: number }
  chroma: { up: boolean; collection: string; vectors: number }
  embeddings: { configured: boolean; model: string }
}

export interface IngestStatus {
  ingested_customer_ids: string[]
  total_customers: number
  es_assets: number
  chroma_vectors: number
}

export const getCustomers = () => apiGet<CustomerSummary[]>('/customers')
export const getCustomer = (id: string) => apiGet<CustomerDetail>(`/customers/${id}`)
export const getStoresStatus = () => apiGet<StoresStatus>('/stores/status')
export const getIngestStatus = () => apiGet<IngestStatus>('/ingest/status')

export async function resetIngest(): Promise<void> {
  const res = await fetch('/api/ingest/reset', { method: 'POST' })
  if (!res.ok) throw new Error('reset failed')
}

export async function ingestAll(): Promise<void> {
  const res = await fetch('/api/ingest/all', { method: 'POST' })
  if (!res.ok) throw new Error('ingest all failed')
}

// SSE endpoint URL for ingesting one customer (consumed via EventSource).
export const ingestStreamUrl = (id: string) => `/api/ingest/${id}/stream`

// ── Create a new customer ───────────────────────────────────────────
export interface DraftAsset {
  id?: string
  type: string
  value: string
  aliases?: string[]
  concerns: { type: string; note?: string | null }[]
  keywords?: string[]
}
export interface DraftCustomer {
  id?: string
  name: string
  type: string
  industry?: string | null
  description?: string
  protect_summary: string
  assets: DraftAsset[]
  ingested?: boolean
}

export const suggestCustomer = () => apiGet<DraftCustomer>('/customers/suggest')

export async function createCustomer(
  c: DraftCustomer,
): Promise<{ customer: DraftCustomer; assets_ingested: number }> {
  const res = await fetch('/api/customers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(c),
  })
  if (!res.ok) throw new Error((await res.text()) || 'create failed')
  return res.json()
}

export async function deleteCustomer(id: string): Promise<void> {
  const res = await fetch(`/api/customers/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('delete failed')
}

// ── Part 2: content corpus + pipeline ───────────────────────────────
export interface ContentSummary {
  id: string
  type: string
  origin: string
  label?: string | null
  targets_hint?: string | null
  has_image: boolean
  text_preview: string
}

export interface PipelineStage {
  name: string
  status: 'pending' | 'running' | 'done' | 'error'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  input: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  output: any
  duration_ms?: number | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  meta?: any
}

export interface MetricsSummary {
  total_records: number
  per_stage: { stage: string; count: number; avg_ms: number; max_ms: number }[]
  recent: { run_id: string; content_id: string; stage: string; duration_ms: number; model?: string; at: number }[]
}

export const getMetricsSummary = () => apiGet<MetricsSummary>('/metrics/summary')

export interface PipelineContent {
  id: string
  type: string
  label?: string | null
  text?: string | null
  image_path?: string | null
  has_image: boolean
}

export interface PipelineRun {
  run_id: string
  content_id: string
  content: PipelineContent
  stages: PipelineStage[]
  cursor: number
  done: boolean
}

export const getContentList = () => apiGet<ContentSummary[]>('/content')
export const contentImageUrl = (id: string) => `/api/content/${id}/image`

export async function startPipeline(contentId: string): Promise<PipelineRun> {
  const res = await fetch(`/api/pipeline/start?content_id=${encodeURIComponent(contentId)}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('failed to start pipeline')
  return res.json()
}

export async function stepPipeline(runId: string): Promise<PipelineRun> {
  const res = await fetch(`/api/pipeline/${runId}/step`, { method: 'POST' })
  if (!res.ok) throw new Error('pipeline step failed')
  return res.json()
}
