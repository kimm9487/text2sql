import type { Country, LogStats, QueryLog, QueryResponse, SchemaTable, User } from '../types'
import { clearAuth, getToken } from './auth'

// 401(토큰 만료) 시 App 이 로그인 화면으로 보내도록 전역 이벤트를 쏜다
export const AUTH_EXPIRED_EVENT = 't2s-auth-expired'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers as Record<string, string> | undefined),
    },
  })
  if (res.status === 401 && token) {
    clearAuth()
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  }
  if (!res.ok) {
    let detail = `요청 실패 (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* JSON 이 아닌 응답 */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export function login(loginId: string, password: string) {
  return request<{ access_token: string; user: User }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login_id: loginId, password }),
  })
}

export function runQuery(question: string, country: Country) {
  return request<QueryResponse>('/api/query', {
    method: 'POST',
    body: JSON.stringify({ question, country }),
  })
}

export function getExamples() {
  return request<{ items: string[] }>('/api/examples')
}

export function getSchema() {
  return request<{ tables: SchemaTable[] }>('/api/schema')
}

export function getHealth() {
  return request<{ status: string; db: string; llm: { provider: string; enabled: boolean; model: string } }>(
    '/api/health',
  )
}

export function getLogs(status?: string) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return request<{ stats: LogStats; items: QueryLog[] }>(`/api/admin/logs${qs}`)
}
