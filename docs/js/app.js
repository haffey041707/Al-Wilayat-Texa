/* ============================================================
   Wilayat — App controller (routing, i18n, rendering, modules)
   Vanilla JS · no build step
   ============================================================ */

// Same origin as the page (FastAPI serves both the site and the API), so this works
// on localhost AND on your real domain. Override with window.WILAYAT_API if needed.
const API_BASE = (typeof window !== "undefined" && window.WILAYAT_API) || "/api";

const State = {
  lang: localStorage.getItem("wilayat.lang") || "en",
  theme: "dark",
  route: "home",
  prayer: null,   // { times, tz, label } once loaded for the user's location
  // { lat, lng } — shared everywhere; remembered across refreshes
  coords: JSON.parse(localStorage.getItem("wilayat.coords") || "null"),
  qibla: null,    // bearing to the Kaaba (degrees from North) once computed
};
function saveCoords(lat, lng, meta = {}) {
  State.coords = {
    lat: Number(lat),
    lng: Number(lng),
    source: meta.source || "gps",
    accuracy: Number.isFinite(meta.accuracy) ? Math.round(meta.accuracy) : null,
    updatedAt: Date.now(),
  };
  localStorage.setItem("wilayat.coords", JSON.stringify(State.coords));
}

const t = (key) => (I18N[State.lang] && I18N[State.lang][key]) || I18N.en[key] || key;
const el = (sel) => document.querySelector(sel);
const els = (sel) => [...document.querySelectorAll(sel)];

// ---------------- API layer (graceful offline fallback) ----------------
let API_UP = null; // null=unknown, true/false once probed
// On GitHub Pages there is no backend: every /api call is served from the
// pre-generated static JSON under /api/*, and search runs in the browser.
const STATIC = (typeof window !== "undefined" && window.WILAYAT_STATIC) || /\.github\.io$/.test(location.hostname);
const STATIC_BASE = (() => {
  if (!STATIC) return null;
  const s = [...document.scripts].map((x) => x.src).find((x) => /\/js\/app\.js/.test(x)) || "";
  return s.replace(/js\/app\.js.*$/, "") + "api/";
})();
async function api(path) {
  if (STATIC) { API_UP = true; return staticApi(path); }
  const r = await fetch(API_BASE + path, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status);
  API_UP = true;
  return r.json();
}

// ----- Static (no-backend) API: maps /api paths to files + in-browser search -----
async function _sjson(rel) {
  const r = await fetch(STATIC_BASE + rel, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
let _qIdx = null, _hIdx = null, _surNames = null, _tafMap = {};
const _ar2en = (s) => String(s)
  .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
  .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));
const _en2ar = (s) => String(s).replace(/\d/g, (d) => "٠١٢٣٤٥٦٧٨٩"[+d]);

