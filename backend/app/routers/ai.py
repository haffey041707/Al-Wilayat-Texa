"""AI assistant endpoint (Wilayat Chat).

Safety & scope contract:
  * Only answer questions about Islam in the school of the Ahlul Bayt (AS) — the
    Qur'an, hadith, duas, ziyarat, Islamic history, ethics and core beliefs.
  * Simple greetings (salam, hello) are welcomed.
  * Anything unrelated is politely declined with a fixed scope message.
  * Always provide a reference for substantive answers.
  * Never issue an independent ruling (fatwa); defer to a marjaʿ.

Provider: if OPENAI_API_KEY is set the answer comes live from OpenAI; otherwise
if ANTHROPIC_API_KEY is set it comes from Claude. When no key is set — or the
provider call fails or its quota is exhausted — the request falls back to a
built-in "offline brain" (greetings + core Shia beliefs + the scope guard) so
the app keeps working.
"""
import json
import logging
import os
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import store

log = logging.getLogger("wilayat.ai")

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Models (override via env). OpenAI is preferred when its key is present.
OPENAI_MODEL = os.getenv("WILAYAT_OPENAI_MODEL", "gpt-4o-mini")
AI_MODEL = os.getenv("WILAYAT_AI_MODEL", "claude-opus-4-8")  # Anthropic fallback provider

# The exact line shown when a question is outside the app's scope.
OFFTOPIC_MSG = (
    "This chat is only for Al-Wilayat — Islamic questions about the Qur'an, the Ahlul Bayt (AS) "
    "and matters of faith. Please ask about those."
)

SYSTEM_PROMPT = (
    "You are Wilayat Chat, a knowledgeable, respectful assistant grounded in the Twelver "
    "(Ithna ʿAshari) Shia school of the Ahlul Bayt (peace be upon them). You answer questions "
    "about Islamic core beliefs (Usul al-Din: Tawhid, ʿAdl, Nubuwwah, Imamah, Maʿad), the Quran, "
    "the hadith of the Ahlul Bayt, duas, ziyarat, Islamic history and ethics.\n"
    "Rules you must always follow:\n"
    "1. For substantive religious answers, always provide a concrete reference in the `reference` "
    "field — a Quran citation, a hadith from a named source (e.g. al-Kafi, Nahj al-Balagha), or a "
    "well-known dua/ziyarat. For greetings or the scope refusal, the reference may simply be "
    "'Al-Wilayat'.\n"
    "2. Never issue an independent religious ruling (fatwa). If the question asks whether something "
    "is permissible, obligatory, halal, haram, wajib, etc., set requires_scholar=true and advise the "
    "user to consult their marjaʿ al-taqlid; do not state a ruling yourself.\n"
    "3. Keep `answer` concise (2-5 sentences), accurate and respectful; honour the Prophet (S) and "
    "the Ahlul Bayt (AS) with appropriate salutations.\n"
    "4. If you are unsure or the matter is genuinely disputed, say so rather than fabricating.\n"
    "5. Greetings: if the user only greets you (salam, hello, hi), greet them back warmly and invite "
    "an Islamic question.\n"
    "6. Scope: only answer questions about Islam and the Ahlul Bayt school. If the user asks about "
    "anything unrelated (coding, sport, politics, entertainment, general trivia, personal advice "
    "unrelated to faith, etc.), do NOT answer it — set requires_scholar=false and reply with exactly "
    f"this text in `answer`: \"{OFFTOPIC_MSG}\""
)

RULING_TRIGGERS = ("fatwa", "ruling", "is it halal", "is it haram", "permissible", "wajib", "must i")

# Offline-brain heuristics ----------------------------------------------------
GREETINGS = ("hi", "hello", "hey", "salam", "salaam", "assalam", "asalam", "as-salam",
             "salamun", "marhaba", "greetings")
