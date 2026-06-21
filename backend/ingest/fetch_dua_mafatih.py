#!/usr/bin/env python3
"""Ingest full dua texts (Arabic + Persian translation) from the complete
Mafatih al-Jinan dataset (aminpaydar/Mafatih).
  chapter 0 = ادعیه (supplications), chapter 1 = اعمال سال (yearly deeds),
  chapter 2 = زیارات (ziyarat — holds Nudba, Ahd and the occultation dua).

Output: app/data/dua/{id}.json → {id, ar_title, en_title, count, verses:[{n,ar,en}]}
"""
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
OUT.mkdir(parents=True, exist_ok=True)
SRC = "https://raw.githubusercontent.com/aminpaydar/Mafatih/HEAD/mafatih-server/chapters.json"

# textId -> (chapter, article index, arabic title, english title)
MAP = {
    "kumayl":         (0, 38,  "دعاء كميل",            "Dua Kumayl"),
    "tawassul":       (0, 49,  "دعاء التوسل",          "Dua al-Tawassul"),
    "jawshan":        (0, 45,  "دعاء الجوشن الكبير",   "Dua Jawshan al-Kabir"),
    "sabah":          (0, 37,  "دعاء الصباح",          "Dua al-Sabah"),
    "jawshan-saghir": (0, 46,  "دعاء الجوشن الصغير",   "Dua Jawshan al-Saghir"),
    "faraj":          (0, 51,  "دعاء الفرج",           "Dua al-Faraj"),
    "iftitah":        (1, 29,  "دعاء الافتتاح",        "Dua al-Iftitah"),
    "abu-hamza":      (1, 34,  "دعاء أبي حمزة الثمالي", "Dua Abu Hamza al-Thumali"),
    "shabaniyya":     (1, 19,  "المناجاة الشعبانية",   "Munajat al-Sha'baniyya"),
    "nudba":          (2, 122, "دعاء الندبة",          "Dua al-Nudba"),
    "ahd":            (2, 124, "دعاء العهد",           "Dua al-Ahd"),
    "ghayba":         (2, 125, "دعاء الإمام في الغيبة", "Dua for the Imam during the Occultation"),
}


def is_ar(c: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in c)


def build_verses(article: dict) -> list[dict]:
    verses = []
    for it in article.get("items", []):
        t, c = it.get("type"), (it.get("content") or "").strip()
        if not c:
            continue
        if t == "Text" and is_ar(c):
            verses.append({"n": len(verses) + 1, "ar": c, "en": ""})
        elif t == "Translate" and verses and not verses[-1]["en"]:
            verses[-1]["en"] = c
    return verses


def main():
    raw = subprocess.run(["curl", "-sSL", "-m", "60", SRC],
                         capture_output=True).stdout.decode("utf-8", errors="ignore")
    data = json.loads(raw)
    chapters = [[a for s in ch.get("sections", []) for a in s.get("articles", [])] for ch in data]
    for tid, (ci, idx, ar_t, en_t) in MAP.items():
        verses = build_verses(chapters[ci][idx])
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
