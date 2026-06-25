"""Data store — loads downloaded Quran + hadith JSON from app/data.

Falls back to the small seed sets in content.py when a full download is not
present yet, so the API always responds.
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app import content as SEED


def _norm(s: str) -> str:
    """Lower-case, strip diacritics, and collapse punctuation to spaces — so
    'Al-Kāfi, Vol. 1, H. 100' and 'al-kafi vol 1 h 100' compare the same."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

DATA = Path(__file__).resolve().parent / "data"
QURAN_DIR = DATA / "quran"
HADITH_DIR = DATA / "hadith"
TAFSIR_DIR = DATA / "tafsir"
DUA_DIR = DATA / "dua"
ZIYARAT_DIR = DATA / "ziyarat"


def _texts_search(folder: Path, q: str, limit: int = 40) -> dict:
    """Search verse-by-verse dua/ziyarat JSON files for a line of text."""
    ql = q.lower().strip()
    if not ql or not folder.exists():
        return {"count": 0, "results": []}
    hits = []
    for f in sorted(folder.glob("*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        tid = doc.get("id", f.stem)
        title = doc.get("en_title") or doc.get("ar_title") or f.stem
        for v in doc.get("verses", []):
            if v.get("en") and ql in v["en"].lower():
                hits.append({"id": tid, "title": title, "ar": v.get("ar", ""), "en": v["en"]})
                if len(hits) >= limit:
                    return {"count": len(hits), "results": hits}
    return {"count": len(hits), "results": hits}


def dua_search(q: str, limit: int = 40) -> dict:
    return _texts_search(DUA_DIR, q, limit)


def ziyarat_search(q: str, limit: int = 40) -> dict:
    return _texts_search(ZIYARAT_DIR, q, limit)


# ---------------- Quran ----------------
@lru_cache(maxsize=1)
def quran_index() -> dict:
    idx = QURAN_DIR / "index.json"
    if idx.exists():
        return json.loads(idx.read_text(encoding="utf-8"))
    return {"count": len(SEED.SURAHS), "surahs": SEED.SURAHS, "seed": True}


@lru_cache(maxsize=128)
def surah(n: int) -> dict | None:
    f = QURAN_DIR / f"surah_{n}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if n == 1:  # seed fallback
        return {"n": 1, "en": "Al-Fatihah", "ar": "الفاتحة", "verses": SEED.FATIHA, "seed": True}
    return None


def juz(number: int) -> dict:
    """Collect every verse belonging to a given juz (1..30)."""
    verses = []
    for s in quran_index()["surahs"]:
        data = surah(s["n"])
        if not data:
            continue
        for v in data["verses"]:
            if v.get("juz") == number:
                verses.append({"surah": s["n"], "surahName": data["en"], **v})
    return {"juz": number, "count": len(verses), "verses": verses}


def quran_search(q: str, limit: int = 50) -> dict:
    ql = q.lower().strip()
    hits = []
    if not ql:
        return {"count": 0, "results": []}
    for s in quran_index()["surahs"]:
        data = surah(s["n"])
        if not data:
            continue
        for v in data["verses"]:
            if ql in v.get("en", "").lower() or ql in v.get("translit", "").lower():
                hits.append({"surah": s["n"], "surahName": data["en"], "ayah": v["n"],
                             "ar": v["ar"], "en": v["en"]})
                if len(hits) >= limit:
                    return {"count": len(hits), "results": hits}
    return {"count": len(hits), "results": hits}


# ---------------- Hadith ----------------
# Books in the Thaqalayn catalog whose hadith are not served by its API.
# Every catalog book is now sourced. al-Faqih comes from the PDF edition as a
# single combined full-text book; _catalog.json holds that one entry directly.
# SUPERSEDED_BOOKS is retained as a defensive guard against the old 5 split
# placeholder IDs reappearing; it should match nothing in the current catalog.
UNAVAILABLE_BOOKS: set[str] = set()
SUPERSEDED_BOOKS = {
    "Man-La-Yahduruh-al-Faqih-Volume-1-Saduq", "Man-La-Yahduruh-al-Faqih-Volume-2-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-3-Saduq", "Man-La-Yahduruh-al-Faqih-Volume-4-Saduq",
    "Man-La-Yahduruh-al-Faqih-Volume-5-Saduq",
}


_ARABIC_RE = re.compile(r"[؀-ۿ]")
_AR2EN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def book_edition(book: dict) -> str:
    """Mark the collection's edition by its ORIGINAL language: 'ar' (an Arabic
    work, e.g. al-Kāfi — an English translation may also be shown) or 'en' (an
    English-language work with no Arabic original, e.g. Peshawar Nights)."""
    hs = (book or {}).get("hadiths", [])[:200]
    has_ar = any(_ARABIC_RE.search(h.get("ar", "") or "") for h in hs)
    return "ar" if has_ar else "en"


def hadith_catalog() -> list:  # not cached: reflects live download progress
    cat = HADITH_DIR / "_catalog.json"
    if cat.exists():
        downloaded = {p.stem for p in HADITH_DIR.glob("*.json") if not p.stem.startswith("_")}
        books = [b for b in json.loads(cat.read_text(encoding="utf-8"))
                 if b["bookId"] not in SUPERSEDED_BOOKS]
        for b in books:
            b["downloaded"] = b["bookId"] in downloaded
            b["unavailable"] = b["bookId"] in UNAVAILABLE_BOOKS
            if b["downloaded"]:
                bk = hadith_book(b["bookId"])
                if bk:
                    b["count"] = len(bk.get("hadiths", []))
                    b["edition"] = book_edition(bk)
        # Append extra books on disk that aren't in the Thaqalayn catalog
        catalog_ids = {b["bookId"] for b in books}
        for stem in sorted(downloaded - catalog_ids):
            bk = hadith_book(stem)
            if bk:
                books.append({
                    "bookId": stem, "name": bk.get("name", stem),
                    "englishName": bk.get("name", stem), "author": bk.get("author", ""),
                    "count": bk.get("count", len(bk.get("hadiths", []))),
                    "edition": book_edition(bk),
                    "description": f"Source: {bk.get('source', 'added')}",
                    "downloaded": True, "unavailable": False,
                })
        return books
    return [{**b, "bookId": b["id"], "downloaded": False, "unavailable": False} for b in SEED.HADITH_BOOKS]


# Arabic names of the collections (keyed by book id) — used to render the
# reference in Arabic for Arabic-edition books.
_AR_NAMES = {
    "Al-Kafi-Volume-1-Kulayni": "الكافي – الجزء ١", "Al-Kafi-Volume-2-Kulayni": "الكافي – الجزء ٢",
    "Al-Kafi-Volume-3-Kulayni": "الكافي – الجزء ٣", "Al-Kafi-Volume-4-Kulayni": "الكافي – الجزء ٤",
    "Al-Kafi-Volume-5-Kulayni": "الكافي – الجزء ٥", "Al-Kafi-Volume-6-Kulayni": "الكافي – الجزء ٦",
    "Al-Kafi-Volume-7-Kulayni": "الكافي – الجزء ٧", "Al-Kafi-Volume-8-Kulayni": "الكافي – الجزء ٨",
    "Man-La-Yahduruh-al-Faqih-Saduq": "من لا يحضره الفقيه", "Nahj-al-Balagha-Radi": "نهج البلاغة",
    "Al-Amali-Saduq": "الأمالي (الصدوق)", "Al-Amali-Mufid": "الأمالي (المفيد)",
    "Al-Khisal-Saduq": "الخصال", "Al-Tawhid-Saduq": "التوحيد", "Maani-al-Akhbar-Saduq": "معاني الأخبار",
    "Thawab-al-Amal-wa-iqab-al-Amal-Saduq": "ثواب الأعمال وعقاب الأعمال",
    "Kamal-al-Din-wa-Tamam-al-Nima-Saduq": "كمال الدين وتمام النعمة",
    "Uyun-akhbar-al-Rida-Volume-1-Saduq": "عيون أخبار الرضا – الجزء ١",
    "Uyun-akhbar-al-Rida-Volume-2-Saduq": "عيون أخبار الرضا – الجزء ٢",
    "Sifat-al-Shia-Saduq": "صفات الشيعة", "Fadail-al-Shia-Saduq": "فضائل الشيعة",
    "Kitab-al-Ghayba-Numani": "كتاب الغيبة (النعماني)", "Kitab-al-Ghayba-Tusi": "كتاب الغيبة (الطوسي)",
    "Kamil-al-Ziyarat-Qummi": "كامل الزيارات", "Kitab-al-Mumin-Ahwazi": "كتاب المؤمن",
    "Kitab-al-Zuhd-Ahwazi": "كتاب الزهد", "Kitab-al-Duafa-Ghadairi": "كتاب الضعفاء",
    "Risalat-al-Huquq-Abidin": "رسالة الحقوق",
    "Mujam-al-Ahadith-al-Mutabara-Muhsini": "معجم الأحاديث المعتبرة",
    "Peshawar-Nights-Shirazi": "ليالي بيشاور",
}
_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _book_reference(book_id: str, name: str, h: dict, edition: str = "ar") -> dict:
    """Build a correct citation with exact chapter and hadith numbers.

    The English citation is always provided. For Arabic-edition books an Arabic
    citation (`ar_citation`) is added so the reference reads in Arabic regardless
    of the chosen UI language."""
    vol_m = re.search(r"Volume-(\d+)", book_id)
    vol = vol_m.group(1) if vol_m else None
    if not vol:  # books that carry the volume in the category (e.g. al-Faqih PDF)
        cv = re.match(r"Volume\s+(\d+)$", h.get("category") or "")
        vol = cv.group(1) if cv else None
    title = f"{name}, Vol. {vol}" if vol else name
    chapter = h.get("chapter") or ""
    # chapter number: leading "N." (Thaqalayn) or "Chapter/Sermon/Letter N" (al-islam)
    cm = re.match(r"\s*(?:chapter|sermon|letter|saying|hikmah)?\s*(\d+)\s*[.:)\-]", chapter, re.I)
    chap_no = cm.group(1) if cm else None
    chap_title = re.sub(r"^\s*(?:chapter|sermon|letter|saying|hikmah)?\s*\d+\s*[.:)\-]\s*", "",
                        chapter, flags=re.I).strip()

    parts = [title]
    if chap_no:
        parts.append(f"Ch. {chap_no}")
    if h.get("id"):
        parts.append(f"H. {h['id']}")
    citation = ", ".join(parts)

    loc = " › ".join(p for p in (h.get("category"), chap_title) if p)
    ref = {"citation": citation, "book": title, "category": h.get("category"),
           "chapter_number": chap_no, "chapter": chap_title, "number": h.get("id"),
           "location": loc, "edition": edition}

    # Arabic citation for Arabic-edition books: «الكافي – الجزء ١، باب ٥، ح ١٠٠».
    if edition == "ar":
        ar_name = _AR_NAMES.get(book_id)
        if ar_name:
            ar_parts = [ar_name]
            if chap_no:
                ar_parts.append("باب " + chap_no.translate(_AR_DIGITS))
            if h.get("id"):
                ar_parts.append("ح " + str(h["id"]).translate(_AR_DIGITS))
            ref["ar_citation"] = "، ".join(ar_parts)
    return ref


def _attach_ref(book_id: str, name: str, h: dict, edition: str = "ar") -> dict:
    return {**h, "reference": _book_reference(book_id, name, h, edition)}


@lru_cache(maxsize=64)
def hadith_book(book_id: str) -> dict | None:
    f = HADITH_DIR / f"{book_id}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def hadith_page(book_id: str, page: int, size: int = 20) -> dict | None:
    book = hadith_book(book_id)
    if not book:
        return None
    start = (page - 1) * size
    name = book.get("name")
    ed = book_edition(book)
    items = [_attach_ref(book_id, name, h, ed) for h in book["hadiths"][start:start + size]]
    return {"bookId": book_id, "name": name, "total": book["count"], "edition": ed,
            "page": page, "size": size, "hadiths": items}


def _downloaded_book_ids() -> list[str]:
    return [p.stem for p in HADITH_DIR.glob("*.json") if not p.stem.startswith("_")]


def hadith_by_category(keywords: list[str], books: list[str] | None = None, limit: int = 300) -> dict:
    """Collect narrations whose category OR chapter matches any keyword.

    Used to surface real Shia supplications (al-Kafi 'Book of Supplication')
    and ziyarat (Kamil al-Ziyarat) from the downloaded corpus.
    """
    kw = [k.lower() for k in keywords]
    out, pending = [], []
    book_ids = books or _downloaded_book_ids()
    for bid in book_ids:
        book = hadith_book(bid)
        if not book:
            pending.append(bid)
            continue
        ed = book_edition(book)
        for h in book["hadiths"]:
            hay = f"{h.get('category', '')} {h.get('chapter', '')}".lower()
            if any(k in hay for k in kw):
                out.append({"bookId": bid, "name": book.get("name"), **_attach_ref(bid, book.get("name"), h, ed)})
                if len(out) >= limit:
                    return {"count": len(out), "results": out, "pending": pending}
    return {"count": len(out), "results": out, "pending": pending}


def hadith_search(q: str, book_id: str | None = None, limit: int = 50) -> dict:
    raw = (q or "").strip().translate(_AR2EN_DIGITS)   # Arabic-Indic digits → ASCII
    if not raw:
        return {"count": 0, "results": []}
    numeric = raw.isdigit()
    is_ar = bool(_ARABIC_RE.search(raw))
    norm = _norm(raw)                    # latin-only: "Al-Kāfi, Vol. 1, H. 100" -> "al kafi vol 1 h 100"

    def grab(*pats):
        for p in pats:
            m = re.search(p, raw, re.I)
            if m:
                return m.group(1)
        return None

    # Reference parts — recognise both Latin (Vol./Ch./H.) and Arabic (الجزء/باب/ح) forms.
    vol_q = grab(r"\bvol(?:ume)?\s*(\d+)", r"(?:الجزء|الجز|جزء|ج)\s*[.:]?\s*(\d+)")
    ch_q = grab(r"\bch(?:apter)?\s*(\d+)", r"باب\s*[.:]?\s*(\d+)")
    h_q = grab(r"\bh(?:adith)?\s*(\d+)", r"(?:الحديث|حديث|ح)\s*[.:]?\s*(\d+)")
    ref_mode = (not numeric) and bool(vol_q or ch_q or h_q)
    KEYWORDS = {"vol", "volume", "ch", "chapter", "h", "hadith"}
    name_tokens = [t for t in norm.split() if t not in KEYWORDS and not t.isdigit()] if ref_mode else []
    text_tokens = norm.split()

    # Arabic book-name cores present in the query (e.g. "الكافي").
    ar_cores = {bid: (_AR_NAMES.get(bid, "").split("–")[0].strip()) for bid in _AR_NAMES}
    query_has_ar_name = any(core and core in raw for core in ar_cores.values())

    hits = []
    books = [book_id] if book_id else [p.stem for p in HADITH_DIR.glob("*.json") if not p.stem.startswith("_")]
    for bid in books:
        book = hadith_book(bid)
        if not book:
            continue
        name_norm = _norm(book.get("name", ""))
        name_set = set(name_norm.split())
        ed = book_edition(book)
        vol_m = re.search(r"Volume-(\d+)", bid)
        vol = vol_m.group(1) if vol_m else None
        ar_core = ar_cores.get(bid, "")

        # Whole-book filters (reference mode): skip books by volume / name quickly.
        if ref_mode:
            if vol_q and vol != vol_q:
                continue
            if name_tokens and not all(t in name_set for t in name_tokens):
                continue
            if query_has_ar_name and ar_core and ar_core not in raw:
                continue

        for h in book["hadiths"]:
            hid = str(h.get("id", ""))
            if numeric:
                match = raw == hid                       # bare number = hadith number
            elif ref_mode:
                if h_q:
                    # Volume + hadith number uniquely identify a hadith; chapter is a hint.
                    match = (hid == h_q)
                elif ch_q:
                    cm = re.match(r"\s*(?:chapter|sermon|letter|saying|hikmah|باب)?\s*[.:]?\s*(\d+)",
                                  h.get("chapter", "") or "", re.I)
                    match = bool(cm and cm.group(1) == ch_q)
                else:
                    match = True
            elif is_ar:
                match = raw in (h.get("ar", "") or "")   # Arabic free-text search in the narration
            else:
                hay = name_norm + " " + _norm(h.get("en", ""))
                match = all(tok in hay for tok in text_tokens)
            if match:
                hits.append({"bookId": bid, "name": book.get("name"), **_attach_ref(bid, book.get("name"), h, ed)})
                if len(hits) >= limit:
                    return {"count": len(hits), "results": hits}
    return {"count": len(hits), "results": hits}


# ---------------- Tafsir (Shia: al-Mizan) ----------------
_TAFSIR_META = {
    "almizan_en": {"name": "Tafsir al-Mizan", "language": "en"},
    "almizan_ar": {"name": "تفسير الميزان", "language": "ar"},
    "almizan_fa": {"name": "تفسیر المیزان", "language": "fa"},
    "almizan_ur": {"name": "تفسیر المیزان", "language": "ur"},
}


def tafsir_editions() -> list:
    out = []
    for f in sorted(TAFSIR_DIR.glob("*.json")):
        m = _TAFSIR_META.get(f.stem, {"name": f.stem, "language": "en"})
        out.append({"edition": f.stem, "author": "Allamah Tabatabai", **m})
    return out


@lru_cache(maxsize=4)
def _tafsir(edition: str) -> dict | None:
    f = TAFSIR_DIR / f"{edition}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def tafsir_for(surah: int, ayah: int, edition: str = "almizan_en") -> dict | None:
    data = _tafsir(edition)
    if not data:
        return None
    cid = data["mapping"].get(f"{surah}:{ayah}")
    if cid is None:
        return None
    # al-Mizan comments on groups of verses; report the range this block covers.
    pref = f"{surah}:"
    same = [int(k.split(":")[1]) for k, v in data["mapping"].items()
            if v == cid and k.startswith(pref)]
    return {
        "edition": data["edition"], "name": data["name"], "author": data.get("author"),
        "language": data["language"], "surah": surah, "ayah": ayah,
        "covers": {"from": min(same), "to": max(same)} if same else None,
        "text": data["content"].get(str(cid), ""),
    }


def stats() -> dict:
    qi = quran_index()
    cat = hadith_catalog()
    downloaded = [b for b in cat if b.get("downloaded")]
    hadith_total = sum(b["count"] for b in downloaded)
    return {
        "quran_surahs": qi["count"],
        "quran_complete": not qi.get("seed", False),
        "hadith_books_available": len(cat),
        "hadith_books_downloaded": len(downloaded),
        "hadith_downloaded": hadith_total,
        "hadith_catalog_total": sum(b["count"] for b in cat),
    }
