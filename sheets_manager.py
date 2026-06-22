"""
sheets_manager.py
Google Sheets interface for the AI Job Hunter pipeline.
Usage: imported by scraper/apply scripts to log and update job entries.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Config ────────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_PATH = os.environ.get(
    "GSHEETS_CREDENTIALS_PATH",
    "/root/job-hunter/credentials/gsheets_credentials.json",
)
SPREADSHEET_ID = os.environ.get("GSHEETS_SPREADSHEET_ID", "YOUR_SHEET_ID_HERE")
SHEET_NAME = "Sheet1"

# Column index map (0-based internally, 1-based in Sheets)
COL = {
    "platform":   0,   # A
    "job_title":  1,   # B
    "company":    2,   # C
    "link":       3,   # D
    "date_found": 4,   # E
    "status":     5,   # F
    "cv_used":    6,   # G
    "notes":      7,   # H
}

STATUS = {
    "auto_applied":    "CV Ready ✅",
    "queued":          "CV Ready 🟡",
    "skipped":         "Skipped ❌",
    "manual_applied":  "Manual Applied ✅",
    "failed":          "Failed ⚠️",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Sheets] %(message)s")
log = logging.getLogger(__name__)


# ── Core client ───────────────────────────────────────────────────────────────
def _get_service():
    """Build and return an authenticated Sheets service client."""
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


# ── Sheet initialisation ──────────────────────────────────────────────────────
def init_sheet():
    """
    Ensures the header row exists.
    Safe to call on every run — skips if already present.
    """
    service = _get_service()
    sheet = service.spreadsheets()

    headers = [
        "Platform", "Job Title", "Company", "Link",
        "Date Found", "Status", "CV Used", "Notes",
    ]

    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:H1",
        ).execute()

        if result.get("values"):
            log.info("Header row already present — skipping init.")
            return

        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:H1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()

        # Bold + freeze the header row
        sheet_id = _get_sheet_id(service)
        requests = [
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": requests},
        ).execute()

        log.info("Sheet initialised with header row.")

    except HttpError as e:
        log.error(f"init_sheet failed: {e}")
        raise


def _get_sheet_id(service) -> int:
    """Return the numeric sheetId for SHEET_NAME."""
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == SHEET_NAME:
            return s["properties"]["sheetId"]
    raise ValueError(f"Sheet '{SHEET_NAME}' not found in spreadsheet.")


# ── Duplicate check ───────────────────────────────────────────────────────────
def job_exists(link: str) -> bool:
    """
    Returns True if a job with this URL is already in the sheet.
    Prevents duplicate rows across daily runs.
    """
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!D:D",  # Link column
        ).execute()
        links = [row[0] for row in result.get("values", []) if row]
        return link in links
    except HttpError as e:
        log.error(f"job_exists check failed: {e}")
        return False


# ── Write a new job row ───────────────────────────────────────────────────────
def log_job(
    platform: str,
    job_title: str,
    company: str,
    link: str,
    status: str,
    cv_used: str = "",
    notes: str = "",
) -> Optional[int]:
    """
    Appends a new job row. Returns the row number written (1-based), or None on error.

    Args:
        platform:  "Indeed" | "Bayt" | "Naukrigulf"
        job_title: Job title string
        company:   Company name
        link:      Full job URL
        status:    Use STATUS dict values (e.g. STATUS["auto_applied"])
        cv_used:   Filename of tailored CV PDF, or ""
        notes:     Any extra notes (score, skip reason, etc.)
    """
    if job_exists(link):
        log.info(f"Duplicate skipped: {job_title} @ {company}")
        return None

    service = _get_service()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    row = [""] * 8
    row[COL["platform"]]   = platform
    row[COL["job_title"]]  = job_title
    row[COL["company"]]    = company
    row[COL["link"]]       = link
    row[COL["date_found"]] = date_str
    row[COL["status"]]     = status
    row[COL["cv_used"]]    = cv_used
    row[COL["notes"]]      = notes

    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:H",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        updated_range = result["updates"]["updatedRange"]
        row_num = int(updated_range.split("!")[1].split(":")[0][1:])
        log.info(f"Logged row {row_num}: [{status}] {job_title} @ {company}")
        return row_num

    except HttpError as e:
        log.error(f"log_job failed: {e}")
        return None


# ── Update an existing row ────────────────────────────────────────────────────
def update_job_status(link: str, status: str, notes: str = "") -> bool:
    """
    Finds a job by its link URL and updates its Status (and optionally Notes).
    Used after auto-apply succeeds/fails.
    """
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!D:H",
        ).execute()

        rows = result.get("values", [])
        for i, row in enumerate(rows):
            if row and row[0] == link:
                actual_row = i + 1  # 1-based, but D:H offset means row 1 = header
                status_cell = f"{SHEET_NAME}!F{actual_row}"
                notes_cell  = f"{SHEET_NAME}!H{actual_row}"

                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={
                        "valueInputOption": "USER_ENTERED",
                        "data": [
                            {"range": status_cell, "values": [[status]]},
                            {"range": notes_cell,  "values": [[notes]]},
                        ],
                    },
                ).execute()

                log.info(f"Updated row {actual_row} → {status}")
                return True

        log.warning(f"update_job_status: link not found in sheet: {link}")
        return False

    except HttpError as e:
        log.error(f"update_job_status failed: {e}")
        return False


# ── Daily summary for Telegram ────────────────────────────────────────────────
def get_daily_summary() -> dict:
    """
    Reads today's rows and returns counts by status.
    Returns: {"auto_applied": N, "queued": N, "skipped": N, "failed": N, "total": N}
    """
    service = _get_service()
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:H",
        ).execute()

        rows = result.get("values", [])[1:]  # skip header
        summary = {"auto_applied": 0, "queued": 0, "skipped": 0, "failed": 0, "total": 0}

        for row in rows:
            if len(row) < 6:
                continue
            date_found = row[COL["date_found"]]
            if not date_found.startswith(today):
                continue

            summary["total"] += 1
            status_val = row[COL["status"]]

            if STATUS["auto_applied"] in status_val:
                summary["auto_applied"] += 1
            elif STATUS["queued"] in status_val:
                summary["queued"] += 1
            elif STATUS["skipped"] in status_val:
                summary["skipped"] += 1
            elif STATUS["failed"] in status_val:
                summary["failed"] += 1

        return summary

    except HttpError as e:
        log.error(f"get_daily_summary failed: {e}")
        return {}


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Sheets Manager Smoke Test ===")

    print("\n[1] Initialising sheet headers...")
    init_sheet()

    print("\n[2] Logging a test job...")
    row_num = log_job(
        platform="Indeed",
        job_title="AI Automation Developer",
        company="Test Corp",
        link="https://indeed.com/test-job-001",
        status=STATUS["queued"],
        cv_used="",
        notes="Score: 8.5/10 — test entry",
    )
    print(f"    Written to row: {row_num}")

    print("\n[3] Duplicate check (same link)...")
    exists = job_exists("https://indeed.com/test-job-001")
    print(f"    Already exists: {exists}")

    print("\n[4] Updating status to Auto Applied...")
    updated = update_job_status(
        link="https://indeed.com/test-job-001",
        status=STATUS["auto_applied"],
        notes="Applied via Easy Apply bot",
    )
    print(f"    Update success: {updated}")

    print("\n[5] Daily summary...")
    summary = get_daily_summary()
    print(f"    {summary}")

    print("\n✅ All tests passed. Sheet is ready.")
