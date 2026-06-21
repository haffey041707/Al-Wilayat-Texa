#!/usr/bin/env python3
"""Build a phrase-aligned bilingual Sahifa al-Sajjadiyya from al-islam.org.

Each supplication chapter page (e.g. .../20-his-supplication-noble-moral-traits-and)
carries the Arabic as numbered <blockquote class="rtl"><p>N. …</p></blockquote>
units and the English as matching <p>N- …</p> paragraphs. Both are numbered 1..K
in lockstep, so we pair them by number to get one {n, ar, en} verse per unit —
Arabic with its English directly beneath it, like the other duas.

Outputs (overwrites the older block-layout versions):
  • app/data/dua/sahifa.json  — all 54 supplications, each verse aligned
  • app/data/dua/makarim.json — supplication 20 (Makarim al-Akhlaq) alone
"""
import html as H
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "data" / "dua"
SITE = "https://al-islam.org"
BOOK = "/sahifa-al-kamilah-al-sajjadiyya-imam-ali-zayn-al-abidin"
TOC = f"{SITE}{BOOK}/supplications"


def clean(t: str) -> str:
    return H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))).strip()


def fetch(url: str) -> str:
    """al-islam.org rate-limits with a tiny 503 body; retry until real HTML."""
    for _ in range(6):
        out = subprocess.run(
            ["curl", "-sSL", "--retry", "2", "--retry-delay", "3", "-m", "50",
             "-A", "Mozilla/5.0", url],
            capture_output=True).stdout.decode("utf-8", errors="ignore")
        if len(out) > 5000 and "not available" not in out[:200]:
            return out
        time.sleep(5)
    return out


def chapter_index() -> dict[int, tuple[str, str]]:
    """number -> (full url, chapter title) from the supplications table of contents."""
    h = fetch(TOC)
    seen: dict[int, tuple[str, str]] = {}
    for href, txt in re.findall(
            r'href="(' + re.escape(BOOK) + r'/[^"#]*)"[^>]*>(.*?)</a>', h, re.S):
        m = re.match(r"^\s*(\d+)\)\s*(.+)", clean(txt))
        if m:
            seen.setdefault(int(m.group(1)),
                            (SITE + href.split("#")[0], m.group(2).strip()))
    return seen


def parse_supplication(h: str) -> list[dict]:
    """Return [{n, ar, en}] paired by the running unit number. Any English unit
    with no matching Arabic is folded into the previous verse, so every verse
    carries both Arabic and its English."""
    ar: dict[int, str] = {}
    cur = None
    for c, body in re.findall(r'<blockquote class="(rtl)?"[^>]*>(.*?)</blockquote>', h, re.S):
        t = clean(body)
        if not t:
            continue
        m = re.match(r"^(\d+)\s*[.\-]\s*(.*)", t)
        if m:                                   # "N. …" begins unit N
            cur = int(m.group(1))
            ar[cur] = (ar.get(cur, "") + " " + m.group(2)).strip()
        elif cur is not None and not re.match(r"^\(\d+\)", t):  # continuation line of unit
            ar[cur] = (ar[cur] + " " + t).strip()

    en: dict[int, str] = {}
    for m in re.finditer(r"<p>\s*(\d+)\s*[-.]\s*(.*?)</p>", h, re.S):
        en[int(m.group(1))] = clean(m.group(2))

    verses: list[dict] = []
    for n in sorted(set(ar) | set(en)):
        a, e = ar.get(n, ""), en.get(n, "")
        if not a and e and verses:              # English-only straggler → merge upward
            verses[-1]["en"] = (verses[-1]["en"].rstrip() + " " + e).strip()
            continue
        verses.append({"n": len(verses) + 1, "ar": a, "en": e})
    return verses


def main():
    idx = chapter_index()
    print(f"  table of contents: {len(idx)} supplications")

    all_verses, makarim = [], None
    for n in range(1, 55):
        if n not in idx:
            print(f"  ⚠️  supplication {n}: not in TOC, skipped")
            continue
        url, title = idx[n]
        verses = parse_supplication(fetch(url))
        aligned = sum(1 for v in verses if v["ar"] and v["en"])
        print(f"  ✅ {n:>2}: {len(verses):>3} verses ({aligned} aligned) — {title[:55]}")

        if n == 20:
            mk = [{"n": i + 1, **{k: v[k] for k in ("ar", "en")}}
                  for i, v in enumerate(verses)]
            makarim = {"id": "makarim", "ar_title": "مكارم الأخلاق",
                       "en_title": "Dua Makarim al-Akhlaq (Sahifa, Supplication 20) — Arabic & English",
                       "count": len(mk), "verses": mk}

        all_verses.append({"n": len(all_verses) + 1, "ar": "",
                           "en": f"({n}) {title}", "head": True})
        for v in verses:
            all_verses.append({"n": len(all_verses) + 1, "ar": v["ar"], "en": v["en"]})
        time.sleep(2)  # be gentle with the server

    if makarim:
        (OUT / "makarim.json").write_text(
            json.dumps(makarim, ensure_ascii=False), encoding="utf-8")
        print(f"  → makarim.json: {makarim['count']} verses")

    sahifa = {"id": "sahifa", "ar_title": "الصحيفة السجادية",
              "en_title": "Al-Sahifa al-Sajjadiyya — The Psalms of Islam (Arabic & English)",
              "count": len(all_verses), "verses": all_verses}
    (OUT / "sahifa.json").write_text(json.dumps(sahifa, ensure_ascii=False), encoding="utf-8")
    aligned = sum(1 for v in all_verses if v["ar"] and v["en"])
    print(f"  → sahifa.json: {len(all_verses)} verses, {aligned} Arabic+English aligned")


if __name__ == "__main__":
    main()
