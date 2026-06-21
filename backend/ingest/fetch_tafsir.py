#!/usr/bin/env python3
"""Download SHIA tafsir into local JSON (per verse → exegesis block).

Source: github.com/app-furqan/quran-app-data (SQLite DBs, tar.xz).
Editions (all Shia):
    almizan_en / almizan_ar / almizan_fa / almizan_ur
        — Tafsīr al-Mīzān, ʿAllāmah Muḥammad Ḥusayn Ṭabāṭabāʾī
Each DB: ayah_mapping(surah,ayah->content_id) + content(id->markdown).

Output: app/data/tafsir/{edition}.json
    { "edition","name","language","mapping": {"s:a": content_id},
      "content": {"content_id": "markdown text"} }
"""
import json
import lzma
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

RAW = "https://raw.githubusercontent.com/app-furqan/quran-app-data/main/data"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "tafsir"
OUT.mkdir(parents=True, exist_ok=True)

EDITIONS = {
    "almizan_en": {"file": "tafsir_almizan_en.db", "name": "Tafsir al-Mizan", "language": "en"},
    "almizan_ar": {"file": "tafsir_almizan_ar.db", "name": "تفسير الميزان", "language": "ar"},
    "almizan_fa": {"file": "tafsir_almizan_fa.db", "name": "تفسیر المیزان", "language": "fa"},
    "almizan_ur": {"file": "tafsir_almizan_ur.db", "name": "تفسیر المیزان", "language": "ur"},
}


def download(name: str, dest: Path):
    url = f"{RAW}/tafsir_{name}.db.tar.xz"
    print(f"  ↓ {url}")
    subprocess.run(["curl", "-sSL", "-m", "120", url, "-o", str(dest)], check=True)


def extract_db(tar_path: Path, tmp: Path) -> Path:
    with tarfile.open(tar_path) as t:
        member = t.getnames()[0]
        t.extract(member, tmp)  # noqa: S202 — trusted source, single .db file
    return tmp / member


def convert(edition: str, meta: dict):
    out_file = OUT / f"{edition}.json"
    if out_file.exists():
        print(f"  ✓ {edition} already present")
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        tar = tmp / f"{edition}.tar.xz"
        download(edition, tar)
        db = extract_db(tar, tmp)
        con = sqlite3.connect(db)
        cur = con.cursor()
        mapping = {f"{s}:{a}": cid for s, a, cid in
                   cur.execute("SELECT surah_number, ayah_number, content_id FROM ayah_mapping")}
        content = {str(cid): txt for cid, txt in
                   cur.execute("SELECT content_id, content FROM content")}
        con.close()
    out_file.write_text(json.dumps({
        "edition": edition, "name": meta["name"], "language": meta["language"],
        "author": "Allamah Muhammad Husayn Tabatabai",
        "mapping": mapping, "content": content,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ {edition}: {len(mapping)} ayah mappings, {len(content)} blocks")


def main():
    print("Downloading Shia tafsir (al-Mizan)…")
    for ed, meta in EDITIONS.items():
        convert(ed, meta)
    print("Done.")


if __name__ == "__main__":
    main()
