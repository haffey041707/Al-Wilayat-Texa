#!/usr/bin/env python3
"""Download the COMPLETE Quran (114 surahs / 6236 verses) into local JSON.

Source: AlQuran Cloud API (https://alquran.cloud) — Quran text is public domain.
Editions chosen with a Shia audience in mind:
    ar  : quran-uthmani          (Uthmani Arabic script)
    en  : en.asad                (Muhammad Asad)
    ur  : ur.jawadi              (Allamah Zeeshan Haider Jawadi — Shia)
    fa  : fa.makarem             (Ayatollah Makarem Shirazi — Shia marja')
    az  : az.mammadaliyev        (Vasim Mammadaliyev & Ziya Bunyadov — Azerbaijani)
    ms  : ms.basmeih             (Abdullah Muhammad Basmeih — Malay)
    tr  : en.transliteration     (Latin transliteration)
    audio (per-ayah mp3 URLs)    : ar.alafasy

Output:
    app/data/quran/index.json          -> surah list
    app/data/quran/surah_{n}.json      -> full verses w/ all editions + audio
"""
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = "https://api.alquran.cloud/v1"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "quran"
OUT.mkdir(parents=True, exist_ok=True)

EDITIONS = {
    "ar": "quran-uthmani",
    "en": "en.asad",
    "ur": "ur.jawadi",
    "fa": "fa.makarem",
    "az": "az.mammadaliyev",
    "ms": "ms.basmeih",
    "translit": "en.transliteration",
}
AUDIO_EDITION = "ar.alafasy"


def get(url: str, tries: int = 4):
    """Fetch JSON via curl (robust SSL on macOS system Python)."""
    for i in range(tries):
        try:
            out = subprocess.run(
                ["curl", "-sS", "-m", "60", url],
                capture_output=True, text=True, check=True,
            ).stdout
            return json.loads(out)
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i+1} ({e})", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def main():
    print("Downloading full Quran editions…")
    full = {}
    for key, ed in {**EDITIONS, "audio": AUDIO_EDITION}.items():
        print(f"  · {key:8} ({ed})")
        full[key] = get(f"{BASE}/quran/{ed}")["data"]["surahs"]

    index = []
    grand_total = 0
    for i in range(114):
        meta = full["ar"][i]
        n = meta["number"]
        verses = []
        for j, ayah in enumerate(meta["ayahs"]):
            verses.append({
                "n": ayah["numberInSurah"],
                "juz": ayah.get("juz"),
                "ar": ayah["text"],
                "translit": full["translit"][i]["ayahs"][j]["text"],
                "en": full["en"][i]["ayahs"][j]["text"],
                "ur": full["ur"][i]["ayahs"][j]["text"],
                "fa": full["fa"][i]["ayahs"][j]["text"],
                "az": full["az"][i]["ayahs"][j]["text"],
                "ms": full["ms"][i]["ayahs"][j]["text"],
                "audio": full["audio"][i]["ayahs"][j].get("audio", ""),
            })
        grand_total += len(verses)
        surah = {
            "n": n,
            "ar": meta["name"],
            "en": meta["englishName"],
            "meaning": meta["englishNameTranslation"],
            "type": meta["revelationType"],
            "ayat": len(verses),
            "verses": verses,
        }
        (OUT / f"surah_{n}.json").write_text(
            json.dumps(surah, ensure_ascii=False), encoding="utf-8")
        index.append({k: surah[k] for k in ("n", "ar", "en", "meaning", "type", "ayat")})

    (OUT / "index.json").write_text(
        json.dumps({"count": len(index), "surahs": index}, ensure_ascii=False),
        encoding="utf-8")

    print(f"\n✅ Done: {len(index)} surahs, {grand_total} verses written to {OUT}")
    assert len(index) == 114, "expected 114 surahs"
    assert grand_total == 6236, f"expected 6236 verses, got {grand_total}"
    print("✅ Integrity check passed (114 surahs / 6236 verses).")


if __name__ == "__main__":
    main()
