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

# macOS' bundled Python often lacks root certs; use certifi if present, else fall
# back to an unverified context (we're only reading a public translation API).
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL = ssl._create_unverified_context()

HADITH = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data", "hadith")
DEFAULT_LANGS = ["ur", "fa", "az", "ms"]
SAVE_EVERY = 150          # save the book file this often (resumability)


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
            return None
        out.append(got)
    return " ".join(out)


def main():
    langs = [a for a in sys.argv[1:] if a in DEFAULT_LANGS] or DEFAULT_LANGS
    files = sorted(f for f in glob.glob(os.path.join(HADITH, "*.json"))
                   if not os.path.basename(f).startswith("_"))
    print(f"Translating into {langs} across {len(files)} books\n")
    grand = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        hadiths = d.get("hadiths", [])
        todo = sum(1 for h in hadiths if (h.get("en") or "").strip()
                   and any(not h.get(l) for l in langs))
        if not todo:
            print(f"  ✓ {d.get('name','?')[:34]:34} already done")
            continue
        done = 0
        for i, h in enumerate(hadiths):
            en = (h.get("en") or "").strip()
            if not en:
                continue
            for lang in langs:
                if h.get(lang):
                    continue
                tr = translate(en, lang)
                if tr:
                    h[lang] = tr
                    done += 1
                    grand += 1
                time.sleep(0.05)
            if done and i % SAVE_EVERY == 0:
                json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  • {d.get('name','?')[:34]:34} +{done} translations (total {grand})")
    print(f"\nDone. {grand} translations added.")


if __name__ == "__main__":
    main()
