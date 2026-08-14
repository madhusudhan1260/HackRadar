import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ApplicationAssistant } from '../components/AssistantPanel'

/**
 * Form Filling AI as its own page, reached from the hub or the sidebar
 * rather than only alongside the Discover list.
 *
 * It has no list of hackathons handed to it, so it builds one: your saved
 * events first, then whatever is top of Priority, and a search box to pull
 * in anything else by name.
 */
export default function FormFiller({ toast }) {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [defaultList, setDefaultList] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.bookmarks().catch(() => []),
      api.list({ sort: 'priority', per_page: 20 }).catch(() => ({ items: [] })),
    ]).then(([saved, priority]) => {
      if (cancelled) return
      const seen = new Set()
      const merged = []
      ;[...saved, ...priority.items].forEach((item) => {
        if (!seen.has(item.id)) {
          seen.add(item.id)
          merged.push(item)
        }
      })
      setDefaultList(merged)
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults(null)
      return undefined
    }
    const timer = setTimeout(() => {
      api
        .list({ q: query, per_page: 15, sort: 'priority' })
        .then((result) => setSearchResults(result.items))
        .catch(() => setSearchResults([]))
    }, 320)
    return () => clearTimeout(timer)
  }, [query])

  const hackathons = searchResults ?? defaultList

  return (
    <div className="page-formfiller">
      <div className="topbar">
        <Link to="/" className="btn">
          ← Home
        </Link>
        <div className="search">
          <span className="icon">🔎</span>
          <input
            type="search"
            placeholder="Find a hackathon to apply to…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <h1 className="page-title">✨ Form Filling AI</h1>
      <p className="view-intro">
        Pick a hackathon and draft the answers its application will ask for.
        Nothing here submits anything — copy an answer across, or use the
        browser extension to fill the external form and review it yourself.
      </p>

      {loading ? (
        <div className="empty">Loading your hackathons…</div>
      ) : hackathons.length === 0 ? (
        <div className="empty">
          <div className="big">🔎</div>
          <p>No hackathons to prepare for yet.</p>
          <p className="empty-hint">
            Save a few from Discover, or search above for one by name.
          </p>
          <Link className="btn primary" to="/hackathons">
            Browse hackathons
          </Link>
        </div>
      ) : (
        <ApplicationAssistant hackathons={hackathons} toast={toast} />
      )}
    </div>
  )
}
