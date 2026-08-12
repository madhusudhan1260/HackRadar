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

**3. Pull in real hackathons**

```bash
cd backend && ./venv/bin/python scripts/manage.py ingest
```

Or click **Sources → Refresh all sources** in the UI. The backend also
re-ingests automatically every 6 hours while it runs.

---

## Features

| Feature | Where it lives |
|---|---|
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
./venv/bin/python scripts/manage.py reset               # drop and recreate tables
```

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
