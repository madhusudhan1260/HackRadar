/** Thin wrapper around the HackRadar API. */

const BASE = '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(`${response.status} ${response.statusText} — ${detail.slice(0, 200)}`)
  }
  return response.status === 204 ? null : response.json()
}

/** Build a query string, dropping empty values and expanding arrays. */
function qs(params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === false) return
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, item))
    } else {
      search.append(key, value)
    }
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/hackathons/stats'),
  list: (filters) => request(`/hackathons${qs(filters)}`),
  detail: (id) => request(`/hackathons/${id}`),
  deadlines: (params = {}) => request(`/hackathons/deadlines${qs(params)}`),

  profile: () => request('/profile'),
  saveProfile: (payload) =>
    request('/profile', { method: 'PUT', body: JSON.stringify(payload) }),
  recommendations: (params = {}) => request(`/recommendations${qs(params)}`),

  bookmarks: () => request('/bookmarks'),
  addBookmark: (hackathonId) =>
    request('/bookmarks', {
      method: 'POST',
      body: JSON.stringify({ hackathon_id: hackathonId }),
    }),
  removeBookmark: (hackathonId) =>
    request(`/bookmarks/${hackathonId}`, { method: 'DELETE' }),

  sources: () => request('/sources'),
  ingest: (sources) =>
    request('/ingest', {
      method: 'POST',
      body: JSON.stringify({ sources: sources ?? null, limit: 200 }),
    }),
  notificationPreview: () => request('/notifications/preview'),
}
