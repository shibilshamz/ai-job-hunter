"""
scorer.py
Claude API — Job Description Scorer + CV Tailor
Part of the AI Job Hunter pipeline.

Usage:
    from scorer import score_job, tailor_cv

    result = score_job(job_title, company, job_description)
    if result["score"] >= 7:
        cv_data = tailor_cv(job_description, result)
"""

import os
import json
import logging
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Scorer] %(message)s")
log = logging.getLogger(__name__)

# ── Claude client ─────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"  # Fast + cheap for daily pipeline runs

# ── Candidate profile (used in prompts) ──────────────────────────────────────
CANDIDATE_PROFILE = """
Name: Shibil Shamsudheen
Current Role: Lab Assistant, Sterling Perfumes Industries LLC, Dubai UAE
Target Role: AI Automation Developer / Agent Developer / n8n Developer / RPA Developer / AI Ops

Key Projects:
- Stock Trading Agent v3: Plugin-based NSE trading platform (Python, FastAPI, yfinance, Upstox API, pandas-ta). Four contracts (Market, Strategy, DataFeed, Risk) auto-discovered by a registry, so one strategy runs unmodified across backtest, historical replay, paper and live modes. FastAPI + vanilla-JS dashboard with Excel trade reporting, deployed on Ubuntu VPS under systemd. 80 hermetic unit tests, no live network calls.
- HR CV Pipeline (paid client delivery): 13-node self-hosted n8n workflow for a Dubai recruitment client. Google Drive trigger, PDF text extraction, Claude Haiku 4.5 extraction of 14 fields, two-level deduplication, Google Sheets append, error routing. Runs in Docker behind Caddy with automatic TLS.
- AI Job Hunter: Python job-search pipeline on Ubuntu VPS — four scrapers (Indeed/LinkedIn via Apify, Bayt/NaukriGulf via JSearch), dedupe, Claude Haiku relevance scoring, automated tailored-CV generation, Google Sheets logging, Gmail digest. Flask runner under Supervisor, triggered daily at 5PM Asia/Dubai by self-hosted n8n.
- StyleCode App: React/TypeScript/Vite web app with Claude API integration, deployed on Vercel (stylecode-app.vercel.app)

Technical Skills:
- Automation & Agents: n8n (self-hosted, production), Python, Claude API, Claude Haiku, Groq API, LLaMA 3.1, MCP Protocol, Apify, UiPath RPA (in progress)
- Backend: Python, FastAPI, Flask, Node.js, REST APIs, Playwright, Supervisor, Cron
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Infrastructure: Ubuntu VPS administration (Hostinger KVM), systemd, Supervisor, Docker, Caddy (reverse proxy + TLS), ufw, GitHub Actions, SSH
- Data: pandas, pandas-ta, yfinance, SQLite, Google Sheets API, Google Drive API, ReportLab

Education: B.Tech Chemical Engineering
Languages: English (fluent), Malayalam (native), Arabic (basic)
Location: Dubai/Sharjah UAE | Visa: Company visa (Sterling Perfumes), transferable
Portfolio: shibilshamz.github.io
"""

# ── CV base content (for tailoring) ──────────────────────────────────────────
CV_BASE = {
    "summary": (
        "Self-taught AI Automation Builder with 3 years of UAE industry experience, "
        "transitioning from chemical engineering into AI agent development and workflow automation. "
        "I design, deploy, and administer production systems on infrastructure I run myself — a "
        "plugin-based NSE trading platform, a daily job-search pipeline that writes its own tailored "
        "CVs, and a paid CV-extraction workflow delivered for a Dubai recruitment client. "
        "Skilled in Python, FastAPI, n8n, Claude API, and Ubuntu VPS administration. "
        "Seeking AI Implementation / Automation / AI Ops roles in Dubai UAE."
    ),
    "skills": [
        "n8n workflow automation (self-hosted, production workflows on own VPS)",
        "Python scripting (agents, scrapers, data pipelines)",
        "Claude API & Claude Haiku (LLM integration, structured extraction, prompt engineering)",
        "FastAPI / Flask (HTTP services, dashboards)",
        "Playwright (web scraping, browser automation)",
        "Apify & JSearch/RapidAPI (job-board data sourcing)",
        "React / TypeScript / Vite (frontend development)",
        "Ubuntu VPS administration (Hostinger KVM, systemd, Supervisor, ufw)",
        "Docker & Caddy (containers, reverse proxy, automatic TLS)",
        "Google Sheets API & Google Drive API (data logging, document pipelines)",
        "GitHub Actions (CI/CD workflows)",
        "UiPath RPA (Developer Associate — in progress)",
        "ReportLab (PDF generation)",
        "REST API integration",
    ],
}