async function staticApi(path) {
  const [p, qs] = path.split("?");
  const q = new URLSearchParams(qs || "");
  if (p === "/quran/search") return staticQuranSearch(q.get("q") || "", +(q.get("limit") || 50));
  if (p === "/hadith/search") return staticHadithSearch(q.get("q") || "", +(q.get("limit") || 50));
  if (p === "/dua/search") return staticListSearch(typeof DUAS !== "undefined" ? DUAS : [], q.get("q") || "", +(q.get("limit") || 40));
  if (p === "/ziyarat/search") return staticListSearch(typeof ZIYARAT !== "undefined" ? ZIYARAT : [], q.get("q") || "", +(q.get("limit") || 40));
  let m = p.match(/^\/quran\/tafsir\/(\d+)\/(\d+)$/);
  if (m) return staticTafsir(+m[1], +m[2], q.get("edition") || "almizan_en");
  m = p.match(/^\/hadith\/book\/(.+)$/);
  if (m) return _sjson(`hadith/book/${m[1]}/${+(q.get("page") || 1)}.json`);
  return _sjson(p.replace(/^\//, "") + ".json");
}

async function staticQuranSearch(qq, limit) {
  const ql = qq.toLowerCase().trim();
  if (!ql) return { count: 0, results: [] };
  if (!_qIdx) _qIdx = await _sjson("search/quran.json");
  if (!_surNames) { const idx = await _sjson("quran/surahs.json"); _surNames = {}; (idx.surahs || []).forEach((s) => { _surNames[s.n] = s.en; }); }
  const out = [];
  for (const v of _qIdx) {
    if ((v.en && v.en.toLowerCase().includes(ql)) || (v.translit && v.translit.toLowerCase().includes(ql)) ||
        (v.ar && v.ar.includes(qq)) || (v.ur && v.ur.includes(qq)) || (v.fa && v.fa.includes(qq))) {
      out.push({ surah: v.s, surahName: _surNames[v.s] || "", ayah: v.a, ar: v.ar, en: v.en });
      if (out.length >= limit) break;
    }
  }
  return { count: out.length, results: out };
}

async function staticHadithSearch(rawIn, limit) {
  const raw = _ar2en((rawIn || "").trim());
  if (!raw) return { count: 0, results: [] };
  if (!_hIdx) _hIdx = await _sjson("search/hadith.json");
  const numeric = /^\d+$/.test(raw), isAr = /[؀-ۿ]/.test(raw), norm = raw.toLowerCase();
  const grab = (...pats) => { for (const p of pats) { const m = raw.match(p); if (m) return m[1]; } return null; };
  const vol_q = grab(/\bvol(?:ume)?\s*(\d+)/i, /(?:الجزء|الجز|جزء|ج)\s*[.:]?\s*(\d+)/);
  const ch_q = grab(/\bch(?:apter)?\s*(\d+)/i, /باب\s*[.:]?\s*(\d+)/);
  const h_q = grab(/\bh(?:adith)?\s*(\d+)/i, /(?:الحديث|حديث|ح)\s*[.:]?\s*(\d+)/);
  const refMode = !numeric && !!(vol_q || ch_q || h_q);
  // Book-name tokens are Latin-only (Arabic keywords like ح/باب must not become a name filter).
  const latinNorm = norm.replace(/[^a-z0-9\s]/g, " ");
  const nameToks = refMode ? latinNorm.split(/\s+/).filter((t) => t && !["vol", "volume", "ch", "chapter", "h", "hadith"].includes(t) && !/^\d+$/.test(t)) : [];
  const queryHasArName = isAr && _hIdx.some((b) => b.ar && raw.includes(b.ar));
  const out = [];
  for (const b of _hIdx) {
    if (refMode) {
      if (vol_q && b.vol !== vol_q) continue;
      if (nameToks.length) { const ns = (b.name || "").toLowerCase(); if (!nameToks.every((t) => ns.includes(t))) continue; }
      if (queryHasArName && b.ar && !raw.includes(b.ar)) continue;
    }
    for (const it of b.items) {
      const hid = String(it.id);
      let match;
      if (numeric) match = raw === hid;
      else if (refMode) match = h_q ? hid === h_q : (ch_q ? String(it.ch) === ch_q : true);
      else if (isAr) match = (it.ar || "").includes(raw);
      else match = (b.name + " " + (it.en || "")).toLowerCase().includes(norm);
      if (match) {
        const citation = b.name + (it.ch ? ` · Ch. ${it.ch}` : "") + ` · H. ${it.id}`;
        const ar_citation = (b.ed === "ar" && b.ar)
          ? b.ar + (b.vol ? ` – الجزء ${_en2ar(b.vol)}` : "") + (it.ch ? `، باب ${_en2ar(it.ch)}` : "") + `، ح ${_en2ar(it.id)}`
          : null;
        out.push({ bookId: b.bookId, name: b.name, id: it.id, chapter: it.ch, ar: it.ar, en: it.en,
                   edition: b.ed, reference: { citation, ar_citation } });
        if (out.length >= limit) return { count: out.length, results: out };
      }
    }
  }
  return { count: out.length, results: out };
}

function staticListSearch(list, qq, limit) {
  const ql = qq.toLowerCase().trim();
  list = list || [];
  const out = [];
  for (const d of list) {
    if (((d.en || "") + " " + (d.ar || "") + " " + (d.note || "")).toLowerCase().includes(ql)) {
      out.push({ ar: d.ar || "", en: d.en || "", title: d.en || "", id: d.textId || "" });
      if (out.length >= limit) break;
    }
  }
  return { count: out.length, results: out };
}

async function staticTafsir(s, a, ed) {
  if (!_tafMap[ed]) _tafMap[ed] = await _sjson(`quran/tafsir/${ed}/map.json`);
  const cid = _tafMap[ed][`${s}:${a}`];
  if (cid == null) throw new Error("HTTP 404");
  return { ...(await _sjson(`quran/tafsir/${ed}/c/${cid}.json`)), surah: s, ayah: a };
}
function offlineBanner() {
  return `<div class="card" style="border-color:var(--gold);background:linear-gradient(135deg,rgba(31,123,255,.14),transparent);margin-bottom:16px">
    ⚠️ ${t("offline")} <code>uvicorn app.main:app --reload</code></div>`;
}
// Maps each UI language onto the language whose CONTENT (phrase map + data) to use.
// Dari→Persian, Kashmiri→Urdu, Azerbaijani/Malay/Singapore borrow per case.
const CONTENT_LANG = { en: "en", sg: "en", az: "az", ms: "ms", ur: "ur", ks: "ur", fa: "fa", prs: "fa", ar: "ar" };
const contentLang = () => CONTENT_LANG[State.lang] || "en";
// Quran/verse translation field (verse data carries en/ur/fa/az/ms; ks→ur, prs→fa, sg→en).
const trField = () => ({ en: "en", sg: "en", az: "az", ms: "ms", ur: "ur", ks: "ur", fa: "fa", prs: "fa", ar: null }[State.lang] ?? null);
let currentAudio = null;
// Clean play / pause glyphs (SVG, not emoji) for the recitation buttons.
const ICON_PLAY = '<svg class="picon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
const ICON_PAUSE = '<svg class="picon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1.2"/><rect x="14" y="5" width="4" height="14" rx="1.2"/></svg>';
// Western → Arabic-Indic digits (for numbering shown beside Arabic text).
const arDigits = (s) => String(s).replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[+d]);
// Arabic hadith text often begins with its order number ("1 - حدثنا…"); render
// that leading number in Arabic-Indic numerals (the English translation keeps 1.).
const arHadithText = (s) => String(s).replace(/^(\s*)(\d+)/, (_, sp, n) => sp + arDigits(n));
function playAudio(url) {
  if (!url) return toast(t("coming_soon"));
  if (currentAudio) currentAudio.pause();
  currentAudio = new Audio(url);
  currentAudio.play().then(() => toast("🔊 " + t("listen"))).catch(() => toast(t("audio_unavailable")));
}

// Per-ayah play/pause: the button shows ▶ when idle and ⏸ while that ayah plays.
let _ayahBtn = null;
function playAyah(btn, url) {
  if (!url) return toast(t("coming_soon"));
  if (currentAudio && _ayahBtn === btn && !currentAudio.paused) {
    currentAudio.pause();
    btn.innerHTML = ICON_PLAY;
    return;
  }
  if (currentAudio) currentAudio.pause();
  if (_ayahBtn && _ayahBtn !== btn) _ayahBtn.innerHTML = ICON_PLAY;
  if (typeof stopSurahAudio === "function") stopSurahAudio();
  currentAudio = new Audio(url);
  _ayahBtn = btn;
  btn.innerHTML = ICON_PAUSE;
  currentAudio.onended = () => { if (_ayahBtn === btn) btn.innerHTML = ICON_PLAY; };
  currentAudio.play().catch(() => { btn.innerHTML = ICON_PLAY; toast(t("audio_unavailable")); });
}

// ---------------- i18n + direction ----------------
function applyLang() {
  const conf = I18N[State.lang];
  document.body.setAttribute("dir", conf._dir);
  document.documentElement.lang = State.lang;
  localStorage.setItem("wilayat.lang", State.lang);
  els("[data-i18n]").forEach((n) => (n.textContent = t(n.dataset.i18n)));
  els("[data-i18n-ph]").forEach((n) => (n.placeholder = t(n.dataset.i18nPh)));
  el("#langLabel").textContent = conf._name;
  localizeNumbers();
}

// ---------------- Locale numerals + phrase translation ----------------
const DIGIT_SETS = { ar: "٠١٢٣٤٥٦٧٨٩", ur: "۰۱۲۳۴۵۶۷۸۹", fa: "۰۱۲۳۴۵۶۷۸۹", prs: "۰۱۲۳۴۵۶۷۸۹", ks: "۰۱۲۳۴۵۶۷۸۹" };
let _phraseRe = null;
function buildPhraseRegex() {
  if (typeof PHRASES === "undefined") return;
  const keys = Object.keys(PHRASES).sort((a, b) => b.length - a.length)
    .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  // Letter boundaries so e.g. "All" never matches inside "Allah".
  try {
    _phraseRe = new RegExp("(?<![A-Za-z])(?:" + keys.join("|") + ")(?![A-Za-z])", "g");
  } catch {
    // Older Safari has no lookbehind — fall back to multi-char keys only (safe without boundaries).
    const safe = keys.filter((k) => k.length >= 5 && k !== "Allah");
    _phraseRe = new RegExp("\\b(?:" + safe.join("|") + ")\\b", "g");
  }
}
// Localize one string: translate known phrases, then convert digits.
function localizeStr(str) {
  const plang = contentLang();   // Dari→Persian, Kashmiri→Urdu phrases; en-mapped langs keep English
  let out = str;
  if (plang !== "en" && _phraseRe) out = out.replace(_phraseRe, (m) => (PHRASES[m] && PHRASES[m][plang]) || m);
  const d = DIGIT_SETS[State.lang];
  if (d) out = out.replace(/[0-9]/g, (n) => d[+n]);
  return out;
}
// Walk the active view and localize every text node (phrases + numerals).
function localizeNumbers(root) {
  if (State.lang === "en") return;
  root = root || document.querySelector("#views");
  if (!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  for (const node of nodes) {
    const nv = localizeStr(node.nodeValue);
    if (nv !== node.nodeValue) node.nodeValue = nv;
  }
}
let _numObserver;
function setupNumberLocalization() {
  const root = document.querySelector("#views");
  if (!root || _numObserver) return;
  buildPhraseRegex();
  _numObserver = new MutationObserver(() => {
    if (State.lang === "en") return;
    _numObserver.disconnect();           // avoid self-retrigger while we edit text
    localizeNumbers(root);
    _numObserver.observe(root, { childList: true, subtree: true, characterData: true });
  });
  _numObserver.observe(root, { childList: true, subtree: true, characterData: true });
}

function applyTheme() {
  State.theme = "dark";
  document.body.setAttribute("data-theme", "dark");
  localStorage.removeItem("wilayat.theme");
}

// ---------------- Toast ----------------
let toastTimer;
function toast(msg) {
  const box = el("#toast");
  box.textContent = msg;
  box.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("show"), 1900);
}

// ---------------- Router ----------------
let _navIndex = 0;

function normalizeRoute(route) {
  return RENDERERS[route] ? route : "home";
}

function routeUrl(route) {
  const base = location.pathname + location.search;
  return route === "home" ? base : `${base}#${route}`;
}

function syncHistory(route, options = {}) {
  if (options.history === false || !window.history || !history.pushState) return;
  const state = history.state && history.state.wilayat ? history.state : null;
  if (options.replace || !state) {
    history.replaceState({ wilayat: true, route, index: _navIndex }, "", routeUrl(route));
    return;
  }
  if (state.route === route) return;
  _navIndex += 1;
  history.pushState({ wilayat: true, route, index: _navIndex }, "", routeUrl(route));
}

function appBack(fallback = "home") {
  if (_navIndex > 0) {
    history.back();
    return;
  }
  if (State.route !== fallback) go(fallback);
}

function go(route, options = {}) {
  route = normalizeRoute(route);
  if (route !== "qibla") stopQiblaCompass();
  stopSurahAudio();   // stop any Quran recitation when navigating away / going back
  State.route = route;
  els(".nav-item, .bottom-item").forEach((n) => n.classList.toggle("active", n.dataset.route === route));
  els(".view").forEach((v) => v.classList.remove("active"));
  const view = el("#view-" + route);
  if (view) {
    view.classList.add("active");
    view.scrollIntoView({ behavior: "instant", block: "start" });
  }
  RENDERERS[route] && RENDERERS[route](view);
  el("#sidebar").classList.remove("open");
  window.scrollTo({ top: 0 });
  syncHistory(route, options);
  updateSearchMark();
  if (route === "home") {
    const si = el(".search input");
    if (si && si.value.trim()) filterHomeModules(si.value);
  }
}

// ---------------- Renderers per module ----------------
const RENDERERS = {
  home: renderHome,
  quran: renderQuran,
  hadith: renderHadith,
  dua: renderDua,
  ziyarat: renderZiyarat,
  prayer: renderPrayer,
  qibla: renderQibla,
  calendar: renderCalendar,
  ahlulbayt: renderAhlulBayt,
  ai: renderAI,
  library: renderLibrary,
  community: renderCommunity,
  search: renderSearch,
  media: renderMedia,
  tasbih: renderTasbih,
  admin: renderAdmin,
};

function head(titleKey, subKey) {
  // Settings-reached pages keep a back arrow on phone (others use the bottom nav).
  const settingsPage = State.route !== "home" && !isPrimaryRoute(State.route);
  const back = State.route !== "home"
    ? `<button class="screen-back${settingsPage ? " for-settings" : ""}" onclick="appBack()" aria-label="Back">←</button>` : "";
  return `<div class="page-head">${back}<div class="eyebrow wilayat-mark">Al-Wilayat</div>
    <h1>${t(titleKey)}</h1>${subKey ? `<p>${t(subKey)}</p>` : ""}</div>`;
}

// ---------- Usage stats (persisted; real numbers on the home page) ----------
const Stats = {
  KEY: "wilayat.stats",
  _today: () => new Date().toISOString().slice(0, 10),
  _yesterday: () => new Date(Date.now() - 864e5).toISOString().slice(0, 10),
  load() { try { return JSON.parse(localStorage.getItem(this.KEY) || "{}"); } catch { return {}; } },
  save(s) { try { localStorage.setItem(this.KEY, JSON.stringify(s)); } catch { /* ignore */ } },
  _roll(s) {
    const t = this._today();
    if (s.date !== t) { s.date = t; s.versesToday = 0; s.dhikrToday = 0; s.readSurahs = []; }
    return s;
  },
  get() { const s = this._roll(this.load()); this.save(s); return s; },
  touchStreak() {
    const s = this._roll(this.load());
    if (s.lastActive !== this._today()) {
      s.streak = (s.lastActive === this._yesterday()) ? (s.streak || 0) + 1 : 1;
      s.lastActive = this._today();
    }
    if (!s.streak) s.streak = 1;
    this.save(s);
  },
  addSurahRead(n, verseCount) {
    const s = this.get();
    s.readSurahs = s.readSurahs || [];
    if (!s.readSurahs.includes(n)) {
      s.readSurahs.push(n);
      s.versesToday = (s.versesToday || 0) + (verseCount || 0);
      this.save(s);
    }
  },
  addDhikr(n = 1) { const s = this.get(); s.dhikrToday = (s.dhikrToday || 0) + n; this.save(s); },
};

// ---------- HOME ----------
function renderHome(v) {
  const next = nextPrayer();
  const st = Stats.get();
  const cards = MODULES.map((m, i) => `
    <div class="module-card" style="animation-delay:${i * 55}ms" onclick="go('${routeFor(m.id)}')">
      <span class="glow" style="--accent:${m.accent}"></span>
      <h3>${t(m.titleKey)}</h3>
      <p>${t(m.descKey)}</p>
    </div>`).join("");

  v.innerHTML = `
    <div class="hero glass-hi">
      <div class="kalima-calligraphy" dir="rtl" aria-label="محمد رسول الله">
        <img src="assets/kalima-calligraphy.png?v=1" alt="محمد رسول الله" draggable="false" ondragstart="return false" />
      </div>
    </div>
    <div class="stat-row">
      <div class="stat"><div class="big">${next.time}</div><div class="lbl">${t("next_prayer")} · ${langName(next)}</div></div>
      <div class="stat"><div class="big">${st.streak || 1} ${t("days")}</div><div class="lbl">${t("streak")}</div></div>
      <div class="stat"><div class="big">${st.versesToday || 0} ${t("verses")}</div><div class="lbl">${t("read_today")}</div></div>
      <div class="stat"><div class="big">${st.dhikrToday || 0} ${t("times")}</div><div class="lbl">${t("dhikr_today")}</div></div>
    </div>
    ${State.coords ? "" : `<div class="card" style="text-align:center;margin-bottom:18px">
      <span style="color:var(--text-2);font-size:13px">${t("enable_loc")}</span>
      <button class="btn" style="margin-top:10px" onclick="requestLocation(true)">📍 ${t("use_location")}</button></div>`}
    <div class="page-head"><h1 style="font-size:22px">${t("explore")}</h1><p>${t("explore_sub")}</p></div>
    <div class="grid modules">${cards}</div>`;
}
const routeFor = (id) => (id === "ahlulbayt" ? "ahlulbayt" : id);
const ARABIC_SCRIPT_LANGS = ["ar", "ur", "fa", "prs", "ks"];
// Latin-script langs: untranslated phrases stay English instead of blank.
const EN_LIKE_LANGS = ["en", "sg", "az", "ms"];
const ARABIC_RE = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/;
const isArabicScript = (s) => ARABIC_RE.test(s || "");
const localizedText = (str) => localizeStr(str || "");
const selectedText = (str) => {
  const raw = str || "";
  const out = localizedText(raw);
  return (EN_LIKE_LANGS.includes(State.lang) || out !== raw) ? out : "";
};
const localizedName = (p) => {
  if (!p) return "";
  if (p[State.lang]) return p[State.lang];
  if (State.lang === "ar") return p.ar || selectedText(p.en) || "";
  return selectedText(p.en || "");
};
const langName = (p) => localizedName(p);
// Main panel titles follow the selected language; the right-side .ar title stays Arabic.
const disp = (en, ar, fallback = "") => (State.lang === "ar"
  ? (ar || selectedText(en) || fallback)
  : (selectedText(en) || fallback));
const plain = (str) => (str || "").replace(/\s+/g, " ").trim();
const sameText = (a, b) => plain(a) === plain(b);
const sideArabic = (ar, main = "") => {
  // Suppress the side Arabic when it duplicates the main title or the main is
  // already Arabic script (any Arabic-script UI language) — avoids Arabic twice.
  if (!ar || State.lang === "ar" || sameText(ar, main) || isArabicScript(main)) return "";
  return `<div class="ar">${ar}</div>`;
};
const quranListTitle = (s) => {
  const title = disp(s.en, s.ar);
  if (title) return title;
  return `${t("surah")} ${s.n}`;
};
const translatedOrEmpty = (str) => {
  const out = localizedText(str || "");
  return (EN_LIKE_LANGS.includes(State.lang) || out !== (str || "")) ? out : "";
};
const translatedContent = (str) => translatedOrEmpty(str);
// Hadith translation in the current language: use the stored per-language field
// (ur/fa/az/ms — Kashmiri→ur, Dari→fa) when available; otherwise the English.
// The Arabic original (h.ar) is never changed.
function hadithTrans(h) {
  const f = trField();                       // "ur" | "fa" | "az" | "ms" | "en" | null
  if (f && f !== "en" && h && h[f]) return h[f];
  return translatedContent(h && h.en);
}
// Surah-name meaning: exact-match table (az/ms) first, else the phrase map.
const surahMeaning = (m) => {
  const o = typeof QURAN_MEANINGS !== "undefined" ? QURAN_MEANINGS[m] : null;
  if (o && o[contentLang()]) return o[contentLang()];
  return translatedOrEmpty(m);
};
// Localized category label (dua/ziyarat/library groups).
const tcat = (name) => (!CATS[name] ? (selectedText(name) || name) : (CATS[name][State.lang] || selectedText(name) || name));
// Compass cardinal letters for Arabic-script language modes.
const dirLabel = (d) => (ARABIC_SCRIPT_LANGS.includes(State.lang) ? ({ N: "شم", S: "جن", E: "شر", W: "غر" })[d] : d);
// Fallback chains so the month/weekday always localize (never an English month
// when a niche tag like ks-Arab / fa-AF isn't in the browser's data).
const dateLocale = () => ({
  en: undefined,
  sg: ["en-SG", "en"],
  ar: ["ar"],
  ur: ["ur", "ur-PK"],
  fa: ["fa"],
  prs: ["fa-AF", "fa"],
  az: ["az", "az-Latn", "tr"],
  ms: ["ms", "ms-MY", "id"],
  ks: ["ks-Arab", "ks", "ur"],
})[State.lang];

// ---------- QURAN ----------
async function renderQuran(v) {
  v.innerHTML = head("m_quran", "m_quran_d") + `
    <label class="search" style="margin-bottom:16px"><span>🔍</span>
      <input id="qSearch" placeholder="${t("search")}" onkeydown="if(event.key==='Enter')quranSearch()"></label>
    <div class="chips" id="juzChips">
      <span class="chip active" onclick="renderQuran(document.getElementById('view-quran'))">${t("surahs")}</span>
      ${Array.from({ length: 30 }, (_, i) => `<span class="chip" onclick="openJuz(${i + 1})">${t("juz")} ${i + 1}</span>`).join("")}
    </div>
    <div id="quranBody"><div class="card">${t("loading")}</div></div>`;
  try {
    const data = await api("/quran/surahs");
    const list = data.surahs.map((s) => {
      const title = quranListTitle(s);
      const meaningText = surahMeaning(s.meaning);
      const meaning = meaningText ? `${meaningText} · ` : "";
      return `<div class="list-item" onclick="openSurah(${s.n})">
        <div class="badge-num">${s.n}</div>
        <div class="meta"><div class="t">${title}</div><div class="s">${meaning}${s.ayat} ${t("verses")} · ${localizedText(s.type)}</div></div>
        ${sideArabic(s.ar, title)}
      </div>`;
    }).join("");
    el("#quranBody").innerHTML = (data.seed ? offlineBanner() : "") + list;
  } catch {
    el("#quranBody").innerHTML = offlineBanner() + SURAHS.map((s) => {
      const title = quranListTitle(s);
      const meaningText = surahMeaning(s.meaning);
      const meaning = meaningText ? `${meaningText} · ` : "";
      return `<div class="list-item" onclick="openSurah(${s.n})"><div class="badge-num">${s.n}</div>
        <div class="meta"><div class="t">${title}</div><div class="s">${meaning}${s.ayat} ${t("verses")} · ${localizedText(s.type)}</div></div>
        ${sideArabic(s.ar, title)}</div>`;
    }).join("");
  }
}

function verseBlock(a, surahN) {
  const tf = trField();
  const tr = tf ? `<div class="tr">${a[tf] || ""}</div>` : "";
  const audio = a.audio ? `<button class="chip" onclick="event.stopPropagation();playAyah(this,'${a.audio}')">${ICON_PLAY}</button>` : "";
  const taf = surahN ? `<button class="chip" onclick="event.stopPropagation();toggleTafsir(${surahN},${a.n},this)">📚 ${localizedText("Tafsir al-Mizan")}</button>` : "";
  return `<div class="ayah-block">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span class="num">${surahN ? surahN + ":" : ""}${a.n}</span>
        <span style="display:flex;gap:6px">${audio}${taf}</span></div>
      <div class="ar">${a.ar}</div>
      <div class="translit">${a.translit || ""}</div>${tr}
      <div class="tafsir-box" style="display:none"></div></div>`;
}

// tafsir edition follows the active language (falls back to English)
const tafsirEdition = () => "almizan_" + (["en", "ar", "fa", "ur"].includes(State.lang) ? State.lang : "en");

async function toggleTafsir(s, a, btn) {
  const box = btn.closest(".ayah-block").querySelector(".tafsir-box");
  if (box.style.display === "block") { box.style.display = "none"; return; }
  box.style.display = "block";
  box.innerHTML = `<div style="color:var(--text-2);padding:10px">${t("loading")}</div>`;
  try {
    const d = await api(`/quran/tafsir/${s}/${a}?edition=${tafsirEdition()}`);
    box.innerHTML = `
      <div style="margin-top:12px;padding:16px;border-radius:14px;background:rgba(8,35,84,.58);border:1px solid var(--glass-brd)">
        <div class="eyebrow">📚 ${localizedText(d.name)} · ${localizedText(d.author || "Allamah Tabatabai")}</div>
        <div style="margin-top:10px;line-height:1.8;white-space:pre-wrap;${ARABIC_SCRIPT_LANGS.includes(State.lang) ? "direction:rtl;text-align:right" : ""}">${tafsirToHtml(d.text)}</div>
      </div>`;
  } catch {
    box.innerHTML = `<div style="color:var(--text-2);padding:10px">${localizedText("Tafsir unavailable. Please make sure the backend is running.")}</div>`;
  }
}
// minimal markdown: strip code fences, bold, headings
function tafsirToHtml(md) {
  return escapeHtml(md || "")
    .replace(/```[a-z]*\n?/g, "").replace(/```/g, "")
    .replace(/^#+\s*(.+)$/gm, "<strong>$1</strong>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

async function openSurah(n) {
  stopSurahAudio();                       // reset recitation state for the new surah
  const body = el("#quranBody");
  body.innerHTML = `<div class="card">${t("loading")}</div>`;
  try {
    const d = await api(`/quran/surah/${n}`);
    Stats.addSurahRead(n, (d.verses || []).length);   // count toward "Read Today"
    const allAudio = d.verses.filter((v) => v.audio).map((v) => v.audio);
    body.innerHTML = `
      <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap">
        <button class="btn ghost" onclick="renderQuran(document.getElementById('view-quran'))">← ${t("surahs")}</button>
        <button class="btn" id="surahPlayBtn" onclick="playSurah(${n})">${ICON_PLAY} ${t("listen")}</button>
        <button class="btn ghost" onclick="toast(t('saved'))">🔖 ${t("bookmark")}</button>
      </div>
      <div class="card" style="text-align:center;margin-bottom:16px">
        <h2 style="font-family:Amiri,serif;font-size:32px;color:var(--text-0)">${d.ar}</h2>
        <p style="color:var(--text-2)">${quranListTitle({ ...d, n })}${surahMeaning(d.meaning) ? " · " + surahMeaning(d.meaning) : ""} · ${d.ayat} ${t("verses")}</p>
      </div>
      ${n !== 1 && n !== 9 ? `<div class="ayah-block" style="text-align:center"><div class="ar">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div></div>` : ""}
      ${d.verses.map((a) => verseBlock(a, n)).join("")}`;
    window._surahAudio = allAudio;
  } catch {
    body.innerHTML = offlineBanner();
  }
}
// Surah recitation with a play / pause button that reflects the real state.
let _surahPlay = { queue: [], i: 0, active: false };
function setSurahPlayBtn(playing) {
  const btn = el("#surahPlayBtn");
  if (btn) btn.innerHTML = playing ? `${ICON_PAUSE} ${t("pause")}` : `${ICON_PLAY} ${t("listen")}`;
}
function stopSurahAudio() {
  if (currentAudio) { currentAudio.pause(); currentAudio.onended = null; }  // break the auto-advance chain
  _surahPlay.active = false;
  if (_ayahBtn) { _ayahBtn.innerHTML = ICON_PLAY; _ayahBtn = null; }        // reset any per-ayah button
  setSurahPlayBtn(false);
}
function _surahNext() {
  if (_surahPlay.i >= _surahPlay.queue.length) { _surahPlay.active = false; setSurahPlayBtn(false); return; }
  if (currentAudio) currentAudio.pause();
  currentAudio = new Audio(_surahPlay.queue[_surahPlay.i++]);
  currentAudio.onended = _surahNext;
  currentAudio.play().catch(() => {});
}
function playSurah(n) {
  if (_surahPlay.active && currentAudio) {
    if (currentAudio.paused) { currentAudio.play().catch(() => {}); setSurahPlayBtn(true); }
    else { currentAudio.pause(); setSurahPlayBtn(false); }
    return;
  }
  const q = window._surahAudio || [];
  if (!q.length) return toast(t("coming_soon"));
  if (_ayahBtn) { _ayahBtn.innerHTML = ICON_PLAY; _ayahBtn = null; }
  _surahPlay = { queue: q, i: 0, active: true };
  setSurahPlayBtn(true);
  _surahNext();
  toast("🔊 " + t("surah") + " " + n);
}

async function openJuz(j) {
  const body = el("#quranBody");
  body.innerHTML = `<div class="card">${t("loading")}</div>`;
  try {
    const d = await api(`/quran/juz/${j}`);
    body.innerHTML = `
      <button class="btn ghost" style="margin-bottom:16px" onclick="renderQuran(document.getElementById('view-quran'))">← ${t("surahs")}</button>
      <div class="card" style="text-align:center;margin-bottom:16px"><h2>${t("juz")} ${j}</h2><p style="color:var(--text-2)">${d.count} ${t("verses")}</p></div>
      ${d.verses.map((a) => verseBlock(a, a.surah)).join("")}`;
  } catch { body.innerHTML = offlineBanner(); }
}

async function quranSearch() {
  const q = el("#qSearch").value.trim(); if (q.length < 2) return;
  const body = el("#quranBody");
  body.innerHTML = `<div class="card">${t("searching")}</div>`;
  try {
    const d = await api(`/quran/search?q=${encodeURIComponent(q)}`);
    body.innerHTML = `<button class="btn ghost" style="margin-bottom:16px" onclick="renderQuran(document.getElementById('view-quran'))">← ${t("surahs")}</button>
      <div class="page-head"><h1 style="font-size:18px">${d.count} ${t("results_for")} "${escapeHtml(q)}"</h1></div>
      ${d.results.map((r) => `<div class="ayah-block" onclick="openSurah(${r.surah})">
        <div class="num">${localizedText(r.surahName || "")} ${r.surah}:${r.ayah}</div>
        <div class="ar">${r.ar}</div>${translatedContent(r.en) ? `<div class="tr">${translatedContent(r.en)}</div>` : ""}</div>`).join("") || `<div class='card'>${t("no_matches")}</div>`}`;
  } catch { body.innerHTML = offlineBanner(); }
}

// ---------- HADITH ----------
async function renderHadith(v) {
  v.innerHTML = head("m_hadith", "m_hadith_d") + `
    <label class="search" style="margin-bottom:16px"><span>🔍</span>
      <input id="hSearch" placeholder="${t("search")}" inputmode="search" oninput="hadithSearchLive(this.value)" onkeydown="if(event.key==='Enter')hadithSearch()"></label>
    <div id="hadithBody"><div class="card">${t("loading")}</div></div>`;
  try {
    const d = await api("/hadith/books");
    const books = d.books.map((b) => {
      const status = b.downloaded ? "" : b.unavailable ? ` · ⚠️ ${localizedText("not in source API")}` : " · ⏳";
      const click = b.downloaded ? `openBook('${b.bookId}')`
        : b.unavailable ? `toast(localizedText('This book is not available yet.'))`
        : `toast(t('downloading'))`;
      const arName = HADITH_AR[b.bookId] || b.name;
      const author = ARABIC_SCRIPT_LANGS.includes(State.lang)
        ? (AUTHOR_AR[b.bookId.split("-").pop()] || localizedText(b.author))
        : localizedText(b.author);
      const title = disp(b.englishName || b.name, arName, t("nav_hadith"));
      return `<div class="list-item" onclick="${click}" ${b.unavailable ? 'style="opacity:.55"' : ""}>
        <div class="badge-num">${b.downloaded ? "📖" : b.unavailable ? "🚫" : "📜"}</div>
        <div class="meta"><div class="t">${title}${status}</div>
          <div class="s">${author} · ${b.count.toLocaleString()} ${t("narrations")}${b.edition ? " · " + editionLabel(b.edition) : ""}</div></div>
        ${sideArabic(arName, title)}
      </div>`;
    }).join("");
    el("#hadithBody").innerHTML = `<div class="page-head"><h1 style="font-size:18px">${t("collections")} (${d.books.length})</h1></div>${books}`;
  } catch {
    el("#hadithBody").innerHTML = offlineBanner() + HADITH_BOOKS.map((b) => {
      const title = disp(b.en, b.ar, t("nav_hadith"));
      return `<div class="list-item"><div class="badge-num">📜</div>
        <div class="meta"><div class="t">${title}</div><div class="s">${localizedText(b.author)} · ${b.count} ${t("narrations")}</div></div>
        ${sideArabic(b.ar, title)}</div>`;
    }).join("");
  }
}

// Exact reference (book, volume, chapter no., hadith no.) under every narration
// Localized label for a book's edition — "Arabic" or "English".
function editionLabel(ed) {
  return ed === "en" ? t("ed_en") : t("ed_ar");
}

function refLine(h) {
  const r = h.reference || {};
  // Reference follows the BOOK's edition (Arabic book → Arabic ref, RTL; English
  // book → English ref) and is never run through the phrase translator, so it
  // never mixes languages.
  const arCite = r.ar_citation;
  const cite = arCite || r.citation || r.book || h.name || "";
  const dir = arCite ? "rtl" : "ltr";
  const loc = (!arCite && r.location) ? ` - ${r.location}` : "";
  return `<div class="translit" dir="${dir}" style="margin-top:10px;border-top:1px solid var(--glass-brd);padding-top:8px">
    📖 <strong style="color:var(--text-0)">${cite}</strong>${loc}</div>`;
}

let _book = { id: null, page: 1, total: 0 };
async function openBook(id, page = 1) {
  _book = { id, page, total: 0 };
  const body = el("#hadithBody");
  body.innerHTML = `<div class="card">${t("loading")}</div>`;
  try {
    const d = await api(`/hadith/book/${id}?page=${page}&size=20`);
    _book.total = d.total;
    const pages = Math.ceil(d.total / d.size);
    const items = d.hadiths.map((h) => `
      <div class="ayah-block">
        <div class="translit" style="margin:0 0 8px">${localizedText(h.category || "")} ${h.chapter ? "· " + localizedText(h.chapter) : ""}</div>
        ${h.ar ? `<div class="ar">${arHadithText(h.ar)}</div>` : ""}
        ${hadithTrans(h) ? `<div class="tr">${hadithTrans(h)}</div>` : ""}
        ${h.grading ? `<div class="translit">⚖️ ${localizedText(h.grading)}</div>` : ""}
        ${refLine(h)}
      </div>`).join("");
    body.innerHTML = `
      <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;align-items:center">
        <button class="btn ghost" onclick="renderHadith(document.getElementById('view-hadith'))">← ${t("collections")}</button>
        <strong>${localizedText(d.name)}</strong><span style="color:var(--text-2)">· ${d.total.toLocaleString()} ${t("narrations")}${d.edition ? " · " + editionLabel(d.edition) : ""}</span>
      </div>${items}
      <div style="display:flex;gap:10px;justify-content:center;margin-top:18px;align-items:center">
        <button class="btn ghost" ${page <= 1 ? "disabled" : ""} onclick="openBook('${id}',${page - 1})">←</button>
        <span style="color:var(--text-2)">${localizedText("Page")} ${page} / ${pages}</span>
        <button class="btn ghost" ${page >= pages ? "disabled" : ""} onclick="openBook('${id}',${page + 1})">→</button>
      </div>`;
    window.scrollTo({ top: 0 });
  } catch { body.innerHTML = offlineBanner(); }
}

// Live hadith search — fires as you type (debounced). Numbers from 1 digit; text 2+.
let _hSearchTimer = null;
function hadithSearchLive(q) {
  clearTimeout(_hSearchTimer);
  q = (q || "").trim();
  if (!q) { renderHadith(el("#view-hadith")); return; }
  if (q.length < 2 && !/^\d+$/.test(q)) return;
  _hSearchTimer = setTimeout(hadithSearch, 300);
}

async function hadithSearch() {
  const q = el("#hSearch").value.trim();
  if (q.length < 2 && !/^\d+$/.test(q)) return;
  const body = el("#hadithBody");
  body.innerHTML = `<div class="card">${t("searching")}</div>`;
  try {
    const d = await api(`/hadith/search?q=${encodeURIComponent(q)}`);
    body.innerHTML = `<button class="btn ghost" style="margin-bottom:16px" onclick="renderHadith(document.getElementById('view-hadith'))">← ${t("collections")}</button>
      <div class="page-head"><h1 style="font-size:18px">${d.count} ${t("results_for")} "${escapeHtml(q)}"</h1></div>
      ${d.results.map((h) => `<div class="ayah-block">
        ${h.ar ? `<div class="ar">${arHadithText(h.ar)}</div>` : ""}${hadithTrans(h) ? `<div class="tr">${hadithTrans(h)}</div>` : ""}${refLine(h)}</div>`).join("") || `<div class='card'>${t("no_matches")}</div>`}`;
  } catch { body.innerHTML = offlineBanner(); }
}

// ---------- DUA (curated index + real texts from al-Kafi Book of Supplication) ----------
async function renderDua(v) {
  const cats = [...new Set(DUAS.map((d) => d.cat))];
  const sections = cats.map((c) => {
    const cards = DUAS.filter((d) => d.cat === c).map((d) => {
      const title = disp(d.en, d.ar, t("nav_dua"));
      return `<div class="list-item" onclick="openText('dua','${d.textId || ""}', this)">
        <div class="meta"><div class="t">${title} ›</div><div class="s">${localizedText(d.src)} · ${localizedText(d.note)}</div></div>
        ${sideArabic(d.ar, title)}
      </div>`;
    }).join("");
    return `<div class="page-head" style="margin-top:18px"><h1 style="font-size:17px">${tcat(c)}</h1></div>${cards}`;
  }).join("");
  v.innerHTML = head("m_dua", "m_dua_d") + sections;
}

// ---------- ZIYARAT (curated index + real Kamil al-Ziyarat texts) ----------
async function renderZiyarat(v) {
  const cats = [...new Set(ZIYARAT.map((z) => z.cat))];
  const sections = cats.map((c) => {
    const cards = ZIYARAT.filter((z) => z.cat === c).map((z) => {
      const title = disp(z.en, z.ar, t("nav_ziyarat"));
      return `<div class="list-item" onclick="openText('ziyarat','${z.textId || ""}', this)">
        <div class="meta"><div class="t">${title} ›</div><div class="s">${localizedText(z.to)}</div></div>
        ${sideArabic(z.ar, title)}
      </div>`;
    }).join("");
    return `<div class="page-head" style="margin-top:18px"><h1 style="font-size:17px">${tcat(c)}</h1></div>${cards}`;
  }).join("");
  v.innerHTML = head("m_ziyarat", "m_ziyarat_d") + sections;
}

// shared inline reader for both ziyarat and dua cards
async function openText(kind, id, row) {
  const title = row.querySelector(".t").textContent.replace(" ›", "").trim();
  const arTitle = row.querySelector(".ar") ? row.querySelector(".ar").textContent.trim() : title;
  const existing = document.getElementById("textReader");
  const key = kind + ":" + (id || title);
  // toggle closed if clicking the same card again
  if (existing && existing.dataset.key === key) { existing.remove(); return; }
  if (existing) existing.remove();

  const box = document.createElement("div");
  box.id = "textReader"; box.dataset.key = key; box.className = "card";
  box.style.marginTop = "12px";
  box.innerHTML = t("loading");
  row.after(box);
  const close = `<button class="btn ghost" onclick="document.getElementById('textReader').remove()">✕</button>`;

  if (!id) {  // full text not bundled — dignified inline note (never a dead toast)
    box.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
        <div style="flex:1">
          <h2 style="font-family:Amiri,serif;color:var(--text-0)">${arTitle}</h2>
          <div style="color:var(--text-2);font-size:14px">${title}</div>
        </div>${close}
      </div>
      <p style="color:var(--text-1);line-height:1.8">${localizedText("The full text for this item is not bundled yet.")}</p>`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  try {
    const d = await api(`/${kind}/full/${id}`);
    box.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <h2 style="flex:1;font-family:Amiri,serif;color:var(--text-0)">${d.ar_title}</h2>${close}
      </div>
      <p style="color:var(--text-2);margin-bottom:14px">${disp(d.en_title, d.ar_title, title)} · ${d.count} ${t("passages")}</p>
      ${d.verses.map((vrs) => {
        if (vrs.head) return `<h3 style="color:var(--text-0);margin:18px 0 8px;font-size:16px">${localizedText(vrs.en || "")}</h3>`;
        const ar = vrs.ar ? `<div class="ar">${vrs.ar}</div>` : "";
        const tr = translatedContent(vrs.en);
        const en = tr ? `<div class="tr"${vrs.ar ? "" : ' style="font-size:16px;color:var(--text-1)"'}>${tr}</div>` : "";
        return `<div class="ayah-block">${ar}${en}</div>`;
      }).join("")}`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    box.innerHTML = `<div style="display:flex;gap:10px"><span style='flex:1;color:var(--text-2)'>${localizedText("Text unavailable. Please make sure the backend is running.")}</span>${close}</div>`;
  }
}

// shared loader for corpus-backed dua/ziyarat text lists
async function loadCorpus(path, sel, pendingMsg) {
  try {
    const d = await api(path);
    const box = el(sel);
    if (!d.count) { box.innerHTML = `<div class="card" style="color:var(--text-2)">⏳ ${pendingMsg}</div>`; return; }
    box.innerHTML = d.results.slice(0, 80).map((h) => `
      <div class="ayah-block">
        ${h.ar ? `<div class="ar">${arHadithText(h.ar)}</div>` : ""}
        ${hadithTrans(h) ? `<div class="tr">${hadithTrans(h)}</div>` : ""}
        ${h.grading ? `<div class="translit">⚖️ ${localizedText(h.grading)}</div>` : ""}
        ${refLine(h)}
      </div>`).join("") + (d.count > 80 ? `<div class="card" style="text-align:center;color:var(--text-2)">+${d.count - 80} ${localizedText("more")}</div>` : "");
  } catch {
    el(sel).innerHTML = offlineBanner();
  }
}

// ---------- PRAYER ----------
// ---------- LIVE PRAYER TIMES (location-aware, default India) ----------
const HMS_TO_MIN = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
const PRAYER_KEYS = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];

// Current minutes-since-midnight in a given IANA timezone (falls back to device time).
function nowMinutesIn(tz) {
  try {
    const s = new Date().toLocaleTimeString("en-GB", { timeZone: tz, hour12: false, hour: "2-digit", minute: "2-digit" });
    const [h, m] = s.split(":").map(Number);
    return h * 60 + m;
  } catch {
    const n = new Date();
    return n.getHours() * 60 + n.getMinutes();
  }
}

// Active prayer times — live ones if loaded, else the bundled sample times.
function prayerTimes() {
  if (State.prayer && State.prayer.times) return State.prayer.times;
  return Object.fromEntries(PRAYERS.map((p) => [p.key, p.time]));
}

// The next upcoming prayer (skipping sunrise), based on the location's local time.
function nextPrayer() {
  const times = prayerTimes();
  const tz = State.prayer && State.prayer.tz;
  const nowMin = tz ? nowMinutesIn(tz) : (new Date().getHours() * 60 + new Date().getMinutes());
  const key = PRAYER_KEYS.find((k) => k !== "sunrise" && HMS_TO_MIN(times[k]) > nowMin) || "fajr";
  const seed = PRAYERS.find((p) => p.key === key) || {};
  return { key, time: times[key], en: seed.en, ar: seed.ar, emoji: seed.emoji };
}

const INDIA_DEFAULT = { lat: 28.6139, lng: 77.2090, label: "India · New Delhi (default)" };

// Approximate location from the user's IP — works even on file:// or when GPS
// is blocked/denied, so a click always resolves to a usable location.
async function ipLocate() {
  // Several free providers (different JSON shapes) — first one that responds wins.
  const sources = [
    ["https://ipapi.co/json/", (j) => [j.latitude, j.longitude]],
    ["https://ipwho.is/", (j) => [j.latitude, j.longitude]],
    ["https://get.geojs.io/v1/ip/geo.json", (j) => [j.latitude, j.longitude]],
    ["https://freeipapi.com/api/json", (j) => [j.latitude, j.longitude]],
    ["https://ipinfo.io/json", (j) => (j.loc ? j.loc.split(",") : [])],
  ];
  for (const [url, pick] of sources) {
    try {
      const j = await (await fetch(url, { cache: "no-store" })).json();
      const [a, b] = pick(j) || [];
      const lat = Number(a), lng = Number(b);
      if (isFinite(lat) && isFinite(lng) && (lat || lng)) return { lat, lng };
    } catch { /* try next */ }
  }
  return null;
}

// Resolve a location: precise GPS first, IP fallback otherwise. Resolves null only
// if everything fails. Saves the result so it persists across refreshes.
function getLocation(options = {}) {
  const highAccuracy = !!options.highAccuracy;
  const allowIpFallback = options.allowIpFallback !== false;
  const timeout = options.timeout ?? (highAccuracy ? 11000 : 6000);
  const maximumAge = options.maximumAge ?? (highAccuracy ? 0 : 600000);
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const viaIp = async () => {
      if (!allowIpFallback) { finish(null); return; }
      const c = await ipLocate();
      if (c) saveCoords(c.lat, c.lng, { source: "ip" });
      finish(c ? State.coords : null);
    };
    if (!navigator.geolocation) { viaIp(); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        saveCoords(pos.coords.latitude, pos.coords.longitude, {
          source: "gps",
          accuracy: pos.coords.accuracy,
        });
        finish(State.coords);
      },
      () => viaIp(),  // denied / unavailable → IP fallback
      { enableHighAccuracy: highAccuracy, timeout, maximumAge },
    );
    // Safety net: geolocation can silently hang — fall back to IP after a moment.
    setTimeout(() => { if (!done) viaIp(); }, timeout + 500);
  });
}

