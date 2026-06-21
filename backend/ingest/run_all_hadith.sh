#!/usr/bin/env bash
# Watchdog: download ALL 33 Shia hadith books to completion, unattended.
# Re-runs the (resumable) fetcher until every book is present, recovering from
# transient network failures. Writes a DONE marker when finished.
set -u
cd "$(dirname "$0")/.." || exit 1

DATA="app/data/hadith"
MARKER="$DATA/_ALL_DONE.txt"
LOG="$DATA/_download.log"
MAX_ROUNDS=15

echo "=== run_all_hadith started $(date) ===" >>"$LOG"

for round in $(seq 1 $MAX_ROUNDS); do
  echo "--- round $round $(date) ---" | tee -a "$LOG"
  PYTHONUNBUFFERED=1 python3 ingest/fetch_hadith.py >>"$LOG" 2>&1

  # Count completed books (>=98% of expected, matching fetcher's skip rule)
  done_count=$(python3 - <<'PY'
import json, glob, os
cat = json.load(open("app/data/hadith/_catalog.json"))
exp = {b["bookId"]: b["count"] for b in cat}
done = 0
for f in glob.glob("app/data/hadith/*.json"):
    bid = os.path.splitext(os.path.basename(f))[0]
    if bid.startswith("_") or bid not in exp:
        continue
    try:
        got = len(json.load(open(f)).get("hadiths", []))
        if got >= max(1, int(exp[bid] * 0.98)):
            done += 1
    except Exception:
        pass
print(done)
PY
)
  echo "completed books: ${done_count}/24 fetchable" | tee -a "$LOG"
  if [ "$done_count" -ge 24 ]; then
    echo "ALL 24 FETCHABLE BOOKS COMPLETE $(date)" | tee -a "$LOG" >"$MARKER"
    exit 0
  fi
  sleep 5
done

echo "Reached MAX_ROUNDS without full completion; re-run this script to continue." | tee -a "$LOG"
exit 1
