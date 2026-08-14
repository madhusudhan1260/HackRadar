import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import CountUp from '../components/CountUp'

/**
 * What to learn next.
 *
 * Every number on this page comes from re-running the real match scorer
 * with one candidate skill added to a copy of the profile — not a static
 * "trending skills" list. "Would unlock 6" means 6 open hackathons move
 * from below a good match to at or above it if that skill were added.
 */
export default function SkillBuilder({ toast }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .skillGaps()
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  if (error) {
    return (
      <div className="empty">
        <div className="big">🎯</div>
        <p>{error}</p>
      </div>
    )
  }

  if (!data) return <div className="empty">Scoring your profile against open hackathons…</div>

  return (
    <div className="page-skills">
      <div className="topbar">
        <Link to="/" className="btn">
          ← Home
        </Link>
      </div>

      <h1 className="page-title">🎯 Skill Builder</h1>
      <p className="view-intro">
        What to learn next, ranked by how many hackathons it would actually
        unlock — measured by re-scoring every open hackathon as if you already
        had it, not a generic trending-skills list.
      </p>

      <div className="stat-row">
        <div className="stat">
          <div className="value">
            <CountUp value={data.currently_good} />
          </div>
          <div className="label">Good matches now</div>
        </div>
        <div className="stat">
          <div className="value">
            <CountUp value={data.total_open} />
          </div>
          <div className="label">Open hackathons</div>
        </div>
      </div>

      {data.skills.length === 0 ? (
        <div className="empty">
          <div className="big">🏆</div>
          <p>Your skills already cover what's open right now.</p>
          <p className="empty-hint">Check back as new hackathons come in.</p>
        </div>
      ) : (
        <div className="skill-grid">
          {data.skills.map((skill, index) => (
            <article className="skill-card" key={skill.skill} style={{ '--stagger': index }}>
              <div className="skill-head">
                <h3>{skill.skill}</h3>
                {skill.would_unlock > 0 ? (
                  <span className="skill-unlock">+{skill.would_unlock} hackathons</span>
                ) : (
                  <span className="skill-unlock dim">helps your score</span>
                )}
              </div>

              <p className="skill-detail">
                Requested in <strong>{skill.events_seen}</strong> open hackathon
                {skill.events_seen === 1 ? '' : 's'}. Adding it would raise your match by{' '}
                <strong>{skill.avg_gain > 0 ? `+${skill.avg_gain}` : skill.avg_gain}</strong> points
                on average.
              </p>

              {skill.sample_titles.length > 0 && (
                <p className="skill-examples">
                  {skill.sample_titles.slice(0, 2).join(' · ')}
                  {skill.sample_titles.length > 2 && ` +${skill.sample_titles.length - 2} more`}
                </p>
              )}

              <a
                className="btn primary skill-cta"
                href={skill.resource_url}
                target="_blank"
                rel="noreferrer"
                onClick={() => toast?.info(`Opening ${skill.resource_label}`)}
              >
                {skill.resource_label} ↗
              </a>
            </article>
          ))}
        </div>
      )}

      <p className="skill-footnote">
        Add a skill for real under{' '}
        <Link to="/profile" className="link-btn">
          Profile
        </Link>{' '}
        once you've started learning it — your match scores update immediately.
      </p>
    </div>
  )
}
