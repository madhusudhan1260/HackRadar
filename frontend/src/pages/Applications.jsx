import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { buildBulkIcs, deadlineLabel } from '../format'

const STATUSES = [
  { key: 'saved', label: 'Saved', cls: '' },
  { key: 'applied', label: 'Applied', cls: 'cool' },
  { key: 'interviewing', label: 'Interviewing', cls: 'warn' },
  { key: 'rejected', label: 'Rejected', cls: 'hot' },
  { key: 'accepted', label: 'Accepted', cls: 'good' },
]
const STATUS_LABEL = Object.fromEntries(STATUSES.map((s) => [s.key, s.label]))
const STATUS_CLASS = Object.fromEntries(STATUSES.map((s) => [s.key, s.cls]))

const FILTERS = [{ key: 'all', label: 'All' }, ...STATUSES]

/**
 * The application tracker: everything bookmarked, hackathon or internship,
 * in one list with a status you control. Reads/writes /api/applications
 * rather than the hackathon/internship list endpoints — a status change
 * here never touches the bookmark itself.
 */
export default function Applications({ toast }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    api
      .applications()
      .then((data) => setItems(data.items))
      .then(() => setError(''))
      .catch((err) => setError(err.message))
  }

  useEffect(load, [])

  const changeStatus = async (item, status) => {
    const busyKey = `${item.kind}-${item.id}`
    setBusyId(busyKey)
    const prev = items
    setItems((current) => current.map((row) => (row === item ? { ...row, status } : row)))
    try {
      const call = item.kind === 'hackathon' ? api.setHackathonStatus : api.setInternshipStatus
      await call(item.id, status)
      toast?.success(`Marked ${STATUS_LABEL[status].toLowerCase()}`)
    } catch (err) {
      setItems(prev)
      toast?.error(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const exportCalendar = () => {
    const withDeadlines = (items || []).filter((item) => item.deadline)
    if (!withDeadlines.length) {
      toast?.info('Nothing with a deadline to export yet')
      return
    }
    const url = URL.createObjectURL(buildBulkIcs(withDeadlines))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'hackradar-deadlines.ics'
    anchor.click()
    URL.revokeObjectURL(url)
    toast?.success(`Exported ${withDeadlines.length} deadline${withDeadlines.length === 1 ? '' : 's'}`)
  }

  const counts = useMemo(() => {
    const base = Object.fromEntries(STATUSES.map((s) => [s.key, 0]))
    ;(items || []).forEach((item) => {
      base[item.status] = (base[item.status] || 0) + 1
    })
    return base
  }, [items])

  const visible = (items || []).filter((item) => filter === 'all' || item.status === filter)

  if (error) return <div className="error-banner">⚠ {error}</div>
  if (!items) return <div className="empty">Loading applications…</div>

  return (
    <div className="page-applications">
      <div className="topbar">
        <h1 className="page-title" style={{ margin: 0 }}>📋 Applications</h1>
        <button className="btn primary" onClick={exportCalendar} style={{ marginLeft: 'auto' }}>
          📅 Export calendar (.ics)
        </button>
      </div>
      <p className="view-intro">
        Every hackathon and internship you've saved, in one place, with what actually happened next.
      </p>

      <div className="chips" style={{ marginBottom: 20 }}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`chip ${filter === f.key ? 'on' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label} {f.key !== 'all' && <span style={{ opacity: 0.6 }}>({counts[f.key] || 0})</span>}
          </button>
        ))}
      </div>

      {items.length === 0 && (
        <div className="empty">
          <div className="big">📋</div>
          <p>Nothing saved yet.</p>
          <p className="empty-hint">
            Bookmark a hackathon or internship and it'll show up here, ready to track.
          </p>
        </div>
      )}

      {items.length > 0 && visible.length === 0 && (
        <div className="empty">
          <p>Nothing with that status yet.</p>
        </div>
      )}

      {visible.length > 0 && (
        <div className="application-list">
          {visible.map((item) => {
            const busyKey = `${item.kind}-${item.id}`
            return (
              <div key={busyKey} className="board-row application-row">
                <span className="kind-icon">{item.kind === 'hackathon' ? '🛩' : '💼'}</span>
                <div className="info">
                  <a className="name" href={item.url} target="_blank" rel="noreferrer">
                    {item.title}
                  </a>
                  <div className="when">
                    {item.organizer && <span>{item.organizer} · </span>}
                    {deadlineLabel(item.days_left, item.deadline)}
                    {item.value_display !== '—' && <span> · {item.value_display}</span>}
                  </div>
                </div>
                <span className={`status-pill ${STATUS_CLASS[item.status]}`}>
                  {STATUS_LABEL[item.status]}
                </span>
                <select
                  className="btn"
                  value={item.status}
                  disabled={busyId === busyKey}
                  onChange={(event) => changeStatus(item, event.target.value)}
                  aria-label={`Status for ${item.title}`}
                >
                  {STATUSES.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
