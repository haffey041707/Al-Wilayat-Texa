#!/usr/bin/env python3
"""Ingest the Sahifa al-Sajjadiyya (Chittick, 'The Psalms of Islam') in English
from the bilingual duas.org PDF. The PDF's Arabic uses a broken font encoding and
cannot be recovered, but the English translation extracts cleanly.

Output:
  app/data/dua/makarim.json  — Supplication 20 (Makarim al-Akhlaq)
  app/data/dua/sahifa.json   — the full collection (54 supplications)
Verses use {n, ar:"", en, head?} — English-only; `head` marks supplication titles.
"""
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
OUT.mkdir(parents=True, exist_ok=True)
PDF = Path("/tmp/sahifa.pdf")
URL = "https://www.duas.org/pdfs/Sahifa%20Kamila%20English_arabic.pdf"

FOOTER = re.compile(r"Presented by|ziaraat\.com|www\.|^\s*\d+\s*$", re.I)


def load_text() -> str:
    if not PDF.exists():
        subprocess.run(["curl", "-sSL", "-m", "180", "-A", "Mozilla/5.0", URL, "-o", str(PDF)])
    import pypdf
    r = pypdf.PdfReader(str(PDF))
    pages = [re.sub(r"[ \t]+", " ", re.sub(r"[؀-ۿ]+", " ", (p.extract_text() or ""))) for p in r.pages]
    return "\n".join(pages)


def lines_between(text: str, start: int, end: int) -> list[str]:
    out = []
    for ln in text[start:end].split("\n"):
        ln = ln.strip()
        if len(re.sub(r"[^A-Za-z]", "", ln)) < 2:
            continue
        if FOOTER.search(ln):
            continue
        out.append(ln)
    return out


def to_verses(lines: list[str]) -> list[dict]:
    verses = []
    for ln in lines:
        is_head = bool(re.match(r"\d{1,2}\.\s+His Supplication", ln)) or \
            ln.isupper() and len(ln) > 6
        verses.append({"n": len(verses) + 1, "ar": "", "en": ln, "head": is_head})
    return verses


def main():
    text = load_text()

    # ----- Makarim (Supplication 20) by content boundaries -----
    s = text.find("cause my faith to reach the most perfect faith")
    op = text.rfind("bless Muhammad and his Household", max(0, s - 400), s)
    s = op if op > 0 else s
    nxt = re.search(r"(His Supplication when Something|\bSorrow\b)", text[s + 200:])
    e = s + 200 + nxt.start() if nxt else s + 8000
    mk = [ln for ln in lines_between(text, s, e) if "Supplication" not in ln]
    (OUT / "makarim.json").write_text(json.dumps({
        "id": "makarim", "ar_title": "مكارم الأخلاق",
        "en_title": "Dua Makarim al-Akhlaq (Sahifa, Supplication 20) — English",
        "count": len(mk), "verses": [{"n": i + 1, "ar": "", "en": l} for i, l in enumerate(mk)],
    }, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ makarim: {len(mk)} lines (English)")

    # ----- Full Sahifa: body from Supplication 1 to end of 54 -----
    # Supplication 1's body opens "Praise belongs to God, the First, without a first…"
    anchor = text.find("the First, without a first")
    b0 = text.rfind("His Supplication", max(0, anchor - 400), anchor) if anchor > 0 else 0
    if b0 < 0:
        b0 = anchor if anchor > 0 else 0
    b1 = text.rfind("chastisement of the Fire")
    body = lines_between(text, max(0, b0), b1 + 60 if b1 > 0 else len(text))
    verses = to_verses(body)
    (OUT / "sahifa.json").write_text(json.dumps({
        "id": "sahifa", "ar_title": "الصحيفة السجادية",
        "en_title": "Al-Sahifa al-Sajjadiyya — The Psalms of Islam (English)",
        "count": len(verses), "verses": verses,
    }, ensure_ascii=False), encoding="utf-8")
    heads = sum(1 for v in verses if v.get("head"))
    print(f"  ✅ sahifa: {len(verses)} lines, {heads} supplication headers (English)")


if __name__ == "__main__":
    main()
