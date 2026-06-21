#!/usr/bin/env python3
"""Ingest duas with Arabic + ENGLISH from supplications.al-islam.org/adiya/.

These print pages use the same clean structure as the ziyarat:
    <div class="arabic2">…</div>   Arabic
    <div class="trla2">…</div>     English translation

Output: app/data/dua/{id}.json → {id, ar_title, en_title, count, verses:[{n,ar,en}]}
(overwrites the Arabic+Persian versions for these ids with Arabic+English ones)
"""
import html as H
import json
import re
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://supplications.al-islam.org/adiya"

# our textId -> (adiya slug, arabic title, english title)
DUAS = {
    "kumayl": ("dua-kumayl",  "دعاء كميل",   "Dua Kumayl"),
    "nudba":  ("dua-nudbah",  "دعاء الندبة", "Dua al-Nudba"),
    "sabah":  ("dua-sabah",   "دعاء الصباح", "Dua al-Sabah"),
}


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def fetch(slug: str) -> str:
    for attempt in range(5):
        out = subprocess.run(
            ["curl", "-sSL", "--retry", "2", "--retry-delay", "3", "-m", "30",
             "-A", "Mozilla/5.0", f"{BASE}/{slug}.php?t=ar_en&m=print"],
            capture_output=True).stdout.decode("utf-8", errors="ignore")
        if 'class="arabic2"' in out:
            return out
        time.sleep(5)  # rate-limited (503) — back off
    return out


def build(doc: str) -> list[dict]:
    # walk verse blocks in order; each carries an arabic2 + trla2 div
    verses = []
    for block in re.findall(r'class="verse2">(.*?)</div>\s*</div>', doc, re.S):
        ar = re.search(r'class="arabic2">(.*?)</div>', block, re.S)
        en = re.search(r'class="trla2">(.*?)</div>', block, re.S)
        if ar and clean(ar.group(1)):
            verses.append({"n": len(verses) + 1, "ar": clean(ar.group(1)),
                           "en": clean(en.group(1)) if en else ""})
    return verses


def main():
    for tid, (slug, ar_t, en_t) in DUAS.items():
        verses = build(fetch(slug))
        if not verses:
            print(f"  ⚠️  {tid}: no verses (rate-limited?), kept existing file")
            continue
        (OUT / f"{tid}.json").write_text(json.dumps({
            "id": tid, "ar_title": ar_t, "en_title": en_t,
            "count": len(verses), "verses": verses,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {tid}: {len(verses)} verses (Arabic + English)")
        time.sleep(4)  # be gentle with the server


if __name__ == "__main__":
    main()
