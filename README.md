# 🤖 AI Job Hunter

An automated job application pipeline that scrapes UAE job boards daily, scores listings with Claude AI, generates tailored CVs, and sends a daily digest — fully deployed on a Hostinger VPS with n8n orchestration.

---

## Architecture

```
n8n (Schedule: 5 PM UAE)
        │
        ▼
  runner.py (Flask)
        │
   ┌────┴────┐
   ▼         ▼         ▼
scraper_    scraper_   scraper_
indeed.py   bayt.py    naukrigulf.py
   │         │         │
   └────┬────┘
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
| 4 | `scraper_indeed.py` | JSearch API — scrapes Indeed for UAE AI/automation jobs |
| 5 | `scraper_bayt.py` | JSearch API — scrapes Bayt for UAE AI/automation jobs |
| 6 | `scraper_naukrigulf.py` | JSearch API — scrapes Naukrigulf for UAE AI/automation jobs |
| 7 | `runner.py` + n8n | Flask HTTP runner — n8n triggers all scrapers, collects stats, sends email digest |

**Scoring thresholds:**
- Score ≥ 8 → `Queued 🟡` + CV generated
- Score 7 → logged, no CV
- Score < 7 → `Skipped ❌`
- Already seen → `Duplicate` (filtered out)

---

## Tech Stack

- **AI Scoring:** Anthropic Claude Haiku (`claude-haiku-4-5`)
- **CV Generation:** ReportLab
- **Job Data:** JSearch API via RapidAPI
- **Logging:** Google Sheets API
- **Orchestration:** n8n (self-hosted on VPS)
- **Runtime:** Flask HTTP server (`runner.py`)
- **Infrastructure:** Hostinger Ubuntu VPS (Supervisor + n8n Docker)

---

## Environment Variables

Add to `/root/.bashrc` on the VPS:

```bash
export ANTHROPIC_API_KEY="your_key"
export JSEARCH_API_KEY="your_rapidapi_key"
export GSHEETS_SPREADSHEET_ID="your_spreadsheet_id"
export GSHEETS_CREDENTIALS_PATH="/root/job-hunter/credentials/gsheets_credentials.json"
```

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
├── scraper_stats.py
├── runner.py
├── requirements.txt
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
HTTP Request → POST http://localhost:5679/run-all
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

# Start Flask runner
python runner.py

# Import n8n_workflow.json into your n8n instance
```

---

## Built by

**Shibil Shamsudheen** — AI Automation Builder, Dubai UAE  
Portfolio: [shibilshamz.github.io](https://shibilshamz.github.io)
