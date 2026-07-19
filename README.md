<div align="center">

# Al-Wilayat · ولايت

**A complete Shia Islamic super-app — Qur'an, Hadith, Du'a, Ziyarat, prayer times, Qibla, the Islamic calendar, and more, in 9 languages.**

_Powered by Texa_

⚠️ **View-only. All Rights Reserved.** See [LICENSE](LICENSE) — this project may be **viewed only**; it may not be copied, used, modified, or redistributed.

</div>

---

## ✨ Features

- **Qur'an** — full text with translations and per-ayah recitation (play / pause).
- **Hadith** — major Shia collections, searchable by hadith number **and** by full citation (English **or** Arabic references), with each book labelled as an Arabic or English edition.
- **Du'a & Ziyarat** — curated supplications and ziyarat.
- **Prayer times & Qibla** — location-aware, fully localized.
- **Islamic calendar** — Hijri dates localized per language.
- **Library** — reference works and PDFs.
- **9 languages** — English, العربية, اردو, فارسی, Azərbaycanca, کٲشُر (Kashmiri), دری فارسی (Dari), Bahasa Melayu, Singapore English — with full RTL support.
- **Accounts** — secure sign-up / sign-in, bcrypt password hashing, JWT sessions, rate limiting, and email-code password reset.
- **Responsive** — desktop sidebar; phone bottom-nav + settings sheet.

## 🧱 Tech stack

- **Backend:** Python · FastAPI · Uvicorn · SQLite · python-jose (JWT) · passlib/bcrypt
- **Frontend:** Vanilla HTML / CSS / JavaScript (no framework), glassmorphism UI, RTL-aware

## 🚀 Run it

```bash
cd backend
python app/main.py
```

`main.py` auto-creates the virtual environment, installs dependencies if needed, starts the server on **http://localhost:8000**, and opens the app in your browser.

### Publish it as a website
To host Al-Wilayat as its own site on your own server (with a domain + HTTPS), follow **[DEPLOY.md](DEPLOY.md)** — a step-by-step VPS guide (nginx + systemd + free SSL).

## 📦 Content data

The large reference datasets (Qur'an, Hadith, Tafsir) are **not stored in this repository** — they are downloadable and are fetched by the ingest scripts:

```bash
cd backend
python ingest/fetch_quran.py
python ingest/fetch_hadith.py
# …and the other ingest scripts as needed
```

Curated Du'a and Ziyarat data is included.

## 🔐 Configuration

Copy `backend/.env.example` to `backend/.env` and fill in your own values:

- `WILAYAT_SECRET` — a long random string used to sign JWT tokens.
- `SMTP_*` — optional; for sending password-reset emails (e.g. a Gmail app password).

> **Never commit `.env`.** It is git-ignored by default.

## 📖 A note on the references

The Qur'an, Hadith, Du'a, and Ziyarat are the shared religious heritage of the Muslim community and are **not owned by anyone**. Translations and explanations are aids for the reader, not religious rulings (fatwa). For matters of practice, please consult a qualified scholar (marja'/'alim).

## 📜 License

**Proprietary — All Rights Reserved (View-Only).** © 2026 Texa (Muhammad Hafeez).
You may **view** this project only. Copying, using, modifying, redistributing, or claiming ownership of any part is **not permitted** without written permission. See [LICENSE](LICENSE).
