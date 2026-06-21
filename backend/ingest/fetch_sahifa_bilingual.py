#!/usr/bin/env python3
"""Build a bilingual Sahifa al-Sajjadiyya:
  • Arabic   — ar.wikisource.org (54 supplications, one clean paragraph each)
  • English  — Chittick 'Psalms of Islam' from the duas.org PDF (English extracts
               cleanly; the PDF's Arabic is in a broken font and is discarded)

Both run supplication 1→54 in order, so we key the English segments by their
"N. His Supplication …" header number and pair them with Arabic paragraph N.

Each supplication is rendered as: a title header, then the Arabic recitation
(split into phrase verses), then the English translation lines.

Output: app/data/dua/sahifa.json (all 54) and app/data/dua/makarim.json (#20).
"""
import html as H
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "dua"
PDF = Path("/tmp/sahifa.pdf")
WIKI = ("https://ar.wikisource.org/wiki/"
        "%D8%A7%D9%84%D8%B5%D8%AD%D9%8A%D9%81%D8%A9_%D8%A7%D9%84%D8%B3%D8%AC%D8%A7%D8%AF%D9%8A%D8%A9")
PDF_URL = "https://www.duas.org/pdfs/Sahifa%20Kamila%20English_arabic.pdf"
FOOT = re.compile(r"Presented by|ziaraat\.com|^www\.|^\s*\d+\s*$", re.I)


def clean(t):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def arabic_supplications():
    h = subprocess.run(["curl", "-sSL", "-m", "40", "-A", "Mozilla/5.0", WIKI],
                       capture_output=True).stdout.decode("utf-8", errors="ignore")
    titles = [clean(x) for x in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", h, re.S)
              if clean(x).startswith(("الدعاء", "الدعای"))]
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", h, re.S) if len(clean(p)) > 30]
    paras = paras[:54]
    return titles, paras


def english_text():
    """Full clean English body (Chittick). Arabic glyphs are stripped (broken font)."""
    import pypdf
    if not PDF.exists():
        subprocess.run(["curl", "-sSL", "-m", "180", "-A", "Mozilla/5.0", PDF_URL, "-o", str(PDF)])
    r = pypdf.PdfReader(str(PDF))
    return "\n".join(re.sub(r"[ \t]+", " ", re.sub(r"[؀-ۿ]+", " ", (p.extract_text() or "")))
                     for p in r.pages)


def clean_lines(segment):
    out = []
    for ln in segment.split("\n"):
        ln = ln.strip()
        if len(re.sub(r"[^A-Za-z]", "", ln)) >= 2 and not FOOT.search(ln) and "Supplication" not in ln:
            out.append(ln)
    return out


def makarim_english(text):
    """Supplication 20 English, isolated by its unmistakable opening/closing phrases."""
    s = text.find("cause my faith to reach the most perfect faith")
    op = text.rfind("bless Muhammad and his Household", max(0, s - 400), s)
    s = op if op > 0 else s
    nxt = re.search(r"(His Supplication when Something|\bSorrow\b)", text[s + 200:])
    e = s + 200 + nxt.start() if nxt else s + 8000
    return clean_lines(text[s:e])


def english_by_supplication(text):
    """Segment the English body into per-supplication line-lists, keyed by number,
    using the supplication titles (which recur at each body section start, in order)."""
    toc = re.findall(r"(\d{1,2})\.\s+(His Supplication\b[^\n]{3,110}?)\s*\.{2,}\s*\d", text)
    titles = {}
    for n, t in toc:
        n = int(n); t = re.sub(r"\s+", " ", re.sub(r"\d+$", "", t)).strip(" .,")
        if 1 <= n <= 54 and n not in titles:
            titles[n] = t
    BODY = 135000  # body section begins after the front matter / lists
    pos = {}
    for n, t in titles.items():
        for probe in (t, t[:40], t[:30]):
            m = re.search(re.escape(probe), text[BODY:])
            if m:
                pos[n] = BODY + m.start(); break
    order = sorted(pos, key=lambda n: pos[n])
    b1 = text.rfind("chastisement of the Fire") + 60
    segs = {}
    for i, n in enumerate(order):
        start = pos[n]
        end = pos[order[i + 1]] if i + 1 < len(order) else b1
        # drop the title line itself, keep the body lines
        body = text[start:end]
        body = re.sub(r"^[^\n]*\n", "", body, count=1)
        segs[n] = clean_lines(body)
    # English before the first anchor → goes to supplication 1
    if order:
        head_txt = text[text.find("the First, without a first") - 60:pos[order[0]]]
        segs.setdefault(order[0], [])
        pre = clean_lines(head_txt)
        if 1 not in segs and pre:
            segs[1] = pre
    return segs


def phrases(arabic):
    return [s.strip() for s in re.split(r"[،۔.؛]", arabic) if len(s.strip()) > 1]


def build_verses(ar_para, en_lines):
    v = []
    for p in phrases(ar_para):
        v.append({"n": len(v) + 1, "ar": p, "en": ""})
    for ln in en_lines:
        v.append({"n": len(v) + 1, "ar": "", "en": ln})
    return v


def main():
    titles, paras = arabic_supplications()
    text = english_text()
    print(f"  arabic supplications: {len(paras)}")

    # ---- Makarim = supplication 20: Arabic recitation + English translation ----
    mk = build_verses(paras[19], makarim_english(text))
    (OUT / "makarim.json").write_text(json.dumps({
        "id": "makarim", "ar_title": "مكارم الأخلاق",
        "en_title": "Dua Makarim al-Akhlaq (Sahifa, Supplication 20)",
        "count": len(mk), "verses": mk}, ensure_ascii=False), encoding="utf-8")
    aen = sum(1 for v in mk if v["en"])
    print(f"  ✅ makarim: {len(mk)} verses (Arabic {len(mk)-aen} + English {aen})")

    # ---- Full Sahifa: per supplication, Arabic recitation then its English below ----
    en_segs = english_by_supplication(text)
    verses, withen = [], 0
    for i in range(len(paras)):
        n = i + 1
        title = titles[i] if i < len(titles) else f"الدعاء {n}"
        verses.append({"n": len(verses) + 1, "ar": "", "en": f"الدعاء {n} — {title}", "head": True})
        for p in phrases(paras[i]):
            verses.append({"n": len(verses) + 1, "ar": p, "en": ""})
        seg = en_segs.get(n, [])
        if seg:
            withen += 1
        for ln in seg:
            verses.append({"n": len(verses) + 1, "ar": "", "en": ln})
    (OUT / "sahifa.json").write_text(json.dumps({
        "id": "sahifa", "ar_title": "الصحيفة السجادية",
        "en_title": "Al-Sahifa al-Sajjadiyya — The Psalms of Islam (Arabic + English)",
        "count": len(verses), "verses": verses}, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ sahifa: {len(verses)} verses · {len(paras)} supplications · English under {withen}")


if __name__ == "__main__":
    main()
