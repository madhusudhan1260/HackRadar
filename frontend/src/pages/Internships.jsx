import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import CountUp from '../components/CountUp'
import InternshipCard from '../components/InternshipCard'
import InternshipDetail from '../components/InternshipDetail'

const REGIONS = [
  { key: 'all', label: '🌐 All' },
  { key: 'india', label: '🇮🇳 India' },
  { key: 'global', label: '🌎 Global' },
]

const MODES = [
  { key: 'all', label: 'Any' },
  { key: 'remote', label: '🌐 Remote' },
  { key: 'onsite', label: '📍 On-site' },
  { key: 'hybrid', label: '🔀 Hybrid' },
]

/**
 * Internships, mirroring Discover's shape but scoped to its own table and
 * its own lean matcher — stipend and duration stand in for prize and team
 * size, and there is no shared listing with hackathons to de-duplicate.
 */
export default function Internships({ toast }) {
  const [filters, setFilters] = useState({
    q: '', region: 'all', mode: 'all', paid_only: false, sort: 'match', page: 1,
  })
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [stats, setStats] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.internshipStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== filters.q) setFilters((f) => ({ ...f, q: search, page: 1 }))
    }, 320)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .internships({ ...filters, per_page: 24 })
      .then((result) => !cancelled && setData(result))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [filters])

  const openDetail = useCallback(async (item) => {
    setSelected(item)
    try {
      setSelected(await api.internship(item.id))
    } catch {
      /* keep the list version */
    }
  }, [])

  const toggleBookmark = useCallback(
    async (item) => {
      const flip = (list) =>
        list.map((row) => (row.id === item.id ? { ...row, bookmarked: !row.bookmarked } : row))
      setData((current) => (current ? { ...current, items: flip(current.items) } : current))
      setSelected((current) =>
        current && current.id === item.id ? { ...current, bookmarked: !current.bookmarked } : current,
      )
      try {
        if (item.bookmarked) {
          await api.unbookmarkInternship(item.id)
          toast?.info('Removed from saved')
        } else {
          await api.bookmarkInternship(item.id)
          toast?.success('Saved to your list')
        }
      } catch (err) {
        toast?.error(err.message)
      }
    },
    [toast],
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1

  return (
    <div className="page-internships">
      <div className="topbar">
        <Link to="/" className="btn">
          ← Home
        </Link>
        <div className="search">
          <span className="icon">🔎</span>
          <input
            type="search"
            placeholder="Search internships, companies, technologies…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select
          className="btn"
          value={filters.sort}
          onChange={(event) => setFilters({ ...filters, sort: event.target.value, page: 1 })}
        >
          <option value="match">🧠 Best match</option>
          <option value="deadline">📅 Nearest deadline</option>
          <option value="stipend">💰 Highest stipend</option>
          <option value="recent">🆕 Recently added</option>
          <option value="title">🔤 Title</option>
        </select>
      </div>

      <h1 className="page-title">💼 Internships</h1>

      {stats && (
        <div className="stat-row">
          <div className="stat">
            <div className="value"><CountUp value={stats.open} /></div>
            <div className="label">Open</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.remote} /></div>
            <div className="label">Remote</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.india} /></div>
            <div className="label">🇮🇳 In India</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.paid} /></div>
            <div className="label">Paid</div>
          </div>
          <div className="stat">
            <div className="value">
              <CountUp value={Object.keys(stats.by_source).length} duration={700} />
            </div>
            <div className="label">Sources</div>
          </div>
        </div>
      )}

      <div className="chips" style={{ marginBottom: 10 }}>
        {REGIONS.map((r) => (
          <button
            key={r.key}
            className={`chip ${filters.region === r.key ? 'on' : ''}`}
            onClick={() => setFilters({ ...filters, region: r.key, page: 1 })}
          >
            {r.label}
          </button>
        ))}
      </div>
      <div className="chips" style={{ marginBottom: 16 }}>
        {MODES.map((m) => (
          <button
            key={m.key}
            className={`chip ${filters.mode === m.key ? 'on' : ''}`}
            onClick={() => setFilters({ ...filters, mode: m.key, page: 1 })}
          >
            {m.label}
          </button>
        ))}
        <button
          className={`chip ${filters.paid_only ? 'on' : ''}`}
          onClick={() => setFilters({ ...filters, paid_only: !filters.paid_only, page: 1 })}
        >
          💰 Paid only
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {loading && (
        <div className="grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="skeleton" />
          ))}
        </div>
      )}

      {!loading && data && data.items.length === 0 && (
        <div className="empty">
          <div className="big">💼</div>
          <p>Nothing matches these filters.</p>
          <p className="empty-hint">Sourced from Remotive and an open internship tracker — mostly US tech roles today. Try widening the filters.</p>
        </div>
      )}

      {!loading && data && data.items.length > 0 && (
        <>
          <div className="grid">
            {data.items.map((item, index) => (
              <InternshipCard
                key={item.id}
                index={index}
                item={item}
                onOpen={openDetail}
                onToggleBookmark={toggleBookmark}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="pager">
              <button
                className="btn"
                disabled={filters.page <= 1}
                onClick={() => setFilters({ ...filters, page: filters.page - 1 })}
              >
                ← Previous
              </button>
              <span>
                Page {data.page} of {totalPages} · {data.total} results
              </span>
              <button
                className="btn"
                disabled={filters.page >= totalPages}
                onClick={() => setFilters({ ...filters, page: filters.page + 1 })}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      {selected && (
        <InternshipDetail
          item={selected}
          onClose={() => setSelected(null)}
          onToggleBookmark={toggleBookmark}
        />
      )}
    </div>
  )
}
