import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import { api } from './api'
import { useAuth } from './auth'
import { useToast } from './components/Toast'
import CountUp from './components/CountUp'
import RadarMark from './components/RadarMark'
import Filters from './components/Filters'
import HackathonCard from './components/HackathonCard'
import HackathonDetail from './components/HackathonDetail'
import DeadlineBoard from './components/DeadlineBoard'
import ProfilePanel from './components/ProfilePanel'
import SourcesPanel from './components/SourcesPanel'
import AssistantPanel from './components/AssistantPanel'
import AdminPortal from './pages/AdminPortal'
import FormFiller from './pages/FormFiller'
import Hub from './pages/Hub'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import SkillBuilder from './pages/SkillBuilder'

/** Filters that live in the URL, so a filtered view can be shared. */
const URL_FILTERS = {
  q: '',
  region: 'all',
  mode: 'all',
  prize: '',
  sort: 'priority',
  page: 1,
}

/** Filters kept in component state — too fiddly to be worth a URL param. */
const LOCAL_FILTERS = {
  within_days: '',
  free_only: false,
  student_only: false,
  team_size: '',
  group_duplicates: true,
  per_page: 24,
}

const VIEWS = [
  { path: '/', icon: '🏠', label: 'Home', end: true },
  { path: '/hackathons', icon: '🔎', label: 'Hackathons' },
  { path: '/deadlines', icon: '🔥', label: 'Deadlines' },
  { path: '/for-you', icon: '🧠', label: 'For You' },
  { path: '/saved', icon: '⭐', label: 'Saved' },
  { path: '/form-filler', icon: '✨', label: 'Form Filling AI' },
  { path: '/skills', icon: '🎯', label: 'Skill Builder' },
  { path: '/profile', icon: '👤', label: 'Profile' },
  { path: '/sources', icon: '🔌', label: 'Sources' },
]

export default function App() {
  const { user, ready, signOut, isAdmin } = useAuth()

  if (!ready) {
    return (
      <div className="boot-screen">
        <RadarMark size={44} />
        <p>Loading HackRadar…</p>
      </div>
    )
  }

  // Unauthenticated: every path shows the login screen.
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }

  return <Dashboard signOut={signOut} isAdmin={isAdmin} user={user} />
}

