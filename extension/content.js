/**
 * Runs on the application page. Two jobs: read the form's fields, and
 * later write values into them.
 *
 * It never reads existing values and never submits — the page's own submit
 * button stays the only way anything is sent.
 */

/** Find the human-readable question for an input. */
function labelFor(el) {
  // 1. A <label for="..."> pointing at it.
  if (el.id) {
    const explicit = document.querySelector(`label[for="${CSS.escape(el.id)}"]`)
    if (explicit) return clean(explicit.innerText)
  }

  // 2. A <label> wrapping it.
  const wrapping = el.closest('label')
  if (wrapping) return clean(wrapping.innerText)

  // 3. aria-label / aria-labelledby, used by most form builders.
  const aria = el.getAttribute('aria-label')
  if (aria) return clean(aria)
  const labelledBy = el.getAttribute('aria-labelledby')
  if (labelledBy) {
    const node = document.getElementById(labelledBy)
    if (node) return clean(node.innerText)
  }

  // 4. A placeholder is the input's own text, so trust it before looking
  //    outward at the page structure.
  if (el.placeholder) return clean(el.placeholder)

  // 5. Google Forms and similar put the question in an ancestor's heading.
  //    Only accept one when that ancestor wraps this input alone — otherwise
  //    a field with no label of its own inherits a neighbour's question.
  let parent = el.parentElement
  for (let depth = 0; parent && depth < 4; depth += 1, parent = parent.parentElement) {
    if (parent.querySelectorAll('input, textarea, select').length !== 1) break
    const heading = parent.querySelector(
      '[role="heading"], .question-title, .field-label, legend, h1, h2, h3, h4, h5',
    )
    if (heading && heading.innerText.trim()) return clean(heading.innerText)
  }

  return clean(el.name || '')
}

function clean(text) {
  return (text || '')
    .replace(/\s+/g, ' ')
    .replace(/\*+$/, '')
    .replace(/\(required\)|\(optional\)/gi, '')
    .trim()
    .slice(0, 200)
}

function isVisible(el) {
  if (el.type === 'hidden' || el.disabled || el.readOnly) return false
  const style = getComputedStyle(el)
  if (style.display === 'none' || style.visibility === 'hidden') return false
  const box = el.getBoundingClientRect()
  return box.width > 0 && box.height > 0
}

const SKIP_TYPES = new Set(['submit', 'button', 'reset', 'image', 'hidden'])

/** Every fillable control on the page, with its question. */
function scanFields() {
  const controls = [...document.querySelectorAll('input, textarea, select')]
  const fields = []

  controls.forEach((el, index) => {
    const type = (el.type || el.tagName).toLowerCase()
    if (SKIP_TYPES.has(type)) return
    if (!isVisible(el)) return

    const label = labelFor(el)
    if (!label) return

    // Tag the element so the fill step can find this exact control again.
    const ref = `hackradar-${index}`
    el.setAttribute('data-hackradar-ref', ref)

    fields.push({
      ref,
      label,
      name: el.name || '',
      type: el.tagName === 'SELECT' ? 'select' : type,
      options:
        el.tagName === 'SELECT'
          ? [...el.options].map((o) => o.text.trim()).filter(Boolean)
          : [],
    })
  })

  return fields
}

/** Write a value in the way the page's own framework will notice. */
function setValue(el, value) {
  if (el.tagName === 'SELECT') {
    const wanted = value.trim().toLowerCase()
    const option =
      [...el.options].find((o) => o.text.trim().toLowerCase() === wanted) ||
      [...el.options].find((o) => o.text.trim().toLowerCase().includes(wanted))
    if (!option) return false
    el.value = option.value
  } else {
    // React and Vue track the value internally, so assigning el.value is
    // silently discarded. Going through the native setter and then firing
    // the events makes the framework accept it.
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement
    const setter = Object.getOwnPropertyDescriptor(proto.prototype, 'value')?.set
    if (setter) setter.call(el, value)
    else el.value = value
  }

  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
  return true
}

function fillFields(values) {
  let filled = 0
  const failed = []

  values.forEach(({ ref, value }) => {
    if (!value) return
    const el = document.querySelector(`[data-hackradar-ref="${ref}"]`)
    if (!el) {
      failed.push(ref)
      return
    }
    if (setValue(el, value)) {
      filled += 1
      // Brief highlight so the user can see exactly what changed.
      const previous = el.style.boxShadow
      el.style.transition = 'box-shadow .25s'
      el.style.boxShadow = '0 0 0 3px rgba(99,102,241,.55)'
      setTimeout(() => {
        el.style.boxShadow = previous
      }, 2200)
    } else {
      failed.push(ref)
    }
  })

  if (filled) {
    const first = document.querySelector('[data-hackradar-ref]')
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  return { filled, failed }
}

chrome.runtime.onMessage.addListener((message, _sender, respond) => {
  if (message.type === 'HACKRADAR_SCAN') {
    respond({ fields: scanFields(), title: document.title, url: location.href })
  }
  if (message.type === 'HACKRADAR_FILL') {
    respond(fillFields(message.values || []))
  }
  return true
})
