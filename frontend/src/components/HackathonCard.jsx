import { deadlineLabel, deadlineClass, modeIcon } from '../format'

export function MatchBadge({ match }) {
  if (!match) return null
  const emoji = match.level === 'strong' ? '🔥' : match.level === 'good' ? '✨' : ''
  return (
    <span className={`badge ${match.level}`} title={match.reasons.join(' · ')}>
      {emoji} {match.score}%
    </span>
  )
}

export default function HackathonCard({ item, onOpen, onToggleBookmark, index = 0 }) {
  return (
    <article
      className="card"
      style={{ '--stagger': index }}
      onClick={() => onOpen(item)}
    >
      <div className="card-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="card-title">{item.title}</h3>
          {item.organizer && <p className="card-org">{item.organizer}</p>}
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
        <span className={`deadline-pill ${deadlineClass(item.days_left)}`}>
          {deadlineLabel(item.days_left, item.deadline)}
        </span>
        {item.prize_inr > 0 && <span>💰 {item.prize_display}</span>}
        <span>
          {modeIcon(item.mode)} {item.mode === 'online' ? 'Online' : item.location || item.mode}
        </span>
        <span>👥 {item.team_min === item.team_max ? item.team_min : `${item.team_min}–${item.team_max}`}</span>
        {item.is_free && <span>🆓 Free</span>}
      </div>

      <div className="tag-row">
        {item.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="tag">
            {tag}
          </span>
        ))}
        {item.also_on.length > 0 && (
          <span className="tag" title={item.also_on.map((m) => m.source).join(', ')}>
            +{item.also_on.length} more source{item.also_on.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
    </article>
  )
}
