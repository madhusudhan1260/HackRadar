/** Thin wrapper around the HackRadar API. */

/**
 * Where the API lives.
 *
 * Empty by default, so calls go to /api on the current origin — that is
 * what the Vite dev proxy and a same-origin host both want. Set
 * VITE_API_BASE to an absolute URL when the frontend is served from a
 * different host than the API; the backend's CORS_ORIGINS must then list
 * this site's origin.
 */
const BASE = `${(import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')}/api`
const TOKEN_KEY = 'hackradar_token'

/** Exposed for the handful of calls that must be a real browser navigation
 * (OAuth start) rather than a fetch — those build the URL themselves. */
export const apiBase = BASE

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/** Raised for any non-2xx response, carrying the server's message. */
export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

/** Called when the server rejects our token, so the app can show the login screen. */
let onUnauthorized = () => {}
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Free-tier hosts park idle instances and answer with a platform-level 404
 * or 502 while one wakes up. Retry read-only calls so a cold start looks
 * like a slow load instead of a broken page.
 *
 * Only GETs are retried — replaying a POST could double-create.
 */
async function fetchWithWakeRetry(url, init, attempts = 3) {
  const isRead = !init.method || init.method.toUpperCase() === 'GET'
  let lastError

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, init)
      const wakingUp =
        response.status === 502 ||
        response.status === 503 ||
        // Render marks "no instance running" with this header.
        (response.status === 404 && response.headers.get('x-render-routing') === 'no-server')

      if (!wakingUp || !isRead || attempt === attempts - 1) return response
    } catch (error) {
      lastError = error
      if (!isRead || attempt === attempts - 1) throw error
    }
    await sleep(900 * (attempt + 1))
  }

  throw lastError || new Error('Server unavailable')
}

async function request(path, options = {}) {
  const token = getToken()
  const response = await fetchWithWakeRetry(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })

  if (response.status === 401) {
    setToken('')
    onUnauthorized()
  }

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      // FastAPI sends a string detail, or a list of validation errors.
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail[0]?.msg || message
    } catch {
      /* keep the status-line fallback */
    }
    throw new ApiError(response.status, message)
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

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) })
const patch = (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) })

export const api = {
  health: () => request('/health'),

  // --- auth ---------------------------------------------------------
  register: (payload) => post('/auth/register', payload),
  verifyOtp: (username, code) => post('/auth/verify-otp', { username, code }),
  resendOtp: (username) => post('/auth/resend-otp', { username }),
  login: (username, password, asAdmin = false) =>
    post('/auth/login', { username, password, as_admin: asAdmin }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  forgotPassword: (username) => post('/auth/forgot-password', { username }),
  resetPassword: (username, code, newPassword) =>
    post('/auth/reset-password', { username, code, new_password: newPassword }),
  checkUsername: (username) => request(`/auth/check-username${qs({ username })}`),

  // --- hackathons ----------------------------------------------------
  stats: () => request('/hackathons/stats'),
  list: (filters) => request(`/hackathons${qs(filters)}`),
  detail: (id) => request(`/hackathons/${id}`),
  deadlines: (params = {}) => request(`/hackathons/deadlines${qs(params)}`),

  // --- profile -------------------------------------------------------
  profile: () => request('/profile'),
  saveProfile: (payload) => request('/profile', { method: 'PUT', body: JSON.stringify(payload) }),
  recommendations: (params = {}) => request(`/recommendations${qs(params)}`),

  bookmarks: () => request('/bookmarks'),
  addBookmark: (hackathonId) => post('/bookmarks', { hackathon_id: hackathonId }),
  removeBookmark: (hackathonId) => request(`/bookmarks/${hackathonId}`, { method: 'DELETE' }),

  // --- sources / notifications ---------------------------------------
  sources: () => request('/sources'),
  ingest: (sources) => post('/ingest', { sources: sources ?? null, limit: 200 }),
  notificationPreview: () => request('/notifications/preview'),
  sendNotifications: () => post('/notifications/send', {}),

  // --- internships ------------------------------------------------------
  internships: (filters) => request(`/internships${qs(filters)}`),
  internship: (id) => request(`/internships/${id}`),
  internshipStats: () => request('/internships/stats'),
  bookmarkInternship: (id) => post(`/internships/${id}/bookmark`, {}),
  unbookmarkInternship: (id) => request(`/internships/${id}/bookmark`, { method: 'DELETE' }),
  internshipSources: () => request('/internships/sources'),
  internshipIngest: (sources) => post('/internships/ingest', { sources: sources ?? null, limit: 300 }),

  // --- applications (bookmark status tracker) -------------------------
  applications: () => request('/applications'),
  setHackathonStatus: (id, status) => patch(`/applications/hackathon/${id}/status`, { status }),
  setInternshipStatus: (id, status) => patch(`/applications/internship/${id}/status`, { status }),

  // --- OAuth sign-in ---------------------------------------------------
  oauthProviders: () => request('/auth/oauth/providers'),

  // --- skill builder ----------------------------------------------------
  skillGaps: () => request('/skills/gaps'),

  // --- form filler ----------------------------------------------------
  formReadiness: () => request('/form/readiness'),
  analyseForm: (payload) => post('/form/analyse', payload),
  generateAnswer: (payload) => post('/form/generate', payload),

  // --- admin portal ---------------------------------------------------
  adminOverview: () => request('/admin/overview'),
  adminUsers: (params = {}) => request(`/admin/users${qs(params)}`),
  adminLoginEvents: (params = {}) => request(`/admin/login-events${qs(params)}`),
  adminOtpLog: (params = {}) => request(`/admin/otp-log${qs(params)}`),
  adminResetPassword: (userId, newPassword) =>
    post(`/admin/users/${userId}/reset-password`, { new_password: newPassword }),
  adminSetStatus: (userId, newStatus) =>
    request(`/admin/users/${userId}/status${qs({ new_status: newStatus })}`, { method: 'POST' }),
  adminForceSignout: (userId) => request(`/admin/users/${userId}/sessions`, { method: 'DELETE' }),
  adminDeleteUser: (userId) => request(`/admin/users/${userId}`, { method: 'DELETE' }),
}
