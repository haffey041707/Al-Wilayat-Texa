#!/usr/bin/env python3
"""Extract Munajat al-Sha'baniyya (Arabic + English) from duas.org/shaban.htm,
where it sits inside the month-of-Sha'ban page as a contiguous block of verses
from "Allahumma salli ala Muhammad ... wasma' du'a'i" to "wa 'an siwaka munharifan".

Output: app/data/dua/shabaniyya.json
"""
import html as H
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
URL = "https://www.duas.org/shaban.htm"
_EN = re.compile(r"\b(the|and|of|to|your|you|who|which|with|upon|we|are|is|be|for|"
                 r"from|whom|all|my|me|his|their|them|that|this|have|not|may|O)\b", re.I)


def clean(t):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def strip(s):
    return re.sub(r"[ًٌٍَُِّْٰـ\s]", "", s)


def main():
    h = subprocess.run(["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", URL],
                       capture_output=True).stdout.decode("utf-8", errors="ignore")
    toks = [(c, clean(b)) for c, b in
            re.findall(r'class="(Ara|Tra|Trl)"[^>]*>(.*?)</(?:p|div|span|td)>', h, re.S)
            if clean(b)]
    # group into verses: each Ara plus the following translation candidates
    verses, cur, cands = [], None, []

    def flush():
        if cur is not None:
            cur["en"] = max(cands, key=lambda s: len(_EN.findall(s))) if cands else ""

    for c, t in toks:
        if c == "Ara":
            flush()
            cur = {"ar": t, "en": ""}; verses.append(cur); cands = []
        elif cur is not None:
            cands.append(t)
    flush()

    # slice the Sha'baniyya block by Arabic markers
    start = next((i for i, v in enumerate(verses)
                  if strip("اللهم صل على محمد وآل محمد") in strip(v["ar"])
                  and i + 1 < len(verses) and "دعوتك" in strip(verses[i + 1]["ar"])), None)
    end = next((i for i, v in enumerate(verses) if "سواكمنحرفا" in strip(v["ar"])), None)
    if start is None or end is None:
        raise SystemExit(f"markers not found (start={start} end={end})")
    block = verses[start:end + 1]
    out = [{"n": i + 1, "ar": v["ar"], "en": v["en"]} for i, v in enumerate(block)]
    (OUT / "shabaniyya.json").write_text(json.dumps({
        "id": "shabaniyya", "ar_title": "المناجاة الشعبانية",
        "en_title": "Munajat al-Sha'baniyya", "count": len(out), "verses": out,
    }, ensure_ascii=False), encoding="utf-8")
    en = sum(1 for v in out if v["en"])
    print(f"  ✅ shabaniyya: {len(out)} verses (English on {en})")


if __name__ == "__main__":
    main()