# Words that signal a question really is about Islam / the Ahlul Bayt school.
ISLAMIC_HINTS = (
    "allah", "god", "islam", "muslim", "shia", "shi'a", "quran", "qur'an", "ayah", "surah",
    "hadith", "sunnah", "prophet", "muhammad", "rasul", "ahlul", "ahl al", "imam", "ali",
    "fatima", "zahra", "hasan", "husayn", "hussain", "sajjad", "baqir", "sadiq", "kazim",
    "rida", "reza", "jawad", "hadi", "askari", "mahdi", "wilayah", "wilayat", "ghadir",
    "dua", "munajat", "ziyarat", "namaz", "salah", "salat", "prayer", "fast", "sawm",
    "ramadan", "karbala", "ashura", "muharram", "marja", "taqlid", "fiqh", "aqeedah",
    "tawhid", "nubuwwah", "imamah", "qiyamah", "akhirah", "jannah", "barzakh", "halal",
    "haram", "wudu", "ghusl", "zakat", "khums", "hajj", "kaaba", "masjid", "mosque",
    "infallible", "maʿsum", "masum", "ziyarah", "tasbih", "dhikr", "faith", "belief",
    # virtues / common religious topics so topical questions are recognised
    "patience", "sabr", "charity", "sadaqah", "mercy", "rahmah", "forgiveness", "forgive",
    "repentance", "tawbah", "gratitude", "thankful", "shukr", "justice", "sin", "paradise",
    "hell", "angel", "jinn", "soul", "death", "marriage", "parents", "mother", "father",
    "wealth", "poor", "orphan", "fasting", "honesty", "truth", "patience", "anger", "pride",
    "humility", "love", "fear", "hope", "worship", "sincerity", "intention", "heart",
    "knowledge", "ilm", "wisdom", "guidance", "sabr", "piety", "taqwa", "sustenance",
)

# The five roots of religion (Usul al-Din) in the school of Ahlul Bayt (AS).
# Each entry: list of trigger keywords -> (answer, reference).
CORE_BELIEFS: list[tuple[tuple[str, ...], str, str]] = [
    (("tawhid", "tawheed", "oneness", "monotheism", "unity of god"),
     "Tawhid is the absolute Oneness of Allah — that He is One in His Essence, Attributes and "
     "actions, with no partner, no equal and no resemblance to creation. It is the first and "
     "foundational root of religion (Usul al-Din).",
     "Quran 112 (al-Ikhlas) · Nahj al-Balagha, Sermon 1 — Imam Ali (AS) on knowing God."),
    (("adl", "adalah", "justice", "divine justice"),
     "ʿAdl means Divine Justice: Allah is absolutely just and never wrongs anyone, nor does He "
     "act without wisdom. Humans have free will and are accountable for their deeds. It is the "
     "second root of religion in the Shia school.",
     "Quran 4:40 — 'Indeed Allah does not wrong [anyone] by even an atom's weight.'"),
    (("nubuwwah", "nubuwwat", "prophethood", "prophet", "messenger", "risalah"),
     "Nubuwwah is Prophethood: Allah sent prophets to guide humanity, beginning with Adam (AS) "
     "and sealed by the Prophet Muhammad (S), the final messenger. Prophets are infallible "
     "(maʿsum) in conveying the divine message.",
     "Quran 33:40 — 'Muhammad is the Messenger of Allah and the Seal of the Prophets.'"),
    (("imamah", "imamat", "imam", "wilayah", "wilayat", "successor", "caliph", "ghadir", "twelve imams"),
     "Imamah is the divinely-appointed leadership after the Prophet (S). The twelve Imams, "
     "beginning with Imam Ali (AS) and ending with Imam al-Mahdi (AJ), are appointed by Allah, "
     "infallible, and the authoritative guides and interpreters of the religion.",
     "Quran 5:55 · Hadith al-Ghadir · Hadith al-Thaqalayn — 'I leave among you the Book and my "
     "Household (Ahlul Bayt).'"),
    (("ma'ad", "maad", "maʿad", "resurrection", "hereafter", "qiyamah", "day of judgment", "akhirah", "afterlife"),
     "Maʿad is the Resurrection and Return: every soul will be raised on the Day of Judgement to "
     "be recompensed for its deeds, with Paradise for the righteous and accountability for the "
     "wrongdoers. It is the fifth root of religion.",
     "Quran 99:7-8 — 'Whoever does an atom's weight of good will see it, and whoever does an "
     "atom's weight of evil will see it.'"),
]


