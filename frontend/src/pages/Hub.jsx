import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import CountUp from '../components/CountUp'

/**
 * The landing screen right after sign-in: a handful of doors, nothing
 * else. Each card is a real destination, not a teaser — clicking it opens
 * that page directly.
 */
export default function Hub({ user }) {
  const [stats, setStats] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [gaps, setGaps] = useState(null)
  const [internStats, setInternStats] = useState(null)

  useEffect(() => {
    api.stats().then(setStats).catch(() => {})
    api.formReadiness().then(setReadiness).catch(() => {})
    api.skillGaps().then(setGaps).catch(() => {})
    api.internshipStats().then(setInternStats).catch(() => {})
  }, [])

  const firstName = (user?.name || '').split(' ')[0] || user?.username

  return (
    <div className="hub">
      <div className="hub-greeting">
        <h1>Welcome back, {firstName}.</h1>
        <p>Where do you want to go?</p>
      </div>

      <div className="hub-grid">
        <Link to="/hackathons" className="hub-card hackathons">
          <div className="hub-icon">🔎</div>
          <h2>Hackathons</h2>
          <p>Devpost and MLH, de-duplicated and ranked against your skills.</p>
          <div className="hub-stat">
            {stats ? (
              <>
                <CountUp value={stats.open} /> open ·{' '}
                <span className="hub-stat-hot">{stats.closing_this_week} closing this week</span>
              </>
            ) : (
              'Loading…'
            )}
          </div>
          <span className="hub-go">Browse hackathons →</span>
        </Link>

        <Link to="/form-filler" className="hub-card formfill">
          <div className="hub-icon">✨</div>
          <h2>Form Filling AI</h2>
          <p>Draft application answers from your profile, ready to paste in.</p>
          <div className="hub-stat">
            {readiness ? (
              <>
                Profile <strong>{readiness.percent}%</strong> ready
                {readiness.missing.length > 0 && (
                  <span className="hub-stat-warn"> · {readiness.missing.length} fields missing</span>
                )}
              </>
            ) : (
              'Loading…'
            )}
          </div>
          <span className="hub-go">Open form filler →</span>
        </Link>

        <Link to="/internships" className="hub-card internships">
          <div className="hub-icon">💼</div>
          <h2>Internships</h2>
          <p>Real tech internships from Remotive and an open listings tracker.</p>
          <div className="hub-stat">
            {internStats ? (
              <>
                <CountUp value={internStats.open} /> open ·{' '}
                {internStats.remote} remote
              </>
            ) : (
              'Loading…'
            )}
          </div>
          <span className="hub-go">Browse internships →</span>
        </Link>

        <Link to="/skills" className="hub-card skills">
          <div className="hub-icon">🎯</div>
          <h2>Skill Builder</h2>
          <p>What to learn next, ranked by how many hackathons it unlocks.</p>
          <div className="hub-stat">
            {gaps ? (
              gaps.skills.length > 0 ? (
                <>
                  Learning <strong>{gaps.skills[0].skill}</strong> would unlock{' '}
                  {gaps.skills[0].would_unlock} more
                </>
              ) : (
                'You already match everything open'
              )
            ) : (
              'Loading…'
            )}
          </div>
          <span className="hub-go">See skill gaps →</span>
        </Link>
      </div>
    </div>
  )
}
