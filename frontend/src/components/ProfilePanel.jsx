import { useEffect, useState } from 'react'
import { api } from '../api'
import { CATEGORY_LABELS } from '../format'

const SKILL_SUGGESTIONS = [
  'Python', 'C++', 'Java', 'JavaScript', 'TypeScript', 'React', 'HTML/CSS',
  'SQL', 'Machine Learning', 'Deep Learning', 'LLM', 'NLP', 'Computer Vision',
  'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Android', 'Flutter', 'iOS',
  'Cybersecurity', 'Blockchain', 'Solidity', 'IoT', 'UI/UX', 'Go', 'Rust',
]

function Field({ label, value, onChange, placeholder }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type="text"
        value={value || ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

export default function ProfilePanel({ onSaved, toast }) {
  const [profile, setProfile] = useState(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    api.profile().then(setProfile).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="error-banner">{error}</div>
  if (!profile) return <div className="empty">Loading profile…</div>

  const set = (patch) => setProfile({ ...profile, ...patch })

  const toggleSkill = (skill) => {
    const has = profile.skills.includes(skill)
    set({ skills: has ? profile.skills.filter((s) => s !== skill) : [...profile.skills, skill] })
  }

  const toggleInterest = (key) => {
    const has = profile.interests.includes(key)
    set({
      interests: has ? profile.interests.filter((i) => i !== key) : [...profile.interests, key],
    })
  }

  const save = async () => {
    setStatus('Saving…')
    try {
      await api.saveProfile({
        name: profile.name,
        email: profile.email,
        phone: profile.phone,
        college: profile.college,
        degree: profile.degree,
        branch: profile.branch,
        year_of_study: profile.year_of_study,
        graduation_year: profile.graduation_year,
        registration_number: profile.registration_number,
        city: profile.city,
        github_url: profile.github_url,
        linkedin_url: profile.linkedin_url,
        portfolio_url: profile.portfolio_url,
        resume_url: profile.resume_url,
        bio: profile.bio,
        experience: profile.experience,
        achievements: profile.achievements,
        team_name: profile.team_name,
        skills: profile.skills,
        interests: profile.interests,
        prefer_mode: profile.prefer_mode,
        india_only: profile.india_only,
        min_prize_inr: Number(profile.min_prize_inr) || 0,
        free_only: profile.free_only,
        team_size: Number(profile.team_size) || 1,
        notify_min_score: Number(profile.notify_min_score) || 0,
        telegram_chat_id: profile.telegram_chat_id,
      })
      setStatus('')
      toast?.success('Profile saved — match scores updated')
      onSaved?.()
    } catch (err) {
      setStatus('')
      toast?.error(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>🧠 My profile</h2>
      <p className="hint">
        Match scores are calculated from this. The more accurate it is, the better the
        recommendations.
      </p>

      <div className="inline-fields">
        <div className="field">
          <label>Name</label>
          <input
            type="text"
            value={profile.name}
            onChange={(event) => set({ name: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Email (for deadline alerts)</label>
          <input
            type="email"
            value={profile.email}
            placeholder="you@example.com"
            onChange={(event) => set({ email: event.target.value })}
          />
        </div>
      </div>

      <div className="field">
        <label>My skills ({profile.skills.length} selected)</label>
        <div className="chips">
          {[...new Set([...SKILL_SUGGESTIONS, ...profile.skills])].map((skill) => (
            <button
              key={skill}
              className={`chip ${profile.skills.includes(skill) ? 'on' : ''}`}
              onClick={() => toggleSkill(skill)}
            >
              {profile.skills.includes(skill) ? '✓ ' : ''}
              {skill}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Interests</label>
        <div className="chips">
          {Object.entries(CATEGORY_LABELS)
            .filter(([key]) => key !== 'general')
            .map(([key, label]) => (
              <button
                key={key}
                className={`chip ${profile.interests.includes(key) ? 'on' : ''}`}
                onClick={() => toggleInterest(key)}
              >
                {label}
              </button>
            ))}
        </div>
      </div>

      <div className="inline-fields">
        <div className="field">
          <label>Preferred mode</label>
          <select
            value={profile.prefer_mode}
            onChange={(event) => set({ prefer_mode: event.target.value })}
          >
            <option value="any">Any</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>
        <div className="field">
          <label>Team size</label>
          <input
            type="number"
            min="1"
            max="20"
            value={profile.team_size}
            onChange={(event) => set({ team_size: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Minimum prize (₹)</label>
          <input
            type="number"
            min="0"
            step="1000"
            value={profile.min_prize_inr}
            onChange={(event) => set({ min_prize_inr: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Alert me above match %</label>
          <input
            type="number"
            min="0"
            max="100"
            value={profile.notify_min_score}
            onChange={(event) => set({ notify_min_score: event.target.value })}
          />
        </div>
      </div>

      <h2 style={{ marginTop: 28 }}>📝 Application details</h2>
      <p className="hint">
        What hackathon forms ask for. Fill it once and the browser extension
        completes applications from it.
      </p>

      <div className="inline-fields">
        <Field label="Phone" value={profile.phone} onChange={(v) => set({ phone: v })}
               placeholder="+91 98765 43210" />
        <Field label="City" value={profile.city} onChange={(v) => set({ city: v })}
               placeholder="Bengaluru" />
      </div>

      <Field label="College / University" value={profile.college}
             onChange={(v) => set({ college: v })} placeholder="CMR Institute of Technology" />

      <div className="inline-fields">
        <Field label="Degree" value={profile.degree} onChange={(v) => set({ degree: v })}
               placeholder="B.Tech" />
        <Field label="Branch" value={profile.branch} onChange={(v) => set({ branch: v })}
               placeholder="Computer Science Engineering" />
        <Field label="Year of study" value={profile.year_of_study}
               onChange={(v) => set({ year_of_study: v })} placeholder="3rd Year" />
        <Field label="Graduation year" value={profile.graduation_year}
               onChange={(v) => set({ graduation_year: v })} placeholder="2027" />
      </div>

      <div className="inline-fields">
        <Field label="Registration / roll number" value={profile.registration_number}
               onChange={(v) => set({ registration_number: v })} placeholder="1CR22CS045" />
        <Field label="Team name (optional)" value={profile.team_name}
               onChange={(v) => set({ team_name: v })} placeholder="Byte Squad" />
      </div>

      <div className="inline-fields">
        <Field label="GitHub" value={profile.github_url} onChange={(v) => set({ github_url: v })}
               placeholder="https://github.com/you" />
        <Field label="LinkedIn" value={profile.linkedin_url}
               onChange={(v) => set({ linkedin_url: v })} placeholder="https://linkedin.com/in/you" />
      </div>

      <div className="inline-fields">
        <Field label="Portfolio" value={profile.portfolio_url}
               onChange={(v) => set({ portfolio_url: v })} placeholder="https://yoursite.dev" />
        <Field label="Resume link" value={profile.resume_url}
               onChange={(v) => set({ resume_url: v })} placeholder="https://drive.google.com/…" />
      </div>

      <div className="field">
        <label>Short bio</label>
        <textarea rows={3} value={profile.bio || ''} placeholder="Two lines about you."
                  onChange={(e) => set({ bio: e.target.value })} />
      </div>

      <div className="field">
        <label>Experience</label>
        <textarea rows={3} value={profile.experience || ''}
                  placeholder="Past hackathons, internships, notable projects."
                  onChange={(e) => set({ experience: e.target.value })} />
      </div>

      <button className="btn primary" onClick={save}>
        Save profile
      </button>
      {status && (
        <span className="save-status">{status}</span>
      )}
    </div>
  )
}