// Get location and apply it to prayer times, Qibla & mosque finder.
async function requestLocation(announce) {
  if (State.coords) applyLocationEverywhere();   // reuse remembered location at once
  const c = await getLocation({ highAccuracy: !!announce, maximumAge: announce ? 0 : 600000 });
  applyLocationEverywhere();
  if (announce) toast(c ? "📍 " + t("loc_set") : t("loc_fail"));
}

function applyLocationEverywhere() {
  loadPrayerTimes();
  if (State.route === "qibla") RENDERERS.qibla(el("#view-qibla"));
}

// Fetch real times via the free Aladhan API for the shared location (default India).
async function loadPrayerTimes() {
  const c = State.coords || INDIA_DEFAULT;
  const label = State.coords ? "yours" : "india";
  try {
    // method=0 → Shia Ithna-Ashari (Leva Institute, Qum)
    const r = await fetch(`https://api.aladhan.com/v1/timings?latitude=${c.lat}&longitude=${c.lng}&method=0`);
    const j = await r.json();
    const tg = j.data.timings;
    const clean = (s) => (s || "").split(" ")[0]; // "04:12 (IST)" → "04:12"
    State.prayer = {
      times: { fajr: clean(tg.Fajr), sunrise: clean(tg.Sunrise), dhuhr: clean(tg.Dhuhr),
               asr: clean(tg.Asr), maghrib: clean(tg.Maghrib), isha: clean(tg.Isha) },
      tz: j.data.meta.timezone,
      label: label,
    };
  } catch { /* keep bundled fallback */ }
  if (State.route === "home" || State.route === "prayer") {
    RENDERERS[State.route](el("#view-" + State.route));
  }
}

