"""Content endpoints: Quran, Hadith, Dua, Ziyarat, Prayer, Calendar, Ahlul Bayt."""
from fastapi import APIRouter, HTTPException, Query

from app import content as C
from app import store

router = APIRouter(prefix="/api", tags=["content"])


# ---------- Quran (full 114 surahs / 30 juz when downloaded) ----------
@router.get("/quran/surahs")
def list_surahs():
    return store.quran_index()


@router.get("/quran/surah/{number}")
def get_surah(number: int):
    data = store.surah(number)
    if not data:
        raise HTTPException(404, "Surah not found")
    return data


@router.get("/quran/juz/{number}")
def get_juz(number: int):
    if not 1 <= number <= 30:
        raise HTTPException(400, "Juz must be 1..30")
    return store.juz(number)


@router.get("/quran/search")
def search_quran(q: str = Query(..., min_length=2), limit: int = 50):
    return store.quran_search(q, limit)


# ---------- Tafsir (Shia: al-Mizan, Allamah Tabatabai) ----------
@router.get("/quran/tafsir/editions")
def tafsir_editions():
    return {"editions": store.tafsir_editions()}


@router.get("/quran/tafsir/{surah}/{ayah}")
def tafsir(surah: int, ayah: int, edition: str = "almizan_en"):
    data = store.tafsir_for(surah, ayah, edition)
    if not data:
        raise HTTPException(404, "Tafsir not available for this verse/edition")
    return data


# ---------- Hadith (33 Shia collections via Thaqalayn) ----------
@router.get("/hadith/books")
def hadith_books():
    return {"books": store.hadith_catalog()}


@router.get("/hadith/book/{book_id}")
def hadith_book(book_id: str, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    data = store.hadith_page(book_id, page, size)
    if not data:
        raise HTTPException(404, f"Book '{book_id}' not downloaded yet")
    return data


@router.get("/hadith/search")
def hadith_search(q: str = Query(..., min_length=2), book_id: str | None = None, limit: int = 50):
    return store.hadith_search(q, book_id, limit)


# ---------- Dua / Ziyarat (curated index + real texts from corpus) ----------
@router.get("/dua")
def duas():
    return {"duas": C.DUAS}


@router.get("/dua/full/{dua_id}")
def dua_full(dua_id: str):
    """Full verse-by-verse dua text (Arabic + translation)."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "data" / "dua" / f"{dua_id}.json"
    if not f.exists():
        raise HTTPException(404, "Dua text not available")
    return json.loads(f.read_text(encoding="utf-8"))


@router.get("/dua/texts")
def dua_texts(limit: int = 300):
    """Real supplications from the Shia corpus (al-Kafi Book of Supplication, etc.)."""
    return store.hadith_by_category(
        ["supplication", "du'a", "dua", "invocation", "seeking refuge", "dhikr", "remembrance"],
        limit=limit,
    )


@router.get("/dua/search")
def search_dua(q: str = Query(..., min_length=2), limit: int = 40):
    return store.dua_search(q, limit)


@router.get("/ziyarat")
def ziyarat():
    return {"ziyarat": C.ZIYARAT}


@router.get("/ziyarat/full/{ziyarat_id}")
def ziyarat_full(ziyarat_id: str):
    """Full verse-by-verse ziyarat text (Arabic + English)."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "data" / "ziyarat" / f"{ziyarat_id}.json"
    if not f.exists():
        raise HTTPException(404, "Ziyarat text not available")
    return json.loads(f.read_text(encoding="utf-8"))


@router.get("/ziyarat/texts")
def ziyarat_texts(limit: int = 300):
    """Real ziyarat from Kamil al-Ziyarat (Ibn Qulawayh al-Qummi)."""
    res = store.hadith_by_category(["ziyara", "visiting", "pilgrimage"],
                                   books=["Kamil-al-Ziyarat-Qummi"], limit=limit)
    if not res["count"]:  # book not downloaded yet → scan whole corpus
        res = store.hadith_by_category(["ziyara", "visiting"], limit=limit)
    return res


@router.get("/ziyarat/search")
def search_ziyarat(q: str = Query(..., min_length=2), limit: int = 40):
    return store.ziyarat_search(q, limit)


# ---------- Prayer ----------
@router.get("/prayer/times")
def prayer_times(lat: float | None = None, lng: float | None = None):
    return {"method": "Shia (Leva Institute, Qum)", "location": {"lat": lat, "lng": lng}, "times": C.PRAYERS}


# ---------- Calendar / Ahlul Bayt ----------
@router.get("/calendar/events")
def calendar_events():
    return {"events": C.EVENTS}


@router.get("/ahlulbayt")
def ahlulbayt():
    return {"infallibles": C.MASUMEEN}


# ---------- PDF library (books available only as full PDF, e.g. al-Faqih) ----------
@router.get("/library/pdfs")
def library_pdfs():
    return {"pdfs": C.PDF_BOOKS}


# ---------- Library stats ----------
@router.get("/stats")
def stats():
    return store.stats()
