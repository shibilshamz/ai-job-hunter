"""
scraper_indeed.py
Indeed job scraper using JSearch API (no Cloudflare issues)
+ Easy Apply bot via Playwright for matched jobs.

Pipeline:
1. JSearch API → fetch jobs for each keyword in Dubai/UAE
2. scorer.py → score each JD, skip < 7
3. cv_generator.py → generate tailored PDF
4. Playwright → Easy Apply if score >= 8 and easy_apply flag set
5. sheets_manager.py → log everything to Google Sheet
"""

import os
import time
import json
import random
import logging
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from scorer import score_job, tailor_cv
from cv_generator import generate_cv
from sheets_manager import log_job, update_job_status, job_exists, STATUS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Indeed] %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
JSEARCH_API_KEY = os.environ.get("JSEARCH_API_KEY", "")
JSEARCH_URL     = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "x-rapidapi-host": "jsearch.p.rapidapi.com",
    "x-rapidapi-key":  JSEARCH_API_KEY,
}

SEARCH_QUERIES = [
    "AI Automation Developer Dubai",
    "n8n developer UAE",
    "workflow automation engineer Dubai",
    "AI Agent developer UAE",
    "RPA Developer Dubai",
    "AI Ops engineer UAE",
    "process automation developer Dubai",
]

MAX_JOBS_PER_QUERY = 10
SCORE_THRESHOLD    = 7
APPLY_THRESHOLD    = 8

CANDIDATE = {
    "first_name": "Shibil",
    "last_name":  "Shamsudheen",
    "email":      os.environ.get("APPLY_EMAIL", "shibilshamz123@gmail.com"),
    "phone":      os.environ.get("APPLY_PHONE", "+971543220599"),
    "location":   "Dubai, United Arab Emirates",
    "linkedin":   "linkedin.com/in/shibil-shamsudheen",
    "portfolio":  "shibilshamz.github.io",
    "cover_note": (
        "I'm a self-taught AI Automation Builder with hands-on experience deploying "
        "production n8n pipelines, Python agents, and Claude API integrations on live VPS "
        "infrastructure. My portfolio at shibilshamz.github.io shows working systems, not "
        "side projects. I'd love to bring this to your team."
    ),
}


def _sleep(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))