function renderPrayer(v) {
  const times = prayerTimes();
  const next = nextPrayer();
  const loc = State.prayer ? t(State.prayer.label === "yours" ? "loc_yours" : "loc_india") : t("loc_sample");
  const tz = (State.prayer && State.prayer.tz) || Intl.DateTimeFormat().resolvedOptions().timeZone;
  const dateStr = new Date().toLocaleDateString(dateLocale(), { timeZone: tz, weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const rows = PRAYERS.map((p) => `
    <div class="prayer-row ${p.key === next.key ? "next" : ""}">
      <div class="pn">${langName(p)} ${p.key === next.key ? "· " + t("next_prayer") : ""}</div>
      <div class="pt">${times[p.key] || p.time}</div>
    </div>`).join("");
  v.innerHTML = head("m_prayer", "m_prayer_d") + `
    <div class="card" style="margin-bottom:16px;text-align:center">
      <div style="color:var(--text-2);font-size:13px">📍 ${escapeHtml(loc)}${State.lang === "en" ? " · " + escapeHtml(tz) : ""} · ${t("method_shia")}</div>
      <div class="big" style="font-size:24px;margin-top:6px;font-weight:800">${dateStr}</div>
      <button class="btn ghost" style="margin-top:10px" onclick="requestLocation(true)">📍 ${t("use_location")}</button>
    </div>${rows}`;
}

// ---------- QIBLA ----------
async function renderQibla(v) {
  v.innerHTML = head("m_qibla", "m_qibla_d") + `
    <div class="card" style="text-align:center">
      <div class="compass" id="compass">
        <span class="deg N">${dirLabel("N")}</span><span class="deg S">${dirLabel("S")}</span><span class="deg E">${dirLabel("E")}</span><span class="deg W">${dirLabel("W")}</span>
        <span class="kaaba">🕋</span>
        <div class="needle" id="needle"></div>
      </div>
      <div id="qiblaFacing" class="qibla-facing">✓ ${t("facing_qibla")}</div>
      <div class="stat-row" style="margin-top:10px">
        <div class="stat"><div class="big" id="qiblaDeg">—</div><div class="lbl">${t("qibla_dir")}</div></div>
        <div class="stat"><div class="big" id="kaabaDist">—</div><div class="lbl">${t("distance_kaaba")}</div></div>
      </div>
      <button class="btn" onclick="locateQibla()">🧭 ${t("calibrate")}</button>
      <a class="btn ghost" id="qiblaMapBtn" target="_blank" rel="noopener" style="margin-top:8px;display:inline-block">🗺️ ${t("qibla_map")}</a>
      <p id="qiblaHint" style="color:var(--text-2);font-size:12.5px;margin-top:12px">${t("qibla_hint")}</p>
      <p id="qiblaDebug" style="color:var(--text-2);font-size:11px;margin-top:6px;opacity:.8"></p>
      <p style="color:var(--text-2);font-size:12px;margin-top:6px">↻ ${t("qibla_drag")}</p>
    </div>`;
  attachQiblaDrag();
  if (State.coords) applyQibla(State.coords);
  await refreshQiblaLocation();
}

async function refreshQiblaLocation() {
  const hint = el("#qiblaHint");
  if (hint) hint.textContent = t("locating");
  const c = await getLocation({ highAccuracy: true, timeout: 12000, maximumAge: 0 });
  if (State.route !== "qibla") return null;
  if (c) {
    applyQibla(c);
    loadPrayerTimes();
  } else if (!State.coords && hint) {
    hint.textContent = t("loc_fail");
  }
  return c;
}
// Single place that rotates the needle and lights the "Facing Qibla" badge.
let _needleRot = 0;
function qiblaSetNeedle(deg) {
  deg = ((deg % 360) + 360) % 360;
  _needleRot = deg;
  const n = el("#needle"); if (n) n.style.transform = `rotate(${deg}deg)`;
  const f = el("#qiblaFacing"); if (f) f.classList.toggle("on", Math.min(deg, 360 - deg) <= 6);
}
// Drag the dial to rotate it manually (handy for testing on a laptop with no compass).
function attachQiblaDrag() {
  const c = el("#compass"); if (!c) return;
  let dragging = false;
  const angleAt = (e) => {
    const r = c.getBoundingClientRect();
    const x = e.clientX - (r.left + r.width / 2), y = e.clientY - (r.top + r.height / 2);
    return ((Math.atan2(x, -y) * 180 / Math.PI) + 360) % 360; // clockwise from up
  };
  c.addEventListener("pointerdown", (e) => { dragging = true; c.setPointerCapture(e.pointerId); qiblaSetNeedle(angleAt(e)); });
  c.addEventListener("pointermove", (e) => { if (dragging) { e.preventDefault(); qiblaSetNeedle(angleAt(e)); } });
  c.addEventListener("pointerup", () => { dragging = false; });
  c.style.cursor = "grab";
}
// Great-circle bearing + distance from {lat,lng} to the Kaaba.
function applyQibla(c) {
  const kLa = 21.4225, kLo = 39.8262, R = 6371;
  const toRad = (x) => (x * Math.PI) / 180;
  const la = Number(c.lat), lo = Number(c.lng);
  if (!Number.isFinite(la) || !Number.isFinite(lo)) return;
  const dLon = toRad(kLo - lo);
  const y = Math.sin(dLon) * Math.cos(toRad(kLa));
  const x = Math.cos(toRad(la)) * Math.sin(toRad(kLa)) - Math.sin(toRad(la)) * Math.cos(toRad(kLa)) * Math.cos(dLon);
  let brng = (Math.atan2(y, x) * 180) / Math.PI; brng = (brng + 360) % 360;
  const dLat = toRad(kLa - la);
  const aa = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(la)) * Math.cos(toRad(kLa)) * Math.sin(dLon / 2) ** 2;
  const dist = Math.round(R * 2 * Math.atan2(Math.sqrt(aa), Math.sqrt(1 - aa)));
  State.qibla = brng;
  const source = c.source === "gps" ? t("loc_precise") : t("loc_approx");
  const accuracy = c.accuracy ? ` ±${Math.round(c.accuracy)}m` : "";
  const dbg = el("#qiblaDebug");
  if (dbg) dbg.textContent = `${source}${accuracy}: ${la.toFixed(5)}, ${lo.toFixed(5)} → ${Math.round(brng)}°`;
  const dg = el("#qiblaDeg"); if (dg) dg.textContent = Math.round(brng) + "°";
  const ds = el("#kaabaDist"); if (ds) ds.textContent = dist.toLocaleString() + " " + t("km");
  const mb = el("#qiblaMapBtn");
  if (mb) mb.href = `https://www.google.com/maps/dir/?api=1&origin=${c.lat},${c.lng}&destination=21.4225,39.8262`;
  const hint = el("#qiblaHint");
  if (hint) hint.textContent = c.source === "gps" ? t("qibla_hint") : t("qibla_approx");
  // Visibly swing the needle from North to the Qibla bearing on open.
  qiblaSetNeedle(0);
  setTimeout(() => startQiblaCompass(brng), 90); // then live needle if the device has a compass
}

// Live compass: rotate the needle by (qibla − device heading) so it points to the
// real Qibla as the user turns. Falls back to a static bearing when no sensor.
let _qiblaHandler = null, _compassLive = false, _compassTimer = null, _motionPermissionGranted = false;
function stopQiblaCompass() {
  if (_qiblaHandler) {
    window.removeEventListener("deviceorientationabsolute", _qiblaHandler, true);
    window.removeEventListener("deviceorientation", _qiblaHandler, true);
    _qiblaHandler = null;
  }
  if (_compassTimer) { clearTimeout(_compassTimer); _compassTimer = null; }
}
function startQiblaCompass(qibla) {
  stopQiblaCompass();
  _compassLive = false;
  let usedAbsolute = false;
  qiblaSetNeedle(qibla); // static default (assumes screen-up = North)
  const D = window.DeviceOrientationEvent;
  if (D && typeof D.requestPermission === "function" && !_motionPermissionGranted) {
    const hint = el("#qiblaHint");
    if (hint) hint.textContent = t("qibla_permission");
    return;
  }
  // Non-secure pages (http over LAN) have the compass blocked outright.
  if (!window.isSecureContext) {
    const hint = el("#qiblaHint"); if (hint) hint.textContent = t("qibla_insecure");
    return;
  }
  _qiblaHandler = (e) => {
    if (State.route !== "qibla") return stopQiblaCompass();
    let heading = null;
    if (typeof e.webkitCompassHeading === "number") heading = e.webkitCompassHeading;      // iOS: from North, CW
    else if (e.absolute === true && typeof e.alpha === "number") { heading = 360 - e.alpha; usedAbsolute = true; }
    else if (!usedAbsolute && typeof e.alpha === "number") heading = 360 - e.alpha;          // relative fallback
    if (heading == null) return;
    const screenAngle = (screen.orientation && Number.isFinite(screen.orientation.angle))
      ? screen.orientation.angle
      : (Number.isFinite(window.orientation) ? window.orientation : 0);
    heading = (heading + screenAngle + 360) % 360;
    _compassLive = true;
    const hint = el("#qiblaHint");
    if (hint && hint.dataset.live !== "1") { hint.dataset.live = "1"; hint.textContent = t("qibla_live"); }
    qiblaSetNeedle(qibla - heading);
  };
  window.addEventListener("deviceorientationabsolute", _qiblaHandler, true);
  window.addEventListener("deviceorientation", _qiblaHandler, true);
  // Otherwise, if no sensor data arrives shortly, explain why (permission / no compass).
  _compassTimer = setTimeout(() => {
    if (!_compassLive) { const hint = el("#qiblaHint"); if (hint) hint.textContent = t("qibla_nosensor"); }
  }, 2800);
}

// iOS 13+ needs an explicit permission request from a user gesture.
async function enableCompassPermission() {
  const D = window.DeviceOrientationEvent;
  if (D && typeof D.requestPermission === "function") {
    try {
      const s = await D.requestPermission();
      _motionPermissionGranted = s === "granted";
      if (_motionPermissionGranted && State.qibla != null) startQiblaCompass(State.qibla);
      if (!_motionPermissionGranted) toast(t("compass_denied"));
      return _motionPermissionGranted;
    } catch {
      toast(t("compass_denied"));
      return false;
    }
  }
  _motionPermissionGranted = true;
  return true;
}

async function locateQibla() {
  await enableCompassPermission();              // user gesture → ask for motion sensor (iOS)
  toast("📍 " + t("locating"));
  const c = await refreshQiblaLocation();        // fresh GPS first, IP fallback only if needed
  if (!c) return toast(t("loc_fail"));
  toast("📍 " + t("qibla_set"));
}

// ---------- CALENDAR ----------
const EVENT_STYLE = {
  wiladat: { emoji: "⭐", color: "rgba(31,123,255,.45)", label: "Wiladat" },
  shahadat: { emoji: "🏴", color: "rgba(6,27,70,.62)", label: "Shahadat" },
  occasion: { emoji: "✨", color: "rgba(53,164,255,.45)", label: "Occasion" },
};
let _calFilter = "all";

function renderCalendar(v) {
  const counts = { wiladat: 0, shahadat: 0, occasion: 0 };
  EVENTS.forEach((e) => counts[e.type]++);
  const legend = `<div class="chips">
    <span class="chip ${_calFilter === "all" ? "active" : ""}" onclick="setCal('all')">${tcat("All")} (${EVENTS.length})</span>
    ${Object.entries(EVENT_STYLE).map(([k, s]) => `<span class="chip ${_calFilter === k ? "active" : ""}" onclick="setCal('${k}')">${localizedText(s.label)} (${counts[k]})</span>`).join("")}
  </div>`;

  const months = HIJRI_MONTHS.map((m, i) => {
    let evs = EVENTS.filter((e) => e.mi === i + 1 && (_calFilter === "all" || e.type === _calFilter))
      .sort((a, b) => a.day - b.day);
    if (!evs.length) return "";
    const items = evs.map((e) => {
      const s = EVENT_STYLE[e.type];
      return `<div class="list-item">
        <div class="badge-num" style="background:linear-gradient(135deg,${s.color},transparent)">${e.day}</div>
        <div class="meta"><div class="t">${localizedText(e.en)}</div><div class="s">${e.day} ${localizedText(m)} · ${localizedText(s.label)}</div></div>
      </div>`;
    }).join("");
    return `<div class="page-head" style="margin-top:18px"><h1 style="font-size:16px;color:var(--text-0)">${i + 1}. ${localizedText(m)}</h1></div>${items}`;
  }).join("");

  v.innerHTML = head("m_calendar", "m_calendar_d") + legend + months;
}
function setCal(f) { _calFilter = f; renderCalendar(el("#view-calendar")); }

// ---------- AHLUL BAYT ----------
function renderAhlulBayt(v) {
  const list = MASUMEEN.map((m, i) => {
    const title = localizedText(m.en);
    return `<div class="list-item">
      <div class="badge-num">${i === 0 ? "🌟" : i}</div>
      <div class="meta"><div class="t">${title}</div><div class="s">${localizedText(m.role)}</div></div>
      ${sideArabic(m.ar, title)}
    </div>`;
  }).join("");
  v.innerHTML = head("m_ahl", "m_ahl_d") + `
    <div class="card" style="margin-bottom:18px;text-align:center">
      <div class="ayah" style="font-family:Amiri,serif;font-size:26px;color:var(--text-0);direction:rtl">اللّٰهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ وَآلِ مُحَمَّد</div>
      <p style="color:var(--text-1);margin-top:8px">${localizedText("The Fourteen Infallibles (peace be upon them all)")}</p>
    </div>${list}`;
}

// ---------- AI ASSISTANT ----------
function renderAI(v) {
  v.innerHTML = head("m_ai", "m_ai_d") + `
    <div class="card" style="border-color:var(--gold);background:linear-gradient(135deg,rgba(31,123,255,.14),transparent);margin-bottom:16px">
      <strong>⚠️ ${t("ai_disclaimer")}</strong>
    </div>
    <div class="card">
      <div class="chips" style="margin-bottom:10px">${aiStatusBadge()}</div>
      <div class="chat" id="chat">
        <div class="bubble ai">${localizedText("Assalamu Alaikum! Ask me about the Quran, hadith of Ahlul Bayt (AS), duas or Islamic history.")} <span class="ref">${localizedText("I always cite references and never issue rulings.")}</span></div>
      </div>
      <div class="chat-input">
        <input id="aiInput" data-i18n-ph="ask_placeholder" placeholder="${t("ask_placeholder")}" onkeydown="if(event.key==='Enter')aiSend()">
        <button class="btn" onclick="aiSend()">${t("send")}</button>
      </div>
    </div>`;
  refreshAiStatus();
}
async function aiSend() {
  const inp = el("#aiInput"); const q = inp.value.trim(); if (!q) return;
  const chat = el("#chat");
  chat.insertAdjacentHTML("beforeend", `<div class="bubble user">${escapeHtml(q)}</div>`);
  inp.value = "";
  const typing = document.createElement("div");
  typing.className = "bubble ai"; typing.textContent = "…"; chat.appendChild(typing);
  chat.scrollTop = chat.scrollHeight;
  const rxId = "ai_" + hashCode(q);
  const render = (answer, ref, withReact) => {
    typing.innerHTML = escapeHtml(localizedText(answer)) +
      (ref ? `<span class="ref">${escapeHtml(localizedText(ref))}</span>` : "") +
      (withReact ? reactionBar(rxId) : "");
    chat.scrollTop = chat.scrollHeight;
  };

  // Try streaming the answer live; settle with a reaction bar when complete.
  let fullText = "";
  const streamed = await streamAsk(q, (full) => {
    fullText = full;
    const { answer, ref } = splitAnswerRef(full);
    render(answer || "…", ref, false);
  });
  if (streamed) {
    const { answer, ref } = splitAnswerRef(fullText);
    render(answer, ref, true);
    return;
  }

  // Fallback: live backend (/ask), else the client-side local brain.
  const d = await askOrLocal(q);
  typing.innerHTML = `${escapeHtml(localizedText(d.answer))}<span class="ref">${escapeHtml(localizedText(d.reference || ""))}</span>` +
    `${d.requires_scholar ? `<span class="ref">⚠️ ${localizedText("For any ruling, consult your marja al-taqlid.")}</span>` : ""}` +
    reactionBar(rxId);
  chat.scrollTop = chat.scrollHeight;
}

// ---------- LIBRARY (real downloaded books, categorized) ----------
const BOOK_CAT = {
  "Al-Kafi-Volume-1-Kulayni": "Theology", "Al-Kafi-Volume-2-Kulayni": "Ethics",
  "Al-Kafi-Volume-3-Kulayni": "Fiqh", "Al-Kafi-Volume-4-Kulayni": "Fiqh",
  "Al-Kafi-Volume-5-Kulayni": "Fiqh", "Al-Kafi-Volume-6-Kulayni": "Fiqh",
  "Al-Kafi-Volume-7-Kulayni": "Fiqh", "Al-Kafi-Volume-8-Kulayni": "Hadith",
  "Man-La-Yahduruh-al-Faqih-Volume-1-Saduq": "Fiqh", "Man-La-Yahduruh-al-Faqih-Volume-2-Saduq": "Fiqh",
  "Man-La-Yahduruh-al-Faqih-Volume-3-Saduq": "Fiqh", "Man-La-Yahduruh-al-Faqih-Volume-4-Saduq": "Fiqh",
  "Man-La-Yahduruh-al-Faqih-Volume-5-Saduq": "Fiqh",
  "Nahj-al-Balagha-Radi": "Ethics", "Risalat-al-Huquq-Abidin": "Ethics",
  "Al-Tawhid-Saduq": "Aqeedah", "Kitab-al-Ghayba-Numani": "Aqeedah", "Kitab-al-Ghayba-Tusi": "Aqeedah",
  "Kamal-al-Din-wa-Tamam-al-Nima-Saduq": "Aqeedah", "Fadail-al-Shia-Saduq": "Aqeedah", "Sifat-al-Shia-Saduq": "Aqeedah",
  "Kamil-al-Ziyarat-Qummi": "Ziyarat",
  "Uyun-akhbar-al-Rida-Volume-1-Saduq": "History", "Uyun-akhbar-al-Rida-Volume-2-Saduq": "History",
  "Al-Amali-Mufid": "History", "Al-Amali-Saduq": "History",
  "Al-Khisal-Saduq": "Ethics", "Maani-al-Akhbar-Saduq": "Theology",
  "Thawab-al-Amal-wa-iqab-al-Amal-Saduq": "Ethics", "Kitab-al-Zuhd-Ahwazi": "Ethics",
  "Kitab-al-Mumin-Ahwazi": "Ethics", "Kitab-al-Duafa-Ghadairi": "Rijal",
  "Mujam-al-Ahadith-al-Mutabara-Muhsini": "Hadith",
  "Peshawar-Nights-Shirazi": "History",
  "Man-La-Yahduruh-al-Faqih-Saduq": "Fiqh",
};
const catEmoji = { Fiqh: "⚖️", Ethics: "📗", Aqeedah: "🕌", Theology: "☪️", History: "📜", Ziyarat: "🤲", Rijal: "👤", Hadith: "📖" };
let _libFilter = "All";

async function renderLibrary(v) {
  v.innerHTML = head("m_library", "m_library_d") + `<div id="libBody"><div class="card">${t("loading_library")}</div></div>`;
  try {
    const d = await api("/hadith/books");
    const cats = ["All", ...new Set(Object.values(BOOK_CAT))];
    const chips = `<div class="chips">${cats.map((c) => `<span class="chip ${c === _libFilter ? "active" : ""}" onclick="setLibFilter('${c}')">${tcat(c)}</span>`).join("")}</div>`;
    const books = d.books.filter((b) => _libFilter === "All" || BOOK_CAT[b.bookId] === _libFilter);
    const grid = books.map((b) => {
      const cat = BOOK_CAT[b.bookId] || "Hadith";
      return `<div class="module-card" style="opacity:1;transform:none" onclick="${b.downloaded ? `go('hadith');setTimeout(()=>openBook('${b.bookId}'),60)` : `toast(t('downloading'))`}">
        <span class="glow" style="--accent:var(--royal)"></span>
        <h3 style="font-size:15px">${disp(b.englishName || b.name, HADITH_AR[b.bookId] || b.name, t("nav_hadith"))}</h3>
        <p>${tcat(cat)} · ${b.count.toLocaleString()} ${t("narrations")}</p>
      </div>`;
    }).join("");
    el("#libBody").innerHTML = `
      <div class="stat-row">
        <div class="stat"><div class="big">${d.books.length}</div><div class="lbl">${t("total_books")}</div></div>
        <div class="stat"><div class="big">${d.books.reduce((a, b) => a + b.count, 0).toLocaleString()}</div><div class="lbl">${t("total_narr")}</div></div>
        <div class="stat"><div class="big">${cats.length - 1}</div><div class="lbl">${t("categories")}</div></div>
      </div>${chips}<div class="grid modules">${grid}</div>
      <div class="page-head" style="margin-top:26px"><h1 style="font-size:18px">${t("pdf_library")}</h1><p>${t("pdf_sub")}</p></div>
      <div class="grid modules" id="pdfGrid"></div>`;
    loadPdfs();
  } catch {
    el("#libBody").innerHTML = offlineBanner();
  }
}
function setLibFilter(c) { _libFilter = c; renderLibrary(el("#view-library")); }

async function loadPdfs() {
  try {
    const d = await api("/library/pdfs");
    el("#pdfGrid").innerHTML = d.pdfs.map((p) => `
      <div class="module-card" style="opacity:1;transform:none" onclick='openPdf(${JSON.stringify(p).replace(/'/g, "&#39;")})'>
        <span class="glow" style="--accent:var(--plum)"></span>
        <h3 style="font-size:15px">${localizedText(p.en)}</h3>
        <p>${localizedText(p.cat)} · ${localizedText(p.author)} · PDF${p.edition ? " · " + editionLabel(p.edition) : ""}</p>
      </div>`).join("");
  } catch { /* backend offline */ }
}
function openPdf(p) {
  let m = el("#pdfModal");
  if (!m) {
    m = document.createElement("div");
    m.id = "pdfModal";
    m.style.cssText = "position:fixed;inset:0;z-index:200;background:rgba(3,8,16,.85);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);display:flex;flex-direction:column;padding:14px";
    document.body.appendChild(m);
  }
  m.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;color:var(--text-0)">
      <strong style="flex:1">📕 ${localizedText(p.en)} — ${localizedText(p.author)}</strong>
      <a class="btn ghost" href="${p.url}" target="_blank" rel="noopener">⬇ ${t("download")}</a>
      <button class="btn" onclick="document.getElementById('pdfModal').remove()">✕</button>
    </div>
    <iframe src="${p.url}" style="flex:1;width:100%;border:none;border-radius:14px;background:var(--bg-0)"></iframe>`;
  m.style.display = "flex";
}

// ---------- COMMUNITY ----------
// reactions persist locally (no account / no server) — "complete access" toggling
const REACTIONS = JSON.parse(localStorage.getItem("wilayat.reactions") || "{}");
const saveReactions = () => localStorage.setItem("wilayat.reactions", JSON.stringify(REACTIONS));

// ----- Live-AI status badge (Claude vs built-in answers) -----
function aiStatusBadge() {
  return `<span class="chip ai-status" style="cursor:default">… ${localizedText("checking AI")}</span>`;
}
async function refreshAiStatus() {
  const badges = els(".ai-status");
  if (!badges.length) return;
  let label = "⚪ " + localizedText("Built-in answers");
  try {
    const d = await api("/ai/status");
    label = d.live ? `🟢 ${localizedText("Live AI")} · ${d.model}` : "⚪ " + localizedText("Built-in answers");
  } catch { label = "⚪ " + localizedText("Offline - built-in answers"); }
  badges.forEach((b) => (b.textContent = label));
}

// ----- Streaming answer consumer (SSE) with graceful fallback -----
// Splits the streamed text into answer + "REFERENCE: …" tail.
function splitAnswerRef(full) {
  const i = full.indexOf("REFERENCE:");
  if (i < 0) return { answer: full, ref: "" };
  return { answer: full.slice(0, i).trim(), ref: full.slice(i + "REFERENCE:".length).trim() };
}
// onChunk(fullText) per token; resolves true if streamed ok, false to fall back.
async function streamAsk(question, onChunk) {
  try {
    const r = await fetch(`${API_BASE}/ai/ask/stream`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, lang: State.lang }),
    });
    if (!r.ok || !r.body) return false; // e.g. 503 (no key) → caller falls back
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "", full = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        let obj;
        try { obj = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (obj.error) return false;       // mid-stream failure → fall back
        if (obj.done) return true;
        if (obj.t) { full += obj.t; onChunk(full); }
      }
    }
    return true;
  } catch {
    return false;
  }
}

// ----- Client-side "local brain" — works even with the backend offline -----
const OFFTOPIC_MSG = "This chat is only for Al-Wilayat - Islamic questions about the Quran, the Ahlul Bayt (AS) and matters of faith. Please ask about those.";
const LOCAL_BELIEFS = [
  { k: ["tawhid", "tawheed", "oneness", "monotheism", "unity of god"],
    a: "Tawhid is the absolute Oneness of Allah — One in His Essence, Attributes and actions, with no partner, equal or resemblance to creation. It is the first root of religion (Usul al-Din).",
    r: "Quran 112 (al-Ikhlas) · Nahj al-Balagha, Sermon 1 — Imam Ali (AS)." },
  { k: ["adl", "adalah", "divine justice", "justice"],
    a: "ʿAdl means Divine Justice: Allah is absolutely just, never wrongs anyone and acts with wisdom. Humans have free will and are accountable for their deeds. It is the second root of religion.",
    r: "Quran 4:40 — 'Indeed Allah does not wrong [anyone] by an atom's weight.'" },
  { k: ["nubuwwah", "nubuwwat", "prophethood", "prophet", "messenger", "risalah"],
    a: "Nubuwwah is Prophethood: Allah sent prophets to guide humanity, from Adam (AS) to the final Messenger Muhammad (S). Prophets are infallible (maʿsum) in conveying the message.",
    r: "Quran 33:40 — 'Muhammad is the Messenger of Allah and the Seal of the Prophets.'" },
  { k: ["imamah", "imamat", "imam", "wilayah", "wilayat", "successor", "ghadir", "twelve imams", "ali"],
    a: "Imamah is the divinely-appointed leadership after the Prophet (S). The twelve Imams, from Imam Ali (AS) to Imam al-Mahdi (AJ), are appointed by Allah, infallible, and the authoritative guides of the religion.",
    r: "Quran 5:55 · Hadith al-Ghadir · Hadith al-Thaqalayn." },
  { k: ["ma'ad", "maad", "resurrection", "hereafter", "qiyamah", "day of judgment", "akhirah", "afterlife"],
    a: "Maʿad is the Resurrection: every soul will be raised on the Day of Judgement and recompensed for its deeds — Paradise for the righteous, accountability for the wrongdoers. It is the fifth root of religion.",
    r: "Quran 99:7-8 — 'Whoever does an atom's weight of good or evil will see it.'" },
];
const LOCAL_GREET = ["hi", "hello", "hey", "salam", "salaam", "assalam", "asalam", "marhaba", "greetings", "salamun"];
const LOCAL_HINTS = ["allah", "god", "islam", "muslim", "shia", "quran", "qur'an", "surah", "ayah", "hadith",
  "sunnah", "prophet", "muhammad", "ahlul", "ahl al", "imam", "fatima", "zahra", "hasan", "husayn", "hussain",
  "sadiq", "baqir", "kazim", "rida", "mahdi", "ghadir", "dua", "munajat", "ziyarat", "namaz", "salah", "salat",
  "prayer", "fast", "sawm", "ramadan", "karbala", "ashura", "muharram", "marja", "fiqh", "aqeedah", "tawhid",
  "nubuwwah", "imamah", "jannah", "hajj", "kaaba", "masjid", "mosque", "zakat", "khums", "faith", "belief", "wudu"];
const LOCAL_RULING = ["fatwa", "ruling", "is it halal", "is it haram", "permissible", "wajib", "must i"];
const LOCAL_SMALLTALK = [
  { k: ["how are you", "how r u", "how do you do", "how's it going", "hows it going"],
    a: "Alhamdulillah, I'm well and at your service. Ask me about the Qur'an, the Ahlul Bayt (AS), duas or core beliefs." },
  { k: ["thank", "shukran", "jazak"],
    a: "You're most welcome — barakallahu fik. Is there anything else about Islam you'd like to know?" },
  { k: ["who are you", "what are you", "your name", "who r u", "what is this"],
    a: "I'm Wilayat Chat — a helper for questions about Islam in the school of the Ahlul Bayt (AS): the Qur'an, hadith, duas and beliefs, always with a reference." },
  { k: ["bye", "goodbye", "good night", "khuda hafiz", "fi amanillah", "see you"],
    a: "Fi amanillah — may Allah protect you. Come back any time with your questions." },
  { k: ["what can you do", "help", "what do you do"],
    a: "I can answer questions about the Qur'an, the hadith of the Ahlul Bayt (AS), duas, ziyarat, Islamic history and the core beliefs of Shia Islam — always with a reference." },
];

function localBrain(q) {
  const s = (q || "").toLowerCase().trim();
  const words = s.replace(/[?!.,]/g, " ").split(/\s+/).filter(Boolean);
  if (LOCAL_RULING.some((t) => s.includes(t)))
    return { answer: "This concerns a religious ruling. Wilayat Chat does not issue fatwas - please consult your marja al-taqlid or a qualified scholar.", reference: "Quran 16:43 - Ask the people of remembrance if you do not know.", requires_scholar: true };
  if (words.length <= 3 && (words.some((w) => LOCAL_GREET.includes(w)) || ["salam", "salaam", "marhaba"].some((x) => s.includes(x))))
    return { answer: "Wa ʿalaykum as-salam! I'm Wilayat Chat. Ask me about the Qur'an, the Ahlul Bayt (AS), duas, ziyarat or the core beliefs of Shia Islam.", reference: "Al-Wilayat" };
  for (const st of LOCAL_SMALLTALK) if (st.k.some((t) => s.includes(t))) return { answer: st.a, reference: "Al-Wilayat" };
  for (const b of LOCAL_BELIEFS) if (b.k.some((t) => s.includes(t))) return { answer: b.a, reference: b.r };
  if (s.includes("knowledge") || s.includes("ilm"))
    return { answer: "The pursuit of knowledge is strongly emphasised in the school of the Ahlul Bayt (AS).", reference: "Al-Kafi — Imam al-Sadiq (AS): 'Seeking knowledge is an obligation upon every Muslim.'" };
  if (["husayn", "hussain", "ashura", "karbala"].some((t) => s.includes(t)))
    return { answer: "Imam al-Husayn (AS) was martyred at Karbala on the 10th of Muharram (Ashura), standing against tyranny so that truth and justice would live on.", reference: "Ziyarat Ashura · Mafatih al-Jinan." };
  if (LOCAL_HINTS.some((t) => s.includes(t)))
    return { answer: "I can help with the Qur'an, the hadith of the Ahlul Bayt (AS), duas, ziyarat and the core beliefs of Shia Islam — always with a reference. Could you give a little more detail about what you'd like to know?", reference: "Quran 16:43 — 'Ask the people of remembrance if you do not know.'" };
  return { answer: OFFTOPIC_MSG, reference: "Al-Wilayat" };
}

// Try the live backend (/ai/ask); if it's unreachable, answer with the local brain.
async function askOrLocal(q) {
  try {
    const r = await fetch(`${API_BASE}/ai/ask`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, lang: State.lang }),
    });
    if (!r.ok) throw new Error("bad status");
    const d = await r.json();
    if (!d || !d.answer) throw new Error("empty");
    return d;
  } catch {
    return localBrain(q);
  }
}

// Shia indicators in OSM names (denomination tags are often missing upstream)
const SHIA_RE = /shi'?[ai]|ja'?fari|jaffari|husayn|hussain|husain|hosseini|imam\s*barg|imambarg|imambara|husayniyy|hussainiyy|hosseiniy|ahl[- ]?al[- ]?bayt|ahlul\s*bayt|al-?zahra|az-?zahra|al-?mahdi|al-?askari|al-?kazim|ithna|twelver|fatemi|fatima|panjtan/i;

function renderCommunity(v) {
  v.innerHTML = head("m_community", "m_community_d") + `
    <div class="card" style="margin-bottom:16px">
      <div class="meta" style="margin-bottom:12px"><div class="t">🕌 ${t("mosque_locator")}</div>
        <div class="s">${t("mosque_sub")}</div></div>
      <button class="btn" onclick="findMosques()">📍 ${t("find_mosques")}</button>
      <div id="mosqueResults" style="margin-top:12px"></div>
    </div>

    <div class="card">
      <div class="meta" style="cursor:pointer" onclick="togglePrivacy()">
        <div class="t">📜 ${t("license_privacy")}</div>
        <div class="s">${t("license_privacy_sub")}</div></div>
      <div id="privacyBody" style="display:none;margin-top:14px"></div>
    </div>`;
}

// ---------- GLOBAL SEARCH (Quran · hadith · dua · ziyarat) ----------
// Run from the top-bar search box: finds the exact line and related ones,
// and every result jumps straight into the full surah / book / text.
function globalSearch(q) {
  q = (q || "").trim();
  if (q.length < 2) return;
  State.searchQ = q;
  const input = el(".search input");
  if (input) input.value = q;
  go("search");
  updateSearchMark();
}

function updateSearchMark() {
  const btn = el("#searchBackBtn");
  const input = el(".search input");
  if (!btn || !input) return;
  btn.classList.toggle("show", State.route === "search" || input.value.trim().length > 0);
}

// Live-filter the home module boxes as the user types in the search bar.
function filterHomeModules(q) {
  const view = el("#view-home");
  if (!view) return;
  const query = (q || "").trim().toLowerCase();
  let shown = 0;
  view.querySelectorAll(".module-card").forEach((card) => {
    const match = !query || card.textContent.toLowerCase().includes(query);
    card.style.display = match ? "" : "none";
    if (match) shown += 1;
  });
  const grid = view.querySelector(".grid.modules");
  let empty = view.querySelector(".modules-empty");
  if (grid && query && shown === 0) {
    if (!empty) { empty = document.createElement("div"); empty.className = "modules-empty card"; grid.after(empty); }
    empty.textContent = t("no_matches"); empty.style.display = "";
  } else if (empty) { empty.style.display = "none"; }
}

function closeSearchFromBar() {
  const input = el(".search input");
  if (input) input.value = "";
  State.searchQ = "";
  updateSearchMark();
  filterHomeModules("");
  if (State.route === "search") appBack("home");
}

// Open a full dua / ziyarat text inline in the search results.
async function openSearchText(kind, id) {
  const ex = document.getElementById("textReader");
  if (ex && ex.dataset.key === kind + ":" + id) { ex.remove(); return; }
  if (ex) ex.remove();
  const box = document.createElement("div");
  box.id = "textReader"; box.dataset.key = kind + ":" + id; box.className = "card";
  box.style.marginTop = "12px"; box.innerHTML = t("loading");
  el("#searchBody").prepend(box);
  const close = `<button class="btn ghost" onclick="document.getElementById('textReader').remove()">✕</button>`;
  try {
    const d = await api(`/${kind}/full/${id}`);
    box.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <h2 style="flex:1;font-family:Amiri,serif;color:var(--text-0)">${d.ar_title || ""}</h2>${close}
      </div>
      <p style="color:var(--text-2);margin-bottom:14px">${disp(d.en_title, d.ar_title, t("passages"))} · ${d.count || 0} ${t("passages")}</p>
      ${(d.verses || []).map((vrs) => {
        if (vrs.head) return `<h3 style="color:var(--text-0);margin:18px 0 8px;font-size:16px">${localizedText(vrs.en || "")}</h3>`;
        const ar = vrs.ar ? `<div class="ar">${vrs.ar}</div>` : "";
        const tr = translatedContent(vrs.en);
        const en = tr ? `<div class="tr"${vrs.ar ? "" : ' style="font-size:16px;color:var(--text-1)"'}>${tr}</div>` : "";
        return `<div class="ayah-block">${ar}${en}</div>`;
      }).join("")}`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    box.innerHTML = `<div style="display:flex;gap:10px"><span style='flex:1;color:var(--text-2)'>${localizedText("Text unavailable. Please make sure the backend is running.")}</span>${close}</div>`;
  }
}

