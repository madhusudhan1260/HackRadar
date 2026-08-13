# Deploying HackRadar

Backend + Postgres on **Render**, frontend on **Vercel**. Both have free tiers
and both deploy straight from this GitHub repo.

You need to create the two accounts yourself — sign-up and billing are yours,
not something that can be automated for you. Everything else is already
configured in `render.yaml` and `frontend/vercel.json`.

Total time: about 25 minutes.

---

## Part 1 — Backend on Render

1. Sign up at **[render.com](https://render.com)** with your GitHub account.
2. **New → Blueprint**, pick the `HackRadar` repo, and approve the plan it
   shows. `render.yaml` provisions:
   - `hackradar-api` — the FastAPI service
   - `hackradar-db` — a Postgres database, wired to `DATABASE_URL` automatically
3. First deploy takes ~5 minutes. Watch the log for `Application startup complete`.
4. Copy the service URL — something like `https://hackradar-api.onrender.com`.
5. Check it works:

   ```
   https://<your-api-url>/api/health
   ```

   You should get `{"status":"ok","hackathons":0,...}`. Zero is correct on a
   fresh database — the background ingest starts on boot and fills it within a
   minute or two.

### Create your admin account on the live database

The local admin exists only in your local SQLite file. In the Render dashboard
open your service → **Shell**, then:

```bash
python scripts/manage.py create-admin
```

It prompts for username, name, phone and password. Use a **different, strong
password** from your local one — this database is reachable from the internet.

---

## Part 2 — Frontend on Vercel

1. **Edit `frontend/vercel.json` first.** Replace the API host with your real
   Render URL:

   ```json
   "destination": "https://YOUR-API.onrender.com/api/:path*"
   ```

   Commit and push. This rewrite is what lets the browser call `/api/...` on
   your own domain, so there is no CORS setup at all.

2. Sign up at **[vercel.com](https://vercel.com)** with GitHub.
3. **Add New → Project**, import `HackRadar`.
4. Set **Root Directory** to `frontend`. Vercel reads the rest from
   `vercel.json` — framework, build command and output directory are already
   correct.
5. Deploy. You get a URL like `https://hackradar.vercel.app`.

---

## Part 3 — Check it end to end

Open your Vercel URL and confirm:

- [ ] The login screen loads with animations
- [ ] Creating an account works, and signs you straight in
- [ ] The dashboard fills with real hackathons
- [ ] Deep links work — visit `/deadlines` directly and refresh
- [ ] The Admin tab lets your admin account in, and refuses a normal one
- [ ] The tab shows the radar favicon
- [ ] Pasting the link into WhatsApp shows a preview card

---

## Things that will surprise you

**The API sleeps.** Render's free tier spins a service down after ~15 minutes
of no traffic, and the next request takes 30–60 seconds to wake it. The page
itself loads instantly from Vercel's CDN, so visitors see the UI with loading
skeletons rather than a blank screen — but the first data load after a quiet
period is slow. Paid instances stay warm; a free uptime pinger every 10 minutes
also works.

**Scheduled ingestion only runs while the service is awake.** The 6-hourly
background job pauses when the instance sleeps. Fine in practice — a visit
wakes it and the schedule resumes. For guaranteed refreshes use a Render Cron
Job running `python scripts/manage.py ingest`.

**Check the free tier's current terms before relying on it.** Free Postgres
plans commonly expire or cap storage after a trial window, and the details
change. Confirm what applies to your account rather than trusting this file.

**Set a real `SECRET_KEY`.** `render.yaml` generates one automatically, so this
is already handled — but never reuse the local development value in production.
Rotating it signs everyone out.

---

## Custom domain

### hackradar.com is not available

It was registered in **January 2011**, is held through the registrar Ascio
(nameservers at Loopia), and currently resolves to a live server. A domain that
is already owned can only be bought from its owner, usually for far more than a
new registration — it is not something a registrar can sell you.

Checked at the same time, these were unregistered:

| Domain | Why it works | Rough cost |
|---|---|---|
| `hackradar.in` | India-focused product, cheapest option | ~₹800/year |
| `hackradar.app` | `.app` is HTTPS-only by design, reads as a product | ~₹1,500/year |
| `hackradar.dev` | Developer-facing, fits the audience | ~₹1,500/year |

Availability changes daily — confirm at your registrar before planning on one.
[Cloudflare Registrar](https://domains.cloudflare.com) sells at cost;
[Namecheap](https://namecheap.com) and [GoDaddy](https://godaddy.com) are the
common alternatives. You buy it yourself: it needs your payment details and
your name on the WHOIS record.

**You do not need a domain to launch.** `hackradar.vercel.app` is free,
permanent and gets HTTPS automatically. A custom domain can be added later
without changing any code.

### Connecting one once you own it

1. Vercel → Project → **Settings → Domains** → add `hackradar.in` and
   `www.hackradar.in`.
2. Vercel shows the DNS records to create. At your registrar add either:
   - an `A` record for the apex pointing at Vercel's IP, and
   - a `CNAME` for `www` pointing at `cname.vercel-dns.com`
3. Propagation takes minutes to a few hours. HTTPS is issued automatically.
4. Pick which form is canonical — `www` or bare — and set the other to
   redirect. Vercel offers this in the same screen.
5. **Update the social preview URL.** In Vercel → Settings → Environment
   Variables set:

   ```
   VITE_SITE_URL = https://www.hackradar.in
   ```

   then redeploy. This is baked into the `og:url` and `og:image` tags at build
   time — several platforms will not follow relative image paths, so previews
   break without it.
