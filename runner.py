from flask import Flask, jsonify
import subprocess, os, json

app = Flask(__name__)
ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}

def run_scraper(script):
    result = subprocess.run(
        ["python3", script],
        cwd="/root/job-hunter",
        capture_output=True, text=True, env=ENV
    )
    output = result.stdout + result.stderr
    for line in output.splitlines():
        if line.startswith("STATS_JSON:"):
            return json.loads(line.replace("STATS_JSON:", ""))
    return {"source": script, "queued": 0, "skipped": 0, "duplicates": 0, "error": "no stats line"}

@app.route("/run", methods=["POST"])
def run_all():
    indeed     = run_scraper("scraper_indeed.py")
    bayt       = run_scraper("scraper_bayt.py")
    naukrigulf = run_scraper("scraper_naukrigulf.py")
    linkedin   = run_scraper("scraper_linkedin.py")
    return jsonify({"indeed": indeed, "bayt": bayt, "naukrigulf": naukrigulf, "linkedin": linkedin})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5679)