// Modules (Quran, Hadith, …) whose name matches the query — shown as boxes.
function matchModules(q) {
  const ql = q.toLowerCase();
  return MODULES.filter((m) =>
    m.id.includes(ql) || ql.includes(m.id) ||
    t(m.titleKey).toLowerCase().includes(ql) || t(m.descKey).toLowerCase().includes(ql));
}
function moduleBoxes(mods) {
  if (!mods.length) return "";
  return `<div class="page-head"><h1 style="font-size:18px">${t("sections")}</h1></div>
    <div class="grid modules">${mods.map((m) => `
      <div class="module-card" style="opacity:1;transform:none" onclick="go('${routeFor(m.id)}')">
        <span class="glow" style="--accent:${m.accent}"></span>
        <h3>${t(m.titleKey)}</h3><p>${t(m.descKey)}</p>
      </div>`).join("")}</div>`;
}

async function renderSearch(v) {
  const q = State.searchQ || "";
  v.innerHTML = `<div class="page-head"><button class="screen-back" onclick="closeSearchFromBar()" aria-label="Back">←</button><div class="eyebrow wilayat-mark">Al-Wilayat</div>
      <h1>${t("search_title")}</h1><p>${t("results_for")} “${escapeHtml(q)}”</p></div>
    <div id="searchBody"></div>`;
  const body = el("#searchBody");
  if (!q) { body.innerHTML = `<div class="card">${t("type_to_search")}</div>`; return; }

  // If the query names a section (e.g. "hadith", "quran"), show only that box —
  // not the text lines. Text-line results are for actual verses / hadith phrases.
  const mods = matchModules(q);
  if (mods.length) { body.innerHTML = moduleBoxes(mods); return; }

  // Otherwise search the corpus for matching lines.
  body.innerHTML = `<div id="searchContent"><div class="card">${t("searching")}</div></div>`;
  const content = el("#searchContent");
  const enc = encodeURIComponent(q);
  const safe = (p) => api(p).catch(() => null); // a missing endpoint shouldn't sink the page
  try {
    const [hd, qr, du, zi] = await Promise.all([
      api(`/hadith/search?q=${enc}&limit=40`),   // these two define backend availability
      api(`/quran/search?q=${enc}&limit=30`),
      safe(`/dua/search?q=${enc}&limit=20`),
      safe(`/ziyarat/search?q=${enc}&limit=20`),
    ]);
    const hadith = hd.results || [], verses = qr.results || [];
    const duas = (du && du.results) || [], ziyarat = (zi && zi.results) || [];
    if (!hadith.length && !verses.length && !duas.length && !ziyarat.length) {
      content.innerHTML = `<div class="card">${t("no_matches")}</div>`;
      return;
    }
    const lineCard = (ar, en, foot, onclick) => `
      <div class="card" style="margin-bottom:12px;cursor:pointer" onclick="${onclick}">
        ${ar ? `<div class="ar" style="margin-bottom:8px">${ar}</div>` : ""}
        ${translatedContent(en) ? `<div class="tr">${escapeHtml(translatedContent(en))}</div>` : ""}
        <div class="s" style="margin-top:6px;color:var(--text-1)">${localizedText(foot)} ›</div>
      </div>`;
    const section = (label, n, html) => n
      ? `<div class="page-head" style="margin-top:18px"><h1 style="font-size:18px">${label} (${n})</h1></div>${html}` : "";

    const hadithHtml = hadith.map((h) =>
      lineCard(arHadithText(h.ar), h.en, `📖 ${escapeHtml((h.reference && h.reference.citation) || h.name || t("nav_hadith"))}`,
        `go('hadith');setTimeout(()=>openBook('${h.bookId}'),60)`)).join("");
    const verseHtml = verses.map((vv) =>
      lineCard(vv.ar, vv.en, `📖 ${t("nav_quran")} ${vv.surah}:${vv.ayah} (${escapeHtml(localizedText(vv.surahName || ""))})`,
        `go('quran');setTimeout(()=>openSurah(${vv.surah}),60)`)).join("");
    const duaHtml = duas.map((d) =>
      lineCard(d.ar, d.en, `🤲 ${escapeHtml(localizedText(d.title || t("nav_dua")))}`, `openSearchText('dua','${d.id}')`)).join("");
    const ziHtml = ziyarat.map((z) =>
      lineCard(z.ar, z.en, `🕋 ${escapeHtml(localizedText(z.title || t("nav_ziyarat")))}`, `openSearchText('ziyarat','${z.id}')`)).join("");

    content.innerHTML = section(t("nav_hadith"), hadith.length, hadithHtml)
      + section(t("nav_quran"), verses.length, verseHtml)
      + section(t("nav_dua"), duas.length, duaHtml)
      + section(t("nav_ziyarat"), ziyarat.length, ziHtml);
  } catch {
    content.innerHTML = offlineBanner();
  }
}

