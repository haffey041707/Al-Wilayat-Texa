#!/usr/bin/env python3
"""Ingest full ziyarat texts from al-islam.org's supplication browser.

The print view exposes clean, numbered verses:
    <div class="arabic2">…</div>  Arabic
    <div class="trla2">…</div>    English translation
    <span class="id2">N</span>    verse number

Output: app/data/ziyarat/{id}.json  → {id, ar_title, en_title, verses:[{n,ar,en}]}
"""
import html
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "ziyarat"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://supplications.al-islam.org/ziaraat"

ZIYARAT = {
    "ashura": "ziarat-ashura.php",
    "warith": "ziarat-warith.php",
    "ale-yaseen": "ziarat-ale-yaseen.php",
}


def clean(t: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").strip()


def fetch(slug: str) -> str:
    out = subprocess.run(
        ["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", f"{BASE}/{slug}?t=ar_en&m=print"],
        capture_output=True).stdout
    return out.decode("utf-8", errors="ignore")


def parse(h: str) -> tuple[str, str, list]:
    ar_title = (re.search(r'class="titleArabic">(.*?)</span>', h, re.S) or [None, ""])[1]
    en_title = (re.search(r'class="titleEnglish">(.*?)</span>', h, re.S) or [None, ""])[1]
    verses = []
    # each verse block carries an Arabic and a translation div
    for block in re.findall(r'class="verse2">(.*?)</div>\s*</div>', h, re.S):
        ar = re.search(r'class="arabic2">(.*?)</div>', block, re.S)
        en = re.search(r'class="trla2">(.*?)</div>', block, re.S)
        if ar:
            verses.append({"n": len(verses) + 1,
                           "ar": clean(ar.group(1)),
                           "en": clean(en.group(1)) if en else ""})
    return clean(ar_title), clean(en_title), verses


def main():
    for zid, slug in ZIYARAT.items():
        h = fetch(slug)
        ar_title, en_title, verses = parse(h)
        if not verses:  # fallback: split by arabic2 alone
            verses = [{"n": i + 1, "ar": clean(a), "en": ""}
                      for i, a in enumerate(re.findall(r'class="arabic2">(.*?)</div>', h, re.S))]
        (OUT / f"{zid}.json").write_text(json.dumps({
            "id": zid, "ar_title": ar_title, "en_title": en_title,
            "count": len(verses), "verses": verses,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {zid}: {len(verses)} verses ({en_title})")


if __name__ == "__main__":
    main()
