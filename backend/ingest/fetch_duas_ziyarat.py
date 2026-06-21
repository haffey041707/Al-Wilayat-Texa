#!/usr/bin/env python3
"""Ingest full ziyarat texts (Arabic + English) from duas.org's static pages,
which expose a clean per-line structure:  <p class="Ara">…</p> Arabic,
<p class="Tra">…</p> English translation, <p class="Trl">…</p> transliteration.

Output: app/data/ziyarat/{id}.json → {id, ar_title, en_title, count, verses:[{n,ar,en}]}
"""
import html as H
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "ziyarat"
OUT.mkdir(parents=True, exist_ok=True)

# textId -> (url, arabic title, english title, optional pane-marker)
# When a marker is given, the tab-pane containing it is used; otherwise the pane
# with the most Arabic+English pairs is chosen.
PAGES = {
    "nahiya": ("https://www.duas.org/mobile/ziyarat-nahiya.html",
               "الزيارة الناحية المقدسة", "Ziyarat al-Nahiya al-Muqaddasa", None),
    "zaynab": ("https://www.duas.org/mobile/ziyarat-lady-zainab.html",
               "زيارة السيدة زينب", "Ziyarat of Lady Zaynab (SA)", None),
    "jamia-aimma": ("https://www.duas.org/mobile/ziarat-aimmat-momineen.html",
                    "زيارة أئمة المؤمنين", "Ziyarat A'immat al-Mu'minin", None),
    # second Ziyarat al-Nahiya — salutations to Imam al-Husayn and each martyr of Karbala
    "martyrs": ("https://www.duas.org/mobile/ziyarat-nahiya.html",
                "زيارة شهداء كربلاء", "Ziyarat of the Martyrs of Karbala", "أَوَّلَ قَتِيلٍ"),
    # re-sourced from Arabic+English (replacing the earlier Arabic+Persian versions)
    "arbaeen":       ("https://www.duas.org/mobile/ziyarat-arbaeen.html",
                      "زيارة الأربعين", "Ziyarat Arbaeen", None),
    "abbas":         ("https://www.duas.org/mobile/ziyarat-hazrat-abbas.html",
                      "زيارة أبي الفضل العباس", "Ziyarat of Hazrat Abbas (AS)", None),
    "fatima-masuma": ("https://www.duas.org/mobile/ziyarat-masuma-qom.html",
                      "زيارة السيدة المعصومة", "Ziyarat of Lady Fatima al-Masuma (SA)", None),
    "askariyyayn":   ("https://www.duas.org/mobile/imam-hassan-askari-as.html",
                      "زيارة العسكريين", "Ziyarat of al-Askariyyayn (AS)", None),
    "kazimayn":      ("https://www.duas.org/mobile/imam-musa-kazim-as.html",
                      "زيارة الكاظمين", "Ziyarat of al-Kazimayn (AS)", None),
    "prophet":       ("https://www.duas.org/mobile/holy-prophet-saw.html",
                      "زيارة رسول الله ﷺ", "Ziyarat of the Holy Prophet (SAWW)", None),
    "imam-rida":     ("https://www.duas.org/mobile/ziyarat-imam-ali-reza.html",
                      "زيارة الإمام الرضا", "Ziyarat of Imam al-Rida (AS)", None),
    "fatima-zahra":  ("https://www.duas.org/mobile/syeda-fatima-sa.html",
                      "زيارة فاطمة الزهراء", "Ziyarat of Lady Fatima al-Zahra (SA)", None),
    "imam-ali":      ("https://www.duas.org/mobile/ziyarat-imam-ali-shrine.html",
                      "زيارة أمير المؤمنين", "Ziyarat of Imam Ali (AS)", None),
    "arafah":        ("https://www.duas.org/arafa.htm",
                      "زيارة يوم عرفة", "Ziyarat of Imam al-Husayn on the Day of Arafah", None),
    "baqi":          ("https://www.duas.org/ziaratbaqi.htm",
                      "زيارة أئمة البقيع", "Ziyarat of the Imams of al-Baqi (AS)", None),
}


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def fetch(url: str) -> str:
    return subprocess.run(["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", url],
                          capture_output=True).stdout.decode("utf-8", errors="ignore")


def build(html_doc: str, marker: str | None = None) -> list[dict]:
    # duas.org pages carry several Bootstrap tab-panes (full text, no-translation,
    # transliteration-only…). Pick the pane containing `marker`, else the pane with
    # the most Arabic+English pairs, so we never concatenate different views.
    panes = re.split(r'class="tab-pane', html_doc)
    if marker:
        strip = lambda s: re.sub(r"[ًٌٍَُِّْٰـ\s]", "", s)
        m = strip(marker)
        best = next((p for p in panes if m in strip(p)), None)
        if best is None:
            raise SystemExit(f"marker not found: {marker}")
    else:
        best = max(panes, key=lambda p: len(re.findall(r'class="Ara"', p))
                  if re.search(r'class="Tra"', p) else -1)
    toks = re.findall(r'class="(Ara|Tra)"[^>]*>(.*?)</(?:p|div|span|td)>', best, re.S)
    verses, cur = [], None
    for cls, body in toks:
        txt = clean(body)
        if not txt:
            continue
        if cls == "Ara":
            cur = {"n": len(verses) + 1, "ar": txt, "en": ""}
            verses.append(cur)
        elif cls == "Tra" and cur is not None and not cur["en"]:
            cur["en"] = txt
            cur = None
    return verses


def main():
    cache = {}
    for tid, (url, ar_t, en_t, marker) in PAGES.items():
        if url not in cache:
            cache[url] = fetch(url)
        verses = build(cache[url], marker)
        if not verses:
            print(f"  ⚠️  {tid}: no verses, skipped")
            continue
        (OUT / f"{tid}.json").write_text(json.dumps({
            "id": tid, "ar_title": ar_t, "en_title": en_t,
            "count": len(verses), "verses": verses,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"  ✅ {tid}: {len(verses)} verses ({en_t})")


if __name__ == "__main__":
    main()
