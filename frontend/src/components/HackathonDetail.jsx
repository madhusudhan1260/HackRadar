import { useEffect } from 'react'
import { categoryLabel, formatDate, matchColor, modeIcon } from '../format'

export default function HackathonDetail({ item, onClose, onToggleBookmark }) {
  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!item) return null
  const match = item.match

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h2>{item.title}</h2>
        <p className="org">
          {item.organizer || 'Independent'} · via {item.source}
        </p>

        {item.description && (
          <p style={{ color: 'var(--text-dim)', fontSize: 13.5, margin: 0 }}>
            {item.description}
          </p>
        )}

        <div className="detail-grid">
          <div>
            <div className="k">Deadline</div>
            <div className="v">📅 {formatDate(item.deadline)}</div>
          </div>
          <div>
            <div className="k">Prize</div>
            <div className="v">💰 {item.prize_text || item.prize_display}</div>
          </div>
          <div>
            <div className="k">Mode</div>
            <div className="v">
              {modeIcon(item.mode)} {item.location || item.mode}
            </div>
          </div>
          <div>
            <div className="k">Team size</div>
            <div className="v">
              👥 {item.team_min === item.team_max ? item.team_min : `${item.team_min}–${item.team_max}`}
            </div>
          </div>
          <div>
            <div className="k">Entry</div>
            <div className="v">{item.is_free ? '🆓 Free' : `₹${item.fee_inr}`}</div>
          </div>
          <div>
            <div className="k">Audience</div>
            <div className="v">{item.is_student_only ? '🏫 Student' : '🌍 Open'}</div>
          </div>
        </div>

        {match && (
          <div className="match-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: 13 }}>Skill match</strong>
              <strong style={{ color: matchColor(match.level), fontSize: 15 }}>
                {match.score}%
              </strong>
            </div>
            <div className="match-bar">
              <div style={{ width: `${match.score}%`, background: matchColor(match.level) }} />
            </div>
            {match.reasons.map((reason) => (
              <p key={reason} className="reason">
                ✓ {reason}
              </p>
            ))}
            {match.missing.map((gap) => (
              <p key={gap} className="reason gap">
                ⚠ {gap}
              </p>
            ))}
          </div>
        )}

        {item.tags.length > 0 && (
          <>
            <div className="k" style={{ fontSize: 10.5, color: 'var(--text-faint)', letterSpacing: 0.7 }}>
              TECHNOLOGIES
            </div>
            <div className="tag-row" style={{ marginTop: 6 }}>
              {item.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </>
        )}

        {item.categories.length > 0 && (
          <div className="tag-row" style={{ marginTop: 8 }}>
            {item.categories.map((cat) => (
              <span key={cat} className="tag">
                {categoryLabel(cat)}
              </span>
            ))}
          </div>
        )}

        {item.also_on.length > 0 && (
          <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 12 }}>
            Also listed on{' '}
            {item.also_on.map((mirror, index) => (
              <span key={mirror.url}>
                {index > 0 && ', '}
                <a href={mirror.url} target="_blank" rel="noreferrer">
                  {mirror.source}
                </a>
              </span>
            ))}
          </p>
        )}

        <div className="modal-actions">
          <a className="btn primary" href={item.url} target="_blank" rel="noreferrer">
            Register Now ↗
          </a>
          <button className="btn" onClick={() => onToggleBookmark(item)}>
            {item.bookmarked ? '★ Saved' : '☆ Save'}
          </button>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
