import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import Filters from './components/Filters'
import HackathonCard from './components/HackathonCard'
import HackathonDetail from './components/HackathonDetail'
import DeadlineBoard from './components/DeadlineBoard'
import ProfilePanel from './components/ProfilePanel'
import SourcesPanel from './components/SourcesPanel'
import AdminPortal from './pages/AdminPortal'
import Login from './pages/Login'
import { useAuth } from './auth'

const DEFAULT_FILTERS = {
  q: '',
  region: 'all',
  category: [],
  mode: 'all',
  prize: '',
  within_days: '',
  free_only: false,
  student_only: false,
  team_size: '',
  group_duplicates: true,
  sort: 'priority',
  page: 1,
  per_page: 24,
}

const VIEWS = [
  { key: 'discover', icon: '🔎', label: 'Discover' },
  { key: 'deadlines', icon: '🔥', label: 'Deadlines' },
  { key: 'foryou', icon: '🧠', label: 'For You' },
  { key: 'saved', icon: '⭐', label: 'Saved' },
  { key: 'profile', icon: '👤', label: 'Profile' },
  { key: 'sources', icon: '🔌', label: 'Sources' },
]

export default function App() {
  const { user, ready, signOut, isAdmin } = useAuth()
  const [view, setView] = useState('discover')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [stats, setStats] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const bumpRefresh = useCallback(() => setRefreshKey((key) => key + 1), [])

  // Debounce the search box so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((current) => ({ ...current, q: search, page: 1 }))
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  // Admins land in their portal; they can still reach every other view.
  useEffect(() => {
    if (user?.role === 'admin') setView('admin')
  }, [user?.id, user?.role])

  useEffect(() => {
    if (!user) return
    api.stats().then(setStats).catch(() => {})
  }, [refreshKey, user])

  useEffect(() => {
    if (!user) return undefined
    if (!['discover', 'saved', 'foryou'].includes(view)) return undefined

    let cancelled = false
    setLoading(true)
    setError(null)

    const request =
      view === 'foryou'
        ? api.recommendations({ limit: 24, min_score: 40 }).then((items) => ({
            items,
            total: items.length,
            page: 1,
            per_page: items.length || 1,
          }))
        : api.list(view === 'saved' ? { ...filters, bookmarked_only: true } : filters)

    request
      .then((result) => !cancelled && setData(result))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))

    return () => {
      cancelled = true
    }
  }, [view, filters, refreshKey, user])

  const toggleBookmark = useCallback(
    async (item) => {
      // Optimistic flip so the star responds instantly.
      const flip = (list) =>
        list.map((row) => (row.id === item.id ? { ...row, bookmarked: !row.bookmarked } : row))
      setData((current) => (current ? { ...current, items: flip(current.items) } : current))
      setSelected((current) =>
        current && current.id === item.id ? { ...current, bookmarked: !current.bookmarked } : current,
      )

      try {
        if (item.bookmarked) {
          await api.removeBookmark(item.id)
        } else {
          await api.addBookmark(item.id)
        }
        if (view === 'saved') bumpRefresh()
      } catch (err) {
        setError(err.message)
        bumpRefresh()
      }
    },
    [view, bumpRefresh],
  )

  const openDetail = useCallback(async (item) => {
    setSelected(item)
    try {
      setSelected(await api.detail(item.id))
    } catch {
      /* keep the list version we already have */
    }
  }, [])

  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1),
    [data],
  )

  const showsList = ['discover', 'saved', 'foryou'].includes(view)

  if (!ready) {
    return <div className="empty" style={{ paddingTop: '25vh' }}>Loading…</div>
  }
  if (!user) return <Login />

  return (
    <div className="app">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-mark">📡</div>
          <h1>HackRadar</h1>
        </div>
        <p className="brand-tag">One place for every hackathon</p>

        <nav className="nav">
          {VIEWS.map((entry) => (
            <button
              key={entry.key}
              className={view === entry.key ? 'active' : ''}
              onClick={() => {
                setView(entry.key)
                setSidebarOpen(false)
              }}
            >
              <span>{entry.icon}</span>
              <span>{entry.label}</span>
              {entry.key === 'discover' && stats && <span className="count">{stats.open}</span>}
              {entry.key === 'deadlines' && stats && (
                <span className="count">{stats.closing_this_week}</span>
              )}
            </button>
          ))}
        </nav>

        {isAdmin && (
          <nav className="nav" style={{ marginTop: -14 }}>
            <button
              className={view === 'admin' ? 'active' : ''}
              onClick={() => {
                setView('admin')
                setSidebarOpen(false)
              }}
            >
              <span>🛡️</span>
              <span>Admin portal</span>
            </button>
          </nav>
        )}

        <div className="account-box">
          <div className="account-name">
            {user.name}
            {isAdmin && <span className="role-tag">admin</span>}
          </div>
          <div className="account-meta">@{user.username} · {user.phone_masked}</div>
          <button className="link-btn" onClick={signOut}>
            Sign out
          </button>
        </div>

        {view === 'discover' && (
          <Filters
            filters={filters}
            setFilters={setFilters}
            categoryCounts={stats?.by_category}
          />
        )}
      </aside>

      <main className="main">
        {showsList && (
          <div className="topbar">
            <button
              className="btn mobile-toggle"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle filters"
            >
              ☰
            </button>
            <div className="search">
              <span className="icon">🔎</span>
              <input
                type="search"
                placeholder="Search hackathons, organisers, technologies…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            {view === 'discover' && (
              <select
                className="btn"
                value={filters.sort}
                onChange={(event) =>
                  setFilters({ ...filters, sort: event.target.value, page: 1 })
                }
              >
                <option value="priority">⚡ Priority (urgency + match)</option>
                <option value="deadline">📅 Nearest deadline</option>
                <option value="match">🧠 Best match</option>
                <option value="prize">💰 Biggest prize</option>
                <option value="recent">🆕 Recently added</option>
                <option value="title">🔤 Title</option>
              </select>
            )}
          </div>
        )}

        {view === 'discover' && stats && (
          <div className="stat-row">
            <div className="stat">
              <div className="value">{stats.open}</div>
              <div className="label">Open now</div>
            </div>
            <div className="stat hot">
              <div className="value">{stats.closing_this_week}</div>
              <div className="label">Closing this week</div>
            </div>
            <div className="stat">
              <div className="value">{stats.india}</div>
              <div className="label">🇮🇳 In India</div>
            </div>
            <div className="stat">
              <div className="value">{stats.online}</div>
              <div className="label">Online</div>
            </div>
            <div className="stat">
              <div className="value">{stats.student}</div>
              <div className="label">Student-friendly</div>
            </div>
            <div className="stat">
              <div className="value">{Object.keys(stats.by_source).length}</div>
              <div className="label">Sources</div>
            </div>
          </div>
        )}

        {error && <div className="error-banner">⚠ {error}</div>}

        {view === 'deadlines' && <DeadlineBoard onOpen={openDetail} refreshKey={refreshKey} />}
        {view === 'profile' && <ProfilePanel onSaved={bumpRefresh} />}
        {view === 'sources' && <SourcesPanel onIngested={bumpRefresh} />}
        {view === 'admin' && isAdmin && <AdminPortal />}

        {showsList && (
          <>
            {view === 'foryou' && (
              <p style={{ color: 'var(--text-dim)', marginTop: 0 }}>
                Ranked by how well each event matches the skills and interests in your
                profile.
              </p>
            )}

            {loading && (
              <div className="grid">
                {Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="skeleton" />
                ))}
              </div>
            )}

            {!loading && data && data.items.length === 0 && (
              <div className="empty">
                <div className="big">{view === 'saved' ? '⭐' : '🔍'}</div>
                <p>
                  {view === 'saved'
                    ? 'No saved hackathons yet — tap the star on any card.'
                    : 'Nothing matches these filters. Try widening them.'}
                </p>
              </div>
            )}

            {!loading && data && data.items.length > 0 && (
              <>
                <div className="grid">
                  {data.items.map((item) => (
                    <HackathonCard
                      key={item.id}
                      item={item}
                      onOpen={openDetail}
                      onToggleBookmark={toggleBookmark}
                    />
                  ))}
                </div>

                {view === 'discover' && totalPages > 1 && (
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
          </>
        )}
      </main>

      {selected && (
        <HackathonDetail
          item={selected}
          onClose={() => setSelected(null)}
          onToggleBookmark={toggleBookmark}
        />
      )}
    </div>
  )
}