# ----- Retrieval over Wilayat's own Quran + hadith corpus -----
_STOP = {
    "the", "and", "for", "are", "was", "what", "who", "whom", "how", "why", "when", "where",
    "does", "did", "do", "is", "in", "of", "to", "on", "a", "an", "about", "tell", "me",
    "explain", "say", "says", "said", "can", "you", "your", "please", "give", "i", "we",
    "it", "this", "that", "with", "from", "have", "has", "be", "as", "or", "any", "some",
    "there", "their", "they", "he", "she", "his", "her", "regarding", "concerning",
}


# Meta words that match almost every translation — useless as search terms.
_SEARCH_STOP = {"quran", "quranic", "hadith", "hadiths", "ayah", "ayat", "surah", "surahs",
                "verse", "verses", "narration", "narrations", "book", "chapter", "islam",
                "islamic", "shia", "sunni", "muslim", "muslims"}


def _keywords(q: str) -> list[str]:
    seen, out = set(), []
    for w in re.findall(r"[a-z']{4,}", q.lower()):  # length >= 4 avoids noise like "won"
        if w not in _STOP and w not in _SEARCH_STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:6]


def _corpus_search(question: str, want: int = 2) -> list[dict]:
    """Find the best-matching verses / narrations from Wilayat's data."""
    kws = _keywords(question)
    hits: list[dict] = []
    try:
        for kw in kws:  # Quran first — small files, fast
            for v in store.quran_search(kw, limit=2).get("results", []):
                hits.append({"kind": "Quran", "en": v["en"], "ar": v.get("ar", ""),
                             "cite": f"Quran {v['surah']}:{v['ayah']} ({v['surahName']})"})
            if hits:
                break
        for kw in kws[:2]:  # then a couple of keywords against the hadith corpus
            if len(hits) >= want:
                break
            for h in store.hadith_search(kw, limit=2).get("results", []):
                hits.append({"kind": "Hadith", "en": h.get("en", ""), "ar": h.get("ar", ""),
                             "cite": h.get("reference", {}).get("citation", h.get("name", "Hadith"))})
    except Exception:
        log.exception("corpus search failed")
    # de-dupe by citation, keep order
    uniq, seen = [], set()
    for h in hits:
        if h["en"].strip() and h["cite"] not in seen:
            seen.add(h["cite"])
            uniq.append(h)
    return uniq[:want]


def _grounded(question: str) -> "AskOut | None":
    """Answer purely from the corpus (no LLM) with real citations."""
    hits = _corpus_search(question, want=2)
    if not hits:
        return None
    lines = [f"• {h['en'].strip()}" for h in hits]
    refs = " · ".join(dict.fromkeys(h["cite"] for h in hits))
    return AskOut(answer="From the Wilayat sources:\n" + "\n".join(lines), reference=refs)


def _context(question: str) -> str:
    """Retrieved snippets to ground the LLM answer (RAG)."""
    hits = _corpus_search(question, want=4)
    if not hits:
        return ""
    return "\n".join(f"[{h['kind']}] {h['cite']}: {h['en'].strip()}" for h in hits)


# Light, on-brand small talk so normal conversation feels natural.
SMALLTALK: list[tuple[tuple[str, ...], str]] = [
    (("how are you", "how r u", "how do you do", "how's it going", "hows it going"),
     "Alhamdulillah, I'm well and at your service. Ask me about the Qur'an, the Ahlul Bayt (AS), duas or core beliefs."),
    (("thank", "shukran", "jazak"),
     "You're most welcome — barakallahu fik. Is there anything else about Islam you'd like to know?"),
    (("who are you", "what are you", "your name", "who r u", "what is this"),
     "I'm Wilayat Chat — a helper for questions about Islam in the school of the Ahlul Bayt (AS): the Qur'an, hadith, duas and beliefs, always with a reference."),
    (("bye", "goodbye", "good night", "khuda hafiz", "fi amanillah", "see you"),
     "Fi amanillah — may Allah protect you. Come back any time with your questions."),
    (("what can you do", "help", "what do you do"),
     "I can answer questions about the Qur'an, the hadith of the Ahlul Bayt (AS), duas, ziyarat, Islamic history and the core beliefs of Shia Islam — and I always cite a reference."),
]


