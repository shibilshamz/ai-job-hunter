"""
scraper_bayt.py
Bayt job scraper using JSearch API for the AI Job Hunter pipeline.

Bayt is the #1 job board in the Middle East. JSearch aggregates Bayt listings
so we query it with Bayt-specific terms and site filter.

Pipeline:
1. JSearch API → fetch Bayt jobs for each keyword in Dubai/UAE
2. scorer.py → score each JD, skip < 7
3. cv_generator.py → generate tailored PDF
4. Log to Google Sheet as "Bayt" platform (manual apply only — no Easy Apply)

Usage:
    python3 scraper_bayt.py
    
    # Or import into orchestrator:
    from scraper_bayt import run_bayt_scraper
"""

import os
import time
import random
import logging
import requests

from scorer import score_job, tailor_cv
from cv_generator import generate_cv
from sheets_manager import log_job, job_exists, STATUS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Bayt] %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
JSEARCH_API_KEY = os.environ.get("JSEARCH_API_KEY", "")
JSEARCH_URL     = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "x-rapidapi-host": "jsearch.p.rapidapi.com",
    "x-rapidapi-key":  JSEARCH_API_KEY,
}

# Bayt-specific search queries — Middle East focused terms
SEARCH_QUERIES = [
    "AI automation developer Bayt Dubai",
    "automation engineer AI Dubai site:bayt.com",
    "n8n workflow developer UAE Bayt",
    "AI agent developer Dubai Bayt",
    "RPA developer UAE Bayt",
    "process automation engineer Dubai",
    "AI implementation specialist UAE",
]

MAX_JOBS_PER_QUERY = 10
SCORE_THRESHOLD    = 7


def _sleep(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))


# ── JSearch fetch ─────────────────────────────────────────────────────────────
def fetch_bayt_jobs(query: str) -> list[dict]:
    """
    Fetches jobs from JSearch API, filters for Bayt.com results.
    Returns normalized job dicts.
    """
    log.info(f"Searching: {query}")
    params = {
        "query":    query,
        "page":     "1",
        "num_pages":"1",
        "employment_types": "FULLTIME,CONTRACTOR,PARTTIME",
    }

    try:
        resp = requests.get(JSEARCH_URL, headers=JSEARCH_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("data", [])[:MAX_JOBS_PER_QUERY]:
            apply_link = (
                item.get("job_apply_link") or
                item.get("job_google_link") or ""
            )

            # Determine platform label
            link_lower = apply_link.lower()
            if "bayt.com" in link_lower:
                platform = "Bayt"
            elif "gulftalent" in link_lower:
                platform = "GulfTalent"
            elif "naukrigulf" in link_lower:
                platform = "Naukrigulf"
            elif "linkedin" in link_lower:
                platform = "LinkedIn"
            else:
                platform = "Bayt"  # Default for this scraper

            jobs.append({
                "title":       item.get("job_title", "Unknown"),
                "company":     item.get("employer_name", "Unknown"),
                "link":        apply_link,
                "description": item.get("job_description", ""),
                "platform":    platform,
                "location":    ", ".join(filter(None, [
                    item.get("job_city"),
                    item.get("job_country"),
                ])),
            })

        log.info(f"  Found {len(jobs)} jobs")
        return jobs

    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            log.error("JSearch rate limit — waiting 60s")
            time.sleep(60)
        else:
            log.error(f"HTTP error: {e}")
        return []
    except Exception as e:
        log.error(f"Fetch error: {e}")
        return []


# ── Main pipeline ─────────────────────────────────────────────────────────────
def run_bayt_scraper() -> dict:
    """
    Main entry point. Runs full scrape → score → CV → log pipeline for Bayt.
    Returns stats dict.
    """
    stats = {"queued": 0, "skipped": 0, "duplicates": 0, "errors": 0}
    seen_links = set()

    for query in SEARCH_QUERIES:
        log.info(f"\n{'='*50}")
        log.info(f"Query: {query}")
        log.info(f"{'='*50}")

        jobs = fetch_bayt_jobs(query)
        _sleep(1, 2)

        for job in jobs:
            link = job["link"]
            if not link:
                continue

            # Dedup within this run
            if link in seen_links:
                continue
            seen_links.add(link)

            # Dedup against Google Sheet
            if job_exists(link):
                log.info(f"Already logged: {job['title']} @ {job['company']}")
                stats["duplicates"] += 1
                continue

            log.info(f"\nProcessing: {job['title']} @ {job['company']}")

            jd_text = job["description"]
            if not jd_text or len(jd_text) < 100:
                log.warning("JD too short — skipping")
                stats["errors"] += 1
                continue

            # Score with Claude
            score_result = score_job(job["title"], job["company"], jd_text)
            score  = score_result.get("score", 0)
            reason = score_result.get("reason", "")

            if score < SCORE_THRESHOLD:
                log.info(f"Score {score}/10 — skipping")
                log_job(
                    platform=job["platform"],
                    job_title=job["title"],
                    company=job["company"],
                    link=link,
                    status=STATUS["skipped"],
                    notes=f"Score: {score}/10 — {reason[:100]}",
                )
                stats["skipped"] += 1
                continue

            # Tailor CV
            log.info(f"Score {score}/10 — tailoring CV")
            cv_data  = tailor_cv(jd_text, score_result)
            cv_path  = generate_cv(job["company"], cv_data["summary"], cv_data["skills"])
            cv_fname = os.path.basename(cv_path)

            # Log as Queued — Bayt always manual apply
            log_job(
                platform=job["platform"],
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

    # Summary
    log.info(f"\n{'='*50}")
    log.info("BAYT SCRAPER COMPLETE")
    log.info(f"Queued:     {stats['queued']}")
    log.info(f"Skipped:    {stats['skipped']}")
    log.info(f"Duplicates: {stats['duplicates']}")
    log.info(f"Errors:     {stats['errors']}")
    log.info(f"{'='*50}")

    return stats


if __name__ == "__main__":
    from scraper_stats import print_stats
    result = run_bayt_scraper()
    print_stats(
        queued=result["queued"],
        skipped=result["skipped"],
        duplicates=result["duplicates"],
        source="bayt"
    )
