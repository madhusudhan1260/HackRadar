import { CATEGORY_LABELS } from '../format'

const REGIONS = [
  { key: 'all', label: '🌐 All' },
  { key: 'india', label: '🇮🇳 India' },
  { key: 'global', label: '🌎 Global' },
]

const MODES = [
  { key: 'all', label: 'Any' },
  { key: 'online', label: '🌐 Online' },
  { key: 'offline', label: '📍 Offline' },
  { key: 'hybrid', label: '🔀 Hybrid' },
]

const PRIZES = [
  { key: '0-10k', label: '₹0–10K' },
  { key: '10k-1l', label: '₹10K–1L' },
  { key: '1l+', label: '₹1L+' },
]

const DEADLINES = [
  { key: 7, label: '7 days' },
  { key: 14, label: '14 days' },
  { key: 30, label: '30 days' },
]

function Toggle({ label, value, onChange }) {
  return (
    <div className="toggle-row">
      <span>{label}</span>
      <button
        className={`switch ${value ? 'on' : ''}`}
        aria-pressed={value}
        aria-label={label}
        onClick={() => onChange(!value)}
      />
    </div>
  )
}

export default function Filters({ filters, setFilters, categoryCounts }) {
  const update = (patch) => setFilters({ ...filters, ...patch, page: 1 })

  const toggleCategory = (key) => {
    const current = filters.category || []
    update({
      category: current.includes(key)
        ? current.filter((c) => c !== key)
        : [...current, key],
    })
  }

  const activeCount =
    (filters.category?.length || 0) +
    (filters.region !== 'all' ? 1 : 0) +
    (filters.mode !== 'all' ? 1 : 0) +
    (filters.prize ? 1 : 0) +
    (filters.within_days ? 1 : 0) +
    (filters.free_only ? 1 : 0) +
    (filters.student_only ? 1 : 0) +
    (filters.team_size ? 1 : 0)

  return (
    <>
      <div className="filter-group">
        <h3>Region</h3>
        <div className="chips">
          {REGIONS.map((region) => (
            <button
              key={region.key}
              className={`chip ${filters.region === region.key ? 'on' : ''}`}
              onClick={() => update({ region: region.key })}
            >
              {region.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <h3>Category</h3>
        <div className="chips">
          {Object.entries(CATEGORY_LABELS)
            .filter(([key]) => key !== 'general' && (categoryCounts?.[key] ?? 1) > 0)
            .map(([key, label]) => (
              <button
                key={key}
                className={`chip ${filters.category?.includes(key) ? 'on' : ''}`}
                onClick={() => toggleCategory(key)}
              >
                {label}
              </button>
            ))}
        </div>
      </div>

      <div className="filter-group">
        <h3>Event type</h3>
        <div className="chips">
          {MODES.map((mode) => (
            <button
              key={mode.key}
              className={`chip ${filters.mode === mode.key ? 'on' : ''}`}
              onClick={() => update({ mode: mode.key })}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <h3>Prize pool</h3>
        <div className="chips">
          {PRIZES.map((prize) => (
            <button
              key={prize.key}
              className={`chip ${filters.prize === prize.key ? 'on' : ''}`}
              onClick={() => update({ prize: filters.prize === prize.key ? '' : prize.key })}
            >
              {prize.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <h3>Closing within</h3>
        <div className="chips">
          {DEADLINES.map((option) => (
            <button
              key={option.key}
              className={`chip ${filters.within_days === option.key ? 'on' : ''}`}
              onClick={() =>
                update({ within_days: filters.within_days === option.key ? '' : option.key })
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <h3>Options</h3>
        <Toggle
          label="🆓 Free entry only"
          value={filters.free_only}
          onChange={(value) => update({ free_only: value })}
        />
        <Toggle
          label="🏫 Student events"
          value={filters.student_only}
          onChange={(value) => update({ student_only: value })}
        />
        <Toggle
          label="🔗 Merge duplicates"
          value={filters.group_duplicates}
          onChange={(value) => update({ group_duplicates: value })}
        />
      </div>

      <div className="filter-group">
        <h3>My team size</h3>
        <select
          value={filters.team_size || ''}
          onChange={(event) =>
            update({ team_size: event.target.value ? Number(event.target.value) : '' })
          }
        >
          <option value="">Any size</option>
          {[1, 2, 3, 4, 5, 6].map((size) => (
            <option key={size} value={size}>
              {size} {size === 1 ? 'person (solo)' : 'people'}
            </option>
          ))}
        </select>
      </div>

      {activeCount > 0 && (
        <button
          className="link-btn"
          onClick={() =>
            setFilters({
              ...filters,
              region: 'all',
              category: [],
              mode: 'all',
              prize: '',
              within_days: '',
              free_only: false,
              student_only: false,
              team_size: '',
              page: 1,
            })
          }
        >
          Clear {activeCount} filter{activeCount > 1 ? 's' : ''}
        </button>
      )}
    </>
  )
}
