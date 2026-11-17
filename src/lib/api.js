const API_ROOT = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      detail = body.detail || body.error || detail
    } catch {
      // Keep the HTTP error when the response is not JSON.
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  return response.json()
}

const json = (method, body) => ({ method, body: JSON.stringify(body) })

export const api = {
  health: () => request('/health'),
  listMemories: (params = {}) => {
    const search = new URLSearchParams({ owner_id: 'user', include_demo: 'true', ...params })
    return request(`/memory/list?${search}`)
  },
  saveMemory: (memory) => request('/memory/save', json('POST', memory)),
  updateMemory: (id, memory) => request(`/memory/${id}`, json('PUT', memory)),
  deleteMemory: (id) => request(`/memory/${id}`, { method: 'DELETE' }),
  resolveMemory: (id) => request(`/memory/${id}/resolve`, json('POST', { action: 'make_current' })),
  retrieve: (query) => request('/memory/retrieve', json('POST', { query, owner_id: 'user', limit: 12 })),
  sessions: () => request('/agent/sessions'),
  messages: (sessionId) => request(`/agent/sessions/${sessionId}/messages`),
  chat: (sessionId, message) => request('/agent/chat', json('POST', { session_id: sessionId, message, owner_id: 'user' })),
  events: (limit = 50) => request(`/system/events?limit=${limit}`),
  outage: () => request('/system/simulate-outage', json('POST', {})),
  restore: () => request('/system/restore-provider', json('POST', {})),
}

export function timeLabel(value, includeDate = false) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en', {
    ...(includeDate ? { month: 'short', day: 'numeric' } : {}),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function relativeTime(value) {
  if (!value) return '—'
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000)
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  if (Math.abs(seconds) < 60) return formatter.format(seconds, 'second')
  const minutes = Math.round(seconds / 60)
  if (Math.abs(minutes) < 60) return formatter.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return formatter.format(hours, 'hour')
  return formatter.format(Math.round(hours / 24), 'day')
}

export const providerLabel = (health) => {
  if (!health) return 'Connecting'
  const status = health.provider?.status
  return ({ online: 'Online', offline: 'Offline', standby: 'Local mode', degraded: 'Degraded' })[status] || status
}
