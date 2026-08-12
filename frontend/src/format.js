/** Shared display helpers. */

export function deadlineLabel(daysLeft, deadline) {
  if (daysLeft === null || daysLeft === undefined) return 'No deadline'
  if (daysLeft < 0) return 'Closed'
  if (daysLeft === 0) return 'Closes today'
  if (daysLeft === 1) return 'Closes tomorrow'
  if (daysLeft <= 30) return `${daysLeft} days left`
  return formatDate(deadline)
}

export function deadlineClass(daysLeft) {
  if (daysLeft === null || daysLeft === undefined || daysLeft < 0) return ''
  if (daysLeft <= 2) return 'urgent'
  if (daysLeft <= 7) return 'soon'
  return ''
}

export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function modeIcon(mode) {
  if (mode === 'online') return '🌐'
  if (mode === 'hybrid') return '🔀'
  return '📍'
}

export function matchColor(level) {
  return {
    strong: 'var(--good)',
    good: 'var(--cool)',
    stretch: 'var(--warn)',
    weak: 'var(--text-faint)',
  }[level] || 'var(--text-faint)'
}

export const CATEGORY_LABELS = {
  'ai-ml': '🤖 AI / ML',
  web: '💻 Web Dev',
  cybersecurity: '🔐 Cybersecurity',
  cloud: '☁️ Cloud',
  blockchain: '⛓️ Blockchain',
  mobile: '📱 Mobile',
  data: '📊 Data',
  'iot-hardware': '🔌 IoT / Hardware',
  fintech: '💳 Fintech',
  healthtech: '🩺 HealthTech',
  gamedev: '🎮 Game Dev',
  design: '🎨 Design',
  sustainability: '🌱 Sustainability',
  'open-source': '🐙 Open Source',
  general: '📦 General',
}

export function categoryLabel(key) {
  return CATEGORY_LABELS[key] || key
}