// ----- Mosque locator (browser geolocation → OpenStreetMap Overpass) -----
async function findMosques() {
  const box = el("#mosqueResults");
  box.innerHTML = `<div class="s">📍 ${t("getting_loc")}</div>`;
  const c = State.coords || await getLocation(); // GPS → IP fallback
  if (!c) {
    box.innerHTML = `<div class="s">${t("no_loc")}</div>`;
    return;
  }
  box.innerHTML = `<div class="s">🔎 ${t("searching_near")}</div>`;
  queryMosques(c.lat, c.lng, box);
}

const haversine = (la1, lo1, la2, lo2) => {
  const R = 6371, d = (x) => x * Math.PI / 180;
  const a = Math.sin(d(la2 - la1) / 2) ** 2 +
    Math.cos(d(la1)) * Math.cos(d(la2)) * Math.sin(d(lo2 - lo1) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
};

async function queryMosques(lat, lng, box) {
  box.innerHTML = `<div class="s">🔎 ${t("searching")}</div>`;
  const radius = 20000;
  const oql = `[out:json][timeout:25];(` +
    `node["amenity"="place_of_worship"]["religion"="muslim"](around:${radius},${lat},${lng});` +
    `way["amenity"="place_of_worship"]["religion"="muslim"](around:${radius},${lat},${lng});` +
    `);out center tags 300;`;
  try {
    const r = await fetch("https://overpass-api.de/api/interpreter",
      { method: "POST", body: "data=" + encodeURIComponent(oql) });
    const d = await r.json();
    const places = (d.elements || []).map((e) => {
      const c = e.center || e, tg = e.tags || {};
      return {
        name: tg.name || tg["name:en"] || localizedText("Unnamed mosque"),
        denom: (tg.denomination || "").toLowerCase(),
        lat: c.lat, lng: c.lon, dist: haversine(lat, lng, c.lat, c.lon),
      };
    });
    const shia = places
      .filter((p) => p.denom.includes("shia") || (SHIA_RE.test(p.name) && !p.denom.includes("sunni")))
      .sort((a, b) => a.dist - b.dist).slice(0, 25);
    if (!shia.length) {
      box.innerHTML = `<div class="s">${localizedText("No Shia-identified mosques were found nearby. Try again from a different area.")}</div>`;
      return;
    }
    const mapAll = `<a class="btn ghost" style="margin-bottom:12px;display:inline-block" target="_blank" rel="noopener"
       href="https://www.google.com/maps/search/shia+mosque/@${lat},${lng},13z">🗺️ ${t("view_map")}</a>`;
    box.innerHTML = mapAll + shia.map((p) => `
      <a class="list-item" style="text-decoration:none;color:inherit" target="_blank" rel="noopener"
         href="https://www.google.com/maps/search/?api=1&query=${p.lat},${p.lng}">
        <div class="badge-num">🕌</div>
        <div class="meta"><div class="t">${escapeHtml(p.name)}</div>
          <div class="s">${p.dist.toFixed(1)} ${t("km")}${p.denom.includes("shia") ? " · " + t("shia_verified") : ""} · ${t("open_maps")} ›</div></div>
      </a>`).join("");
  } catch {
    box.innerHTML = `<div class="s">${t("map_err")}</div>`;
  }
}

const hashCode = (s) => { let h = 0; for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i) | 0; return Math.abs(h); };