# ── JSearch API fetch ─────────────────────────────────────────────────────────
def fetch_jobs_jsearch(query: str) -> list[dict]:
    """
    Fetches jobs from JSearch API for a given query.
    Returns list of normalized job dicts.
    """
    log.info(f"JSearch query: {query}")
    params = {
        "query":        query,
        "page":         "1",
        "num_pages":    "1",
        
        "employment_types": "FULLTIME,CONTRACTOR",
    }

    try:
        resp = requests.get(JSEARCH_URL, headers=JSEARCH_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("data", [])[:MAX_JOBS_PER_QUERY]:
            # Normalize to our internal format
            apply_link = (
                item.get("job_apply_link") or
                item.get("job_google_link") or ""
            )
            jobs.append({
                "title":       item.get("job_title", "Unknown"),
                "company":     item.get("employer_name", "Unknown"),
                "link":        apply_link,
                "description": item.get("job_description", ""),
                "easy_apply":  item.get("job_apply_is_direct", False),
                "platform":    "Indeed" if "indeed" in apply_link.lower() else "Other",
                "location":    ", ".join(filter(None, [item.get("job_city"), item.get("job_country")])),
            })

        log.info(f"  Found {len(jobs)} jobs")
        return jobs

    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            log.error("JSearch rate limit hit — waiting 60s")
            time.sleep(60)
        else:
            log.error(f"JSearch HTTP error: {e}")
        return []
    except Exception as e:
        log.error(f"JSearch fetch error: {e}")
        return []


# ── Easy Apply bot ────────────────────────────────────────────────────────────
def _easy_apply(page, job: dict, cv_path: str) -> bool:
    """Attempts Indeed Easy Apply. Returns True if submitted."""
    log.info(f"Attempting Easy Apply: {job['title']} @ {job['company']}")

    try:
        page.goto(job["link"], wait_until="domcontentloaded", timeout=30000)
        _sleep(2, 3)

        # Find Apply button
        apply_btn = None
        for selector in [
            "button:has-text('Apply now')",
            "button:has-text('Easily apply')",
            "a:has-text('Apply now')",
        ]:
            try:
                apply_btn = page.wait_for_selector(selector, timeout=5000)
                if apply_btn:
                    break
            except:
                continue

        if not apply_btn:
            log.warning("Apply button not found")
            return False

        apply_btn.click()
        _sleep(2, 3)

        # Step through form
        for step in range(8):
            log.info(f"  Form step {step + 1}")

            _fill_field(page, "input[name='firstName']", CANDIDATE["first_name"])
            _fill_field(page, "input[name='lastName']",  CANDIDATE["last_name"])
            _fill_field(page, "input[type='email']",     CANDIDATE["email"])
            _fill_field(page, "input[type='tel']",       CANDIDATE["phone"])

            # Upload CV
            for fi in page.query_selector_all("input[type='file']"):
                try:
                    fi.set_input_files(cv_path)
                    _sleep(1, 2)
                except:
                    pass

            # Fill textareas
            for ta in page.query_selector_all("textarea"):
                try:
                    label = _get_label(page, ta).lower()
                    if any(k in label for k in ["cover", "letter", "message"]):
                        if not ta.input_value():
                            ta.fill(CANDIDATE["cover_note"])
                    elif "linkedin" in label:
                        if not ta.input_value():
                            ta.fill(CANDIDATE["linkedin"])
                except:
                    pass

            # Handle radio/dropdowns
            _handle_radios(page)
            _handle_dropdowns(page)

            # Check for confirmation
            body = page.inner_text("body").lower()
            if any(k in body for k in ["submitted", "thank you for applying", "successfully applied"]):
                log.info("  ✅ Application submitted!")
                return True

            # Click Next/Submit
            submitted = _click_next(page)
            if submitted:
                _sleep(2, 3)
                body = page.inner_text("body").lower()
                if any(k in body for k in ["submitted", "thank you", "successfully"]):
                    return True

            _sleep(1, 2)

        return False

    except Exception as e:
        log.error(f"Easy Apply error: {e}")
        return False


def _fill_field(page, selector, value):
    try:
        el = page.query_selector(selector)
        if el and not el.input_value():
            el.fill(value)
    except:
        pass


def _get_label(page, el) -> str:
    try:
        el_id = el.get_attribute("id")
        if el_id:
            label = page.query_selector(f"label[for='{el_id}']")
            if label:
                return label.inner_text()
    except:
        pass
    return ""


def _handle_radios(page):
    try:
        for q in page.query_selector_all("fieldset"):
            text = q.inner_text().lower()
            radios = q.query_selector_all("input[type='radio']")
            labels = q.query_selector_all("label")
            if not radios:
                continue
            if any(k in text for k in ["authoriz", "eligible", "right to work", "visa"]):
                for i, lb in enumerate(labels):
                    if "yes" in lb.inner_text().lower() and i < len(radios):
                        radios[i].click()
                        break
            elif radios:
                radios[0].click()
    except:
        pass


def _handle_dropdowns(page):
    try:
        for sel in page.query_selector_all("select"):
            opts = sel.query_selector_all("option")
            if len(opts) > 1:
                sel.select_option(index=1)
    except:
        pass


def _click_next(page) -> bool:
    for kw, is_submit in [("Submit", True), ("Apply", True), ("Continue", False), ("Next", False)]:
        try:
            el = page.query_selector(f"button:has-text('{kw}')")
            if el and el.is_visible():
                el.click()
                _sleep(1, 2)
                return is_submit
        except:
            continue
    return False


# ── Main pipeline ─────────────────────────────────────────────────────────────
def run_indeed_scraper():
    stats = {"auto_applied": 0, "queued": 0, "skipped": 0, "failed": 0, "duplicates": 0}
    seen_links = set()

    # Init Playwright once for Easy Apply
    pw_context = sync_playwright().start()
    browser = pw_context.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    ).new_page()

    for query in SEARCH_QUERIES:
        log.info(f"\n{'='*50}")
        log.info(f"Query: {query}")
        log.info(f"{'='*50}")

        jobs = fetch_jobs_jsearch(query)
        _sleep(1, 2)

        for job in jobs:
            link = job["link"]
            if not link:
                continue

            # Dedup within run
            if link in seen_links:
                continue
            seen_links.add(link)

            # Dedup against sheet
            if job_exists(link):
                log.info(f"Already logged: {job['title']} @ {job['company']}")
                stats["duplicates"] += 1
                continue

            log.info(f"\nProcessing: {job['title']} @ {job['company']}")

            # Use JSearch description directly (no need to scrape page)
            jd_text = job["description"]
            if not jd_text or len(jd_text) < 100:
                log.warning("JD too short — skipping")
                continue

            # Score with Claude
            score_result = score_job(job["title"], job["company"], jd_text)
            score  = score_result.get("score", 0)
            reason = score_result.get("reason", "")

            if score < SCORE_THRESHOLD:
                log.info(f"Score {score}/10 — skipping")
                log_job(
                    platform="Indeed",
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

            # Auto-apply or queue
            if job["easy_apply"] and score >= APPLY_THRESHOLD:
                log_job(
                    platform="Indeed",
                    job_title=job["title"],
                    company=job["company"],
                    link=link,
                    status=STATUS["queued"],
                    cv_used=cv_fname,
                    notes=f"Score: {score}/10 — attempting Easy Apply",
                )
                success = _easy_apply(page, job, cv_path)
                if success:
                    update_job_status(link, STATUS["auto_applied"], f"Score: {score}/10 — Easy Apply submitted")
                    stats["auto_applied"] += 1
                else:
                    update_job_status(link, STATUS["failed"], f"Score: {score}/10 — Easy Apply failed")
                    stats["failed"] += 1
            else:
                log_job(
                    platform="Indeed",
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

    browser.close()
    pw_context.stop()

    log.info(f"\n{'='*50}")
    log.info("INDEED SCRAPER COMPLETE")
    log.info(f"Auto-applied: {stats['auto_applied']}")
    log.info(f"Queued:       {stats['queued']}")
    log.info(f"Skipped:      {stats['skipped']}")
    log.info(f"Failed:       {stats['failed']}")
    log.info(f"Duplicates:   {stats['duplicates']}")
    log.info(f"{'='*50}")
    return stats


if __name__ == "__main__":
    from scraper_stats import print_stats
    result = run_indeed_scraper()
    print_stats(
        queued=result["queued"],
        skipped=result["skipped"],
        duplicates=result["duplicates"],
        source="indeed"
    )
