import { useEffect, useState } from 'react'
import { categoryLabel, formatDate, matchColor, modeIcon } from '../format'

/** Build an .ics file so the deadline lands in the user's calendar. */
function calendarFile(item) {
  const stamp = (value) => `${String(value).replace(/-/g, '')}`
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//HackRadar//EN',
    'BEGIN:VEVENT',
    `UID:hackradar-${item.id}@hackradar`,
    `DTSTART;VALUE=DATE:${stamp(item.deadline)}`,
    `DTEND;VALUE=DATE:${stamp(item.deadline)}`,
    `SUMMARY:Deadline — ${item.title}`,
    `DESCRIPTION:${(item.description || '').replace(/[\n,;]/g, ' ').slice(0, 300)}\\n${item.url}`,
    `URL:${item.url}`,
    'BEGIN:VALARM',
    'TRIGGER:-P1D',
    'ACTION:DISPLAY',
    'DESCRIPTION:Hackathon deadline tomorrow',
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ]
  return new Blob([lines.join('\r\n')], { type: 'text/calendar' })
}

export default function HackathonDetail({ item, onClose, onToggleBookmark }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!item) return null
  const match = item.match

  const share = async () => {
    const link = `${window.location.origin}/hackathon/${item.id}`
    // Use the native share sheet on mobile, clipboard everywhere else.
    if (navigator.share) {
      try {
        await navigator.share({ title: item.title, url: link })
        return
      } catch {
        /* user dismissed the sheet — fall through to copying */
      }
    }
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked (needs https or permission) */
    }
  }

  const addToCalendar = () => {
    const url = URL.createObjectURL(calendarFile(item))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${item.title.replace(/[^\w]+/g, '-').slice(0, 50)}.ics`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h2>{item.title}</h2>
        <p className="org">
          {item.organizer || 'Independent'} · via {item.source}
        </p>

        {item.description && (
          <p className="modal-desc">{item.description}</p>
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

        {item.also_on.length > 0 && (
          <p className="also-on">
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
        </div>

        <div className="modal-actions secondary">
          <button className="btn" onClick={share}>
            {copied ? '✓ Link copied' : '🔗 Share'}
          </button>
          {item.deadline && (
            <button className="btn" onClick={addToCalendar}>
              📅 Add to calendar
            </button>
          )}
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
