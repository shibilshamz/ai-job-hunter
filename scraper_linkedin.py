"""
scraper_linkedin.py
LinkedIn job scraper using Apify's Linkedin Jobs Scraper actor
(curious_coder/linkedin-jobs-scraper) for the AI Job Hunter pipeline.

This actor scrapes the *public* LinkedIn jobs search (no login/cookies),
so it's lower-risk than cookie-based LinkedIn scrapers, at the cost of
fewer advanced filters.

Pipeline:
1. Apify actor → fetch LinkedIn jobs for Dubai/UAE search URLs
2. scorer.py → score each JD, skip < 7
3. cv_generator.py → generate tailored PDF
4. Log to Google Sheet as "LinkedIn" platform (manual apply only)

Usage:
    python3 scraper_linkedin.py

    # Or import into orchestrator:
    from scraper_linkedin import run_linkedin_scraper
"""

import os
import time
import random
import logging
from datetime import timedelta
from urllib.parse import quote
from apify_client import ApifyClient

from scorer import score_job, tailor_cv
from cv_generator import generate_cv
from sheets_manager import log_job, job_exists, STATUS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LinkedIn] %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
APIFY_API_TOKEN   = os.environ.get("APIFY_API_TOKEN", "")
LINKEDIN_ACTOR_ID = "curious_coder/linkedin-jobs-scraper"

# Keywords searched against LinkedIn's public jobs search, Dubai/UAE only.
SEARCH_KEYWORDS = [
    "AI automation developer",
    "n8n workflow developer",
    "AI agent developer",
    "RPA developer",
    "process automation engineer",
]

LINKEDIN_LOCATION = "United Arab Emirates"
MAX_JOBS_PER_QUERY = 15
SCORE_THRESHOLD = 7


def _sleep(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))


def _build_search_url(keyword: str) -> str:
    """Builds a public LinkedIn jobs search URL for a keyword + location."""
    kw = quote(keyword)
    loc = quote(LINKEDIN_LOCATION)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}"


# ── Apify fetch ───────────────────────────────────────────────────────────────
def fetch_linkedin_jobs(keyword: str) -> list[dict]:
    """
    Runs the Apify LinkedIn Jobs Scraper actor for a given keyword.
    Returns normalized job dicts. Returns [] on any failure.
    """
    if not APIFY_API_TOKEN:
        log.error("APIFY_API_TOKEN is not set — check your env / Supervisor config")
        return []

    search_url = _build_search_url(keyword)
    log.info(f"Searching: {keyword}  ->  {search_url}")

    client = ApifyClient(APIFY_API_TOKEN)
    run_input = {
        "urls": [search_url],
        "scrapeCompany": False,   # faster/cheaper — skip extra company detail requests
        "count": MAX_JOBS_PER_QUERY,
    }

    try:
        run = client.actor(LINKEDIN_ACTOR_ID).call(run_input=run_input, timeout=timedelta(seconds=90))
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
        if not dataset_id:
            log.error("Apify run returned no dataset id")
            return []

        jobs = []
        for item in client.dataset(dataset_id).iterate_items():
            jobs.append({
                "title":       item.get("title", "Unknown"),
                "company":     item.get("companyName", "Unknown"),
                "link":        item.get("link", ""),
                "description": item.get("descriptionText") or item.get("descriptionHtml", ""),
                "easy_apply":  False,   # manual apply only for LinkedIn
                "platform":    "LinkedIn",
                "location":    item.get("location", ""),
            })

        log.info(f"  Found {len(jobs)} jobs")
        return jobs

    except Exception as e:
        log.error(f"Apify LinkedIn fetch error: {e}")
        return []


# ── Main pipeline ─────────────────────────────────────────────────────────────
def run_linkedin_scraper():
    stats = {"queued": 0, "skipped": 0, "duplicates": 0}
    seen_links = set()

    for keyword in SEARCH_KEYWORDS:
        log.info(f"\n{'='*50}")
        log.info(f"Keyword: {keyword}")
        log.info(f"{'='*50}")

        jobs = fetch_linkedin_jobs(keyword)
        _sleep(1, 2)

        for job in jobs:
            link = job["link"]
            if not link:
                continue

            if link in seen_links:
                continue
            seen_links.add(link)

            if job_exists(link):
                log.info(f"Already logged: {job['title']} @ {job['company']}")
                stats["duplicates"] += 1
                continue

            log.info(f"\nProcessing: {job['title']} @ {job['company']}")

            jd_text = job["description"]
            if not jd_text or len(jd_text) < 100:
                log.warning("JD too short — skipping")
                continue

            score_result = score_job(job["title"], job["company"], jd_text)
            score  = score_result.get("score", 0)
            reason = score_result.get("reason", "")

            if score < SCORE_THRESHOLD:
                log.info(f"Score {score}/10 — skipping")
                log_job(
                    platform="LinkedIn",
                    job_title=job["title"],
                    company=job["company"],
                    link=link,
                    status=STATUS["skipped"],
                    notes=f"Score: {score}/10 — {reason[:100]}",
                )
                stats["skipped"] += 1
                continue

            log.info(f"Score {score}/10 — tailoring CV")
            cv_data  = tailor_cv(jd_text, score_result)
            cv_path  = generate_cv(job["company"], cv_data["summary"], cv_data["skills"])
            cv_fname = os.path.basename(cv_path)

            log_job(
                platform="LinkedIn",
                job_title=job["title"],
                company=job["company"],
                link=link,
                status=STATUS["queued"],
                cv_used=cv_fname,
                notes=f"Score: {score}/10 — CV ready at cvs/{cv_fname}",
            )
            stats["queued"] += 1
            log.info(f"🟡 Queued: {job['title']} @ {job['company']}")

            _sleep(2, 4)

    log.info(f"\n{'='*50}")
    log.info("LINKEDIN SCRAPER COMPLETE")
    log.info(f"Queued:       {stats['queued']}")
    log.info(f"Skipped:      {stats['skipped']}")
    log.info(f"Duplicates:   {stats['duplicates']}")
    log.info(f"{'='*50}")
    return stats


if __name__ == "__main__":
    from scraper_stats import print_stats
    result = run_linkedin_scraper()
    print_stats(
        queued=result["queued"],
        skipped=result["skipped"],
        duplicates=result["duplicates"],
        source="linkedin"
    )
