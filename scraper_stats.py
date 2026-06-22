import json
import sys

def print_stats(queued: int, skipped: int, duplicates: int, source: str = ""):
    stats = {
        "source": source,
        "queued": queued,
        "skipped": skipped,
        "duplicates": duplicates,
    }
    print(f"STATS_JSON:{json.dumps(stats)}")
    sys.stdout.flush()