class AskIn(BaseModel):
    question: str
    lang: str = "en"


class AskOut(BaseModel):
    answer: str
    reference: str
    requires_scholar: bool = False


def _ruling_deferral() -> AskOut:
    return AskOut(
        answer=(
            "This question concerns a religious ruling. Wilayat AI does not issue "
            "fatwas. Please consult your marja' al-taqlid or a qualified scholar for "
            "an authoritative ruling."
        ),
        reference="Quran 16:43 — 'Ask the people of remembrance if you do not know.'",
        requires_scholar=True,
    )


def _fallback(q: str) -> AskOut:
    """The 'offline brain' — used when no live model is configured or its quota
    is exhausted. Handles greetings, core Shia beliefs, and the scope guard."""
    words = set(q.replace("?", " ").replace("!", " ").replace(",", " ").split())

    # Plain greeting / simple conversation (short message that is just a greeting).
    is_greeting = len(words) <= 3 and (
        any(w in GREETINGS for w in words)
        or any(s in q for s in ("salam", "salaam", "marhaba"))
    )
    if is_greeting:
        return AskOut(
            answer=("Wa ʿalaykum as-salam! I'm Wilayat Chat. Ask me about the Qur'an, the Ahlul "
                    "Bayt (AS), duas, ziyarat or the core beliefs of Shia Islam."),
            reference="Al-Wilayat",
        )

    # Core beliefs (Usul al-Din) — answered automatically with a reference.
    for triggers, answer, reference in CORE_BELIEFS:
        if any(tok in q for tok in triggers):
            return AskOut(answer=answer, reference=reference)

    if "knowledge" in q or "ilm" in q:
        return AskOut(
            answer="The pursuit of knowledge is strongly emphasised in the school of Ahlul Bayt (AS).",
            reference="Al-Kafi — Imam al-Sadiq (AS): 'Seeking knowledge is an obligation upon every Muslim.'",
        )

    # Normal conversation.
    for triggers, reply in SMALLTALK:
        if any(t in q for t in triggers):
            return AskOut(answer=reply, reference="Al-Wilayat")

    if "husayn" in q or "hussain" in q or "ashura" in q or "karbala" in q:
        return AskOut(
            answer="Imam al-Husayn (AS) was martyred at Karbala on the 10th of Muharram (Ashura), standing against tyranny.",
            reference="Ziyarat Ashura · Mafatih al-Jinan.",
        )

    # Recognisably Islamic — ground the answer in Wilayat's own Quran + hadith data.
    if any(tok in q for tok in ISLAMIC_HINTS):
        grounded = _grounded(q)
        if grounded:
            return grounded
        return AskOut(
            answer=("I can help with the Qur'an, the hadith of the Ahlul Bayt (AS), duas, ziyarat "
                    "and the core beliefs of Shia Islam — always with a reference. Could you give a "
                    "little more detail about what you'd like to know?"),
            reference="Quran 16:43 — 'Ask the people of remembrance if you do not know.'",
        )

    # Off-topic — outside the app's scope.
    return AskOut(answer=OFFTOPIC_MSG, reference="Al-Wilayat")


def _provider() -> str | None:
    """Which live provider to use, or None for the offline brain."""
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _lang_note(body: AskIn) -> str:
    return "" if not body.lang or body.lang == "en" else (
        f"\nRespond in the language with ISO code '{body.lang}'.")


