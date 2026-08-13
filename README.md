# 📡 HackRadar — One place for every hackathon

Hackathons are scattered across Devpost, MLH, Unstop, HackerEarth, Devfolio and a
dozen others. HackRadar collects them into a single dashboard, cleans and
de-duplicates the listings, classifies them, scores each one against **your**
skills, and warns you before deadlines pass.

```
   HACKATHON SOURCES
  Devpost   MLH   (+ pluggable adapters)
        \    |    /
         DATA COLLECTOR          collectors/
              ↓
        CLEAN / NORMALISE        services/normalize.py
              ↓
        DE-DUPLICATE             services/dedupe.py     same event, many platforms
              ↓
        CLASSIFY + TAG           services/classifier.py rules, optional LLM
              ↓
          DATABASE               SQLite (dev) / Postgres (prod)
              ↓
      ┌───────┴────────┐
  WEB DASHBOARD    NOTIFICATIONS
   React + Vite     Email / Telegram
```

---

## Deploying

Backend + Postgres on Render, frontend on Vercel — both free, both configured
in this repo (`render.yaml`, `frontend/vercel.json`). Step-by-step guide with
the custom-domain setup: **[DEPLOY.md](DEPLOY.md)**.

---

## Quick start

Two terminals. Backend first.

**1. Backend** (http://localhost:8000)

```bash
cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && ./venv/bin/uvicorn app.main:app --reload --port 8000
```

On first run it creates the database and loads 24 bundled sample hackathons, so
the dashboard is never empty. Interactive API docs: http://localhost:8000/docs

**2. Frontend** (http://localhost:5173)

```bash
cd frontend && npm install && npm run dev
```

**3. Create your admin account**

```bash
cd backend && ./venv/bin/python scripts/manage.py create-admin
```

It prompts for username, name, phone and password — the password is read from a
hidden prompt so it never reaches your shell history. Sign in through the
**Admin** tab on the login page.

The app is **single-admin by design**: exactly one account may hold the admin
role. Registration can only ever create normal users, and taking over admin
requires `--replace`, which demotes the previous holder and kills its sessions.
The server logs a loud error at startup if it ever finds more than one admin.

**4. Pull in real hackathons**

```bash
cd backend && ./venv/bin/python scripts/manage.py ingest
```

Or click **Sources → Refresh all sources** in the UI. The backend also
re-ingests automatically every 6 hours while it runs.

---

## Features

| Feature | Where it lives |
|---|---|
| ⚡ Priority ordering (default) | urgency + match + saved, in `routers/hackathons.py` |
| 🔐 Accounts + admin portal | `routers/auth.py`, `routers/admin_users.py` |
| 🔎 All hackathons, one dashboard | `GET /api/hackathons` |
| 🇮🇳 India / 🌎 Global filter | `region=india\|global` — city + country detection |
| 🤖 AI/ML, 💻 Web, 🔐 Security, ☁️ Cloud, +10 more | `services/classifier.py` |
| 💰 Prize buckets ₹0–10K / 10K–1L / 1L+ | multi-currency parsing → INR |
| 🆓 Free entry only | fee detection from listing text |
| 📅 Sort by nearest deadline | `sort=deadline` |
| 📍 Online / Offline / Hybrid | `mode=` |
| 👥 Team size match | `team_size=` |
| ⭐ Bookmarks | `POST /api/bookmarks` |
| 🔔 Deadline alerts (7/3/1 days) | `services/notifier.py` |
| 🧠 Skill-based match score | `services/matcher.py` |
| 🔗 Cross-platform de-duplication | `services/dedupe.py` |

---

## Accounts and the admin portal

### How sign-in works

| Step | What happens |
|---|---|
| **Register** | Name, unique username, phone, password — the account is active immediately and you're signed straight in |
| **Sign in** | Username + password |
| **Wrong password** | Generic error (no user enumeration); 5 failures locks the account for 15 minutes |
| **Forgot password** | A reset code is texted to the registered phone; entering it with a new password signs you back in and revokes old sessions |

Usernames and phone numbers are both unique. An unverified registration holds
its username and phone for 24 hours, then they are released.

Codes are stored hashed, expire in 5 minutes, allow 5 attempts, and are capped
at one per minute and five per hour per account — SMS costs real money and OTP
endpoints attract abuse. The admin portal has an **SMS delivery** tab showing
every send and the provider response.

### Passwords are never readable

Passwords are stored as bcrypt hashes, which are irreversible by design. Nobody
can read a password back — not the user, not the admin, not this code. Helping
someone who is locked out means **setting a new password**, which the admin
portal does in one click; it also signs that account out of every device.

This is deliberate. Displaying stored passwords would expose them to anyone who
reached the admin screen or the database, and because people reuse passwords,
a leak here would follow them to their other accounts.

### Two doors on the login page

The login screen has a **User / Admin** switch. The Admin tab sends
`as_admin=true`, and the API refuses any account without the admin role — so
it's a real server-side boundary, not just a UI hint. Admins land straight in
the portal after signing in.

### Admin portal

Visible only to accounts with `role = admin`, and the API returns **403** to
everyone else even if they call it directly. It shows:

- **Every registered user** — name, full phone number, username, status, login
  count, last login, registration date, active sessions
- **Login activity** — every sign-in, registration, and password reset, with
  success/failure, the reason for failures, and the source IP
- **Live counters** — total/active/pending users, logins and failed logins today
- **Actions** — reset a password, block/unblock an account, or sign it out of
  every device

Normal users only ever see their own masked phone (`+91 ••••• 43210`).

### Security notes

Passwords are bcrypt hashes; session tokens are stored only as peppered
SHA-256 digests, so the database never holds anything that can be replayed.
Sessions expire after 7 days and are revoked on any password change. Repeated
wrong passwords lock an account for 15 minutes. Every account has its own
profile and bookmarks.

Before deploying: set a real `SECRET_KEY`, switch to Postgres, and serve over
HTTPS. Phone numbers are personal data — treat the database accordingly.

---

### The deadline board

`Deadlines` groups everything closing soon into **Today / This Week / Next Week /
Later This Month**, with each event's match score and days remaining.

### AI matching

Set your skills and interests under **Profile**. Every hackathon is then scored
0–100, and the score is fully explainable — no black box:

| Component | Weight | What it measures |
|---|---|---|
| Skills | 50 | your stack vs the event's technology tags |
| Interests | 30 | your interests vs the event's categories |
| Preferences | 20 | mode, location, prize floor, entry fee, team size |

Missing a core skill applies a penalty and surfaces a reason like
**"Requires Blockchain"**. Adding Blockchain and Solidity to your profile takes
ETHIndia from 9% to 66% — the score reacts to real changes.

Optional: set `ANTHROPIC_API_KEY` in `backend/.env` to let Claude re-classify
listings whose text is too vague for keyword rules. Everything works without it.

---

## Adding a new source

1. Create `backend/app/collectors/mysource.py` with a `Collector` subclass whose
   `fetch()` returns `RawHackathon` records.
2. Register it in `backend/app/collectors/__init__.py`.
3. Add its name to `ENABLED_COLLECTORS` in `.env`.

Cleaning, classification, de-duplication and storage are handled for you.

### A note on scraping

Only sources that expose data deliberately are enabled by default:

- **Devpost** — public JSON API (`/api/hackathons`), the same one their site uses.
- **MLH** — public season pages published as schema.org `Event` microdata.

`unstop.py` is written but **disabled**: Unstop has no documented public API and
its Terms of Use restrict automated access. Enable it only with an official feed
or written permission. Adding HackerEarth or Devfolio? Check their robots.txt and
terms first, and prefer an API or RSS feed over scraping HTML.

---

## Configuration

Copy `backend/.env.example` to `backend/.env`. Every value has a working default.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite by default; set a `postgresql+psycopg://` URL for production |
| `ENABLED_COLLECTORS` | Comma-separated collector names |
| `INGEST_INTERVAL_MINUTES` | Background refresh interval (default 360) |
| `SMTP_*` | Email delivery for deadline alerts |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram delivery |
| `ANTHROPIC_API_KEY` | Optional LLM classification |

Alerts appear in the UI regardless; the SMTP/Telegram settings only control
whether they're also delivered to you.

---

## CLI

```bash
./venv/bin/python scripts/manage.py ingest              # run enabled collectors
./venv/bin/python scripts/manage.py ingest --source mlh # run just one
./venv/bin/python scripts/manage.py stats               # what's in the database
./venv/bin/python scripts/manage.py notify --dry-run    # preview alerts
./venv/bin/python scripts/manage.py create-admin        # create/update THE admin
./venv/bin/python scripts/manage.py users               # list registered accounts
./venv/bin/python scripts/manage.py delete-user <name>  # remove a normal account
./venv/bin/python scripts/manage.py reset               # drop and recreate tables
```

## Priority ordering

The dashboard defaults to **Priority**, which answers "what should I act on
first?" rather than just "what closes soonest":

| Component | Points | Why |
|---|---|---|
| Urgency | 0–50 | closes today = 50, decaying to 0 over 45 days |
| Match | 0–40 | your skill match score |
| Saved | +15 | you already committed to it |

A 70% match closing Friday outranks a 95% match closing in three months. The
other sorts (deadline, match, prize, recent, title) are still available.

## Project layout

```
backend/
  app/
    collectors/    one adapter per platform + registry
    services/      normalize, classify, dedupe, match, notify, pipeline
    routers/       hackathons, profile, admin
    models.py      SQLAlchemy tables
    main.py        FastAPI app + background scheduler
  scripts/manage.py
frontend/
  src/
    components/    cards, detail modal, filters, deadline board, profile, sources
    api.js         API client
    App.jsx        dashboard shell
```

## Stack

Python · FastAPI · SQLAlchemy · SQLite/Postgres · APScheduler · httpx ·
BeautifulSoup · React · Vite

## Roadmap

- Postgres + Alembic migrations for deployment
- User accounts (the profile layer is already isolated behind `current_profile`)
- Browser push notifications
- Embedding-based matching to complement the rule-based score
- More sources via official APIs and RSS feeds
