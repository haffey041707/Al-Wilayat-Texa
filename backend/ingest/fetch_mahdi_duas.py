#!/usr/bin/env python3
"""Ingest Imam al-Mahdi (AJTF) supplications (Arabic + English) from duas.org's
imam-mahdi-ajtfs compilation page, sliced by section heading.

Output: app/data/dua/{id}.json
"""
import html as H
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
URL = "https://www.duas.org/mobile/imam-mahdi-ajtfs.html"

# id -> (heading marker, arabic title, english title)
DUAS = {
    "salamati": ("Kun le waliyek", "دعاء سلامة الإمام (اللهم كن لوليك)",
                 "Dua for the Imam's Safety (Allāhumma kun li-waliyyik)"),
    "ghayba":   ("Occultation -Long", "الدعاء في زمن الغيبة",
                 "The Supplication During the Age of Occultation"),
}
_EN = re.compile(r"\b(the|and|of|to|your|you|who|which|with|upon|we|are|is|be|for|"
                 r"from|whom|all|my|me|his|their|them|that|this|have|not|may|O)\b", re.I)


def clean(t):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def section(h, marker):
    parts = re.split(r"(<h[1-5][^>]*>.*?</h[1-5]>)", h, flags=re.S)
    for i, p in enumerate(parts):
        if re.match(r"<h", p) and marker.lower() in clean(p).lower():
            return parts[i + 1] if i + 1 < len(parts) else ""
    return ""


def build(body):
    toks = re.findall(r'class="(Ara|Tra|Trl)"[^>]*>(.*?)</(?:p|div|span|td)>', body, re.S)
    vs, cur, cands = [], None, []

    def flush():
        if cur is not None and cands:
            cur["en"] = max(cands, key=lambda s: len(_EN.findall(s)))

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
    h = subprocess.run(["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", URL],
                       capture_output=True).stdout.decode("utf-8", errors="ignore")
    for tid, (marker, ar_t, en_t) in DUAS.items():
        vs = build(section(h, marker))
        if not vs:
            print(f"  ⚠️  {tid}: section '{marker}' empty"); continue
        (OUT / f"{tid}.json").write_text(json.dumps({
            "id": tid, "ar_title": ar_t, "en_title": en_t,
            "count": len(vs), "verses": vs}, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {tid}: {len(vs)} verses (Arabic + English)")


if __name__ == "__main__":
    main()