def _user_content(question: str) -> str:
    """Enrich the question with retrieved Wilayat passages (RAG)."""
    ctx = _context(question)
    if not ctx:
        return question
    return ("Relevant passages from the Wilayat library — prefer these and cite them when they fit:\n"
            f"{ctx}\n\nQuestion: {question}")


def _ask_openai(body: AskIn) -> AskOut:
    """Answer with OpenAI as strict JSON {answer, reference, requires_scholar}."""
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    system = (
        SYSTEM_PROMPT + _lang_note(body)
        + "\nReturn ONLY a JSON object with keys: answer (string), reference (string), "
        "requires_scholar (boolean)."
    )
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=700,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": _user_content(body.question)},
        ],
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    return AskOut(
        answer=data.get("answer") or OFFTOPIC_MSG,
        reference=data.get("reference") or "Al-Wilayat",
        requires_scholar=bool(data.get("requires_scholar", False)),
    )


def _ask_claude(body: AskIn) -> AskOut:
    """Answer with Claude, parsed straight into AskOut. Raises on any failure."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.parse(
        model=AI_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT + _lang_note(body),
        messages=[{"role": "user", "content": _user_content(body.question)}],
        output_format=AskOut,
    )
    out = response.parsed_output
    if out is None:
        raise ValueError("Claude returned no parsed output")
    return out


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    q = body.question.lower().strip()

    # Ruling questions never reach the model — return the deferral deterministically.
    if any(tok in q for tok in RULING_TRIGGERS):
        return _ruling_deferral()

    provider = _provider()
    if provider:
        try:
            return _ask_openai(body) if provider == "openai" else _ask_claude(body)
        except Exception:  # network, auth, parse, or QUOTA EXHAUSTED — fall back gracefully
            log.exception("%s ask failed; using offline brain", provider)

    return _fallback(q)


@router.get("/status")
def status():
    """Lets the UI show whether answers are live or the built-in offline brain."""
    provider = _provider()
    model = OPENAI_MODEL if provider == "openai" else AI_MODEL if provider == "anthropic" else None
    return {"live": provider is not None, "provider": provider, "model": model}


# For streaming we ask the model to end with a single delimited reference line,
# since token streaming can't carry the structured fields of /ask.
STREAM_SYSTEM = (
    SYSTEM_PROMPT
    + "\nWrite the answer first. Then, on the final line, output exactly one citation "
    "beginning with 'REFERENCE:' and nothing after it. Do not use the word REFERENCE "
    "anywhere else in the answer."
)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ask/stream")
def ask_stream(body: AskIn):
    """Server-sent-events stream of the answer text. Clients fall back to /ask
    on a non-200 response or a streamed {"error": true} event."""
    q = body.question.lower().strip()

    if any(tok in q for tok in RULING_TRIGGERS):
        d = _ruling_deferral()

        def deferral():
            yield _sse({"t": d.answer})
            yield _sse({"t": f"\nREFERENCE: {d.reference}"})
            yield _sse({"done": True})

        return StreamingResponse(deferral(), media_type="text/event-stream")

    provider = _provider()
    if not provider:
        # No live model — tell the client to use the built-in /ask endpoint.
        return JSONResponse({"live": False}, status_code=503)

    system = STREAM_SYSTEM + _lang_note(body)

    def gen_openai():
        from openai import OpenAI

        client = OpenAI()
        stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=700,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _user_content(body.question)},
            ],
        )
        for chunk in stream:
            text = chunk.choices[0].delta.content if chunk.choices else None
            if text:
                yield _sse({"t": text})

    def gen_anthropic():
        import anthropic

        client = anthropic.Anthropic()
        with client.messages.stream(
            model=AI_MODEL,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": _user_content(body.question)}],
        ) as stream:
            for text in stream.text_stream:
                yield _sse({"t": text})

    def gen():
        try:
            yield from (gen_openai() if provider == "openai" else gen_anthropic())
            yield _sse({"done": True})
        except Exception:  # incl. quota exhausted → client falls back to /ask (offline brain)
            log.exception("%s stream failed", provider)
            yield _sse({"error": True})

    return StreamingResponse(gen(), media_type="text/event-stream")