function Dashboard({ signOut, isAdmin, user }) {
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [localFilters, setLocalFilters] = useState(LOCAL_FILTERS)
  const [stats, setStats] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const bumpRefresh = useCallback(() => setRefreshKey((key) => key + 1), [])

  // Merge the URL params over the defaults to get the live filter set.
  const filters = useMemo(() => {
    const fromUrl = {}
    Object.entries(URL_FILTERS).forEach(([key, fallback]) => {
      const raw = searchParams.get(key)
      fromUrl[key] = raw === null ? fallback : key === 'page' ? Number(raw) || 1 : raw
    })
    return {
      ...localFilters,
      ...fromUrl,
      category: searchParams.getAll('category'),
    }
  }, [searchParams, localFilters])

  /** URL-backed keys go to the address bar; the rest to local state. */
  const setFilters = useCallback(
    (next) => {
      const params = new URLSearchParams()
      Object.entries(URL_FILTERS).forEach(([key, fallback]) => {
        const value = next[key]
        // Only non-default values are written, so links stay readable.
        if (value !== undefined && value !== '' && value !== fallback) {
          params.set(key, String(value))
        }
      })
      ;(next.category || []).forEach((c) => params.append('category', c))

      const localPatch = {}
      Object.keys(LOCAL_FILTERS).forEach((key) => {
        if (next[key] !== undefined) localPatch[key] = next[key]
      })
      setLocalFilters((current) => ({ ...current, ...localPatch }))
      setSearchParams(params, { replace: true })
    },
    [setSearchParams],
  )

  useEffect(() => {
    api.stats().then(setStats).catch(() => {})
  }, [refreshKey])

  const openDetail = useCallback((item) => navigate(`/hackathon/${item.id}`), [navigate])

  const shared = { filters, setFilters, stats, refreshKey, bumpRefresh, openDetail, toast }

  return (
    <div className="app">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <Link to="/" className="brand" onClick={() => setSidebarOpen(false)}>
          <RadarMark size={34} />
          <h1>HackRadar</h1>
        </Link>
        <p className="brand-tag">One place for every hackathon</p>

        <nav className="nav">
          {VIEWS.map((entry) => (
            <NavLink
              key={entry.path}
              to={entry.path}
              end={entry.end}
              className={({ isActive }) => (isActive ? 'active' : '')}
              onClick={() => setSidebarOpen(false)}
            >
              <span>{entry.icon}</span>
              <span>{entry.label}</span>
              {entry.path === '/hackathons' && stats && <span className="count">{stats.open}</span>}
              {entry.path === '/deadlines' && stats && (
                <span className="count">{stats.closing_this_week}</span>
              )}
            </NavLink>
          ))}
        </nav>

        {isAdmin && (
          <nav className="nav" style={{ marginTop: -14 }}>
            <NavLink
              to="/admin"
              className={({ isActive }) => (isActive ? 'active' : '')}
              onClick={() => setSidebarOpen(false)}
            >
              <span>🛡️</span>
              <span>Admin portal</span>
            </NavLink>
          </nav>
        )}

        <div className="account-box">
          <div className="account-name">
            {user.name}
            {isAdmin && <span className="role-tag">admin</span>}
          </div>
          <div className="account-meta">
            @{user.username} · {user.phone_masked}
          </div>
          <button className="link-btn" onClick={signOut}>
            Sign out
          </button>
        </div>

        {/* Filters only apply to the Discover list. */}
        <Routes>
          <Route
            path="/hackathons"
            element={
              <Filters
                filters={filters}
                setFilters={setFilters}
                categoryCounts={stats?.by_category}
              />
            }
          />
          <Route path="*" element={null} />
        </Routes>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Hub user={user} />} />
          <Route path="/hackathons" element={<ListView key="discover" view="discover" {...shared} />} />
          <Route path="/saved" element={<ListView key="saved" view="saved" {...shared} />} />
          <Route path="/for-you" element={<ListView key="foryou" view="foryou" {...shared} />} />
          <Route
            path="/deadlines"
            element={<DeadlineBoard onOpen={openDetail} refreshKey={refreshKey} />}
          />
          <Route path="/form-filler" element={<FormFiller toast={toast} />} />
          <Route path="/skills" element={<SkillBuilder toast={toast} />} />
          <Route path="/profile" element={<ProfilePanel onSaved={bumpRefresh} toast={toast} />} />
          <Route
            path="/sources"
            element={<SourcesPanel onIngested={bumpRefresh} toast={toast} />}
          />
          <Route
            path="/admin"
            element={isAdmin ? <AdminPortal toast={toast} /> : <Navigate to="/" replace />}
          />
          <Route path="/hackathon/:id" element={<DetailRoute />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <button
        className="btn mobile-toggle floating"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        ☰
      </button>
    </div>
  )
}

