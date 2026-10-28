import type {
  ChatAccepted,
  IntentAnalysis,
  SessionDetail,
  SessionSummary,
  TaskRecord,
} from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(payload.detail ?? `HTTP ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  listSessions: () => request<SessionSummary[]>('/api/sessions'),
  createSession: (title = '新建投研会话') =>
    request<SessionSummary>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  getSession: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  deleteSession: (id: string) =>
    request<void>(`/api/sessions/${id}`, { method: 'DELETE' }),
  getTask: (id: string) => request<TaskRecord>(`/api/tasks/${id}`),
  cancelTask: (id: string) =>
    request<TaskRecord>(`/api/tasks/${id}/cancel`, { method: 'POST' }),
  parseIntent: (query: string) =>
    request<IntentAnalysis>('/api/intent', {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
  submitChat: (
    query: string,
    sessionId?: string,
    architecture = 'react_multi_agent',
  ) =>
    request<ChatAccepted>('/api/chat', {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        architecture,
      }),
    }),
  eventUrl: (path: string) => `${API_BASE}${path}`,
}
