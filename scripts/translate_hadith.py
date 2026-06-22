#!/usr/bin/env python3
"""Translate each hadith's ENGLISH text into Urdu/Farsi/Azerbaijani/Malay and
store it on the hadith as h["ur"|"fa"|"az"|"ms"]. The Arabic (h["ar"]) and the
English (h["en"]) are never modified.

Resumable: a hadith already carrying a target field is skipped, and each book is
saved as it progresses, so you can stop/restart any time.

    python scripts/translate_hadith.py ur            # one language
    python scripts/translate_hadith.py ur fa az ms   # all (default)
"""
import glob
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# macOS' bundled Python often lacks root certs; use certifi if present, else fall
# back to an unverified context (we're only reading a public translation API).
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL = ssl._create_unverified_context()

HADITH = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data", "hadith")
DEFAULT_LANGS = ["ur", "fa", "az", "ms"]
WORKERS = 20              # concurrent translation requests (speed vs. rate-limits)


def _translate_once(text, tl, sl="en"):
    q = urllib.parse.quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25, context=_SSL) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def _chunks(text, size=1600):
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?؛])\s+", text):
        if cur and len(cur) + len(sent) + 1 > size:
            parts.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        parts.append(cur)
    return parts or [text]


def translate(text, tl, retries=5):
    """Translate possibly-long text; returns None on persistent failure."""
    out = []
    for c in _chunks(text):
        got = None
        for attempt in range(retries):
            try:
                got = _translate_once(c, tl)
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
        if got is None:
            got = c   # keep the original piece rather than dropping the whole chunk
        out.append(got)
    return " ".join(out)


def main():
    langs = [a for a in sys.argv[1:] if a in DEFAULT_LANGS] or DEFAULT_LANGS
    files = [f for f in glob.glob(os.path.join(HADITH, "*.json"))
             if not os.path.basename(f).startswith("_")]
    # Least-text books first (so many short hadiths complete fast; giant-chapter
    # books like Peshawar Nights are translated last).
    def _textsize(fp):
        d = json.load(open(fp, encoding="utf-8"))
        return sum(len(h.get("en") or "") for h in d.get("hadiths", []))
    files.sort(key=_textsize)
    print(f"Translating into {langs} across {len(files)} books\n")
    grand = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        hadiths = d.get("hadiths", [])
        # Every (hadith, language) pair that still needs a translation.
        tasks = [(h, lang, (h.get("en") or "").strip())
                 for h in hadiths for lang in langs
                 if (h.get("en") or "").strip() and not h.get(lang)]
        if not tasks:
            print(f"  ✓ {d.get('name','?')[:34]:34} already done")
            continue
        done = 0
        save = lambda: json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(translate, en, lang): (h, lang) for (h, lang, en) in tasks}
            for i, fut in enumerate(as_completed(futs)):
                h, lang = futs[fut]
                try:
                    tr = fut.result()
                except Exception:
                    tr = None
                if tr:
                    h[lang] = tr
                    done += 1
                    grand += 1
                if done and i % 200 == 0:
                    save()                       # periodic checkpoint (resumable)
        save()
        print(f"  • {d.get('name','?')[:34]:34} +{done}/{len(tasks)} (total {grand})", flush=True)
    print(f"\nDone. {grand} translations added.")


if __name__ == "__main__":
    main()
