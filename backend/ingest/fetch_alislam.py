#!/usr/bin/env python3
"""Ingest complete Shia books from al-islam.org (the Ahlul Bayt Digital Library).

Used for books that the Thaqalayn API does not serve (Nahj al-Balagha,
Risalat al-Huquq, Kamal al-Din, Man La Yahduruh al-Faqih). al-islam.org renders
each book as a landing page (table of contents) + one HTML page per chapter,
with Arabic and English text in <article> paragraphs.

Output: app/data/hadith/{bookId}.json — same schema as the Thaqalayn books, so
these slot straight into the app's Library / Hadith / Dua views.
"""
import html
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "hadith"
BASE = "https://al-islam.org"

# bookId (matches catalog) -> (list of landing slugs, display name, author)
BOOKS = {
    "Risalat-al-Huquq-Abidin": (
        ["/treatise-rights-risalat-al-huquq-imam-ali-zayn-al-abidin"],
        "Risālat al-Ḥuqūq (Treatise on Rights)", "Imam ʿAli Zayn al-ʿAbidin (AS)"),
    "Nahj-al-Balagha-Radi": (
        ["/nahjul-balagha-part-1-sermons", "/nahjul-balagha-part-2-letters-and-sayings"],
        "Nahj al-Balāgha (Peak of Eloquence)", "Imam ʿAli (AS), comp. al-Sharif al-Radi"),
    "Kamal-al-Din-wa-Tamam-al-Nima-Saduq": (
        ["/kamaaluddin-wa-tamaamun-nima-vol-1-shaykh-saduq",
         "/kamaaluddin-wa-tamaamun-nima-vol-2-shaykh-saduq"],
        "Kamāl al-Dīn wa Tamām al-Niʿma", "Shaykh al-Ṣaduq"),
    "Peshawar-Nights-Shirazi": (
        ["/peshawar-nights-sayyid-muhammad-al-musawi-al-shirazi"],
        "Peshawar Nights", "Sulṭānu'l-Wāʿiẓīn Shīrāzī"),
}


def fetch(url: str) -> str:
    # bytes + tolerant decode: some large pages get truncated mid-UTF-8 char
    for _ in range(3):
        out = subprocess.run(["curl", "-sSL", "-m", "45", "-A", "Mozilla/5.0", url],
                             capture_output=True).stdout
        text = out.decode("utf-8", errors="ignore")
        if len(text) > 500:
            return text
    return text


def clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).replace("\xa0", " ").strip()


def is_arabic(s: str) -> bool:
    ar = sum(1 for c in s if "؀" <= c <= "ۿ")
    return ar > len(s) * 0.3


def chapter_links(landing_slug: str) -> list[str]:
    h = fetch(BASE + landing_slug)
    base = re.escape(landing_slug)
    links = re.findall(rf'href="({base}/[a-z0-9-]+)"', h)
    seen, out = set(), []
    for l in links:
        if l not in seen:
            seen.add(l); out.append(l)
    return out


def parse_chapter(url: str) -> dict | None:
    h = fetch(url)
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    title = clean(title_m.group(1)) if title_m else url.rsplit("/", 1)[-1]
    art = re.search(r"<article.*?>(.*?)</article>", h, re.S)
    if not art:
        return None
    body = re.sub(r"<(script|style).*?</\1>", "", art.group(1), flags=re.S)
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    paras = [p for p in paras if len(p) > 1]
    ar = "\n".join(p for p in paras if is_arabic(p))
    en = "\n".join(p for p in paras if not is_arabic(p))
    if not ar and not en:
        return None
    return {"chapter": title, "ar": ar, "en": en, "grading": "", "url": url}


def ingest(book_id: str):
    slugs, name, author = BOOKS[book_id]
    print(f"↓ {name}")
    links = []
    for slug in slugs:
        part = chapter_links(slug)
        print(f"  {slug}: {len(part)} chapters")
        links += part
    if not links:
        print("  ⚠️  no chapters found — check the landing slug"); return
    with ThreadPoolExecutor(max_workers=6) as pool:
        chapters = [c for c in pool.map(parse_chapter, [BASE + l if l.startswith("/") else l for l in links]) if c]
    (OUT / f"{book_id}.json").write_text(json.dumps({
        "bookId": book_id, "name": name, "author": author,
        "source": "al-islam.org", "count": len(chapters), "hadiths": chapters,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ {book_id}: {len(chapters)} sections saved")


def main():
    targets = sys.argv[1:] or list(BOOKS)
    for b in targets:
        if b in BOOKS:
            ingest(b)
        else:
            print(f"  ? unknown book id: {b}")


if __name__ == "__main__":
    main()