// shared like/react bar — used by the Wilayat Chat and the AI assistant chat
function reactionBar(id) {
  const rx = REACTIONS[id] || { like: 0, heart: 0, mine: {} };
  return `<div class="chips react-bar" data-rxid="${id}" style="margin-top:8px">
    <span class="chip ${rx.mine.like ? "active" : ""}" onclick="react('${id}','like')">👍 ${rx.like}</span>
    <span class="chip ${rx.mine.heart ? "active" : ""}" onclick="react('${id}','heart')">❤️ ${rx.heart}</span></div>`;
}
function refreshReactionBars() {
  els(".react-bar").forEach((bar) => { bar.outerHTML = reactionBar(bar.dataset.rxid); });
}
function react(id, type) {
  const rx = REACTIONS[id] || { like: 0, heart: 0, mine: {} };
  if (rx.mine[type]) { rx[type] = Math.max(0, rx[type] - 1); rx.mine[type] = false; }
  else { rx[type] += 1; rx.mine[type] = true; }
  REACTIONS[id] = rx; saveReactions();
  refreshReactionBars();
}

// ----- License & privacy policy -----
const PRIVACY_TEXT = `
  <style>
    #privacyBody {
      background: rgba(3, 12, 28, .62);
      border: 1px solid rgba(148, 163, 184, .22);
      border-radius: 8px;
      padding: 14px;
      overflow-wrap: anywhere;
    }
    #privacyBody h4 { color: var(--text-0); font-size: 14px; margin: 18px 0 8px; letter-spacing:.3px }
    #privacyBody h4:first-child { margin-top: 0 }
    #privacyBody p { color: var(--text-2); line-height: 1.65; font-size: 14px; margin: 0 0 10px }
    #privacyBody ul { color: var(--text-2); line-height: 1.65; font-size: 14px; margin: 0; padding-left: 18px }
    #privacyBody li { margin-bottom: 7px; padding-left: 2px }
    #privacyBody .lic { color: var(--text-1); font-style: italic }
    #privacyBody .owner {
      color: var(--text-1);
      font-size: 13px;
      line-height: 1.6;
      margin: 10px 0 12px;
      padding: 9px 10px;
      border-left: 2px solid rgba(218, 165, 32, .75);
      background: rgba(255, 255, 255, .04);
      border-radius: 6px;
    }
    #privacyBody .owner span { display: block }
  </style>

  <h4>📖 Purpose &amp; License</h4>
  <p class="lic">Al-Wilayat is a free, non-commercial app made to spread the wisdom of the
  Holy Qur'an and the teachings of the Ahlul Bayt (peace be upon them) — for learning,
  remembrance and devotion.</p>
  <p class="owner">
    <span><strong>Al-Wilayat</strong> is an app powered by Aiba Dynamics Company.</span>
    <span>Developer: Sayed Muhammad Hafeez.</span>
    <span>South Asia's first Shia Islamic library app, built for users around the world.</span>
    <span>Origin/Country: Pakistan.</span>
  </p>
  <ul>
    <li>Provided <strong>free of charge</strong> for educational and devotional use; you may use and
    share it for these purposes.</li>
    <li><strong>Available features</strong> — Al-Wilayat includes Qur'an, hadith, duas, ziyarat,
    tafsir, Qibla, prayer times, mosque locator and referenced Islamic learning tools.</li>
    <li>Texts, translations and publications remain the right of their respective compilers,
    translators and publishers.</li>
    <li>The app is offered <strong>"as is"</strong>, with no warranty. It is a study aid, not a source
    of religious rulings (fatwa) — always confirm matters of practice with a qualified scholar or
    your marjaʿ al-taqlid.</li>
    <li>Please use it respectfully, in a manner befitting its sacred content.</li>
  </ul>

  <h4>⚖️ App Rules &amp; How It Works</h4>
  <p>Al-Wilayat must be used with respect for the Qur'an, the Prophet (s), and the Ahlul Bayt (a).</p>
  <ul>
    <li><strong>Respect sacred content</strong> — do not misuse, mock, edit, or share the texts in a
    disrespectful way.</li>
    <li><strong>Learning only</strong> — the app provides Qur'an, hadith, dua, ziyarat, tafsir and
    reference tools for study and devotion. It does not replace scholars.</li>
    <li><strong>No fatwa</strong> — AI answers and search results are for guidance with references only.
    For religious rulings, follow your marjaʿ al-taqlid or a qualified scholar.</li>
    <li><strong>Check references</strong> — users must verify important narrations, translations and
    rulings before acting on them.</li>
    <li><strong>Location features</strong> — Qibla, prayer times and mosque search need your permission
    to use location. Without permission, results may be approximate.</li>
    <li><strong>No abuse</strong> — do not use the app for hate, harassment, false claims, sectarian
    provocation, or disrespect toward any sacred personality.</li>
    <li><strong>Local data</strong> — likes, reactions and saved preferences stay in this browser unless
    you clear your browser data.</li>
  </ul>`;

