# 🤖 AI Job Hunter

An automated job application pipeline that scrapes UAE job boards daily, scores listings with Claude AI, generates tailored CVs, and sends a daily digest — fully deployed on a Hostinger VPS with n8n orchestration.

---

## Architecture

```
n8n (Schedule: 5 PM UAE)
        │
        ▼
  runner.py (Flask, port 5679)
        │
   ┌────┬────┴───┬──────────┐
   ▼    ▼        ▼          ▼
scraper_ scraper_ scraper_   scraper_
indeed   bayt     naukrigulf linkedin
(Apify)  (JSearch)(JSearch)  (Apify)
   │      │        │          │
   └──────┴───┬────┴──────────┘
              ▼
       scorer.py (Claude Haiku)
              │
              ▼
     cv_generator.py (ReportLab)
              │
              ▼
    sheets_manager.py (Google Sheets)
              │
              ▼
  scraper_stats.py → n8n → Email Digest
```

---

## Pipeline Steps

| Step | File | Description |
|------|------|-------------|
| 1 | `sheets_manager.py` | Google Sheets API — logs all jobs, statuses, scores |
| 2 | `scorer.py` | Claude Haiku scores JDs 1–10, tailors CV summary + reorders skills |
| 3 | `cv_generator.py` | ReportLab generates `Shibil_CV_CompanyName.pdf` |
| 4 | `scraper_indeed.py` | Apify `misceres/indeed-scraper` — Indeed UAE AI/automation jobs |
| 5 | `scraper_bayt.py` | JSearch API — Bayt UAE AI/automation jobs |
| 6 | `scraper_naukrigulf.py` | JSearch API — Naukrigulf UAE AI/automation jobs |
| 7 | `scraper_linkedin.py` | Apify `curious_coder/linkedin-jobs-scraper` — LinkedIn public jobs search, manual apply only |
| 8 | `runner.py` + n8n | Flask HTTP runner — n8n triggers all scrapers, collects stats, sends email digest |
| 9 | `vps_api_endpoints.py` | Token-authenticated HTTP API for the browser extension |

**Scoring thresholds:**
- Score ≥ 7 → CV generated + logged as `CV Ready 🟡`
- Score ≥ 8 **and** Easy Apply available → auto-applied via Playwright (Indeed only), logged as `CV Ready ✅`
- Score < 7 → `Skipped ❌`
- Already seen → counted as `Duplicate`, not re-logged

**Sheet status labels** (defined in `sheets_manager.py`):

| Key | Label |
|-----|-------|
| `auto_applied` | `CV Ready ✅` |
| `queued` | `CV Ready 🟡` |
| `skipped` | `Skipped ❌` |
| `manual_applied` | `Manual Applied ✅` |
| `failed` | `Failed ⚠️` |

---

## Job Data Sources

The pipeline pulls from two providers. Indeed migrated from JSearch to Apify in July 2026 after reliability problems; Bayt and Naukrigulf still use JSearch.

| Source | Provider | Actor / Endpoint | Max per query | Apply mode |
|--------|----------|------------------|---------------|------------|
| Indeed | Apify | `misceres/indeed-scraper` | 20 | Easy Apply (Playwright) at score ≥ 8 |
| LinkedIn | Apify | `curious_coder/linkedin-jobs-scraper` | 15 | Manual only |
| Bayt | JSearch (RapidAPI) | `jsearch.p.rapidapi.com/search` | 10 | Manual only |
| Naukrigulf | JSearch (RapidAPI) | `jsearch.p.rapidapi.com/search` | 10 | Manual only |

The LinkedIn actor scrapes the **public** jobs search — no login or cookies — which is lower-risk than cookie-based scrapers at the cost of fewer filters.

---

## Tech Stack

- **AI Scoring:** Anthropic Claude Haiku (`claude-haiku-4-5`)
- **CV Generation:** ReportLab
- **Job Data:** Apify actors (Indeed, LinkedIn) + JSearch API via RapidAPI (Bayt, Naukrigulf)
- **Logging:** Google Sheets API
- **Orchestration:** n8n (self-hosted on VPS, Docker)
- **Runtime:** Flask HTTP server (`runner.py`, port 5679)
- **Process manager:** Supervisor (`job-runner`)
- **Infrastructure:** Hostinger Ubuntu VPS

---

## Environment Variables

The running service reads its environment from **Supervisor**, not from `.bashrc`.
Edit `/etc/supervisor/conf.d/job-runner.conf`:

```ini
[program:job-runner]
command=/usr/bin/python3 /root/job-hunter/runner.py
directory=/root/job-hunter
autostart=true
autorestart=true
environment=HOME="/root",
    GSHEETS_SPREADSHEET_ID="your_spreadsheet_id",
    GSHEETS_CREDENTIALS_PATH="/root/job-hunter/credentials/gsheets_credentials.json",
    ANTHROPIC_API_KEY="your_key",
    JSEARCH_API_KEY="your_rapidapi_key",
    APIFY_API_TOKEN="your_apify_token",
    EXT_API_TOKEN="your_extension_bearer_token"
```

