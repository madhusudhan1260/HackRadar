import { useEffect, useState } from 'react'
import { api } from '../api'
import { MatchBadge } from './HackathonCard'
import { deadlineClass, deadlineLabel, formatDate } from '../format'

export default function DeadlineBoard({ onOpen, refreshKey }) {
  const [board, setBoard] = useState(null)
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .deadlines({ bookmarked_only: bookmarkedOnly, horizon_days: 30 })
      .then((data) => !cancelled && setBoard(data))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [bookmarkedOnly, refreshKey])

  if (error) return <div className="error-banner">{error}</div>
  if (!board) return <div className="empty">Loading deadlines…</div>

  return (
    <>
      <div className="topbar">
        <h2 style={{ margin: 0, fontSize: 18 }}>🔥 Deadlines</h2>
        <button
          className={`btn ${bookmarkedOnly ? 'primary' : ''}`}
          onClick={() => setBookmarkedOnly(!bookmarkedOnly)}
        >
          ★ Saved only
        </button>
      </div>

      {board.groups.length === 0 && (
        <div className="empty">
          <div className="big">🎉</div>
          <p>Nothing closing in the next 30 days{bookmarkedOnly ? ' among your saved events' : ''}.</p>
        </div>
      )}

      {board.groups.map((group) => (
        <section key={group.label} className="board-group">
          <div className="board-head">
            <h3>{group.label}</h3>
            <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>{group.items.length}</span>
            <div className="rule" />
          </div>

          {group.items.map((item, index) => (
            <div
              key={item.id}
              className="board-row"
              style={{ '--stagger': index }}
              onClick={() => onOpen(item)}
            >
              {item.bookmarked && <span title="Saved">★</span>}
              <span className="name">{item.title}</span>
              <MatchBadge match={item.match} />
              <span className={`deadline-pill ${deadlineClass(item.days_left)}`}>
                {deadlineLabel(item.days_left, item.deadline)}
              </span>
              <span className="when">{formatDate(item.deadline)}</span>
            </div>
          ))}
        </section>
      ))}
    </>
  )
}