/** A hackathon opened directly by URL — shareable and bookmarkable. */
function DetailRoute() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .detail(id)
      .then((data) => !cancelled && setItem(data))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [id])

  const toggleBookmark = async (target) => {
    try {
      if (target.bookmarked) {
        await api.removeBookmark(target.id)
        toast.info('Removed from saved')
      } else {
        await api.addBookmark(target.id)
        toast.success('Saved to your list')
      }
      setItem((current) => ({ ...current, bookmarked: !current.bookmarked }))
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (error) {
    return (
      <div className="empty">
        <div className="big">🔍</div>
        <p>{error}</p>
        <button className="btn" onClick={() => navigate('/hackathons')}>
          Back to Discover
        </button>
      </div>
    )
  }

  if (!item) return <div className="empty">Loading…</div>

  return (
    <HackathonDetail
      item={item}
      onClose={() => navigate('/hackathons')}
      onToggleBookmark={toggleBookmark}
    />
  )
}

/** Discover / Saved / For You all render the same card grid. */
function ListView({ view, filters, setFilters, stats, refreshKey, bumpRefresh, openDetail, toast }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState(filters.q || '')

  // Debounce the search box so typing doesn't fire a request per keystroke.
  useEffect(() => {
    if (view !== 'discover') return undefined
    const timer = setTimeout(() => {
      if (search !== (filters.q || '')) setFilters({ ...filters, q: search, page: 1 })
    }, 320)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

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
  }, [view, filters, refreshKey])

  const toggleBookmark = useCallback(
    async (item) => {
      // Optimistic flip so the star responds instantly.
      const flip = (list) =>
        list.map((row) => (row.id === item.id ? { ...row, bookmarked: !row.bookmarked } : row))
      setData((current) => (current ? { ...current, items: flip(current.items) } : current))

      try {
        if (item.bookmarked) {
          await api.removeBookmark(item.id)
          toast.info('Removed from saved')
        } else {
          await api.addBookmark(item.id)
          toast.success('Saved to your list')
        }
        if (view === 'saved') bumpRefresh()
      } catch (err) {
        toast.error(err.message)
        bumpRefresh()
      }
    },
    [view, bumpRefresh, toast],
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1

  const clearFilters = () =>
    setFilters({
      ...filters,
      q: '',
      region: 'all',
      category: [],
      mode: 'all',
      prize: '',
      within_days: '',
      free_only: false,
      student_only: false,
      team_size: '',
      page: 1,
    })

  return (
    <>
      <div className="topbar">
        <div className="search">
          <span className="icon">🔎</span>
          <input
            type="search"
            placeholder={
              view === 'discover'
                ? 'Search hackathons, organisers, technologies…'
                : 'Search from Discover'
            }
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            disabled={view !== 'discover'}
          />
        </div>
        {view === 'discover' && (
          <select
            className="btn"
            value={filters.sort}
            aria-label="Sort by"
            onChange={(event) => setFilters({ ...filters, sort: event.target.value, page: 1 })}
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

      {view === 'discover' && stats && (
        <div className="stat-row">
          <div className="stat">
            <div className="value"><CountUp value={stats.open} /></div>
            <div className="label">Open now</div>
          </div>
          <div className="stat hot">
            <div className="value"><CountUp value={stats.closing_this_week} /></div>
            <div className="label">Closing this week</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.india} /></div>
            <div className="label">🇮🇳 In India</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.online} /></div>
            <div className="label">Online</div>
          </div>
          <div className="stat">
            <div className="value"><CountUp value={stats.student} /></div>
            <div className="label">Student-friendly</div>
          </div>
          <div className="stat">
            <div className="value">
              <CountUp value={Object.keys(stats.by_source).length} duration={700} />
            </div>
            <div className="label">Sources</div>
          </div>
        </div>
      )}

      {view === 'foryou' && (
        <p className="view-intro">
          Ranked by how well each event matches the skills and interests in your profile.
        </p>
      )}

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
          <div className="big">{view === 'saved' ? '⭐' : '🔍'}</div>
          {view === 'saved' ? (
            <>
              <p>Nothing saved yet.</p>
              <p className="empty-hint">
                Tap the ☆ on any hackathon to keep it here and get deadline alerts for it.
              </p>
            </>
          ) : view === 'foryou' ? (
            <>
              <p>No strong matches yet.</p>
              <p className="empty-hint">
                Add more skills to your profile so events can be scored against them.
              </p>
            </>
          ) : (
            <>
              <p>Nothing matches these filters.</p>
              <p className="empty-hint">Try widening them, or clear them all.</p>
              <button className="btn primary" onClick={clearFilters}>
                Clear all filters
              </button>
            </>
          )}
        </div>
      )}

      {!loading && data && data.items.length > 0 && (
        <>
          {/* Discover splits into the list and the AI column; every other
              view keeps the full width. */}
          <div className={view === 'discover' ? 'discover-split' : ''}>
            <div className="grid">
              {data.items.map((item, index) => (
                <HackathonCard
                  key={item.id}
                  index={index}
                  item={item}
                  onOpen={openDetail}
                  onToggleBookmark={toggleBookmark}
                />
              ))}
            </div>

            {view === 'discover' && (
              <AssistantPanel hackathons={data.items} toast={toast} />
            )}
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
  )
}
