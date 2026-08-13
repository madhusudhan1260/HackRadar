/**
 * Popup: sign in, scan the page, show what would be filled, then fill.
 *
 * The token lives in chrome.storage.local and is only ever sent to the
 * HackRadar API. Page content is never stored — field labels go out, values
 * come back, and the filling happens locally in the content script.
 */

const $ = (id) => document.getElementById(id)

const state = {
  api: 'https://hackradar-api.onrender.com',
  token: '',
  user: null,
  fields: [],      // as scanned, carrying refs
  analysis: null,  // as returned by the API
}

// --------------------------------------------------------------------------

async function api(path, options = {}) {
  const response = await fetch(`${state.api}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {}),
    },
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* keep the status line */
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}

function show(view) {
  $('view-auth').hidden = view !== 'auth'
  $('view-scan').hidden = view !== 'scan'
  $('signout').hidden = view !== 'scan'
}

// --------------------------------------------------------------------------
// Sign in
// --------------------------------------------------------------------------

$('auth-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = event.target.querySelector('button')
  button.disabled = true
  button.textContent = 'Connecting…'
  $('auth-error').hidden = true

  state.api = $('api').value
  try {
    const result = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: $('username').value.trim(),
        password: $('password').value,
      }),
    })
    state.token = result.token
    state.user = result.user
    await chrome.storage.local.set({
      token: state.token,
      api: state.api,
      user: state.user,
    })
    show('scan')
    scan()
  } catch (error) {
    $('auth-error').textContent = error.message
    $('auth-error').hidden = false
  } finally {
    button.disabled = false
    button.textContent = 'Connect'
  }
})

$('signout').addEventListener('click', async () => {
  await chrome.storage.local.clear()
  state.token = ''
  state.user = null
  show('auth')
})

// --------------------------------------------------------------------------
// Scan + analyse
// --------------------------------------------------------------------------

async function scan() {
  $('summary').hidden = true
  $('scan-error').hidden = true
  $('scan-status').hidden = false
  $('scan-status').textContent = 'Looking for a form on this page…'

  $('who-name').textContent = state.user?.name || state.user?.username || ''

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id) return fail('No active tab.')

  let scanned
  try {
    scanned = await chrome.tabs.sendMessage(tab.id, { type: 'HACKRADAR_SCAN' })
  } catch {
    return fail(
      'Cannot read this page. Reload it and try again — the extension needs ' +
        'to load with the page. It also cannot run on browser settings pages.',
    )
  }

  if (!scanned?.fields?.length) {
    return fail('No form fields found on this page.')
  }

  state.fields = scanned.fields
  $('scan-status').textContent = `Reading ${scanned.fields.length} fields…`

  try {
    state.analysis = await api('/api/form/analyse', {
      method: 'POST',
      body: JSON.stringify({
        fields: scanned.fields.map(({ label, name, type, options }) => ({
          label,
          name,
          type,
          options,
        })),
        page_title: scanned.title || '',
      }),
    })
  } catch (error) {
    if (error.status === 401) {
      await chrome.storage.local.clear()
      return show('auth')
    }
    return fail(error.message)
  }

  render(scanned.title)
}

function fail(message) {
  $('scan-status').hidden = true
  $('scan-error').textContent = message
  $('scan-error').hidden = false
}

function render(pageTitle) {
  const a = state.analysis
  $('scan-status').hidden = true
  $('summary').hidden = false
  $('page-title').textContent = a.hackathon || pageTitle || 'This page'
  $('who-complete').textContent = `profile ${a.profile_complete}%`
  $('c-fill').textContent = a.will_fill - a.needs_review
  $('c-review').textContent = a.needs_review
  $('c-skip').textContent = a.left_alone

  const icons = { fill: '✓', generate: '✎', sensitive: '🔒', skip: '–' }
  const list = $('fields')
  list.innerHTML = ''

  a.fields.forEach((field, index) => {
    const row = document.createElement('div')
    row.className = `row ${field.action}`

    const head = document.createElement('div')
    head.className = 'row-head'
    head.innerHTML =
      `<span class="icon">${icons[field.action] || '–'}</span>` +
      `<span class="label"></span>` +
      (field.action === 'fill' && field.confidence
        ? `<span class="conf">${Math.round(field.confidence * 100)}%</span>`
        : '')
    head.querySelector('.label').textContent = field.label
    row.appendChild(head)

    if (field.value) {
      // Long drafts are editable in place, short values shown as text.
      if (field.action === 'generate') {
        const box = document.createElement('textarea')
        box.className = 'draft'
        box.value = field.value
        box.rows = 4
        box.addEventListener('input', () => {
          a.fields[index].value = box.value
        })
        row.appendChild(box)
      } else {
        const value = document.createElement('div')
        value.className = 'value'
        value.textContent = field.value
        row.appendChild(value)
      }
    }

    if (field.reason && field.action !== 'fill') {
      const note = document.createElement('div')
      note.className = 'note'
      note.textContent = field.reason
      row.appendChild(note)
    }

    list.appendChild(row)
  })
}

// --------------------------------------------------------------------------
// Fill
// --------------------------------------------------------------------------

$('fill').addEventListener('click', async () => {
  const button = $('fill')
  button.disabled = true
  button.textContent = 'Filling…'

  // Pair each analysed field back to the control it came from, by position.
  const values = state.analysis.fields
    .map((field, index) => ({
      ref: state.fields[index]?.ref,
      value: field.action === 'fill' || field.action === 'generate' ? field.value : '',
    }))
    .filter((v) => v.ref && v.value)

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  try {
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: 'HACKRADAR_FILL',
      values,
    })
    button.textContent = `Filled ${result.filled} field${result.filled === 1 ? '' : 's'}`
    setTimeout(() => {
      button.disabled = false
      button.textContent = 'Fill this form'
    }, 2500)
  } catch (error) {
    fail(error.message)
    button.disabled = false
    button.textContent = 'Fill this form'
  }
})

// --------------------------------------------------------------------------

;(async () => {
  const saved = await chrome.storage.local.get(['token', 'api', 'user'])
  if (saved.token) {
    state.token = saved.token
    state.api = saved.api || state.api
    state.user = saved.user || null
    show('scan')
    scan()
  } else {
    show('auth')
  }
})()
