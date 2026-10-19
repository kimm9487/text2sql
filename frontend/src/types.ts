export type Country = 'ALL' | 'KR' | 'JP' | 'TW'

export interface User {
  id: number
  login_id: string
  name: string
  department: string
  role: 'employee' | 'admin'
}

export type Row = Record<string, string | number | null>

export interface Step {
  key: string
  label: string
  status: 'ok' | 'blocked' | 'error' | 'info'
  detail: string
  ms: number
}

export interface ChartSpec {
  type: 'line' | 'bar' | 'pie'
  x: string
  y: string[]
  series: string | null
}

export interface SummaryCard {
  label: string
  value: number | string | null
  unit: string
}

export interface QueryResponse {
  question: string
  country: Country
  intent: 'sql' | 'chat' | 'weather' | null
  status: 'success' | 'blocked' | 'error' | 'chat'
  message: string | null
  sql_source: 'template' | 'llm' | null
  template: { name: string; title: string; notes: string[] } | null
  date_range: { start: string; end: string; label: string } | null
  sql: string | null
  columns: string[]
  rows: Row[]
  row_count: number
  truncated: boolean
  chart: ChartSpec | null
  summary: SummaryCard[]
  masked_count: number
  warnings: string[]
  llm: { model: string; latency_ms: number; input_tokens: number; output_tokens: number } | null
  steps: Step[]
  elapsed_ms: number
}

export interface ChatMessage {
  id: number
  question: string
  country: Country
  loading: boolean
  response?: QueryResponse
  error?: string
}

export interface QueryLog {
  id: number
  created_at: string
  login_id: string | null
  country: string
  question: string
  intent: string | null
  sql_source: string | null
  status: 'success' | 'blocked' | 'error' | 'chat'
  block_reason: string | null
  sql: string | null
  row_count: number | null
  elapsed_ms: number | null
}

export interface LogStats {
  total: number
  success: number
  blocked: number
  error: number
  template: number
  llm: number
  today: number
}

export interface SchemaTable {
  table: string
  label: string
  description: string
  columns: { name: string; description: string }[]
}
