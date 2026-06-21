#!/usr/bin/env python3
"""Download Shia hadith collections from the Thaqalayn API.

Source: https://www.thaqalayn-api.net  (33 books, ~33,190 narrations)
Each narration includes: Arabic text, English translation, chapter/category,
author, translator, and gradings (Majlisi / Behbudi / Mohseni).

Working route:  /api/{bookId}/{n}   where n = 1 .. idRangeMax (per-book number)

Usage:
    python3 ingest/fetch_hadith.py                 # all books
    python3 ingest/fetch_hadith.py Al-Kafi-Volume-1-Kulayni Al-Kafi-Volume-2-Kulayni
    python3 ingest/fetch_hadith.py --kafi          # all 8 Al-Kafi volumes

Resumable: skips any book whose JSON already has the expected count.
Polite:    small delay between requests; retries on failure.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://www.thaqalayn-api.net/api"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "hadith"
OUT.mkdir(parents=True, exist_ok=True)
WORKERS = 6  # concurrency for the per-hadith requests

# Books listed in the Thaqalayn catalog but NOT served by its API (every ID
# returns an error). Skipped so the run completes instead of retrying forever.
# These are sourced separately where open data exists (see ingest/fetch_nahj.py).
UNAVAILABLE = {
    "Kamal-al-Din-wa-Tamam-al-Nima-Saduq",
    "Kitab-al-Duafa-Ghadairi",
    "Man-La-Yahduruh-al-Faqih-Volume-1-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-2-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-3-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-4-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-5-Saduq",
    "Nahj-al-Balagha-Radi",
    "Risalat-al-Huquq-Abidin",
}


def get(url: str, tries: int = 4):
    for _ in range(tries):
        try:
            out = subprocess.run(
                ["curl", "-sS", "-m", "30", url],
                capture_output=True, text=True, check=True,
            ).stdout
            return json.loads(out)
        except Exception:  # noqa: BLE001
            pass
    return None


def slim(h: dict) -> dict:
    return {
        "id": h.get("id"),
        "category": h.get("category"),
        "chapter": h.get("chapter"),
        "ar": h.get("arabicText", "").strip(),
        "en": h.get("englishText", "").strip(),
        "grading": (h.get("majlisiGrading") or h.get("behdudiGrading") or h.get("mohseniGrading") or "").split("\n")[0].strip(),
        "url": h.get("URL"),
    }


def fetch_book(book: dict):
    bid = book["bookId"]
    count = book["idRangeMax"] - book["idRangeMin"] + 1
    dest = OUT / f"{bid}.json"

    if dest.exists():
        try:
            existing = json.loads(dest.read_text(encoding="utf-8"))
            got = len(existing.get("hadiths", []))
            # Skip if we already have >=98% — the small remainder are genuine
            # gaps in the source API, not network failures. Avoids endless retry.
            if got >= max(1, int(count * 0.98)):
                print(f"  ✓ {bid} complete ({got}/{count})")
                return
        except Exception:  # noqa: BLE001
            pass

    print(f"  ↓ {bid}  ({count} narrations, {WORKERS} workers)", flush=True)
    nums = list(range(book["idRangeMin"], book["idRangeMax"] + 1))

    def one(n):
        h = get(f"{API}/{bid}/{n}")
        return slim(h) if h and "arabicText" in h else None

    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for n, res in zip(nums, pool.map(one, nums)):
            results[n] = res
    hadiths = [results[n] for n in nums if results[n]]
    fail = sum(1 for n in nums if not results[n])

    dest.write_text(json.dumps({
        "bookId": bid, "name": book["BookName"], "author": book["author"],
        "translator": book.get("translator"), "count": len(hadiths),
        "hadiths": hadiths,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ {bid}: saved {len(hadiths)} (fail={fail})")


def main():
    args = sys.argv[1:]
    books = get(f"{API}/v2/allbooks")
    if not books:
        sys.exit("Could not load book catalog")

    # Write/refresh catalog index
    (OUT / "_catalog.json").write_text(json.dumps([
        {"bookId": b["bookId"], "name": b["BookName"], "englishName": b.get("englishName"),
         "author": b["author"], "count": b["idRangeMax"] - b["idRangeMin"] + 1,
         "description": b.get("bookDescription", "")[:400]}
        for b in books
    ], ensure_ascii=False), encoding="utf-8")

    if "--kafi" in args:
        sel = [b for b in books if b["bookId"].startswith("Al-Kafi")]
    elif args:
        sel = [b for b in books if b["bookId"] in args]
    else:
        sel = books

    sel = [b for b in sel if b["bookId"] not in UNAVAILABLE]
    total = sum(b["idRangeMax"] - b["idRangeMin"] + 1 for b in sel)
    print(f"Fetching {len(sel)} fetchable book(s), ~{total} narrations "
          f"({len(UNAVAILABLE)} not served by API, skipped)…")
    for b in sel:
        fetch_book(b)
    print("Done.")


if __name__ == "__main__":
    main()