Apply changes with:

```bash
supervisorctl reread && supervisorctl update && supervisorctl restart job-runner
```

| Variable | Used by | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | `scorer.py` | Claude Haiku scoring + CV tailoring |
| `APIFY_API_TOKEN` | `scraper_indeed.py`, `scraper_linkedin.py` | Apify actor runs |
| `JSEARCH_API_KEY` | `scraper_bayt.py`, `scraper_naukrigulf.py` | JSearch/RapidAPI |
| `GSHEETS_SPREADSHEET_ID` | `sheets_manager.py`, `vps_api_endpoints.py` | Target sheet |
| `GSHEETS_CREDENTIALS_PATH` | `sheets_manager.py`, `vps_api_endpoints.py` | Service-account JSON path |
| `EXT_API_TOKEN` | `vps_api_endpoints.py` | Bearer token for the extension API |
| `CV_OUTPUT_DIR` | `cv_generator.py` | CV output dir (default `/root/job-hunter/cvs`) |

> Running a scraper by hand from an SSH session uses your shell's `.bashrc` exports instead — keep the two in sync, or the manual run and the service will disagree.

---

## HTTP API

`runner.py` serves on port **5679**. All `/api/*` and `/cvs/*` routes require a bearer token:

```
Authorization: Bearer $EXT_API_TOKEN
```

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/run` | none | Runs all four scrapers, returns per-source stats. Called by n8n. |
| `GET` | `/api/jobs` | bearer | Lists sheet rows awaiting application |
| `POST` | `/api/mark-applied` | bearer | Body `{"link": "..."}` — marks that row applied, stamps `Notes` |
| `GET` | `/cvs/<filename>` | bearer | Serves a generated CV PDF (basename-only, no traversal) |

Missing or wrong token returns **401**. If `EXT_API_TOKEN` is unset the routes return **500** rather than serving unauthenticated.

**Network access:** `ufw` allows only ports 22, 80 and 443 from outside, so 5679 is not reachable from the internet. n8n reaches it over the Docker bridge (`172.17.0.0/16`). Anything off-box needs an nginx reverse proxy on 443 — don't open 5679 directly, since the token would cross the wire in clear text over HTTP.

---

## File Structure

```
/root/job-hunter/
├── sheets_manager.py
├── scorer.py
├── cv_generator.py
├── scraper_indeed.py
├── scraper_bayt.py
├── scraper_naukrigulf.py
├── scraper_linkedin.py
├── scraper_stats.py
├── vps_api_endpoints.py
├── runner.py
├── requirements.txt
├── n8n_workflow.json
├── credentials/
│   └── gsheets_credentials.json   # (gitignored)
└── cvs/
    └── Shibil_CV_*.pdf             # (gitignored)
```

---

## n8n Workflow

**Workflow: AI Job Hunter — Dubai Daily Digest**

```
Schedule Trigger (5 PM Asia/Dubai)
        │
        ▼
HTTP Request → POST http://172.17.0.1:5679/run
               (Docker host gateway — n8n runs in a container)
        │
        ▼
Code Node (Format digest message)
        │
        ▼
Send Email (Gmail SMTP)
```

Export the workflow JSON from n8n → Settings → Download and commit as `n8n_workflow.json`.

---

## Daily Email Digest Sample

```
🤖 AI Job Hunter — 2026-06-22

📋 Queued:     0 CVs generated
⏭️ Skipped:    1 (score too low)
🔁 Duplicates: 69 (already seen)

📌 By source:
• Indeed:     0Q / 1S / 47D
• Bayt:       0Q / 0S / 13D
• Naukrigulf: 0Q / 0S / 9D
• LinkedIn:   0Q / 0S / 0D

---
This email was sent automatically with n8n
```

---

## Setup

```bash
# Clone repo
git clone https://github.com/shibilshamz/ai-job-hunter
cd ai-job-hunter

# Install dependencies
pip install -r requirements.txt

# Add Google service-account JSON
mkdir -p credentials
cp /path/to/service-account.json credentials/gsheets_credentials.json

# Export the environment variables listed above, then:
python runner.py

# Import n8n_workflow.json into your n8n instance
```

> No module calls `load_dotenv` — variables must be present in the environment.
> On the VPS that comes from Supervisor; locally, export them in your shell.

---

## Deployment

Run under Supervisor on the VPS:

```bash
supervisorctl status job-runner     # check
supervisorctl restart job-runner    # apply code changes
tail -f /var/log/job-runner.err.log # logs (Flask request log lands here)
```

> `runner.py` uses Flask's built-in development server. It is fine behind the
> firewall as-is, but should sit behind a production WSGI server (gunicorn +
> nginx) before being exposed to any outside traffic.

---

## Built by

**Shibil Shamsudheen** — AI Automation Builder, Dubai UAE  
Portfolio: [shibilshamz.github.io](https://shibilshamz.github.io)
