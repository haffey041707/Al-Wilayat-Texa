#!/usr/bin/env python3
"""Add ONLY Azerbaijani + Malay translations to the already-downloaded Quran.

Fetches az.mammadaliyev and ms.basmeih from AlQuran Cloud and merges an `az` and
`ms` field into every verse of the existing app/data/quran/surah_{n}.json files.
Existing fields (ar/en/ur/fa/translit/audio) are left untouched.

Run:  python3 ingest/add_az_ms_quran.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = "https://api.alquran.cloud/v1"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "quran"
NEW = {"az": "az.mammadaliyev", "ms": "ms.basmeih"}


def get(url: str, tries: int = 4):
    for i in range(tries):
        try:
            out = subprocess.run(["curl", "-sS", "-m", "60", url],
                                 capture_output=True, text=True, check=True).stdout
            return json.loads(out)
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i+1} ({e})", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def main():
    if not (OUT / "surah_1.json").exists():
        sys.exit("No downloaded Quran found. Run fetch_quran.py first.")

    print("Downloading Azerbaijani + Malay editions…")
    eds = {}
    for key, ed in NEW.items():
        print(f"  · {key} ({ed})")
        eds[key] = get(f"{BASE}/quran/{ed}")["data"]["surahs"]

    total = 0
    for i in range(114):
        n = eds["az"][i]["number"]
        f = OUT / f"surah_{n}.json"
        surah = json.loads(f.read_text(encoding="utf-8"))
        # index each edition's ayahs by numberInSurah for safe matching
        by_num = {key: {a["numberInSurah"]: a["text"] for a in eds[key][i]["ayahs"]}
                  for key in NEW}
        for v in surah["verses"]:
            for key in NEW:
                v[key] = by_num[key].get(v["n"], "")
        f.write_text(json.dumps(surah, ensure_ascii=False), encoding="utf-8")
        total += len(surah["verses"])

    print(f"\n✅ Added az + ms to {total} verses across 114 surahs.")
    assert total == 6236, f"expected 6236 verses, got {total}"
    print("✅ Integrity check passed (6236 verses).")


if __name__ == "__main__":
    main()
