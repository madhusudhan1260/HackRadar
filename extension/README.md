# HackRadar AI Form Filler

Fills hackathon application forms from your HackRadar profile.

You enter your details once — college, degree, roll number, GitHub, skills —
and the extension completes the same twenty fields on every application after
that. Open questions like *"Why do you want to participate?"* are drafted from
your profile and the event's theme.

**It never submits anything.** It fills, highlights what it changed, and stops.
You review and press the site's own submit button yourself.

---

## Install (unpacked)

Chrome, Edge, Brave — anything Chromium.

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this `extension/` folder
5. Pin HackRadar to the toolbar

Firefox needs a manifest v2 build; this is v3.

## Use

1. Fill in **Profile → Application details** at
   [hackradar-web.onrender.com](https://hackradar-web.onrender.com) first —
   the filler can only supply what you have entered.
2. Open a hackathon's registration page.
3. Click the HackRadar icon → **Connect** with your HackRadar username and
   password (once; the token is stored locally).
4. It reads the form and shows what it will do:

```
IIT Bombay ML Challenge

  12 ready     2 drafted     6 left to you

  ✓ Full Name                        100%
  ✓ College/University               100%
  ✓ What is your educational…         92%
  ✎ Why do you want to participate?        [editable draft]
  🔒 Create a password                 left for you
  🔒 Aadhaar Number                    left for you
```

5. Edit any draft in the popup, then **Fill this form**.
6. Filled fields flash blue. Check them, then submit the page yourself.

## What it will not touch

Passwords, OTPs, card numbers, UPI, Aadhaar, PAN, passport, bank details,
signatures, dates of birth, consent checkboxes, declarations, and file uploads.

These are refused by pattern, not by omission — see `SENSITIVE_PATTERNS` in
`backend/app/services/field_matcher.py`. Anything resembling a credential,
identity document or legal agreement is yours to enter deliberately.

## How it finds the questions

Forms label their inputs in at least five different ways, and the content
script handles each:

| Pattern | Example |
|---|---|
| `<label for>` | most hand-written forms |
| wrapping `<label>` | Bootstrap-style markup |
| `aria-label` | accessible form builders |
| `placeholder` | minimal designs |
| heading in an ancestor | Google Forms, Typeform |

The ancestor search only accepts a heading when that container holds exactly
one input — otherwise a field with no label of its own inherits the question
next to it, which is a bug this went through before it was fixed.

Values are written through the native property setter and followed by `input`
and `change` events, because React and Vue track their own state and silently
discard a plain `el.value = x`.

## Privacy

Field **labels** are sent to the HackRadar API so it can work out what each one
is asking for. Field **values already on the page are never read**, nothing
about the page is stored, and the filling happens locally in your browser.

Your token lives in `chrome.storage.local` and is only ever sent to the
HackRadar API.

## Development

Point the extension at a local backend by choosing
`localhost:8000 (development)` in the Connect screen.

After editing any file, press the reload icon on the extension card in
`chrome://extensions`, then reload the page you are testing against — content
scripts only attach at page load.
