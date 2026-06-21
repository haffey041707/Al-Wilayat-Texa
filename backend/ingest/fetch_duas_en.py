#!/usr/bin/env python3
"""Re-source duas with Arabic + ENGLISH from duas.org's static pages
(class="Ara" Arabic, class="Tra" English), replacing the earlier Arabic+Persian.

Output: app/data/dua/{id}.json
"""
import html as H
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"

# id -> (url, arabic title, english title)
DUAS = {
    "tawassul":       ("https://www.duas.org/mobile/dua-tawassul.html",
                       "دعاء التوسل", "Dua al-Tawassul"),
    "faraj":          ("https://www.duas.org/mobile/dua-faraj.html",
                       "دعاء الفرج", "Dua al-Faraj"),
    "jawshan":        ("https://www.duas.org/mobile/ramadan-dua-jawshan-kabeer.html",
                       "دعاء الجوشن الكبير", "Dua Jawshan al-Kabir"),
    "jawshan-saghir": ("https://www.duas.org/mobile/ramadan-dua-jawshan-sagheer.html",
                       "دعاء الجوشن الصغير", "Dua Jawshan al-Saghir"),
    "iftitah":        ("https://www.duas.org/iftitah.htm",
                       "دعاء الافتتاح", "Dua al-Iftitah"),
    "abu-hamza":      ("https://www.duas.org/thumali.htm",
                       "دعاء أبي حمزة الثمالي", "Dua Abu Hamza al-Thumali"),
}


def clean(t):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def fetch(url):
    return subprocess.run(["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", url],
                          capture_output=True).stdout.decode("utf-8", errors="ignore")


_EN = re.compile(r"\b(the|and|of|to|your|you|who|which|with|upon|we|are|is|be|for|"
                 r"from|whom|all|my|me|his|their|them|that|this|have|not|may)\b", re.I)


def english_score(s):
    # English translation is rich in function words; Arabic transliteration has ~none
    return len(_EN.findall(s))


def build(h):
    # pick the tab-pane richest in translation pairs
    panes = re.split(r'class="tab-pane', h)
    best = max(panes, key=lambda p: len(re.findall(r'class="(?:Tra|Trl)"', p))
              if re.search(r'class="Ara"', p) else -1)
    # walk Ara / Trl / Tra in order; for each Arabic verse choose the English
    # translation among the following Trl/Tra (the one that is NOT transliteration).
    toks = re.findall(r'class="(Ara|Trl|Tra)"[^>]*>(.*?)</(?:p|div|span|td)>', best, re.S)
    vs, cur, cands = [], None, []

    def flush():
        if cur is not None and cands:
            cur["en"] = max(cands, key=english_score)

    for c, b in toks:
        t = clean(b)
        if not t:
            continue
        if c == "Ara":
            flush()
            cur = {"n": len(vs) + 1, "ar": t, "en": ""}; vs.append(cur); cands = []
        elif cur is not None:
            cands.append(t)
    flush()
    return vs


def main():
    for tid, (url, ar_t, en_t) in DUAS.items():
        vs = build(fetch(url))
        if not vs:
            print(f"  ⚠️  {tid}: no verses, kept existing"); continue
        (OUT / f"{tid}.json").write_text(json.dumps({
            "id": tid, "ar_title": ar_t, "en_title": en_t,
            "count": len(vs), "verses": vs}, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {tid}: {len(vs)} verses (Arabic + English)")


if __name__ == "__main__":
    main()
