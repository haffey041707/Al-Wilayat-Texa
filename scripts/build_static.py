#!/usr/bin/env python3
"""Pre-render every backend response into static JSON so the whole app can run
on GitHub Pages with no server. Reuses the real backend logic for correctness.

    python scripts/build_static.py

Output:
    docs/            <- copy of web/ (the GitHub Pages site root)
    docs/api/...     <- generated JSON the static frontend fetches
"""
import json
import re
import shutil
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import store as S          # noqa: E402
from app import content as C        # noqa: E402

DOCS = ROOT / "docs"
API = DOCS / "api"
DATA = ROOT / "backend" / "app" / "data"


def w(rel, obj):
    p = API / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def ch_num(chapter: str):
    m = re.search(r"(\d+)", chapter or "")
    return int(m.group(1)) if m else None


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    shutil.copytree(ROOT / "web", DOCS)
    API.mkdir(parents=True, exist_ok=True)
    # Turn on no-backend mode + stop GitHub Pages from running Jekyll on the data.
    flag = "<script>window.WILAYAT_STATIC=true;</script>\n  "
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    html = html.replace('<script src="js/data.js', flag + '<script src="js/data.js', 1)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print("• frontend copied to docs/ (+ static flag, .nojekyll)")

    # ---------------- Quran ----------------
    idx = S.quran_index()
    w("quran/surahs.json", idx)
    qsearch = []
    for s in idx["surahs"]:
        n = s["n"]
        data = S.surah(n)
        if not data:
            continue
        w(f"quran/surah/{n}.json", data)
        for v in data["verses"]:
            qsearch.append({"s": n, "a": v.get("n"), "ar": v.get("ar", ""), "en": v.get("en", ""),
                            "translit": v.get("translit", ""), "ur": v.get("ur", ""), "fa": v.get("fa", "")})
    for j in range(1, 31):
        w(f"quran/juz/{j}.json", S.juz(j))
    w("search/quran.json", qsearch)
    print(f"• quran: {len(idx['surahs'])} surahs, 30 juz, {len(qsearch)} verses indexed")

    # ---------------- Tafsir (store each commentary ONCE + a tiny map) ----------------
    eds = S.tafsir_editions()
    w("quran/tafsir/editions.json", {"editions": eds})
    tchunks = 0
    for ed in eds:
        e = ed["edition"]
        tdata = S._tafsir(e)
        if not tdata:
            continue
        w(f"quran/tafsir/{e}/map.json", tdata["mapping"])      # {"s:a": cid} — small
        meta = {"edition": tdata["edition"], "name": tdata["name"],
                "author": tdata.get("author"), "language": tdata["language"]}
        for cid, text in tdata["content"].items():
            w(f"quran/tafsir/{e}/c/{cid}.json", {**meta, "text": text})
            tchunks += 1
    print(f"• tafsir: {len(eds)} editions, {tchunks} unique commentaries")

    # ---------------- Hadith ----------------
    cat = S.hadith_catalog()
    w("hadith/books.json", {"books": cat})
    href = []
    pages = 0
    for b in cat:
        bid = b["bookId"]
        if not b.get("downloaded"):
            continue
        page = 1
        while True:
            pg = S.hadith_page(bid, page, 20)
            if not pg or not pg.get("hadiths"):
                break
            w(f"hadith/book/{bid}/{page}.json", pg)
            pages += 1
            if page * 20 >= pg.get("total", 0):
                break
            page += 1
        raw = S.hadith_book(bid)
        ed = S.book_edition(raw)
        vol_m = re.search(r"Volume-(\d+)", bid)
        vol = vol_m.group(1) if vol_m else None
        ar_core = S._AR_NAMES.get(bid, "").split("–")[0].strip()
        items = [{"id": h.get("id"), "ch": ch_num(h.get("chapter", "")),
                  "en": (h.get("en", "") or "")[:200], "ar": (h.get("ar", "") or "")[:200]}
                 for h in raw["hadiths"]]
        href.append({"bookId": bid, "name": raw.get("name"), "ar": ar_core,
                     "vol": vol, "ed": ed, "items": items})
    w("search/hadith.json", href)
    print(f"• hadith: {sum(1 for b in cat if b.get('downloaded'))} books, {pages} pages, indexed for search")

    # ---------------- Dua ----------------
    w("dua.json", {"duas": C.DUAS})
    w("dua/texts.json", S.hadith_by_category(
        ["supplication", "du'a", "dua", "invocation", "seeking refuge", "dhikr", "remembrance"], limit=300))
    for f in (DATA / "dua").glob("*.json"):
        w(f"dua/full/{f.stem}.json", json.loads(f.read_text(encoding="utf-8")))

    # ---------------- Ziyarat ----------------
    w("ziyarat.json", {"ziyarat": C.ZIYARAT})
    zt = S.hadith_by_category(["ziyara", "visiting", "pilgrimage"],
                              books=["Kamil-al-Ziyarat-Qummi"], limit=300)
    if not zt["count"]:
        zt = S.hadith_by_category(["ziyara", "visiting"], limit=300)
    w("ziyarat/texts.json", zt)
    for f in (DATA / "ziyarat").glob("*.json"):
        w(f"ziyarat/full/{f.stem}.json", json.loads(f.read_text(encoding="utf-8")))
    print("• dua + ziyarat: lists, full texts, corpus texts")

    # ---------------- Misc ----------------
    w("prayer/times.json", {"method": "Shia (Leva Institute, Qum)", "location": {}, "times": C.PRAYERS})
    w("calendar/events.json", {"events": C.EVENTS})
    w("ahlulbayt.json", {"infallibles": C.MASUMEEN})
    w("library/pdfs.json", {"pdfs": C.PDF_BOOKS})
    w("stats.json", S.stats())
    w("ai/status.json", {"enabled": False})
    print("• prayer, calendar, ahlulbayt, library, stats")
    print("\n✅ Static site built at docs/")


if __name__ == "__main__":
    main()
