import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

function when(value) {
  if (!value) return 'never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AdminPortal() {
  const [overview, setOverview] = useState(null)
  const [users, setUsers] = useState([])
  const [events, setEvents] = useState([])
  const [otpRows, setOtpRows] = useState([])
  const [tab, setTab] = useState('users')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [onlyFailed, setOnlyFailed] = useState(false)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setError('')
    api.adminOverview().then(setOverview).catch((err) => setError(err.message))
    api
      .adminUsers({ q: query, status_filter: statusFilter })
      .then(setUsers)
      .catch((err) => setError(err.message))
    api
      .adminLoginEvents({ limit: 100, only_failed: onlyFailed })
      .then(setEvents)
      .catch((err) => setError(err.message))
    api.adminOtpLog({ limit: 50 }).then(setOtpRows).catch(() => {})
  }, [query, statusFilter, onlyFailed])

  useEffect(() => {
    const timer = setTimeout(load, 250)
    return () => clearTimeout(timer)
  }, [load])

  const toggleBlock = async (user) => {
    setBusyId(user.id)
    try {
      await api.adminSetStatus(user.id, user.status === 'blocked' ? 'active' : 'blocked')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const forceSignout = async (user) => {
    setBusyId(user.id)
    try {
      const result = await api.adminForceSignout(user.id)
      setError('')
      alert(`Signed ${user.username} out of ${result.sessions_revoked} session(s).`)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <div className="topbar">
        <h2 style={{ margin: 0, fontSize: 18 }}>🛡️ Admin portal</h2>
        <span className="admin-pill">Restricted</span>
        <button className="btn" onClick={load}>
          ↻ Refresh
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {overview && (
        <>
          <div className="stat-row">
            <div className="stat">
              <div className="value">{overview.total_users}</div>
              <div className="label">Total users</div>
            </div>
            <div className="stat">
              <div className="value">{overview.active_users}</div>
              <div className="label">Active</div>
            </div>
            <div className="stat">
              <div className="value">{overview.pending_users}</div>
              <div className="label">Pending OTP</div>
            </div>
            <div className="stat">
              <div className="value">{overview.logins_today}</div>
              <div className="label">Logins today</div>
            </div>
            <div className="stat hot">
              <div className="value">{overview.failed_logins_today}</div>
              <div className="label">Failed today</div>
            </div>
            <div className="stat">
              <div className="value">{overview.admins}</div>
              <div className="label">Admins</div>
            </div>
          </div>

          <div className={`sms-banner ${overview.sms.is_live ? 'live' : ''}`}>
            <strong>SMS: {overview.sms.provider}</strong> — {overview.sms.note}
          </div>
        </>
      )}

      <div className="auth-tabs" style={{ maxWidth: 460, marginBottom: 16 }}>
        <button className={tab === 'users' ? 'on' : ''} onClick={() => setTab('users')}>
          Users
        </button>
        <button className={tab === 'activity' ? 'on' : ''} onClick={() => setTab('activity')}>
          Login activity
        </button>
        <button className={tab === 'sms' ? 'on' : ''} onClick={() => setTab('sms')}>
          SMS delivery
        </button>
      </div>

      {tab === 'users' && (
        <>
          <div className="topbar">
            <div className="search">
              <span className="icon">🔎</span>
              <input
                type="search"
                placeholder="Search by name, username or phone…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <select
              className="btn"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending OTP</option>
              <option value="blocked">Blocked</option>
            </select>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Username</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th className="num">Logins</th>
                  <th>Last login</th>
                  <th>Registered</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      {user.name}
                      {user.role === 'admin' && <span className="role-tag">admin</span>}
                    </td>
                    <td className="mono">{user.username}</td>
                    <td className="mono">{user.phone}</td>
                    <td>
                      <span className={`status-tag ${user.status}`}>{user.status}</span>
                    </td>
                    <td className="num">{user.login_count}</td>
                    <td className="dim">{when(user.last_login_at)}</td>
                    <td className="dim">{when(user.created_at)}</td>
                    <td className="row-actions">
                      {user.active_sessions > 0 && (
                        <button
                          className="link-btn"
                          disabled={busyId === user.id}
                          onClick={() => forceSignout(user)}
                        >
                          Sign out ({user.active_sessions})
                        </button>
                      )}
                      {user.role !== 'admin' && (
                        <button
                          className="link-btn danger"
                          disabled={busyId === user.id}
                          onClick={() => toggleBlock(user)}
                        >
                          {user.status === 'blocked' ? 'Unblock' : 'Block'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={8} className="dim" style={{ textAlign: 'center', padding: 30 }}>
                      No users match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'sms' && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Sent to</th>
                <th>Name</th>
                <th>Purpose</th>
                <th>Delivery</th>
                <th>State</th>
                <th>Provider note</th>
              </tr>
            </thead>
            <tbody>
              {otpRows.map((row) => (
                <tr key={row.id}>
                  <td className="dim">{when(row.created_at)}</td>
                  <td className="mono">{row.phone}</td>
                  <td>{row.name || <span className="dim">—</span>}</td>
                  <td className="mono">{row.purpose}</td>
                  <td>
                    <span className={`status-tag ${row.delivered ? 'active' : 'blocked'}`}>
                      {row.delivered ? 'sent' : 'failed'}
                    </span>
                  </td>
                  <td className="dim">
                    {row.consumed ? 'used' : row.expired ? 'expired' : 'pending'}
                    {row.attempts > 0 && ` · ${row.attempts} try`}
                  </td>
                  <td className="dim">{row.delivery_note || '—'}</td>
                </tr>
              ))}
              {otpRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="dim" style={{ textAlign: 'center', padding: 30 }}>
                    No codes sent yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'activity' && (
        <>
          <div className="topbar">
            <button
              className={`btn ${onlyFailed ? 'primary' : ''}`}
              onClick={() => setOnlyFailed(!onlyFailed)}
            >
              ⚠ Failed attempts only
            </button>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Event</th>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Result</th>
                  <th>Detail</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td className="dim">{when(event.created_at)}</td>
                    <td className="mono">{event.event}</td>
                    <td>{event.name || <span className="dim">unknown</span>}</td>
                    <td className="mono">{event.phone || '—'}</td>
                    <td>
                      <span className={`status-tag ${event.success ? 'active' : 'blocked'}`}>
                        {event.success ? 'success' : 'failed'}
                      </span>
                    </td>
                    <td className="dim">
                      {event.reason ||
                        (!event.success && event.username_tried
                          ? `tried "${event.username_tried}"`
                          : '—')}
                    </td>
                    <td className="mono dim">{event.ip || '—'}</td>
                  </tr>
                ))}
                {events.length === 0 && (
                  <tr>
                    <td colSpan={7} className="dim" style={{ textAlign: 'center', padding: 30 }}>
                      No activity recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
