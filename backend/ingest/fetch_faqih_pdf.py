#!/usr/bin/env python3
"""Extract Man La Yahduruh al-Faqih as full text from the babulqaim PDFs.

These PDFs (English translation by Haydar Ali Shaykh) have a real text layer,
structured as CHAPTER headings and H.N hadith markers, with Arabic source +
English translation. We parse them into the standard book JSON with correct
chapter and hadith numbers.

Arabic extracted from the PDF carries diacritic-spacing artifacts; English is
clean. Each entry keeps chapter number, chapter title, and hadith number.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pypdf

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "hadith"
PDF_DIR = Path("/tmp")
BASE = "https://babulqaim.com/wp-content/uploads/2025/03"
VOLS = {
    1: "man-la-yahduruhu-al-faqih-vol.1.pdf",
    2: "man-la-yahduruhu-al-faqih-vol.2.pdf",
    3: "man-la-yahduruhu-al-faqih-vol.3-1.pdf",
    4: "man-la-yahduruhu-al-faqih-vol.4.pdf",
}

ARABIC = re.compile(r"[؀-ۿ]")


def download(vol: int) -> Path:
    dest = PDF_DIR / f"faqih{vol}.pdf"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    subprocess.run(["curl", "-sL", "--retry", "3", "-m", "590", "-C", "-",
                    "-A", "Mozilla/5.0", f"{BASE}/{VOLS[vol]}", "-o", str(dest)], check=True)
    return dest


def clean_line(ln: str) -> str:
    # drop running headers/footers like 'CHAPTER 1 - WATER ... 12'
    if re.match(r"\s*CHAPTER\s+\d+\s*[-–].*\d+\s*$", ln):
        return ""
    if re.match(r"\s*\d+\s*$", ln):  # bare page number
        return ""
    return ln


def parse_volume(pdf_path: Path, vol: int) -> list[dict]:
    reader = pypdf.PdfReader(str(pdf_path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    text = "\n".join(clean_line(l) for l in text.split("\n"))

    # tokens: chapter headings + hadith markers, in document order
    tokens = []
    for m in re.finditer(r"CHAPTER\s+(\d+)\s*[-–]\s*([A-Z][A-Z0-9 ;,.()'’\-/&]{3,90})", text):
        tokens.append((m.start(), "chap", m.group(1), m.group(2).strip().rstrip(" 0123456789")))
    for m in re.finditer(r"H\.\s?(\d+)\b", text):
        tokens.append((m.start(), "had", m.group(1), m.end()))
    tokens.sort(key=lambda t: t[0])

    entries, chap_no, chap_title, seen = [], None, "", set()
    for i, (pos, typ, num, extra) in enumerate(tokens):
        if typ == "chap":
            chap_no, chap_title = num, re.sub(r"\s+", " ", extra).strip()
            continue
        if num in seen:  # duplicate H.N from running text
            continue
        seen.add(num)
        end = tokens[i + 1][0] if i + 1 < len(tokens) else len(text)
        body = text[pos:end].strip()
        body = re.sub(r"^H\.\s?\d+\s*[–-]?\s*", "", body)  # strip leading marker
        ar = "\n".join(l for l in body.split("\n") if ARABIC.search(l)).strip()
        en = "\n".join(l for l in body.split("\n") if l.strip() and not ARABIC.search(l)).strip()
        if len(en) < 15 and len(ar) < 15:
            continue
        entries.append({
            "id": int(num), "category": f"Volume {vol}",
            "chapter": f"{chap_no}. {chap_title}" if chap_no else chap_title,
            "ar": ar, "en": en, "grading": "",
        })
    return entries


def main():
    vols = [int(v) for v in sys.argv[1:]] or list(VOLS)
    all_entries = []
    for v in vols:
        pdf = download(v)
        print(f"↓ vol {v}: parsing {pdf.name} ({pdf.stat().st_size//1_000_000}MB)")
        e = parse_volume(pdf, v)
        print(f"  vol {v}: {len(e)} hadiths")
        all_entries += e

    # renumber sequentially across the whole book while keeping per-vol id in category
    book = {
        "bookId": "Man-La-Yahduruh-al-Faqih-Saduq", "name": "Man Lā Yaḥḍuruh al-Faqīh",
        "author": "Shaykh al-Ṣaduq (tr. Haydar Ali Shaykh)", "source": "babulqaim.com (PDF)",
        "count": len(all_entries), "hadiths": all_entries,
    }
    (OUT / "Man-La-Yahduruh-al-Faqih-Saduq.json").write_text(
        json.dumps(book, ensure_ascii=False), encoding="utf-8")
    print(f"✅ saved {len(all_entries)} hadiths to Man-La-Yahduruh-al-Faqih-Saduq.json")


if __name__ == "__main__":
    main()
