#!/usr/bin/env python3
"""Ingest full ziyarat texts (Arabic + Persian translation) from the complete
Mafatih al-Jinan dataset (aminpaydar/Mafatih, chapter 3 = Ziyarat, 142 articles).

Each article's items carry type "Text" (Arabic recitation), "Translate"
(Persian translation) and "AboutText" (instructions). We keep the Arabic
passages, pairing each with the nearest following Persian translation.

Output: app/data/ziyarat/{id}.json → {id, ar_title, en_title, count, verses:[{n,ar,en}]}
The 3 al-islam verse files (ashura/warith/ale-yaseen) already exist and are left intact.
"""
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "ziyarat"
OUT.mkdir(parents=True, exist_ok=True)
SRC = "https://raw.githubusercontent.com/aminpaydar/Mafatih/HEAD/mafatih-server/chapters.json"

# textId -> (article index in chapter-3, arabic title, english title)
MAP = {
    "arbaeen":       (88,  "زيارة الأربعين",            "Ziyarat Arbaeen"),
    "arafah":        (81,  "زيارة يوم عرفة",            "Ziyarat of Imam al-Husayn on the Day of Arafah"),
    "jamia-kabira":  (128, "الزيارة الجامعة الكبيرة",   "Ziyarat Jamia al-Kabira"),
    "amin-allah":    (28,  "زيارة أمين الله",           "Ziyarat Amin Allah"),
    "prophet":       (5,   "زيارة رسول الله ﷺ",         "Ziyarat of the Holy Prophet (SAWW)"),
    "imam-ali":      (24,  "زيارة أمير المؤمنين",       "Ziyarat of Imam Ali (AS)"),
    "imam-rida":     (104, "زيارة الإمام الرضا",        "Ziyarat of Imam al-Rida (AS)"),
    "kazimayn":      (95,  "زيارة الكاظمين",            "Ziyarat of al-Kazimayn (AS)"),
    "askariyyayn":   (112, "زيارة العسكريين",           "Ziyarat of al-Askariyyayn (AS)"),
    "baqi":          (11,  "زيارة أئمة البقيع",         "Ziyarat of the Imams of al-Baqi (AS)"),
    "fatima-zahra":  (7,   "زيارة فاطمة الزهراء",       "Ziyarat of Lady Fatima al-Zahra (SA)"),
    "fatima-masuma": (136, "زيارة السيدة المعصومة",     "Ziyarat of Lady Fatima al-Masuma (SA)"),
    "abbas":         (73,  "زيارة أبي الفضل العباس",    "Ziyarat of Hazrat Abbas (AS)"),
}


def is_ar(c: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in c)


def build_verses(article: dict) -> list[dict]:
    items = article.get("items", [])
    verses, pending_tr = [], ""
    # walk in order: collect Arabic "Text" blocks; attach following Persian "Translate"
    arabic_idx = []
    for it in items:
        t, c = it.get("type"), (it.get("content") or "").strip()
        if not c:
            continue
        if t == "Text" and is_ar(c):
            verses.append({"n": len(verses) + 1, "ar": c, "en": ""})
        elif t == "Translate":
            if verses and not verses[-1]["en"]:
                verses[-1]["en"] = c
    return verses


def main():
    raw = subprocess.run(["curl", "-sSL", "-m", "60", SRC],
                         capture_output=True).stdout.decode("utf-8", errors="ignore")
    data = json.loads(raw)
    arts = [a for s in data[2].get("sections", []) for a in s.get("articles", [])]
    for tid, (idx, ar_t, en_t) in MAP.items():
        verses = build_verses(arts[idx])
        if not verses:
            print(f"  ⚠️  {tid}: no Arabic, skipped")
            continue
        (OUT / f"{tid}.json").write_text(json.dumps({
            "id": tid, "ar_title": ar_t, "en_title": en_t,
            "count": len(verses), "verses": verses,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {tid}: {len(verses)} passages ({en_t})")


if __name__ == "__main__":
    main()
