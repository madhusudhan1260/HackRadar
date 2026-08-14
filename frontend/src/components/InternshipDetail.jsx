import { useEffect } from 'react'
import { categoryLabel, formatDate, matchColor } from '../format'

const MODE_ICON = { remote: '🌐', onsite: '📍', hybrid: '🔀' }

export default function InternshipDetail({ item, onClose, onToggleBookmark }) {
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
          {item.company || 'Company not listed'} · via {item.source}
        </p>

        {item.description && <p className="modal-desc">{item.description}</p>}

        <div className="detail-grid">
          <div>
            <div className="k">Closes</div>
            <div className="v">📅 {item.deadline ? formatDate(item.deadline) : item.term || 'Rolling'}</div>
          </div>
          <div>
            <div className="k">Stipend</div>
            <div className="v">
              💰 {item.stipend_inr > 0 ? `${item.stipend_display}/mo` : 'Not listed'}
            </div>
          </div>
          <div>
            <div className="k">Mode</div>
            <div className="v">
              {MODE_ICON[item.mode] || '📍'} {item.location || item.mode}
            </div>
          </div>
          {item.duration_text && (
            <div>
              <div className="k">Duration</div>
              <div className="v">{item.duration_text}</div>
            </div>
          )}
          {item.eligibility && (
            <div>
              <div className="k">Eligibility</div>
              <div className="v">{item.eligibility}</div>
            </div>
          )}
        </div>

        {match && (
          <div className="match-panel">
            <div className="match-head">
              <strong>Skill match</strong>
              <strong style={{ color: matchColor(match.level) }}>{match.score}%</strong>
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
            <div className="k section-label">Technologies</div>
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

        <div className="modal-actions">
          <a className="btn primary" href={item.url} target="_blank" rel="noreferrer">
            Apply Now ↗
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
