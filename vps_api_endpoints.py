import os
import datetime
from functools import wraps

from flask import request, jsonify, send_from_directory, abort

import gspread
from google.oauth2.service_account import Credentials

EXT_API_TOKEN = os.environ.get("EXT_API_TOKEN")
SPREADSHEET_ID = os.environ.get("GSHEETS_SPREADSHEET_ID")
CREDS_PATH = os.environ.get("GSHEETS_CREDENTIALS_PATH")
CV_DIR = "/root/job-hunter/cvs"

STATUS_READY = "Queued 🟡"
STATUS_APPLIED = "Applied ✅"

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _sheet():
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=_SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID).sheet1


def _require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not EXT_API_TOKEN:
            abort(500, "EXT_API_TOKEN not configured on server")
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {EXT_API_TOKEN}":
            abort(401, "bad token")
        return fn(*args, **kwargs)
    return wrapper


def register_extension_api(app):

    @app.route("/api/jobs", methods=["GET"])
    @_require_token
    def api_jobs():
        rows = _sheet().get_all_records()
        ready = [r for r in rows if str(r.get("Status", "")).strip() == STATUS_READY]
        return jsonify(ready)

    @app.route("/api/mark-applied", methods=["POST"])
    @_require_token
    def api_mark_applied():
        data = request.get_json(silent=True) or {}
        link = (data.get("link") or "").strip()
        if not link:
            abort(400, "link required")

        ws = _sheet()
        records = ws.get_all_records()
        header = ws.row_values(1)
        try:
            status_col = header.index("Status") + 1
            notes_col = header.index("Notes") + 1
        except ValueError:
            abort(500, "Status/Notes column missing")

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for i, row in enumerate(records, start=2):
            if str(row.get("Link", "")).strip() == link:
                ws.update_cell(i, status_col, STATUS_APPLIED)
                ws.update_cell(i, notes_col, f"Applied {ts}")
                return jsonify({"ok": True, "row": i})
        abort(404, "job link not found")

    @app.route("/cvs/<path:filename>", methods=["GET"])
    @_require_token
    def serve_cv(filename):
        safe = os.path.basename(filename)
        full = os.path.join(CV_DIR, safe)
        if not os.path.isfile(full):
            abort(404, "cv not found")
        return send_from_directory(CV_DIR, safe, mimetype="application/pdf")