# ── Job Scorer ────────────────────────────────────────────────────────────────
def score_job(job_title: str, company: str, job_description: str) -> dict:
    """
    Scores a job description for relevance to Shibil's profile.

    Returns:
    {
        "score": 8,
        "reason": "Strong match — requires n8n and Python automation...",
        "key_requirements": ["n8n", "Python", "API integration"],
        "matched_skills": ["n8n", "Python", "Claude API"],
        "missing_skills": ["Zapier"],
        "apply_recommendation": "auto" | "manual" | "skip"
    }
    """
    prompt = f"""You are a job matching assistant. Evaluate how well this candidate matches the job.

CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{job_description}

Score this job from 1-10 based on how well the candidate matches:
- 9-10: Near-perfect match, candidate has almost all requirements
- 7-8: Strong match, candidate has most key requirements  
- 5-6: Partial match, candidate has some requirements but missing key ones
- 3-4: Weak match, different domain but transferable skills
- 1-2: No match, completely different field

Respond ONLY with a valid JSON object, no other text:
{{
    "score": <integer 1-10>,
    "reason": "<2-3 sentence explanation of the score>",
    "key_requirements": ["<req1>", "<req2>", "<req3>"],
    "matched_skills": ["<skill1>", "<skill2>"],
    "missing_skills": ["<skill1>", "<skill2>"],
    "apply_recommendation": "<auto|manual|skip>"
}}

apply_recommendation rules:
- "auto": score >= 8, candidate clearly qualified
- "manual": score 6-7, worth applying but needs careful CV tailoring
- "skip": score <= 5, not a good match"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        log.info(f"Score: {result['score']}/10 — {job_title} @ {company}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e} | Raw: {raw}")
        return {"score": 0, "reason": "Parse error", "apply_recommendation": "skip"}
    except Exception as e:
        log.error(f"score_job failed: {e}")
        return {"score": 0, "reason": str(e), "apply_recommendation": "skip"}


# ── CV Tailor ─────────────────────────────────────────────────────────────────
def tailor_cv(job_description: str, score_result: dict) -> dict:
    """
    Rewrites CV summary and reorders skills to match job description language.

    Returns:
    {
        "summary": "<tailored summary paragraph>",
        "skills": ["<skill1>", "<skill2>", ...],  # reordered by relevance
        "keywords_used": ["<kw1>", "<kw2>"]
    }
    """
    key_reqs = score_result.get("key_requirements", [])
    matched = score_result.get("matched_skills", [])

    prompt = f"""You are a professional CV writer. Tailor this candidate's CV for a specific job.

CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

CANDIDATE'S CURRENT CV SUMMARY:
{CV_BASE["summary"]}

CANDIDATE'S CURRENT SKILLS LIST:
{json.dumps(CV_BASE["skills"], indent=2)}

JOB DESCRIPTION:
{job_description}

KEY REQUIREMENTS FROM JD: {", ".join(key_reqs)}
CANDIDATE'S MATCHED SKILLS: {", ".join(matched)}

Your task:
1. Rewrite the CV summary (3-4 sentences) to:
   - Mirror the language and keywords from the job description
   - Highlight the most relevant projects and skills for THIS specific role
   - Sound natural and human, not keyword-stuffed
   - Keep it honest — only mention real skills the candidate has

2. Reorder the skills list to put the most relevant skills for THIS job first.
   Do NOT add fake skills. Only reorder and optionally rephrase existing ones to match JD terminology.

Respond ONLY with valid JSON, no other text:
{{
    "summary": "<tailored 3-4 sentence summary>",
    "skills": ["<most relevant skill first>", "<second>", ...],
    "keywords_used": ["<keyword from JD used in summary>", ...]
}}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        log.info(f"CV tailored — {len(result.get('keywords_used', []))} keywords matched")
        return result

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error in tailor_cv: {e}")
        return {
            "summary": CV_BASE["summary"],
            "skills": CV_BASE["skills"],
            "keywords_used": [],
        }
    except Exception as e:
        log.error(f"tailor_cv failed: {e}")
        return {
            "summary": CV_BASE["summary"],
            "skills": CV_BASE["skills"],
            "keywords_used": [],
        }


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Scorer + CV Tailor Smoke Test ===\n")

    # Sample JD for testing
    TEST_JD = """
    We are looking for an AI Automation Developer to join our team in Dubai.
    
    Responsibilities:
    - Build and maintain automated workflows using n8n and Python
    - Develop AI agents using LLM APIs (OpenAI, Anthropic, or similar)
    - Integrate REST APIs and third-party services
    - Deploy and manage automation scripts on cloud/VPS infrastructure
    - Create Telegram bots and notification systems
    
    Requirements:
    - 2+ years experience with workflow automation tools (n8n, Zapier, Make)
    - Strong Python scripting skills
    - Experience with LLM APIs and prompt engineering
    - Knowledge of REST API integration
    - Familiarity with Linux/Ubuntu server administration
    - Experience with web scraping (Playwright, Selenium, or similar)
    
    Nice to have:
    - RPA experience (UiPath, Automation Anywhere)
    - React/TypeScript frontend skills
    - Experience with Google Workspace APIs
    
    Location: Dubai, UAE
    Salary: AED 8,000 - 15,000/month
    """

    print("[1] Scoring job...")
    score_result = score_job(
        job_title="AI Automation Developer",
        company="TechCorp Dubai",
        job_description=TEST_JD,
    )
    print(f"\n    Score: {score_result['score']}/10")
    print(f"    Reason: {score_result['reason']}")
    print(f"    Key requirements: {score_result['key_requirements']}")
    print(f"    Matched skills: {score_result['matched_skills']}")
    print(f"    Missing skills: {score_result['missing_skills']}")
    print(f"    Recommendation: {score_result['apply_recommendation']}")

    if score_result["score"] >= 7:
        print("\n[2] Tailoring CV...")
        cv_data = tailor_cv(TEST_JD, score_result)
        print(f"\n    Tailored Summary:\n    {cv_data['summary']}")
        print(f"\n    Top 5 reordered skills:")
        for i, skill in enumerate(cv_data["skills"][:5], 1):
            print(f"      {i}. {skill}")
        print(f"\n    Keywords used: {cv_data['keywords_used']}")
    else:
        print(f"\n[2] Score {score_result['score']}/10 — below threshold, skipping CV tailor")

    print("\n✅ Smoke test complete.")
