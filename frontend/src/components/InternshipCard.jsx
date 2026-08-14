import { MatchBadge } from './HackathonCard'

const MODE_ICON = { remote: '🌐', onsite: '📍', hybrid: '🔀' }

function when(internship) {
  if (internship.days_left !== null && internship.days_left !== undefined) {
    if (internship.days_left < 0) return 'Closed'
    if (internship.days_left === 0) return 'Closes today'
    return `${internship.days_left} days left`
  }
  return internship.term || 'Rolling'
}

export default function InternshipCard({ item, onOpen, onToggleBookmark, index = 0 }) {
  return (
    <article className="card" style={{ '--stagger': index }} onClick={() => onOpen(item)}>
      <div className="card-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="card-title">{item.title}</h3>
          {item.company && <p className="card-org">{item.company}</p>}
        </div>
        <MatchBadge match={item.match} />
        <button
          className={`star ${item.bookmarked ? 'on burst' : ''}`}
          title={item.bookmarked ? 'Remove bookmark' : 'Save for later'}
          onClick={(event) => {
            event.stopPropagation()
            onToggleBookmark(item)
          }}
        >
          {item.bookmarked ? '★' : '☆'}
        </button>
      </div>

      {item.description && <p className="card-desc">{item.description}</p>}

      <div className="meta-row">
        <span
          className={`deadline-pill ${item.days_left !== null && item.days_left <= 7 ? 'soon' : ''}`}
        >
          {when(item)}
        </span>
        {item.stipend_inr > 0 && <span>💰 {item.stipend_display}/mo</span>}
        <span>
          {MODE_ICON[item.mode] || '📍'} {item.mode === 'remote' ? 'Remote' : item.location || item.mode}
        </span>
      </div>

      <div className="tag-row">
        {item.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="tag">
            {tag}
          </span>
        ))}
      </div>
    </article>
  )
}