const PRIVACY_LOCALIZED = {
  ar: {
    title: "📖 الهدف والترخيص",
    body: "الولاية تطبيق مجاني غير تجاري للتعلّم والذكر والخدمة الدينية، يجمع القرآن والحديث والأدعية والزيارات والتفسير وأدوات القبلة والصلاة.",
    owner: ["الولاية تطبيق بدعم شركة Aiba Dynamics.", "المطوّر: Sayed Muhammad Hafeez.", "أول مكتبة/تطبيق شيعي إسلامي في جنوب آسيا للمستخدمين حول العالم.", "المنشأ/الدولة: باكستان."],
    rulesTitle: "⚖️ القواعد والخصوصية",
    rules: ["استخدم المحتوى المقدّس باحترام ولا تسئ استخدامه.", "التطبيق للتعلّم والعبادة ولا يحل محل العلماء أو المرجع.", "الذكاء الاصطناعي والبحث يقدمان مراجع فقط ولا يصدران فتاوى.", "ميزات الموقع مثل القبلة والصلاة والمساجد تحتاج إذن الموقع، وقد تكون تقريبية بدونه.", "الإعجابات والتفضيلات تُحفظ في هذا المتصفح فقط ويمكن حذفها بمسح بيانات المتصفح."]
  },
  ur: {
    title: "📖 مقصد اور لائسنس",
    body: "الولایت ایک مفت غیر تجارتی ایپ ہے جو قرآن، حدیث، دعاؤں، زیارات، تفسیر، قبلہ، نماز اوقات اور اسلامی تعلیمی اوزار کو احترام کے ساتھ پیش کرتی ہے۔",
    owner: ["Al-Wilayat ایپ Aiba Dynamics Company کے ذریعے powered ہے۔", "Developer: Sayed Muhammad Hafeez.", "جنوبی ایشیا کی پہلی شیعہ اسلامی لائبریری/ایپ، دنیا بھر کے صارفین کے لیے۔", "Origin/Country: Pakistan."],
    rulesTitle: "⚖️ اصول اور رازداری",
    rules: ["مقدس مواد کو احترام سے استعمال کریں۔", "ایپ تعلیم اور عبادت کے لیے ہے، علماء یا مرجع کا بدل نہیں۔", "AI اور سرچ صرف حوالہ دیتے ہیں، فتویٰ نہیں دیتے۔", "قبلہ، نماز اوقات اور مسجد تلاش کے لیے مقام کی اجازت درکار ہو سکتی ہے۔", "پسندیدگیاں اور ترجیحات صرف اسی براؤزر میں محفوظ رہتی ہیں۔"]
  },
  fa: {
    title: "📖 هدف و مجوز",
    body: "الولایت یک برنامه رایگان و غیرتجاری برای آموزش، ذکر و استفاده دینی است و قرآن، حدیث، دعا، زیارت، تفسیر، قبله، اوقات نماز و ابزارهای یادگیری را فراهم می‌کند.",
    owner: ["Al-Wilayat برنامه‌ای با پشتیبانی شرکت Aiba Dynamics است.", "توسعه‌دهنده: Sayed Muhammad Hafeez.", "نخستین کتابخانه/برنامه اسلامی شیعه در جنوب آسیا برای کاربران جهان.", "منشأ/کشور: پاکستان."],
    rulesTitle: "⚖️ قوانین و حریم خصوصی",
    rules: ["با محتوای مقدس با احترام برخورد کنید.", "برنامه برای آموزش و عبادت است و جایگزین عالم یا مرجع نیست.", "AI و جستجو فقط با مرجع کمک می‌کنند و فتوا نمی‌دهند.", "قبله، اوقات نماز و مسجد‌یاب برای دقت به اجازه موقعیت نیاز دارند.", "پسندها و تنظیمات فقط در همین مرورگر ذخیره می‌شوند."]
  },
  az: {
    title: "📖 Məqsəd və lisenziya",
    body: "Al-Wilayat pulsuz və qeyri-kommersiya tətbiqidir. Quran, hədis, dua, ziyarət, təfsir, qiblə, namaz vaxtları və İslami öyrənmə alətlərini hörmətlə təqdim edir.",
    owner: ["Al-Wilayat Aiba Dynamics Company tərəfindən dəstəklənən tətbiqdir.", "Tərtibatçı: Sayed Muhammad Hafeez.", "Cənubi Asiyanın dünyadakı istifadəçilər üçün ilk Şiə İslami kitabxana/tətbiqi.", "Mənşə/ölkə: Pakistan."],
    rulesTitle: "⚖️ Qaydalar və məxfilik",
    rules: ["Müqəddəs məzmunu hörmətlə istifadə edin.", "Tətbiq öyrənmə və ibadət üçündür, alim və ya mərceyi əvəz etmir.", "AI və axtarış yalnız istinadlı kömək verir, fətva vermir.", "Qiblə, namaz vaxtları və məscid axtarışı üçün məkan icazəsi lazım ola bilər.", "Bəyənmələr və seçimlər yalnız bu brauzerdə saxlanılır."]
  },
  ks: {
    title: "📖 مقصد تہٕ لائسنس",
    body: "Al-Wilayat اکھ مفت تہٕ غیر تجارتی ایپ چھ، یتھ منز قرآن، حدیث، دعا، زیارت، تفسیر، قبلہ، نماز وقت تہٕ اسلامی سیکھنک اوزار چھ۔",
    owner: ["Al-Wilayat ایپ Aiba Dynamics Company سۭتۍ powered چھ۔", "Developer: Sayed Muhammad Hafeez.", "جنوبی ایشیاک گوڈنیک شیعہ اسلامی لائبریری/ایپ، دنیا بھر صارفن خٲطرٕ۔", "Origin/Country: Pakistan."],
    rulesTitle: "⚖️ قاعدہ تہٕ رازداری",
    rules: ["مقدس مواد عزت سۭتۍ استعمال کرو۔", "ایپ سیکھن تہٕ عبادت خٲطرٕ چھ، عالم یا مرجعک بدل نہٕ۔", "AI تہٕ تلاش صرف حوالہ دیتھ مدد کران، فتویٰ نہٕ۔", "قبلہ، نماز وقت تہٕ مسجد تلاش خٲطرٕ مقام اجازت ضرورت پزِ۔", "پسند تہٕ ترجیح صرف یتھ براؤزر منز محفوظ چھ۔"]
  },
  prs: {
    title: "📖 هدف و جواز",
    body: "Al-Wilayat یک برنامه رایگان و غیرتجاری برای آموزش و عبادت است و قرآن، حدیث، دعا، زیارت، تفسیر، قبله، اوقات نماز و ابزارهای اسلامی را فراهم می‌کند.",
    owner: ["Al-Wilayat برنامه‌ای با پشتیبانی شرکت Aiba Dynamics است.", "توسعه‌دهنده: Sayed Muhammad Hafeez.", "اولین کتابخانه/برنامه اسلامی شیعه در جنوب آسیا برای کاربران جهان.", "منشأ/کشور: پاکستان."],
    rulesTitle: "⚖️ قوانین و حریم خصوصی",
    rules: ["محتوای مقدس را با احترام استفاده کنید.", "برنامه برای آموزش و عبادت است و جای عالم یا مرجع را نمی‌گیرد.", "AI و جستجو فقط مرجع می‌دهند و فتوا صادر نمی‌کنند.", "قبله، اوقات نماز و مسجد‌یاب برای دقت به اجازه موقعیت نیاز دارند.", "پسندها و ترجیحات فقط در همین مرورگر ذخیره می‌شوند."]
  },
  ms: {
    title: "📖 Tujuan & Lesen",
    body: "Al-Wilayat ialah aplikasi percuma dan bukan komersial untuk pembelajaran, zikir dan ibadah. Ia menyediakan Quran, hadis, doa, ziarah, tafsir, kiblat, waktu solat dan alat pembelajaran Islam.",
    owner: ["Al-Wilayat ialah aplikasi yang dikuasakan oleh Aiba Dynamics Company.", "Pembangun: Sayed Muhammad Hafeez.", "Perpustakaan/aplikasi Islam Syiah pertama di Asia Selatan untuk pengguna seluruh dunia.", "Asal/Negara: Pakistan."],
    rulesTitle: "⚖️ Peraturan & Privasi",
    rules: ["Gunakan kandungan suci dengan hormat.", "Aplikasi ini untuk pembelajaran dan ibadah, bukan pengganti ulama atau marja.", "AI dan carian hanya memberi bantuan berserta rujukan, bukan fatwa.", "Kiblat, waktu solat dan pencari masjid mungkin memerlukan izin lokasi.", "Suka dan pilihan disimpan hanya dalam pelayar ini."]
  },
  sg: {
    title: "📖 Purpose & License",
    body: "Al-Wilayat is a free, non-commercial app for learning, remembrance and worship, with Quran, hadith, duas, ziyarat, tafsir, Qibla, prayer times and Islamic learning tools.",
    owner: ["Al-Wilayat is powered by Aiba Dynamics Company.", "Developer: Sayed Muhammad Hafeez.", "South Asia's first Shia Islamic library/app for users around the world.", "Origin/Country: Pakistan."],
    rulesTitle: "⚖️ Rules & Privacy",
    rules: ["Use sacred content respectfully.", "The app is for learning and worship, not a replacement for scholars or your marja.", "AI and search provide referenced help only, not fatwas.", "Qibla, prayer times and mosque search may need location permission.", "Likes and preferences stay only in this browser."]
  }
};

function privacyHtml() {
  const c = PRIVACY_LOCALIZED[State.lang];
  if (!c) return PRIVACY_TEXT;
  const style = (PRIVACY_TEXT.match(/<style>[\s\S]*?<\/style>/) || [""])[0];
  return `${style}
    <h4>${c.title}</h4>
    <p class="lic">${c.body}</p>
    <p class="owner">${c.owner.map((x) => `<span>${x}</span>`).join("")}</p>
    <h4>${c.rulesTitle}</h4>
    <ul>${c.rules.map((x) => `<li>${x}</li>`).join("")}</ul>`;
}

function togglePrivacy() {
  const b = el("#privacyBody");
  const opening = b.style.display === "none";
  b.style.display = opening ? "block" : "none";
  if (opening && !b.innerHTML.trim()) b.innerHTML = privacyHtml();
}

// ---------- MEDIA ----------
function renderMedia(v) {
  v.innerHTML = head("m_media", "m_media_d") + MEDIA.map((m) => `
    <div class="list-item" onclick="toast('▶ ' + t('play'))">
      <div class="badge-num">${m.emoji}</div>
      <div class="meta"><div class="t">${localizedText(m.en)}</div><div class="s">${localizedText(m.type)} · ${localizedText(m.by)} · ${m.dur}</div></div>
      <div style="font-size:20px">${ICON_PLAY}</div>
    </div>`).join("");
}

// ---------- TASBIH ----------
let tasbih = { count: 0, dhikrIdx: 0 };
function renderTasbih(v) {
  const d = DHIKR[tasbih.dhikrIdx];
  v.innerHTML = head("m_tasbih", "m_tasbih_d") + `
    <div class="chips" style="justify-content:center">
      ${DHIKR.map((x, i) => `<span class="chip ${i === tasbih.dhikrIdx ? "active" : ""}" onclick="setDhikr(${i})">${langName(x)}</span>`).join("")}
    </div>
    <div class="tasbih-wrap">
      <div class="tasbih-ring" id="tring" onclick="tap()">
        <div style="text-align:center">
          <div class="dhikr">${d.ar}</div>
          <div class="count" id="tcount">${tasbih.count}</div>
          <div style="color:var(--text-2);font-size:13px">${t("target")}: ${d.target}</div>
        </div>
      </div>
      <p style="color:var(--text-2)">${t("tap_count")}</p>
      <button class="btn ghost" onclick="resetTasbih()">↺ ${t("reset")}</button>
    </div>`;
  updateRing();
}
function setDhikr(i) { tasbih.dhikrIdx = i; tasbih.count = 0; renderTasbih(el("#view-tasbih")); }
function tap() {
  tasbih.count++;
  Stats.addDhikr(1);          // count toward "Dhikr Today"
  const d = DHIKR[tasbih.dhikrIdx];
  el("#tcount").textContent = tasbih.count;
  if (navigator.vibrate) navigator.vibrate(15);
  if (tasbih.count === d.target) { toast("✨ " + langName(d) + " × " + d.target + " " + localizedText("complete")); }
  if (tasbih.count % d.target === 0 && tasbih.count > 0) { /* keep counting */ }
  updateRing();
}
function updateRing() {
  const d = DHIKR[tasbih.dhikrIdx];
  const ring = el("#tring");
  if (ring) ring.style.setProperty("--ring", Math.min(360, (tasbih.count % d.target || (tasbih.count ? d.target : 0)) / d.target * 360) + "deg");
}
function resetTasbih() { tasbih.count = 0; renderTasbih(el("#view-tasbih")); }

// ---------- ADMIN ----------
function renderAdmin(v) {
  const stats = [
    { big: "1.2M", lbl: "Users" }, { big: "6,236", lbl: "Quran Verses" },
    { big: "41,220", lbl: "Hadiths" }, { big: "3,400", lbl: "Books" },
    { big: "98", lbl: "Pending Moderation" }, { big: "99.98%", lbl: "Uptime" },
  ];
  const panels = ["Users", "Quran Content", "Hadith Content", "Audio Files", "Notifications", "AI Moderation", "Analytics", "Reports"];
  v.innerHTML = head("m_admin", "m_admin_d") + `
    <div class="stat-row">${stats.map((s) => `<div class="stat"><div class="big">${s.big}</div><div class="lbl">${localizedText(s.lbl)}</div></div>`).join("")}</div>
    <div class="grid modules">${panels.map((p) => `
      <div class="module-card" onclick="toast(t('coming_soon'))" style="opacity:1;transform:none">
        <div class="m-ic">🛠️</div><h3>${localizedText(p)}</h3><p>${localizedText("Manage")} ${localizedText(p.toLowerCase())}</p>
      </div>`).join("")}</div>`;
}

// ---------------- Helpers ----------------
function escapeHtml(s) { return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

// ---------------- Boot ----------------
// Professional line icons (Lucide-style, MIT), stroke=currentColor.
const ICONS = {
  home: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
  quran: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  hadith: '<path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
  ziyarat: '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
  dua: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  prayer: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  qibla: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
  calendar: '<rect width="18" height="18" x="3" y="4" rx="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
  ahlulbayt: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  library: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="M9.5 2v7l2.5-1.6L14.5 9V2"/>',
  community: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  tasbih: '<circle cx="12" cy="13" r="8"/><circle cx="12" cy="3" r="1.6" fill="currentColor" stroke="none"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;

// [route, i18n-key, isPrimary]. Primary items show in the phone bottom nav; the
// rest live in the Settings sheet. The sidebar (desktop) shows them all.
const NAV = [
  ["home", "nav_home", true], ["quran", "nav_quran", true], ["hadith", "nav_hadith", true],
  ["ziyarat", "nav_ziyarat", true], ["dua", "nav_dua", true],
  ["prayer", "nav_prayer", false], ["qibla", "nav_qibla", false], ["calendar", "nav_calendar", false],
  ["ahlulbayt", "nav_ahl", false], ["library", "nav_library", false],
  ["community", "nav_community", false], ["tasbih", "nav_tasbih", false],
];
const isPrimaryRoute = (route) => NAV.some((n) => n[0] === route && n[2]);

function buildNav() {
  el("#nav").innerHTML = NAV.map(([r, k]) => `
    <div class="nav-item ${r === "home" ? "active" : ""}" data-route="${r}" onclick="go('${r}')">
      <span class="ic">${icon(r)}</span><span data-i18n="${k}">${t(k)}</span>
    </div>`).join("");

  const bn = el("#bottomNav");
  if (bn) bn.innerHTML = NAV.filter((n) => n[2]).map(([r, k]) => `
    <button class="bottom-item ${r === "home" ? "active" : ""}" data-route="${r}" onclick="go('${r}')">
      <span class="bi">${icon(r)}</span><span class="bl" data-i18n="${k}">${t(k)}</span>
    </button>`).join("");

  const sg = el("#settingsGrid");
  if (sg) sg.innerHTML = NAV.filter((n) => !n[2]).map(([r, k]) => `
    <button class="settings-item" data-route="${r}" onclick="openModuleFromSettings('${r}')">
      <span class="si">${icon(r)}</span><span data-i18n="${k}">${t(k)}</span>
    </button>`).join("");

  el("#views").innerHTML = NAV.map(([r]) => `<section class="view ${r === "home" ? "active" : ""}" id="view-${r}"></section>`).join("")
    + `<section class="view" id="view-search"></section>`;
}

function openSettings() {
  el("#settingsPanel")?.classList.add("open");
  el("#settingsBackdrop")?.classList.add("open");
}
function closeSettings() {
  el("#settingsPanel")?.classList.remove("open");
  el("#settingsBackdrop")?.classList.remove("open");
}
// Open a module from Settings; push a marker so Back / left-swipe returns to Settings.
function openModuleFromSettings(route) {
  if (window.history && history.pushState) {
    _navIndex += 1;
    history.pushState({ wilayat: true, route: State.route, index: _navIndex, settingsOpen: true },
                      "", routeUrl(State.route));
  }
  closeSettings();
  go(route);
}

function initialRoute() {
  return normalizeRoute(decodeURIComponent((location.hash || "").replace(/^#/, "")) || "home");
}

function init() {
  Stats.touchStreak();          // advance the daily streak once per app open
  buildNav();
  applyTheme();
  try { applyLang(); } catch (e) { /* never block boot on a localization error */ }
  try { setupNumberLocalization(); } catch (e) { /* observer/regex optional */ }
  const startRoute = initialRoute();
  history.replaceState({ wilayat: true, route: startRoute, index: 0 }, "", routeUrl(startRoute));
  go(startRoute, { history: false });
  requestLocation(); // ask once on open → prayer times, Qibla & mosque finder auto-correct

  // Top-bar search → exact hadith / verse lookup
  const searchInput = el(".search input");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      updateSearchMark();
      if (State.route === "home") filterHomeModules(searchInput.value);
    });
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") globalSearch(searchInput.value);
    });
  }
  const searchBackBtn = el("#searchBackBtn");
  if (searchBackBtn) searchBackBtn.onclick = (e) => {
    e.preventDefault();
    closeSearchFromBar();
  };

  el("#langBtn").onclick = () => el("#langMenu").classList.toggle("open");
  el("#menuBtn").onclick = () => el("#sidebar").classList.toggle("open");
  const settingsBtn = el("#settingsBtn");
  if (settingsBtn) settingsBtn.onclick = openSettings;
  const settingsBackdrop = el("#settingsBackdrop");
  if (settingsBackdrop) settingsBackdrop.onclick = closeSettings;
  const settingsClose = el("#settingsClose");
  if (settingsClose) settingsClose.onclick = closeSettings;
  el("#langMenu").querySelectorAll("button").forEach((b) =>
    (b.onclick = () => {
      State.lang = b.dataset.lang;
      applyLang();
      el("#langMenu").classList.remove("open");
      RENDERERS[State.route] && RENDERERS[State.route](el("#view-" + State.route));
    })
  );
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#langBtn") && !e.target.closest("#langMenu")) el("#langMenu").classList.remove("open");
    if (!e.target.closest("#sidebar") && !e.target.closest("#menuBtn")) el("#sidebar").classList.remove("open");
  });

  window.addEventListener("popstate", (e) => {
    const route = normalizeRoute((e.state && e.state.route) || initialRoute());
    _navIndex = Number.isFinite(e.state && e.state.index) ? e.state.index : 0;
    go(route, { history: false });
    if (e.state && e.state.settingsOpen) openSettings(); else closeSettings();
  });
}

document.addEventListener("DOMContentLoaded", init);
